# ---------------------------------------------------------------------------
# app.py
#
# The Streamlit UI. This file's only job is presentation: show the chat
# history, let the user pick which customer they're chatting as, take new
# input, and hand it off to chatbot.py to do the actual work. All state
# lives in st.session_state, which Streamlit keeps alive between reruns
# (Streamlit reruns this whole script top-to-bottom on every interaction —
# session_state is what survives that).
# ---------------------------------------------------------------------------

import streamlit as st

from chatbot import SYSTEM_PROMPT, get_assistant_reply
from tools import USERS_DB

st.set_page_config(page_title="Netflix Support Bot", page_icon="🎬")

st.title("🎬 Netflix Support Bot")
st.caption(
    "Demo project — fake sample data only, not affiliated with or using real Netflix data."
)


def _greeting_message(user):
    """A friendly, templated greeting shown the moment a customer becomes
    active — on first load, and again every time the sidebar selection
    changes. This is plain Python string formatting, not a model call: it's
    instant, free, and always says exactly what we want it to say."""
    first_name = user["name"].split()[0]
    return {
        "role": "assistant",
        "content": f"Hi {first_name}! 👋 I'm your Netflix support assistant. How can I help you today?",
    }


# ---- Conversation history ----------------------------------------------
# Initialized once per browser session. Every user and assistant message
# from here on gets appended to this same list, which is what makes this a
# real multi-turn conversation instead of a one-shot Q&A: the model sees
# the full history on every request, not just the latest message.
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # No one has been greeted yet — the check further down will fire once
    # the sidebar below determines the initial active customer.
    st.session_state.greeted_user_id = None

# ---- Sidebar: pick which customer you're chatting as ----------------------
# This replaces asking the customer to type their account ID into the chat.
# Instead, the sidebar lists every sample customer by name; whichever one is
# selected becomes the "active" account for every tool call the model makes
# (see chatbot._active_user_context and chatbot.execute_tool_call), until a
# different name is picked.
with st.sidebar:
    st.subheader("You're chatting as")

    # {"Aditi Sharma — Premium (U101)": "U101", ...}, sorted by name so the
    # dropdown is browsable/searchable alphabetically. st.selectbox already
    # supports typing to jump/filter within its options, so no extra
    # search widget or library is needed for a list this size.
    sorted_users = sorted(USERS_DB.items(), key=lambda item: item[1]["name"])
    label_to_id = {
        f"{info['name']} — {info['plan']} ({user_id})": user_id
        for user_id, info in sorted_users
    }

    selected_label = st.selectbox(
        "Search or select a customer",
        options=list(label_to_id.keys()),
        key="active_user_label",
    )
    st.session_state.active_user_id = label_to_id[selected_label]

    active_user = USERS_DB[st.session_state.active_user_id]
    st.caption(
        f"Account **{st.session_state.active_user_id}** · "
        f"{active_user['plan']} · next billing {active_user['billing_date']}"
    )

    st.divider()

    if st.button("Reset conversation"):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.greeted_user_id = None
        st.rerun()

# ---- Greet the active customer -----------------------------------------
# Fires once whenever active_user_id changes — including the very first
# run, since greeted_user_id starts as None. This is what makes a mid-chat
# switch visible IN the chat itself ("Hi Rahul!") instead of only showing
# up as a quiet change in the sidebar.
if st.session_state.active_user_id != st.session_state.greeted_user_id:
    st.session_state.messages.append(_greeting_message(active_user))
    st.session_state.greeted_user_id = st.session_state.active_user_id

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
                st.session_state.messages,
                active_user_id=st.session_state.active_user_id,
            )
        st.markdown(reply_text)
