"""
Genetics Study Assistant — Streamlit app entry point.

A mobile-first study tool for graduate genetic counseling students.
Supports Q&A and essay drafting modes backed by Google Drive documents
and the Claude claude-sonnet-4-20250514 model.
"""

import streamlit as st
import streamlit.components.v1 as components

# ── Page config must be first Streamlit call ──────────────────────────────────
st.set_page_config(
    page_title="Genetics Study Assistant",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Internal imports ──────────────────────────────────────────────────────────
from utils.auth import check_password
from utils.drive import (
    build_auth_url,
    handle_oauth_callback,
    get_access_token,
    get_default_folder,
    list_drive_items,
    fetch_pdf_content,
    fetch_gdoc_content,
)
from utils.chunker import chunks_from_pdf, chunks_from_gdoc, Chunk
from utils.retriever import get_context_chunks, format_context_for_prompt
from utils.claude import stream_response, QA_USER_TEMPLATE, ESSAY_USER_TEMPLATE

# ── Mobile-first CSS ──────────────────────────────────────────────────────────
MOBILE_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"] { font-size: 16px; }

[data-testid="stSidebar"] { min-width: 280px; max-width: 340px; }

/* Thumb-friendly buttons */
button[kind="primary"], button[kind="secondary"] {
    min-height: 48px;
    font-size: 1rem;
    padding: 0.6rem 1.2rem;
}

/* Chat bubbles */
.chat-bubble-user {
    background: #1a73e8;
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 0.75rem 1rem;
    margin: 0.4rem 0 0.4rem 2rem;
    word-wrap: break-word;
    white-space: pre-wrap;
}
.chat-bubble-assistant {
    background: #f1f3f4;
    color: #202124;
    border-radius: 18px 18px 18px 4px;
    padding: 0.75rem 1rem;
    margin: 0.4rem 2rem 0.4rem 0;
    word-wrap: break-word;
}
.chat-sources {
    font-size: 0.78rem;
    color: #5f6368;
    margin: 0.1rem 2rem 0.6rem 0;
    padding-left: 1rem;
}

[data-testid="stTextArea"] textarea { font-size: 1rem; min-height: 90px; }

/* Mobile */
@media (max-width: 768px) {
    [data-testid="stSidebar"] { min-width: 100vw; }
    .chat-bubble-user  { margin-left: 0.5rem; }
    .chat-bubble-assistant { margin-right: 0.5rem; }
}

/* Mode badges */
.mode-badge-qa {
    display: inline-block; background: #1a73e8; color: white;
    border-radius: 12px; padding: 2px 10px;
    font-size: 0.8rem; font-weight: 600;
}
.mode-badge-essay {
    display: inline-block; background: #34a853; color: white;
    border-radius: 12px; padding: 2px 10px;
    font-size: 0.8rem; font-weight: 600;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────────────────────────────────────

def _init_session():
    defaults = {
        "authenticated": False,
        "google_tokens": None,
        "loaded_chunks": [],
        "loaded_file_names": [],
        "mode": "qa",
        "conversation_history": [],
        "current_folder_id": "root",
        "folder_breadcrumbs": [("root", "My Drive")],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_session()

# ─────────────────────────────────────────────────────────────────────────────
# Helper: load documents from Drive into session state
# ─────────────────────────────────────────────────────────────────────────────

def _load_documents(selected_ids: list[tuple[str, str, str]]):
    """Fetch and chunk documents from Drive, adding to session state."""
    if not selected_ids:
        return

    existing_names = set(st.session_state["loaded_file_names"])
    new_chunks: list[Chunk] = []
    new_names: list[str] = []

    with st.spinner("Loading documents..."):
        for file_id, name, mime_type in selected_ids:
            if name in existing_names:
                continue

            if mime_type == "application/pdf":
                pdf_bytes = fetch_pdf_content(file_id)
                if pdf_bytes:
                    doc_chunks = chunks_from_pdf(pdf_bytes, source_name=name)
                    new_chunks.extend(doc_chunks)
                    new_names.append(name)

            elif mime_type == "application/vnd.google-apps.document":
                raw_text = fetch_gdoc_content(file_id)
                if raw_text:
                    doc_chunks = chunks_from_gdoc(raw_text, source_name=name)
                    new_chunks.extend(doc_chunks)
                    new_names.append(name)

    if new_names:
        st.session_state["loaded_chunks"].extend(new_chunks)
        st.session_state["loaded_file_names"].extend(new_names)
        st.success(f"Loaded {len(new_names)} document(s) — {len(new_chunks)} new chunks.")
        st.rerun()
    else:
        st.info("No new documents were loaded.")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Handle Google OAuth callback FIRST — before password gate so the ?code=
#    is exchanged even on a fresh session load after OAuth redirect
# ─────────────────────────────────────────────────────────────────────────────
handle_oauth_callback()

# ─────────────────────────────────────────────────────────────────────────────
# 2. Password gate
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

if not check_password():
    st.stop()

# Evaluate connection state once; used in both sidebar and main area
is_connected = get_access_token() is not None

# ─────────────────────────────────────────────────────────────────────────────
# 3. Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Genetics Study Assistant")
    st.divider()

    # ── Google Drive auth status ──────────────────────────────────────────
    st.markdown("### Google Drive")

    if is_connected:
        st.success("Connected", icon="✅")
        if st.button("Disconnect", use_container_width=True):
            st.session_state.pop("google_tokens", None)
            st.session_state["loaded_chunks"] = []
            st.session_state["loaded_file_names"] = []
            st.rerun()
    else:
        st.info("Not connected")
        auth_url = build_auth_url()
        # Temporary debug — shows the redirect URI being sent to Google
        from utils.drive import get_redirect_uri
        st.caption(f"Redirect URI: `{get_redirect_uri()}`")
        st.markdown(
            f'<a href="{auth_url}" target="_top" style="display:block;text-align:center;'
            'padding:12px;background:#1a73e8;color:white;border-radius:8px;'
            'text-decoration:none;font-size:1rem;font-weight:600;">'
            "Connect Google Drive</a>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── File / folder browser ─────────────────────────────────────────────
    if is_connected:
        st.markdown("### Browse Documents")

        breadcrumbs = st.session_state["folder_breadcrumbs"]
        bc_path = " / ".join(name for _, name in breadcrumbs)
        st.caption(f"📁 {bc_path}")

        # Quick-jump buttons when at root
        if len(breadcrumbs) == 1:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("My Drive", use_container_width=True):
                    st.session_state["folder_breadcrumbs"] = [("root", "My Drive")]
                    st.session_state["current_folder_id"] = "root"
                    st.rerun()
            with col2:
                if st.button("Shared with me", use_container_width=True):
                    st.session_state["folder_breadcrumbs"] = [("sharedWithMe", "Shared with me")]
                    st.session_state["current_folder_id"] = "sharedWithMe"
                    st.rerun()

        if len(breadcrumbs) > 1:
            if st.button("⬆ Up one level", use_container_width=True):
                st.session_state["folder_breadcrumbs"].pop()
                st.session_state["current_folder_id"] = st.session_state["folder_breadcrumbs"][-1][0]
                st.rerun()

        folder_id = st.session_state["current_folder_id"]
        drive_data = list_drive_items(folder_id)
        items = drive_data["items"]

        if not items:
            st.caption("No supported files found in this folder.")
        else:
            folders = [i for i in items if i["mimeType"] == "application/vnd.google-apps.folder"]
            files = [i for i in items if i["mimeType"] != "application/vnd.google-apps.folder"]

            for folder in folders:
                if st.button(f"📂 {folder['name']}", key=f"folder_{folder['id']}", use_container_width=True):
                    st.session_state["folder_breadcrumbs"].append((folder["id"], folder["name"]))
                    st.session_state["current_folder_id"] = folder["id"]
                    st.rerun()

            if files:
                st.markdown("**Select files to load:**")
                selected_ids = []
                for f in files:
                    icon = "📄" if f["mimeType"] == "application/pdf" else "📝"
                    already_loaded = f["name"] in st.session_state["loaded_file_names"]
                    label = f"{icon} {f['name']}" + (" ✓" if already_loaded else "")
                    if st.checkbox(label, key=f"file_{f['id']}", value=already_loaded):
                        selected_ids.append((f["id"], f["name"], f["mimeType"]))

                if st.button("Load selected documents", type="primary", use_container_width=True):
                    _load_documents(selected_ids)

    st.divider()

    # ── Mode toggle ───────────────────────────────────────────────────────
    st.markdown("### Mode")
    mode_options = {"Q&A": "qa", "Essay / Response Drafting": "essay"}
    selected_mode_label = st.radio(
        "Select mode",
        list(mode_options.keys()),
        index=0 if st.session_state["mode"] == "qa" else 1,
        label_visibility="collapsed",
    )
    st.session_state["mode"] = mode_options[selected_mode_label]

    st.divider()

    # ── Loaded documents summary ──────────────────────────────────────────
    loaded_names = st.session_state["loaded_file_names"]
    chunk_count = len(st.session_state["loaded_chunks"])
    if loaded_names:
        st.markdown(f"### Loaded Documents ({chunk_count} chunks)")
        for name in loaded_names:
            st.caption(f"• {name}")
        if st.button("Clear all documents", use_container_width=True):
            st.session_state["loaded_chunks"] = []
            st.session_state["loaded_file_names"] = []
            st.rerun()
    else:
        st.caption("No documents loaded yet.")

    st.divider()
    if st.button("Clear conversation", use_container_width=True):
        st.session_state["conversation_history"] = []
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main chat interface
# ─────────────────────────────────────────────────────────────────────────────

mode = st.session_state["mode"]
mode_badge = (
    '<span class="mode-badge-qa">Q&A Mode</span>'
    if mode == "qa"
    else '<span class="mode-badge-essay">Essay / Drafting Mode</span>'
)
st.markdown(f"# Genetics Study Assistant &nbsp; {mode_badge}", unsafe_allow_html=True)

all_chunks: list[Chunk] = st.session_state["loaded_chunks"]
no_docs = len(all_chunks) == 0

if no_docs and not is_connected:
    st.info(
        "**Get started:** Connect your Google Drive in the sidebar to load study materials. "
        "You can also ask questions without documents — Claude will answer from its training knowledge."
    )
elif no_docs:
    st.info(
        "No documents loaded yet. Browse and select files in the sidebar, "
        "or ask a question and Claude will answer from its training knowledge."
    )

# ── Render conversation history ───────────────────────────────────────────────
for entry in st.session_state["conversation_history"]:
    if entry["role"] == "user":
        st.markdown(
            f'<div class="chat-bubble-user">{entry["display"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        # Assistant messages: render markdown inside a container for proper formatting
        with st.container():
            st.markdown(entry["display"])
        if entry.get("sources"):
            sources_html = "<br>".join(f"• {s}" for s in entry["sources"])
            st.markdown(
                f'<div class="chat-sources"><strong>Sources used:</strong><br>{sources_html}</div>',
                unsafe_allow_html=True,
            )

# ── Input area ────────────────────────────────────────────────────────────────
st.divider()

if mode == "qa":
    placeholder_text = "e.g. 'Explain the two-hit hypothesis in tumor suppressor genes...'"
    submit_label = "Ask"
    input_label = "Your question"
else:
    placeholder_text = "e.g. 'Discuss the ethical considerations of expanded carrier screening...'"
    submit_label = "Draft Response"
    input_label = "Essay prompt"

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area(
        input_label,
        placeholder=placeholder_text,
        height=100,
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)

if submitted and user_input.strip():
    query = user_input.strip()

    # Add user message to history
    st.session_state["conversation_history"].append(
        {"role": "user", "display": query}
    )

    # Retrieve relevant chunks and build context
    ranked = get_context_chunks(query, all_chunks, mode=mode)
    context_str = format_context_for_prompt(ranked)
    source_citations = [chunk.citation for chunk, score in ranked if score > 0.0]

    # Build full user message with injected context
    if mode == "qa":
        full_user_msg = QA_USER_TEMPLATE.format(question=query, context=context_str)
    else:
        full_user_msg = ESSAY_USER_TEMPLATE.format(prompt=query, context=context_str)

    # Build API history from prior turns (exclude the just-added user message)
    api_history = [
        {"role": e["role"], "content": e.get("api_content", e["display"])}
        for e in st.session_state["conversation_history"][:-1]
    ]

    # Stream response into the main area
    response_text = stream_response(full_user_msg, api_history)

    # Persist the full user message (with context) for API continuity
    st.session_state["conversation_history"][-1]["api_content"] = full_user_msg

    # Add assistant response
    st.session_state["conversation_history"].append(
        {
            "role": "assistant",
            "display": response_text,
            "api_content": response_text,
            "sources": source_citations,
        }
    )
    st.rerun()
