import streamlit as st
import requests
import json
import pandas as pd
import os

# Page config
st.set_page_config(
    page_title="NF QueryGPT - NikahForever Data Assistant",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration values
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Custom CSS for modern premium matrimonial theme
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Playfair+Display:ital,wght@0,600;1,400&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Branding Header */
    .brand-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #FF4081 0%, #9C27B0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    
    .brand-subtitle {
        font-size: 1rem;
        color: #8E8A9F;
        margin-bottom: 1.5rem;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0F0B1E;
        border-right: 1px solid #2C2248;
    }
    
    /* Dynamic Buttons & Suggestion Chips */
    .stButton>button {
        background: #1B1233 !important;
        color: #E2D9F3 !important;
        border: 1px solid #3F3066 !important;
        border-radius: 20px !important;
        padding: 0.4rem 1rem !important;
        font-size: 0.85rem !important;
        transition: all 0.3s ease !important;
        text-align: left !important;
        width: 100% !important;
        margin-bottom: 5px !important;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #FF4081 0%, #9C27B0 100%) !important;
        color: white !important;
        border-color: transparent !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 15px rgba(255, 64, 129, 0.3) !important;
    }
    
    /* Glassmorphism Panel */
    .glass-card {
        background: rgba(30, 20, 50, 0.45);
        border: 1px solid rgba(156, 39, 176, 0.25);
        border-radius: 16px;
        padding: 1.5rem;
        backdrop-filter: blur(10px);
        margin-bottom: 1rem;
    }
    
    /* Chat Bubble styling */
    .chat-bubble-user {
        background: linear-gradient(135deg, #FF4081 0%, #D81B60 100%);
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 20px 20px 0px 20px;
        margin-bottom: 1rem;
        max-width: 80%;
        float: right;
        box-shadow: 0 4px 10px rgba(255, 64, 129, 0.2);
    }
    
    .chat-bubble-agent {
        background: #1F1735;
        border: 1px solid #3D2D68;
        color: #E2D9F3;
        padding: 0.8rem 1.2rem;
        border-radius: 20px 20px 20px 0px;
        margin-bottom: 1rem;
        max-width: 80%;
        float: left;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    .chat-clear {
        clear: both;
    }
    
    /* SQL Codeblock Container */
    .sql-code-container {
        border-left: 3px solid #9C27B0;
        background: #090614;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "messages" not in st.session_state:
    st.session_state.messages = []

if "clicked_query" not in st.session_state:
    st.session_state.clicked_query = None

if "schema" not in st.session_state:
    st.session_state.schema = {}

if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

if "active_sql" not in st.session_state:
    st.session_state.active_sql = None

if "active_result" not in st.session_state:
    st.session_state.active_result = None

if "active_explanation" not in st.session_state:
    st.session_state.active_explanation = None

if "clarification_needed" not in st.session_state:
    st.session_state.clarification_needed = False

if "clarification_prompt" not in st.session_state:
    st.session_state.clarification_prompt = ""

# Load Schema & Suggestions from API once
@st.cache_data(ttl=600)
def fetch_schema_info():
    try:
        res = requests.get(f"{BACKEND_URL}/api/schema")
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

@st.cache_data(ttl=600)
def fetch_suggestions():
    try:
        res = requests.get(f"{BACKEND_URL}/api/suggest")
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

st.session_state.schema = fetch_schema_info()
st.session_state.suggestions = fetch_suggestions()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/wedding-rings.png", width=64)
    st.markdown('<h2 style="color: white; margin-top:0px; font-family:\'Playfair Display\', serif;">NikahForever</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color: #8E8A9F; font-size:0.8rem; text-transform:uppercase;">Data RAG Assistant</p>', unsafe_allow_html=True)
    
    st.divider()
    
    # 1. Onboarding Suggestions
    st.markdown("### 💡 Try Asking")
    for group in st.session_state.suggestions:
        with st.expander(group["category"], expanded=True):
            for question in group["questions"]:
                if st.button(question, key=f"btn_{question}"):
                    st.session_state.clicked_query = question
                    st.rerun()

    st.divider()

    # 2. Database Schema Explorer
    st.markdown("### 🗄️ Database Schema")
    if st.session_state.schema:
        for t_name, cols in st.session_state.schema.items():
            with st.expander(f"📋 {t_name}", expanded=False):
                st.markdown(f"**Columns:**")
                for col in cols:
                    pk_marker = " 🔑" if col["pk"] else ""
                    st.markdown(f"- `{col['name']}` *( {col['type']} )*{pk_marker}")
    else:
        st.info("Failed to load schema information.")

# ----------------- MAIN LAYOUT -----------------
st.markdown('<h1 class="brand-title">NF QueryGPT</h1>', unsafe_allow_html=True)
st.markdown('<div class="brand-subtitle">Ask your database anything in plain English or Hinglish</div>', unsafe_allow_html=True)

# Set up split columns
col_chat, col_details = st.columns([1.8, 1.5])

# ----------------- COLUMN 1: CHAT INTERFACE -----------------
with col_chat:
    st.markdown("### 💬 Chat Conversation")
    
    # Chat container
    chat_placeholder = st.container(height=500)
    
    with chat_placeholder:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-bubble-agent">{msg["content"]}</div>', unsafe_allow_html=True)
            st.markdown('<div class="chat-clear"></div>', unsafe_allow_html=True)

    # Process prompt submission (from input or sidebar click)
    prompt = st.chat_input("Enter your request here...")
    
    if st.session_state.clicked_query:
        prompt = st.session_state.clicked_query
        st.session_state.clicked_query = None

    if prompt:
        # Add human message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Add a placeholder for agent stream
        st.session_state.messages.append({"role": "assistant", "content": ""})
        
        # Refresh the chat to show the user bubble and start streaming
        st.rerun()

    # Check if we need to stream the last message
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant" and st.session_state.messages[-1]["content"] == "":
        user_prompt = st.session_state.messages[-2]["content"]
        
        # Prepare chat history to send
        history_to_send = []
        # Exclude the current question/placeholder
        for idx in range(len(st.session_state.messages) - 2):
            msg = st.session_state.messages[idx]
            history_to_send.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        with chat_placeholder:
            # We will render stream to a placeholder
            st.markdown(f'<div class="chat-bubble-user">{user_prompt}</div>', unsafe_allow_html=True)
            st.markdown('<div class="chat-clear"></div>', unsafe_allow_html=True)
            
            agent_bubble = st.empty()
            
            # Call streaming API
            try:
                # SSE POST call
                payload = {
                    "question": user_prompt,
                    "chat_history": history_to_send
                }
                
                response = requests.post(
                    f"{BACKEND_URL}/api/query/stream",
                    json=payload,
                    stream=True
                )
                
                streamed_tokens = ""
                sql_found = None
                result_found = None
                explanation_found = None
                error_found = None
                clarification_found = None
                
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: "):
                            data_str = decoded[6:]
                            if data_str == "[DONE]":
                                break
                            
                            data = json.loads(data_str)
                            
                            if data["type"] == "token":
                                streamed_tokens += data["content"]
                                # Update streaming bubble
                                agent_bubble.markdown(f'<div class="chat-bubble-agent">{streamed_tokens}</div>', unsafe_allow_html=True)
                            elif data["type"] == "sql":
                                sql_found = data["content"]
                            elif data["type"] == "result":
                                result_found = data["content"]
                                explanation_found = data.get("explanation")
                            elif data["type"] == "clarification":
                                clarification_found = data["content"]
                            elif data["type"] == "error":
                                error_found = data["content"]
                
                st.markdown('<div class="chat-clear"></div>', unsafe_allow_html=True)
                
                # Final updates
                if error_found:
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">⚠️ **Error:** {error_found}</div>', unsafe_allow_html=True)
                    st.session_state.messages[-1]["content"] = f"⚠️ **Error:** {error_found}"
                elif clarification_found:
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">❓ **Clarification needed:** {clarification_found}</div>', unsafe_allow_html=True)
                    st.session_state.messages[-1]["content"] = f"❓ **Clarification:** {clarification_found}"
                    st.session_state.clarification_needed = True
                    st.session_state.clarification_prompt = clarification_found
                else:
                    display_text = explanation_found if explanation_found else "Query executed successfully!"
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">{display_text}</div>', unsafe_allow_html=True)
                    st.session_state.messages[-1]["content"] = display_text
                    
                    # Store active results
                    st.session_state.active_sql = sql_found
                    st.session_state.active_result = result_found
                    st.session_state.active_explanation = explanation_found
                    st.session_state.clarification_needed = False
                    
                st.rerun()
                
            except Exception as e:
                err_msg = f"Failed to connect to backend: {str(e)}"
                agent_bubble.markdown(f'<div class="chat-bubble-agent">⚠️ **Connection Error:** {err_msg}</div>', unsafe_allow_html=True)
                st.session_state.messages[-1]["content"] = f"⚠️ **Connection Error:** {err_msg}"
                st.rerun()

# ----------------- COLUMN 2: DETAILS & VISUALIZATION PANEL -----------------
with col_details:
    st.markdown("### 📊 Query Analysis & Visualization")
    
    if st.session_state.active_result:
        result = st.session_state.active_result
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        res_type = result.get("type", "table")
        
        # Load into DataFrame for visualizations
        df = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame()
        
        # Card header for query description
        if st.session_state.active_explanation:
            st.markdown(f"""
            <div class="glass-card">
                <p style="margin:0; font-size:1.05rem; color:#E2D9F3; font-style:italic;">
                    " {st.session_state.active_explanation} "
                </p>
            </div>
            """, unsafe_allow_html=True)
            
        # Display Tabs
        tab_vis, tab_sql, tab_data = st.tabs(["🖼️ Visualization", "🔍 Generated SQL", "📋 Raw Data Table"])
        
        # Tab 1: Visualization tab
        with tab_vis:
            if res_type == "number":
                # Render Metric Card
                val = result.get("value")
                lbl = result.get("label", "Metric Value")
                st.markdown(f"""
                <div style="background:#1B1233; padding:2rem; border-radius:12px; border:1px solid #3F3066; text-align:center; margin-top:10px;">
                    <span style="font-size:1.1rem; color:#8E8A9F; text-transform:uppercase; letter-spacing:1px;">{lbl}</span>
                    <h1 style="font-size:3.5rem; color:#FF4081; margin: 10px 0px 0px 0px; font-weight:700;">{val}</h1>
                </div>
                """, unsafe_allow_html=True)
                
            elif res_type == "chart" and not df.empty:
                chart_conf = result.get("chart_config") or {}
                c_type = chart_conf.get("type", "bar")
                x_col = chart_conf.get("x")
                y_col = chart_conf.get("y")
                
                st.write(f"Plotting **{c_type}** chart: `{x_col}` vs `{y_col}`")
                
                # Render correct chart
                if c_type == "bar":
                    st.bar_chart(df.set_index(x_col)[y_col] if x_col in df.columns else df)
                elif c_type == "line":
                    st.line_chart(df.set_index(x_col)[y_col] if x_col in df.columns else df)
                elif c_type == "pie":
                    # Pie chart fallback using altair or direct st.dataframe
                    st.dataframe(df, use_container_width=True)
                else:
                    st.bar_chart(df.set_index(x_col)[y_col] if x_col in df.columns else df)
            else:
                # Table rendering fallback
                if not df.empty:
                    st.dataframe(df, use_container_width=True, height=350)
                else:
                    st.info("No rows returned from the query.")
                    
        # Tab 2: SQL Tab
        with tab_sql:
            if st.session_state.active_sql:
                st.markdown("**Executed Read-Only SQL:**")
                st.code(st.session_state.active_sql, language="sql")
                
        # Tab 3: Full Data Table Tab
        with tab_data:
            if not df.empty:
                st.markdown(f"**Returned Data:** ({len(df)} rows)")
                st.dataframe(df, use_container_width=True, height=350)
            else:
                st.info("No data available.")
                
    elif st.session_state.clarification_needed:
        st.markdown(f"""
        <div style="background:#2C1226; border:1px solid #FF4081; border-radius:12px; padding:1.5rem; margin-top:10px;">
            <h4 style="color:#FF4081; margin-top:0px;">Clarification Required</h4>
            <p style="color:#E2D9F3; margin-bottom:0px;">{st.session_state.clarification_prompt}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Default placeholder panel
        st.markdown(f"""
        <div style="border: 2px dashed #3F3066; border-radius:16px; padding:4rem 2rem; text-align:center; margin-top:10px; color:#8E8A9F;">
            <img src="https://img.icons8.com/color/96/wedding-rings.png" width="48" style="opacity: 0.5; margin-bottom:10px;"/>
            <h4>Waiting for Database Query...</h4>
            <p>Ask a question or select one of the onboarding prompt chips on the left to see dynamic query visualizations and SQL performance.</p>
        </div>
        """, unsafe_allow_html=True)
