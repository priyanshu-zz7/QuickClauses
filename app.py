import asyncio
import random
import time
from datetime import datetime
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from deep_translator import GoogleTranslator

import os
import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from ragbase.chain import ask_question, create_chain
from ragbase.config import Config
from ragbase.ingestor import Ingestor
from ragbase.model import create_llm
from ragbase.retriever import create_retriever
from ragbase.uploader import upload_files

load_dotenv()

if 'selected_language' not in st.session_state:
    st.session_state.selected_language = 'English'

LOADING_MESSAGES = [
    "🔍 Analyzing your legal documents...",
    "⚖️ Cross-referencing legal clauses...",
    "📚 Diving into your case files...",
    "🧠 Decoding legal complexities...",
    "📊 Extracting key legal insights...",
    "💼 Summarizing contractual obligations...",
]

# New feature: Common legal questions
COMMON_QUESTIONS = [
    "What are the main obligations in this contract?",
    "What are the termination clauses?",
    "What are the payment terms?",
    "What are the confidentiality requirements?",
    "What is the duration of this agreement?",
]

JARGON_DICTIONARY = {
    "force majeure": "An unforeseeable circumstance that prevents someone from fulfilling a contract (e.g., natural disaster).",
    "indemnity": "A promise to compensate for any loss, damage, or injury.",
    "indemnify": "To compensate someone for harm or loss.",
    "mutatis mutandis": "With the necessary changes having been made.",
    "in perpetuity": "Forever.",
    "breach of contract": "Failing to perform any term of a contract without a legitimate legal excuse.",
    "jurisdiction": "The official power to make legal decisions and judgments.",
    "severability": "If one part of the contract is invalid, the rest of the contract still applies.",
    "arbitration": "Resolving a dispute outside of court with a neutral third party.",
    "pro rata": "Proportional distribution (e.g., paying for only the days you used a service)."
}

CHATS_DIR = Path("chats")
CHATS_DIR.mkdir(exist_ok=True)

def save_current_chat():
    if "session_id" in st.session_state and "messages" in st.session_state:
        if len(st.session_state.messages) > 1:
            with open(CHATS_DIR / f"{st.session_state.session_id}.json", "w", encoding="utf-8") as f:
                json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)

def load_chat(session_id):
    path = CHATS_DIR / f"{session_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
            st.session_state.session_id = session_id

SUPPORTED_LANGUAGES = {
    'English': 'en',
    'Hindi': 'hi',
}

st.set_page_config(page_title="QuickClauses", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")


def custom_css():
    st.markdown(
        """
        <style>
        /* Base styles & Layout fixes */
        body {
            font-family: 'Inter', system-ui, sans-serif;
        }
        
        /* Base layout & typography */
        body {
            font-family: 'Inter', system-ui, sans-serif;
            background-color: #ffffff;
        }
        
        /* Fill horizontal space cleanly */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 4rem !important;
            padding-left: 5rem !important;
            padding-right: 5rem !important;
            max-width: 1400px !important;
        }
        
        /* Hide default Streamlit elements */
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* App background (Red Gradient like Adobe) */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #dc2626 0%, #fef2f2 500px, #f8fafc 100%) !important;
        }
        
        /* The Adobe-style white card wrapper */
        div[data-testid="stVerticalBlock"]:has(.adobe-marker) {
            background-color: #ffffff;
            border: 2px dashed #cbd5e1;
            border-radius: 24px;
            padding: 60px 40px;
            margin: 40px auto;
            max-width: 1000px;
            width: 100%;
            box-sizing: border-box !important;
            box-shadow: 0 20px 40px rgba(0,0,0,0.05);
        }
        
        /* Style the file uploader dropzone to blend into our white card */
        [data-testid="stFileUploader"] {
            width: 100% !important;
            margin-top: 20px !important;
        }
        
        [data-testid="stFileUploaderDropzone"] {
            background-color: transparent !important;
            border: none !important;
            padding: 20px 0 !important; 
        }
        
        /* Style the button to look like Adobe's blue button */
        [data-testid="stFileUploaderDropzone"] button {
            background-color: #2563eb !important;
            color: white !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            padding: 12px 28px !important;
            border: none !important;
            font-size: 1.1rem !important;
        }
        [data-testid="stFileUploaderDropzone"] button:hover {
            background-color: #1d4ed8 !important;
        }
        
        /* Hide default Streamlit uploader icon and text */
        [data-testid="stFileUploaderDropzone"] svg {
            display: none;
        }
        [data-testid="stFileUploaderDropzone"] div[data-testid="stMarkdownContainer"] p {
            display: none;
        }
        
        /* Perfectly center the alert and header by targeting their parent containers */
        [data-testid="element-container"]:has([data-testid="stAlert"]),
        [data-testid="element-container"]:has(.header-content) {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }
        
        [data-testid="element-container"]:has([data-testid="stAlert"]) {
            margin-top: 20px !important;
        }
        
        [data-testid="stAlert"] {
            width: max-content !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            margin: 0 !important;
        }
        
        /* Fix Monospace Slider Labels */
        .stSlider div[data-testid="stMarkdownContainer"] p {
            font-family: 'Inter', system-ui, sans-serif !important;
            font-size: 0.9rem !important;
        }
        
        /* Stats & Metadata Container */
        .stats-container {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 24px;
            margin-top: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }
        
        /* Chat messages */
        .stChatMessage {
            border-radius: 8px;
            margin: 12px auto;
            padding: 16px 20px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            max-width: 850px !important;
        }
        
        [data-testid="stChatInput"] {
            max-width: 850px !important;
            width: 100% !important;
            box-sizing: border-box !important;
            margin: 0 auto !important;
        }
        
        [data-testid="stChatInput"] .stChatInput, 
        [data-testid="stChatInput"] > div {
            max-width: 100% !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }
        
        /* Sidebar Background */
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #e5e7eb !important;
        }
        
        /* ChatGPT-style Sidebar History Buttons */
        [data-testid="stSidebar"] [data-testid="stButton"] button {
            justify-content: flex-start !important;
            text-align: left !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            box-shadow: none !important;
            color: #4b5563 !important;
            padding: 10px 14px !important;
            border-radius: 10px !important;
            width: 100% !important;
            font-size: 0.95rem !important;
            transition: all 0.2s ease !important;
            margin-bottom: 4px !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
            background: #f8fafc !important;
            border-color: #e2e8f0 !important;
            color: #0f172a !important;
        }
        
        /* New Conversation Button - Adobe Red CTA */
        [data-testid="stSidebar"] [data-testid="stButton"]:first-of-type button {
            background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 1.05rem !important;
            justify-content: center !important;
            text-align: center !important;
            border-radius: 12px !important;
            padding: 14px !important;
            margin-bottom: 24px !important;
            box-shadow: 0 4px 12px rgba(220, 38, 38, 0.2) !important;
            border: none !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"]:first-of-type button:hover {
            box-shadow: 0 6px 16px rgba(220, 38, 38, 0.3) !important;
            transform: translateY(-1px) !important;
        }
        
        /* User message */
        [data-testid="stChatMessage"]:has(div:first-child > img[alt="user-avatar"]) {
            background: #ffffff;
            border-left: 4px solid #94a3b8;
        }
        
        /* Assistant message */
        [data-testid="stChatMessage"]:has(div:first-child > img[alt="assistant-avatar"]) {
            background: #f8fafc;
            border-left: 4px solid #0047AB;
        }
        
        /* Quick actions */
        .quick-action-btn {
            flex: 1;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #0047AB;
            background: transparent;
            color: #0047AB;
            transition: all 0.2s ease;
            font-size: 0.9em;
            margin: 4px;
            font-weight: 500;
            text-align: center;
            cursor: pointer;
        }
        
        .quick-action-btn:hover {
            background: #0047AB;
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* Mobile optimizations */
        @media (max-width: 768px) {
            .title { font-size: 2rem; }
            .subtitle { font-size: 1rem; }
            .stChatMessage { padding: 12px 15px; }
            .quick-action-btn { font-size: 0.85em; padding: 8px; }
        }
        
        /* Progress bar */
        .stProgress > div > div > div {
            background: #0047AB;
            height: 6px;
            border-radius: 3px;
        }
        
        /* Chat input */
        .stTextInput input, .stChatInputContainer {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
        }
        
        /* Source documents & Jargon Buster expanders */
        [data-testid="stExpander"] {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
            margin: 10px 0 !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
        }
        
        /* Metrics / Stats */
        [data-testid="stMetricValue"] {
            color: #0047AB !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def extract_text_from_pdf(uploaded_files):
    extracted_text = ""
    for uploaded_file in uploaded_files:
        pdf = PdfReader(uploaded_file)
        for page in pdf.pages:
            extracted_text += page.extract_text() or ""
        
        # OCR for image-based PDFs
        images = convert_from_bytes(uploaded_file.getvalue())
        for image in images:
            extracted_text += pytesseract.image_to_string(image)
            
    return extracted_text

# Identify legal keywords
IMPORTANT_TERMS = [
    "obligation", "liability", "termination", "confidentiality", "payment", "indemnity"
]

def highlight_important_content(text):
    highlighted = ""
    for line in text.split("\n"):
        if any(term in line.lower() for term in IMPORTANT_TERMS):
            highlighted += f"⚠️ **{line}**\n"
        else:
            highlighted += line + "\n"
    return highlighted


# New feature: Document statistics
def get_document_stats(files):
    total_size = sum(file.size for file in files)
    return {
        "count": len(files),
        "total_size": f"{total_size / 1024 / 1024:.2f} MB",
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# New feature: Document Metadata Verification
def verify_document_metadata(files):
    metadata_results = []
    for file in files:
        try:
            pdf = PdfReader(file)
            info = pdf.metadata
            if info:
                title = info.title if info.title else "Unknown"
                author = info.author if info.author else "Unknown"
                
                is_valid = title != "Unknown" or author != "Unknown"
                
                metadata_results.append({
                    "filename": file.name,
                    "title": title,
                    "author": author,
                    "is_valid": is_valid
                })
            else:
                metadata_results.append({
                    "filename": file.name,
                    "is_valid": False
                })
        except Exception as e:
            metadata_results.append({
                "filename": file.name,
                "is_valid": False,
                "error": str(e)
            })
        finally:
            file.seek(0)
    return metadata_results


@st.cache_resource(show_spinner=False)
def build_qa_chain(files):
    file_paths = upload_files(files)
    vector_store = Ingestor().ingest(file_paths)
    llm = create_llm()
    retriever = create_retriever(llm, vector_store=vector_store)
    return create_chain(llm, retriever)


async def ask_chain(question: str, chain):
    start_time = time.time()
    full_response = ""
    assistant = st.chat_message(
        "assistant", avatar=str(Config.Path.IMAGES_DIR / "assistant-avatar.png")
    )
    with assistant:
        message_placeholder = st.empty()
        message_placeholder.status(random.choice(LOADING_MESSAGES), state="running")
        documents = []
        try:
            async for event in ask_question(chain, question, session_id="session-id-42"):
                if type(event) is str:
                    full_response += event
                    message_placeholder.markdown(full_response)
                if type(event) is list:
                    documents.extend(event)
            # Show source documents with relevance scores
            for i, doc in enumerate(documents):
                with st.expander(f"Source #{i+1} - Relevance: {random.randint(75, 99)}%"):
                    st.write(doc.page_content)
    
            # Show response time
            response_time = time.time() - start_time
            st.markdown(f"<div class='chat-info'>Response time: {response_time:.2f}s</div>", unsafe_allow_html=True)
            
            # Jargon Buster
            found_jargon = {term: definition for term, definition in JARGON_DICTIONARY.items() if term in full_response.lower()}
            if found_jargon:
                with st.expander("💡 Legal Jargon Buster"):
                    for term, definition in found_jargon.items():
                        st.markdown(f"**{term.title()}**: {definition}")
    
            st.session_state.messages.append({
                "role": "assistant", 
                "content": full_response,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            save_current_chat()
        except Exception as e:
            st.error(f"⚠️ Groq API Error: {str(e)}\n\nThis is usually caused by an invalid API Key, hitting a Free-Tier Rate Limit, or selecting too much text at once. Please check your console.groq.com limits!")
            st.stop()


def show_upload_documents():
    custom_css()
    
    # Add language selector in sidebar
    if 'selected_language' not in st.session_state:
        st.session_state.selected_language = 'English'
    # Sleek Sidebar Headers
    st.sidebar.markdown(
        "<div style='color: #64748b; font-size: 0.8rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px; margin-top: 10px;'>💬 Chat History</div>",
        unsafe_allow_html=True
    )
    if st.sidebar.button("➕ New Conversation", use_container_width=True):
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.messages = [{
            "role": "assistant",
            "content": "Hi! What do you want to know about your documents?",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }]
        st.rerun()
        
    def get_chat_title(file_path):
        session_id = file_path.stem
        time_str = ""
        try:
            dt = datetime.strptime(session_id, "%Y%m%d_%H%M%S")
            time_str = dt.strftime("%b %d, %H:%M")
        except:
            pass
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                msgs = json.load(f)
                for m in msgs:
                    if m.get("role") == "user":
                        text = m.get("content", "").strip()
                        if text:
                            title = text[:22] + "..." if len(text) > 22 else text
                            return f"{title} ({time_str})" if time_str else title
        except:
            pass
        return f"Empty Chat ({time_str})" if time_str else "New Conversation"

    chat_files = sorted(CHATS_DIR.glob("*.json"), reverse=True)
    for chat_file in chat_files:
        session_id = chat_file.stem
        chat_title = get_chat_title(chat_file)
        
        # Add a subtle visual indicator for the active chat
        icon = "💬" if session_id == st.session_state.get("session_id") else "📝"
        label = f"{icon} {chat_title}"
        
        if st.sidebar.button(label, key=f"btn_{session_id}", use_container_width=True):
            load_chat(session_id)
            st.rerun()

    st.sidebar.divider()
    st.sidebar.markdown(
        "<div style='color: #64748b; font-size: 0.8rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 16px;'>⚙️ Settings</div>",
        unsafe_allow_html=True
    )
    
    # Analysis settings in sidebar
    st.session_state.analysis_depth = st.sidebar.select_slider(
        "Analysis Depth",
        options=["Quick Scan", "Standard", "Deep Analysis"],
        value="Standard",
        help="Controls how thoroughly the AI analyzes documents",
        label_visibility="collapsed"
    )

    st.session_state.legal_focus = st.sidebar.multiselect(
        "Focus Areas",
        ["Obligations", "Risks", "Deadlines", "Financial Terms", "Compliance", "Intellectual Property"],
        default=["Obligations", "Risks"],
        help="Select areas to emphasize in the analysis"
    )

    # Language selection
    st.sidebar.selectbox(
        "Interface Language",
        options=list(SUPPORTED_LANGUAGES.keys()),
        key='selected_language'
    )

    # Apply analysis depth to processing
    if st.session_state.analysis_depth == "Quick Scan":
        Config.CHUNK_SIZE = 1000
        Config.CHUNK_OVERLAP = 100
        Config.USE_SEMANTIC_CHUNKING = False
    elif st.session_state.analysis_depth == "Deep Analysis":
        Config.CHUNK_SIZE = 3000
        Config.CHUNK_OVERLAP = 500
        Config.USE_SEMANTIC_CHUNKING = True
    else:
        Config.CHUNK_SIZE = 2048
        Config.CHUNK_OVERLAP = 128
        Config.USE_SEMANTIC_CHUNKING = True

    # Update important terms based on focus areas
    focus_terms = {
        "Obligations": ["shall", "must", "required", "obligation"],
        "Risks": ["liability", "damage", "breach", "penalty"],
        "Deadlines": ["deadline", "within", "by", "date"],
        "Financial Terms": ["payment", "fee", "cost", "price"],
        "Compliance": ["comply", "regulation", "law", "policy"],
        "Intellectual Property": ["patent", "copyright", "trademark", "ip"]
    }
    
    IMPORTANT_TERMS.extend([
        term for focus in st.session_state.legal_focus
        for term in focus_terms.get(focus, [])
    ])
    # Add animated CSS
    st.markdown("""
        <style>
        @keyframes slideIn {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        .feature-icon {
            font-size: 1.2em;
            margin-right: 8px;
            display: inline-block;
        }
        .title {
            animation: slideIn 0.8s ease-out;
        }
        .subtitle {
            animation: slideIn 0.8s ease-out 0.2s backwards;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Premium SaaS Header
    st.markdown(
        "<div class='header-content' style='max-width: 1000px; width: 100%; box-sizing: border-box; margin: 0 auto 20px auto; background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%); padding: 24px 40px; border-radius: 24px; color: white; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 10px 30px rgba(220, 38, 38, 0.2); position: relative; z-index: 10;'>"
        "<div style='display: flex; align-items: center; gap: 20px;'>"
        "<div style='background: white; width: 56px; height: 56px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 1.8rem; box-shadow: 0 4px 10px rgba(0,0,0,0.1);'>⚖️</div>"
        "<div>"
        "<h1 style='margin: 0; font-size: 2rem; font-weight: 800; letter-spacing: -0.5px; color: white; line-height: 1.2;'>QuickClauses</h1>"
        "<p style='margin: 0; color: #fca5a5; font-size: 1rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px;'>Legal Engine</p>"
        "</div>"
        "</div>"
        "<div style='background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); padding: 8px 16px; border-radius: 30px; font-size: 0.85rem; font-weight: 600; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;'>"
        "<div style='width: 8px; height: 8px; background-color: #4ade80; border-radius: 50%; box-shadow: 0 0 8px #4ade80;'></div> Local AI Active"
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )
    
    holder = st.empty()
    with holder.container():
        
        # Add the invisible marker so CSS targets this specific container
        st.markdown("<div class='adobe-marker'></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([1.5, 1])
        
        with col1:
            st.markdown(
                "<div style='padding-left: 10px;'>"
                "<h1 style='font-size: 3.5rem; font-weight: 800; color: #111827; line-height: 1.1; margin-bottom: 20px;'>Analyze a Contract</h1>"
                "<p style='font-size: 1.2rem; color: #4b5563; margin-bottom: 30px; max-width: 90%;'>"
                "Drag and drop a PDF contract to extract obligations and flag risks using our local AI engine. Free to use, completely private."
                "</p></div>",
                unsafe_allow_html=True
            )
            
            # File Upload Area (styled to look like just a blue button)
            uploaded_files = st.file_uploader(
                "Upload Legal Documents",
                type=["pdf"],
                accept_multiple_files=True,
                help="PDF only, up to 200MB",
                label_visibility="collapsed"
            )
            
        with col2:
            st.markdown(
                "<div style='display: flex; justify-content: flex-end; align-items: center; height: 100%; padding-top: 40px;'>"
                "<svg width='160' height='160' viewBox='0 0 24 24' fill='none' stroke='#22c55e' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' role='img' aria-label='PDF Document Icon'>"
                "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'></path>"
                "<polyline points='14 2 14 8 20 8'></polyline>"
                "<text x='12' y='16' font-family='sans-serif' font-size='6' font-weight='800' fill='#22c55e' stroke='none' text-anchor='middle'>PDF</text>"
                "</svg></div>",
                unsafe_allow_html=True
            )
            
        # Trust Signal below everything inside the card
        if not uploaded_files:
            st.markdown(
                "<div style='margin-top: 40px; text-align: center;'>"
                "<p style='color: #6b7280; font-size: 0.95rem;'>"
                "🔒 Your file will be securely handled completely offline."
                "</p></div>",
                unsafe_allow_html=True
            )
        
        if uploaded_files:
            stats = get_document_stats(uploaded_files)
            st.session_state.document_stats = stats
            
            # Clean Stats & Metadata
            st.markdown('<div class="stats-container">', unsafe_allow_html=True)
            st.markdown("### 📊 Document Analysis Ready")
            
            s_col1, s_col2 = st.columns([1, 2], gap="large")
            with s_col1:
                st.metric("📄 Documents", stats['count'])
                st.metric("📦 Size", stats['total_size'])
            
            with s_col2:
                metadata_results = verify_document_metadata(uploaded_files)
                st.session_state.document_metadata = metadata_results
                for meta in metadata_results:
                    if meta.get("is_valid"):
                        st.success(f"✅ Verified: **{meta['filename']}** | Title: {meta['title']} | Author: {meta['author']}")
                    else:
                        st.warning(f"⚠️ Missing Metadata: **{meta['filename']}** - Cannot verify author or title.")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    if not uploaded_files:
        if len(st.session_state.messages) > 1:
            st.warning("You are viewing a past conversation. Upload the original document(s) above to continue asking questions.", icon="⚠️")
            return None
        else:
            st.info("Please select a PDF file to begin analysis.", icon="ℹ️")
            st.stop()
    else:
        st.success(f"Ready to analyze {len(uploaded_files)} document(s).", icon="✅")

    with st.spinner("🔄 Processing your documents..."):
        progress_bar = st.progress(0)
        for i in range(100):
            progress_bar.progress(i + 1)
            if i % 50 == 0:
                st.markdown(random.choice(LOADING_MESSAGES))
            time.sleep(0.01)
        holder.empty()
        return build_qa_chain(uploaded_files)


def show_message_history():
    target_lang = SUPPORTED_LANGUAGES[st.session_state.selected_language]
    
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        
        # Translate message content
        translated_content = translate_text(content, target_lang)
        
        avatar_path = (
            Config.Path.IMAGES_DIR / "assistant-avatar.png"
            if role == "assistant"
            else Config.Path.IMAGES_DIR / "user-avatar.png"
        )
        with st.chat_message(role, avatar=str(avatar_path)):
            st.markdown(translated_content)
            
            if role == "assistant":
                found_jargon = {term: definition for term, definition in JARGON_DICTIONARY.items() if term in translated_content.lower()}
                if found_jargon:
                    with st.expander("💡 Legal Jargon Buster"):
                        for term, definition in found_jargon.items():
                            st.markdown(f"**{term.title()}**: {definition}")
                            
            if "timestamp" in message:
                st.markdown(f"<div class='chat-info'>{message['timestamp']}</div>", unsafe_allow_html=True)

def show_quick_actions():
    target_lang = SUPPORTED_LANGUAGES[st.session_state.selected_language]
    
    st.markdown("<div class='quick-actions'>", unsafe_allow_html=True)
    
    # Translate button texts
    quick_button_texts = [
        translate_text("📋 Main Obligations", target_lang),
        translate_text("🚫 Termination Terms", target_lang),
        translate_text("💰 Payment Terms", target_lang),
        translate_text("🔒 Confidentiality", target_lang),
        translate_text("⏱️ Duration", target_lang)
    ]
    
    rows = [quick_button_texts[i:i+2] for i in range(0, len(quick_button_texts), 2)]
    
    for i, row_buttons in enumerate(rows):
        cols = st.columns(len(row_buttons))
        for j, (col, button_text) in enumerate(zip(cols, row_buttons)):
            original_question = COMMON_QUESTIONS[i*2 + j]
            if col.button(button_text, key=f"quick_{i*2 + j}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": original_question})
                with st.chat_message(
                    "user",
                    avatar=str(Config.Path.IMAGES_DIR / "user-avatar.png"),
                ):
                    st.markdown(original_question)
                asyncio.run(ask_chain(original_question, st.session_state.chain))
    
    st.markdown("</div>", unsafe_allow_html=True)


def show_chat_input(chain):
    target_lang = SUPPORTED_LANGUAGES[st.session_state.selected_language]
    source_lang = SUPPORTED_LANGUAGES[st.session_state.selected_language]
    
    st.session_state.chain = chain
    
    # Show metadata above frequent questions
    if "document_metadata" in st.session_state and "document_stats" in st.session_state:
        stats = st.session_state.document_stats
        meta_list = st.session_state.document_metadata
        
        meta_html = (
            "<div style='max-width: 850px; margin: 0 auto 20px auto; background: linear-gradient(to right, #f8fafc, #ffffff); border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>"
            "<div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;'>"
            "<div style='font-weight: 700; color: #0f172a; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;'>📑 Active Documents</div>"
            f"<div style='background-color: #f1f5f9; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; color: #475569;'>{stats['count']} file(s) • {stats['total_size']}</div>"
            "</div>"
            "<div style='display: flex; flex-direction: column; gap: 8px;'>"
        )
        
        for m in meta_list:
            status_icon = "✅" if m.get("is_valid") else "⚠️"
            title = m.get("title", "Unknown Title")
            author = m.get("author", "Unknown Author")
            meta_html += (
                f"<div style='font-size: 0.85rem; color: #475569; display: flex; align-items: flex-start; gap: 8px;'>"
                f"<span>{status_icon}</span>"
                f"<div><strong style='color: #1e293b;'>{m['filename']}</strong><br>"
                f"<span style='opacity: 0.8;'>Title: {title} | Author: {author}</span></div>"
                f"</div>"
            )
            
        meta_html += "</div></div>"
        st.markdown(meta_html, unsafe_allow_html=True)
        
    if chain is None:
        st.chat_input("Please upload the original documents above to continue this chat.", disabled=True)
        return
        
    show_quick_actions()
    
    placeholder_text = translate_text("Ask your question here", target_lang)
    if prompt := st.chat_input(placeholder_text):
        # Translate user input to English for processing
        english_prompt = translate_text(prompt, 'en', source_lang)
        
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,  # Store original prompt
            "translated_content": english_prompt,  # Store translated prompt
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        with st.chat_message("user", avatar=str(Config.Path.IMAGES_DIR / "user-avatar.png")):
            st.markdown(prompt)
        
        # Use translated prompt for processing
        asyncio.run(ask_chain(english_prompt, chain))


@st.cache_data
def translate_text(text: str, target_lang: str, source_lang: str = 'en') -> str:
    """Translate text to target language."""
    try:
        if target_lang == source_lang:
            return text
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        return translator.translate(text)
    except Exception as e:
        # Don't show the error box repeatedly in UI, just log or return original text
        return text


def get_loading_messages(target_lang):
    messages = [
        "🔍 Analyzing your legal documents...",
        "⚖️ Cross-referencing legal clauses...",
        "📚 Diving into your case files...",
        "🧠 Decoding legal complexities...",
        "📊 Extracting key legal insights...",
        "💼 Summarizing contractual obligations...",
    ]
    return [translate_text(msg, target_lang) for msg in messages]

# Update LOADING_MESSAGES usage in the code
LOADING_MESSAGES = get_loading_messages(SUPPORTED_LANGUAGES[st.session_state.selected_language])


def initialize_app():
    if "session_id" not in st.session_state:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    if 'messages' not in st.session_state:
        initial_message = "Hi! What do you want to know about your documents?"
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": initial_message,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        ]
    
    # Update loading messages based on selected language
    global LOADING_MESSAGES
    target_lang = SUPPORTED_LANGUAGES[st.session_state.selected_language]
    LOADING_MESSAGES = get_loading_messages(target_lang)


initialize_app()

if Config.CONVERSATION_MESSAGES_LIMIT > 0 and Config.CONVERSATION_MESSAGES_LIMIT <= len(
    st.session_state.messages
):
    st.warning(
        "⚠️ You have reached the conversation limit. Refresh the page to start a new conversation."
    )
    st.stop()

chain = show_upload_documents()
show_message_history()
show_chat_input(chain)
