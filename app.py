import os
import sqlite3
import streamlit as st
import ollama

st.set_page_config(page_title="Private Memory Chat", layout="centered")
st.title("Private Phone & PC Memory")

# 1. Connect to local SQLite database
conn = sqlite3.connect("memory.db", check_same_thread=False)

# 2. Initialize chat history in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar controls to check indexed files or clear chat
with st.sidebar:
    st.header("Memory Controls")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    file_count = conn.execute("SELECT COUNT(*) FROM personal_files").fetchone()[0]
    st.caption(f"Indexed files in SQLite: **{file_count}**")

# 3. Render all past messages (text + attached images/PDFs) on every rerun
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        file_path = msg.get("file_path")
        if file_path and os.path.exists(file_path):
            if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                st.image(file_path, caption=os.path.basename(file_path), width=350)
            else:
                with open(file_path, "rb") as f:
                    st.download_button(
                        label=f"Open / Download {os.path.basename(file_path)}",
                        data=f,
                        file_name=os.path.basename(file_path),
                        key=f"dl_{msg['id']}"
                    )

# 4. Handle new user input
query = st.chat_input("Ask about flights, tickets, or photos (e.g., 'photo where I look angry')...")

if query:
    # Append and display user message immediately
    user_msg = {"id": len(st.session_state.messages), "role": "user", "content": query}
    st.session_state.messages.append(user_msg)
    with st.chat_message("user"):
        st.write(query)

    # Fetch indexed files from SQLite
    rows = conn.execute("SELECT id, file_path, summary FROM personal_files").fetchall()

    if not rows:
        reply = "Your memory database is empty. Drop files into `Desktop/TestMemoryFolder` and run `python indexer.py` first."
        matched_path = None
    else:
        # Build local file context
        context = ""
        id_to_path = {}
        for fid, path, summary in rows:
            id_to_path[str(fid)] = path
            context += f"\n[FILE_ID: {fid}] Name: {os.path.basename(path)}\nDetails: {summary}\n---"

        system_prompt = (
            "You are a private, offline personal assistant searching the user's local files. "
            "Use the local file records below and the conversation history to answer accurately. "
            "At the very end of your reply, put `MATCH_ID: <number>` for the single most relevant file "
            "(or `MATCH_ID: NONE` if no file applies).\n\n"
            f"Local File Records:\n{context}"
        )

        # Include recent conversation history so follow-up questions ("What gate is it?") work
        ollama_messages = [{"role": "system", "content": system_prompt}]
        for past in st.session_state.messages[-6:]:
            ollama_messages.append({"role": past["role"], "content": past["content"]})

        with st.spinner("Searching local memory..."):
            response = ollama.chat(
                model="qwen2.5vl:3b",
                messages=ollama_messages,
                options={"num_predict": 200}
            )
            raw_reply = response["message"]["content"]

        # Parse out MATCH_ID so we can attach the actual file
        matched_path = None
        reply = raw_reply
        if "MATCH_ID:" in raw_reply:
            parts = raw_reply.split("MATCH_ID:")
            reply = parts[0].strip()
            match_id = parts[1].strip().split()[0] if len(parts) > 1 and parts[1].strip() else ""
            matched_path = id_to_path.get(match_id)


    # Save assistant message (along with file attachment) to session history
    assistant_msg = {
        "id": len(st.session_state.messages),
        "role": "assistant",
        "content": reply,
        "file_path": matched_path
    }
    st.session_state.messages.append(assistant_msg)

    # Render assistant message now
    with st.chat_message("assistant"):
        st.write(reply)
        if matched_path and os.path.exists(matched_path):
            if matched_path.lower().endswith((".png", ".jpg", ".jpeg")):
                st.image(matched_path, caption=os.path.basename(matched_path), width=350)
            else:
                with open(matched_path, "rb") as f:
                    st.download_button(
                        label=f"Open / Download {os.path.basename(matched_path)}",
                        data=f,
                        file_name=os.path.basename(matched_path),
                        key=f"dl_{assistant_msg['id']}"
                    )
