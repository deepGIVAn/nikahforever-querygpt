from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import QueryRequest, QueryResponse
from app.core.pipeline import stream_query, invoke_query

router = APIRouter(prefix="/api", tags=["query"])

@router.post("/query/stream")
async def handle_query_stream(request: QueryRequest):
    """
    SSE streaming endpoint yielding token-by-token output,
    followed by the final query structure or clarification response.
    """
    return StreamingResponse(
        stream_query(request.question, request.chat_history or []),
        media_type="text/event-stream",
    )

@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Standard non-streaming endpoint returning the full parsed query details
    and SQLite execution results in a single response.
    """
    result = await invoke_query(request.question, request.chat_history or [])
    return result
