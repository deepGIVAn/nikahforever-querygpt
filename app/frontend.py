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

def dataframe_to_markdown(df) -> str:
    """Helper to convert a pandas DataFrame to a markdown table without requiring the tabulate package."""
    if df.empty:
        return "No data available."
    columns = list(df.columns)
    header = "| " + " | ".join(str(col) for col in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    for _, row in df.iterrows():
        row_str = "| " + " | ".join(str(row[col]) for col in columns) + " |"
        rows.append(row_str)
    return "\n".join([header, separator] + rows)

# Custom CSS for modern premium matrimonial theme
# Custom CSS for modern premium matrimonial theme
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&display=swap');
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Apply DM Sans and keep white background on text elements only */
    html, body, .stApp {
        background-color: #FFFFFF !important;
    }
    
    p, h1, h2, h3, h4, h5, h6, .brand-title, .brand-subtitle, button, input, textarea {
        font-family: 'DM Sans', sans-serif !important;
        color: #1D1C1D !important;
    }
    
    /* Title and headings specific color */
    h1, h2, h3, h4, h5, h6 {
        color: #0F0B1E !important;
    }
    
    .brand-title {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #FF4081 0%, #9C27B0 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        margin-bottom: 0px !important;
        margin-top: 0px !important;
        display: inline-block;
    }
    
    .brand-subtitle {
        font-size: 0.95rem !important;
        color: #686477 !important;
        margin-bottom: 1rem !important;
        letter-spacing: 0.5px !important;
    }

    /* Make default streamlit header background transparent and set standard compact height */
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 40px !important;
        min-height: 40px !important;
        border: none !important;
    }
    
    /* Style all collapse/expand chevron and sidebar control buttons with light gray bg and dark icon */
    [data-testid="collapsedControl"], 
    button[kind="header"], 
    button[aria-label="Close sidebar"],
    button[data-testid="stSidebarCollapse"] {
        background-color: #F4F4F4 !important;
        color: #2D2D2D !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.08) !important;
        margin-top: 4px !important;
        margin-left: 10px !important;
        z-index: 999999 !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="collapsedControl"]:hover, 
    button[kind="header"]:hover, 
    button[aria-label="Close sidebar"]:hover {
        background-color: #EAEAEA !important;
    }
    
    [data-testid="collapsedControl"] svg, 
    button[kind="header"] svg, 
    button[aria-label="Close sidebar"] svg,
    button[data-testid="stSidebarCollapse"] svg {
        fill: #2D2D2D !important;
        color: #2D2D2D !important;
    }
    
    /* Adjust page margins and paddings */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 98% !important;
    }
    
    /* Allow scrolling naturally so chat input is visible */
    html, body, [data-testid="stAppViewContainer"] {
        height: auto !important;
        overflow: auto !important;
    }
    
    /* Light gray sidebar like ChatGPT */
    section[data-testid="stSidebar"] {
        background-color: #F9F9F9 !important;
        border-right: 1px solid #E5E5E5 !important;
    }
    
    /* Make sidebar items dark text */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #2D2D2D !important;
    }
    
    /* Dynamic Buttons & Suggestion Chips using light pink #FFF4F6 */
    .stButton>button {
        background: #FFF4F6 !important;
        color: #A61D5D !important;
        border: 1px solid #FFD1DC !important;
        border-radius: 20px !important;
        padding: 0.4rem 1rem !important;
        font-size: 0.85rem !important;
        transition: all 0.3s ease !important;
        text-align: left !important;
        width: 100% !important;
        margin-bottom: 5px !important;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #FF66A3 0%, #B829D6 100%) !important;
        color: white !important;
        border-color: transparent !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 15px rgba(255, 102, 163, 0.2) !important;
    }
    
    /* Glassmorphism Panel using #FFF4F6 */
    .glass-card {
        background: #FFF4F6 !important;
        border: 1px solid #FFD1DC !important;
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    
    .glass-card p {
        color: #A61D5D !important;
    }
    
    /* Chat Bubble styling */
    .chat-bubble-user {
        background: linear-gradient(135deg, #FF4081 0%, #D81B60 100%) !important;
        color: white !important;
        padding: 0.8rem 1.2rem;
        border-radius: 20px 20px 0px 20px;
        margin-bottom: 1rem;
        max-width: 85%;
        float: right;
        box-shadow: 0 4px 10px rgba(255, 64, 129, 0.15);
    }
    
    .chat-bubble-agent {
        background: #F4F4F4 !important;
        border: 1px solid #E5E5E5 !important;
        color: #2D2D2D !important;
        padding: 0.8rem 1.2rem;
        border-radius: 20px 20px 20px 0px;
        margin-bottom: 1rem;
        max-width: 85%;
        float: left;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    
    /* Override internal agent text color inside bubbles */
    .chat-bubble-agent p {
        color: #2D2D2D !important;
    }
    
    .chat-clear {
        clear: both;
    }
    
    /* SQL Codeblock Container remains dark for high code readability */
    .sql-code-container {
        border-left: 3px solid #FF4081 !important;
        background: #09050F !important;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0px;
    }

    /* Style the tabs to match the pink theme in light mode */
    div[data-baseweb="tab-list"] {
        background-color: transparent !important;
        border-bottom: 1px solid #E5E5E5 !important;
    }
    button[data-baseweb="tab"] {
        color: #686477 !important;
        background-color: transparent !important;
        font-weight: 500 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #D81B60 !important;
        border-bottom: 2px solid #FF4081 !important;
    }

    /* Target streamlit expanders/accordions to style them gray background with dark text */
    .streamlit-expanderHeader {
        background-color: #EFEFEF !important;
        border: 1px solid #E5E5E5 !important;
        color: #1D1C1D !important;
        font-weight: 600 !important;
    }
    
    .streamlit-expanderContent {
        background-color: #FFFFFF !important;
        border-left: 1px solid #E5E5E5 !important;
        border-right: 1px solid #E5E5E5 !important;
        border-bottom: 1px solid #E5E5E5 !important;
    }

    /* Explicitly set border for vertical block containers (e.g. st.container with height) to make them visible in dark mode */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #E5E5E5 !important;
        border-radius: 12px !important;
        background-color: #FFFFFF !important;
    }

    /* Style the chat input box - outer element transparent and borderless to avoid double borders */
    [data-testid="stChatInput"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        box-shadow: none !important;
    }

    /* Style the inner chat input wrapper with light gray background and subtle border */
    [data-testid="stChatInput"] > div {
        background-color: #F4F4F4 !important;
        border: 1px solid #E5E5E5 !important;
        border-radius: 12px !important;
        padding: 4px 8px !important;
        box-shadow: none !important;
    }

    [data-testid="stChatInput"] > div:focus-within {
        border-color: #D81B60 !important;
        box-shadow: 0 0 0 1px #D81B60 !important;
    }

    [data-testid="stChatInput"] textarea {
        background-color: transparent !important;
        color: #1D1C1D !important;
        border: none !important;
        box-shadow: none !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    /* Style the chat input send button */
    [data-testid="stChatInput"] button {
        background-color: #D81B60 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 6px !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    [data-testid="stChatInput"] button:hover {
        background-color: #FF4081 !important;
        transform: scale(1.05) !important;
    }

    [data-testid="stChatInput"] button svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }

    /* Disabled send button state */
    [data-testid="stChatInput"] button:disabled {
        background-color: transparent !important;
        opacity: 0.3 !important;
        transform: none !important;
    }

    [data-testid="stChatInput"] button:disabled svg {
        color: #1D1C1D !important;
        fill: #1D1C1D !important;
    }

    /* Streamlit dataframes and tables text readability */
    div[data-testid="stDataFrame"] table {
        background-color: #FFFFFF !important;
        color: #2D2D2D !important;
    }
    div[data-testid="stDataFrame"] th {
        background-color: #F4F4F4 !important;
        color: #2D2D2D !important;
    }
    div[data-testid="stDataFrame"] td {
        background-color: #FFFFFF !important;
        color: #2D2D2D !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "messages" not in st.session_state:
    st.session_state.messages = []

if "generate_response" not in st.session_state:
    st.session_state.generate_response = False

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
    st.image("https://www.nikahforever.com/asset/svgs/landing-page/hero-section/logo.svg", width=180)
    st.markdown('<p style="color: #FFF4F6; font-size:0.8rem; text-transform:uppercase; letter-spacing: 1px; margin-top: 10px; opacity: 0.85;">Data RAG Assistant</p>', unsafe_allow_html=True)
    
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
    chat_placeholder = st.container(height=520)
    
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
        
        # Trigger response generation state
        st.session_state.generate_response = True
        
        # Refresh the chat to show the user bubble and start streaming
        st.rerun()

    # Check if we need to stream the last message
    if st.session_state.generate_response and len(st.session_state.messages) > 0:
        # Reset the generate flag immediately to prevent loop
        st.session_state.generate_response = False
        
        user_prompt = st.session_state.messages[-1]["content"]
        
        # Prepare chat history to send
        history_to_send = []
        # Exclude the last message which is the current query we just added
        for idx in range(len(st.session_state.messages) - 1):
            msg = st.session_state.messages[idx]
            history_to_send.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        with chat_placeholder:
            agent_bubble = st.empty()
            
            # Show premium loading state in agent bubble
            agent_bubble.markdown("""
            <div class="chat-bubble-agent">
                <span style="font-style: italic; opacity: 0.85; display: flex; align-items: center; gap: 8px;">
                    <svg style="animation: spin 1s linear infinite; width: 18px; height: 18px; color: #D81B60;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" style="opacity: 0.25;"></circle>
                        <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Thinking & querying database...
                </span>
            </div>
            <div class="chat-clear"></div>
            """, unsafe_allow_html=True)
            
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
                                agent_bubble.markdown(f'<div class="chat-bubble-agent">{streamed_tokens}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
                            elif data["type"] == "sql":
                                sql_found = data["content"]
                            elif data["type"] == "result":
                                result_found = data["content"]
                                explanation_found = data.get("explanation")
                            elif data["type"] == "clarification":
                                clarification_found = data["content"]
                            elif data["type"] == "error":
                                error_found = data["content"]
                
                # Final updates
                if error_found:
                    final_msg = f"⚠️ **Error:** {error_found}"
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">{final_msg}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": final_msg})
                elif clarification_found:
                    final_msg = f"❓ **Clarification:** {clarification_found}"
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">{final_msg}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": final_msg})
                    st.session_state.clarification_needed = True
                    st.session_state.clarification_prompt = clarification_found
                else:
                    explanation = explanation_found if explanation_found else "Query executed successfully!"
                    if result_found:
                        res_type = result_found.get("type", "table")
                        if res_type == "number":
                            val = result_found.get("value")
                            display_text = f"{explanation}\n\n**Result:** {val}"
                        else:
                            columns = result_found.get("columns", [])
                            rows = result_found.get("rows", [])
                            if rows:
                                df = pd.DataFrame(rows, columns=columns)
                                table_md = dataframe_to_markdown(df.head(5))
                                display_text = f"{explanation}\n\n**Result (Top 5 rows):**\n\n{table_md}"
                            else:
                                display_text = f"{explanation}\n\n**Result:** No rows returned."
                    else:
                        display_text = explanation
                        
                    agent_bubble.markdown(f'<div class="chat-bubble-agent">{display_text}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": display_text})
                    
                    # Store active results
                    st.session_state.active_sql = sql_found
                    st.session_state.active_result = result_found
                    st.session_state.active_explanation = explanation_found
                    st.session_state.clarification_needed = False
                    
                st.rerun()
                
            except Exception as e:
                err_msg = f"⚠️ **Connection Error:** Failed to connect to backend: {str(e)}"
                agent_bubble.markdown(f'<div class="chat-bubble-agent">{err_msg}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
                st.rerun()

# ----------------- COLUMN 2: DETAILS & VISUALIZATION PANEL -----------------
with col_details:
    st.markdown("### 📊 Query Analysis & Visualization")
    
    details_container = st.container(height=520)
    with details_container:
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
                    <p style="margin:0; font-size:1.05rem; color:#A61D5D; font-style:italic; font-weight: 500;">
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
                    <div style="background:#FFF4F6; padding:2rem; border-radius:12px; border:1px solid #FFD1DC; text-align:center; margin-top:10px;">
                        <span style="font-size:1.1rem; color:#A61D5D; text-transform:uppercase; letter-spacing:1px; font-weight: 600;">{lbl}</span>
                        <h1 style="font-size:3.5rem; color:#D81B60; margin: 10px 0px 0px 0px; font-weight:700;">{val}</h1>
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
            <div style="background:#FFF4F6; border:1px solid #FFB3C6; border-radius:12px; padding:1.5rem; margin-top:10px;">
                <h4 style="color:#D81B60; margin-top:0px;">Clarification Required</h4>
                <p style="color:#2D2D2D; margin-bottom:0px;">{st.session_state.clarification_prompt}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Default placeholder panel
            st.markdown(f"""
            <div style="border: 2px dashed #FFB3C6; border-radius:16px; padding:4rem 2rem; text-align:center; margin-top:10px; color:#2D2D2D; background-color: #FFF4F6;">
                <img src="https://www.nikahforever.com/asset/svgs/landing-page/hero-section/logo.svg" width="120" style="opacity: 0.8; margin-bottom:15px;"/>
                <h4 style="color: #D81B60;">Waiting for Database Query...</h4>
                <p style="font-size: 0.9rem; opacity: 0.8; color: #686477;">Ask a question or select one of the onboarding prompt chips on the left to see dynamic query visualizations and SQL performance.</p>
            </div>
            """, unsafe_allow_html=True)
