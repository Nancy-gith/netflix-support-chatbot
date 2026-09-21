# ---------------------------------------------------------------------------
# app.py
#
# The Streamlit UI. This file's only job is presentation: show the chat
# history, take new input, and hand it off to chatbot.py to do the actual
# work. All conversation state lives in st.session_state, which Streamlit
# keeps alive between reruns (Streamlit reruns this whole script top-to-
# bottom on every interaction — session_state is what survives that).
# ---------------------------------------------------------------------------

import streamlit as st

from chatbot import SYSTEM_PROMPT, get_assistant_reply
from tools import USERS_DB

st.set_page_config(page_title="Netflix Support Bot", page_icon="🎬")

st.title("🎬 Netflix Support Bot")
st.caption(
    "Demo project — fake sample data only, not affiliated with or using real Netflix data."
)

# ---- Conversation history ----------------------------------------------
# Initialized once per browser session. Every user and assistant message
# from here on gets appended to this same list, which is what makes this a
# real multi-turn conversation instead of a one-shot Q&A: the model sees
# the full history on every request, not just the latest message.
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# ---- Sidebar: demo helpers ------------------------------------------------
with st.sidebar:
    st.subheader("Sample user IDs")
    st.caption("Try asking about one of these — the data is fake.")
    for user_id, info in USERS_DB.items():
        st.code(f"{user_id} — {info['name']} ({info['plan']})")

    if st.button("Reset conversation"):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

# ---- Render existing history ------------------------------------------
# We skip the system message (internal instructions, not part of the visible
# chat) and skip messages with no content (the intermediate assistant
# message that only contains a tool_calls request, and the raw "tool" role
# messages carrying function results back to the model).
for message in st.session_state.messages:
    if message["role"] in ("user", "assistant") and message.get("content"):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# ---- Handle new input -------------------------------------------------
user_input = st.chat_input("Ask about your plan, billing, or get a recommendation...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            st.session_state.messages, reply_text = get_assistant_reply(
                st.session_state.messages
            )
        st.markdown(reply_text)
