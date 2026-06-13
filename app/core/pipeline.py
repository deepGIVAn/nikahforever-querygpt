import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever

from app.config import settings
from app.vectorstore.retriever import get_full_retriever
from app.prompts.system_prompt import qa_system_prompt
from app.prompts.contextualise import contextualize_q_system_prompt
from app.core.sql_validator import validate_sql
from app.core.query_executor import execute_query
from app.core.response_formatter import format_response

# Configure LLM instances using OpenAI-compatibility layer for Gemini
llm = ChatOpenAI(
    api_key=settings.GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model=settings.selected_model,
    temperature=0
)

streaming_llm = ChatOpenAI(
    api_key=settings.GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model=settings.selected_model,
    temperature=0,
    streaming=True
)

# Prompt templates
contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

qa_prompt = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

def normalize_history(chat_history: list) -> list:
    """
    Normalizes different chat history representations into LangChain's tuple format:
    [("human"|"ai", text)].
    """
    normalized = []
    for msg in chat_history:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            langchain_role = "human" if role in ("user", "human") else "ai"
            normalized.append((langchain_role, content))
        elif isinstance(msg, (tuple, list)) and len(msg) >= 2:
            normalized.append((msg[0], msg[1]))
        else:
            normalized.append(msg)
    return normalized

# ---------------------------------------------------------------------------
# Streaming entry-point (SSE)
# ---------------------------------------------------------------------------
async def stream_query(question: str, chat_history: list):
    """
    SSE streaming generator.

    Yields:
        data: {"type": "sql",     "content": "SELECT ..."}
        data: {"type": "token",   "content": "<token>"}
        data: {"type": "result",  "content": { ... }}
        data: [DONE]
    """
    retriever = get_full_retriever(top_k=15)

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    question_answer_chain = create_stuff_documents_chain(streaming_llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    full_answer = ""
    normalized_hist = normalize_history(chat_history)

    try:
        async for chunk in rag_chain.astream({
            "input": question,
            "chat_history": normalized_hist,
        }):
            if "answer" in chunk:
                token = chunk["answer"]
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'LLM streaming error: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Once streaming is done, parse the full JSON response
    try:
        # Sometimes the model wraps JSON in markdown blocks, let's strip those
        cleaned_answer = full_answer.strip()
        if cleaned_answer.startswith("```json"):
            cleaned_answer = cleaned_answer[7:]
        if cleaned_answer.endswith("```"):
            cleaned_answer = cleaned_answer[:-3]
        cleaned_answer = cleaned_answer.strip()
        
        llm_data = json.loads(cleaned_answer)
    except json.JSONDecodeError:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Failed to parse LLM response. Raw response was: {full_answer}'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Handle clarification
    if llm_data.get("needs_clarification"):
        yield f"data: {json.dumps({'type': 'clarification', 'content': llm_data['clarification']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    sql = llm_data.get("sql", "")
    yield f"data: {json.dumps({'type': 'sql', 'content': sql})}\n\n"

    # Validate
    validation = validate_sql(sql)
    if not validation["valid"]:
        yield f"data: {json.dumps({'type': 'error', 'content': validation['error']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Execute
    result = execute_query(validation["sanitised_sql"])
    if "error" in result:
        yield f"data: {json.dumps({'type': 'error', 'content': result['error']})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Format and send
    formatted = await format_response(result, llm_data)
    yield f"data: {json.dumps({'type': 'result', 'content': formatted, 'explanation': llm_data.get('explanation')})}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Non-streaming entry-point (for testing / API calls)
# ---------------------------------------------------------------------------
async def invoke_query(question: str, chat_history: list) -> dict:
    """
    Non-streaming version — returns the full structured response.
    """
    retriever = get_full_retriever(top_k=15)

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    normalized_hist = normalize_history(chat_history)
    
    try:
        result = await rag_chain.ainvoke({
            "input": question,
            "chat_history": normalized_hist,
        })
    except Exception as e:
        return {"success": False, "error": f"RAG chain execution error: {str(e)}"}

    answer = result.get("answer", "")

    try:
        cleaned_answer = answer.strip()
        if cleaned_answer.startswith("```json"):
            cleaned_answer = cleaned_answer[7:]
        if cleaned_answer.endswith("```"):
            cleaned_answer = cleaned_answer[:-3]
        cleaned_answer = cleaned_answer.strip()
        
        llm_data = json.loads(cleaned_answer)
    except json.JSONDecodeError:
        return {"success": False, "error": "Failed to parse LLM response", "raw": answer}

    if llm_data.get("needs_clarification"):
        return {
            "success": True,
            "needs_clarification": True,
            "clarification": llm_data["clarification"],
        }

    sql = llm_data.get("sql", "")
    validation = validate_sql(sql)
    if not validation["valid"]:
        return {"success": False, "error": validation["error"], "sql": sql}

    query_result = execute_query(validation["sanitised_sql"])
    if "error" in query_result:
        return {"success": False, "error": query_result["error"], "sql": validation["sanitised_sql"]}

    formatted = await format_response(query_result, llm_data)

    return {
        "success": True,
        "question": question,
        "sql": validation["sanitised_sql"],
        "explanation": llm_data.get("explanation"),
        "result": formatted,
        "execution_time_ms": query_result["execution_time_ms"],
    }
