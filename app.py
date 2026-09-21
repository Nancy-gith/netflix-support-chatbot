# ---------------------------------------------------------------------------
# app.py
#
# The Streamlit UI. This file's only job is presentation: show the chat
# history, let the user identify themselves (only once it's actually
# needed), take new input, and hand it off to chatbot.py to do the actual
# work. All state lives in st.session_state, which Streamlit keeps alive
# between reruns (Streamlit reruns this whole script top-to-bottom on every
# interaction — session_state is what survives that).
# ---------------------------------------------------------------------------

import streamlit as st

from chatbot import SYSTEM_PROMPT, get_assistant_reply
from tools import USERS_DB

st.set_page_config(page_title="Netflix Support Bot", page_icon="🎬")

st.title("🎬 Netflix Support Bot")
st.caption(
    "Demo project — fake sample data only, not affiliated with or using real Netflix data."
)

PLACEHOLDER = "Select a customer to begin..."


def _greeting_message(user):
    """A friendly, templated greeting shown the moment a customer becomes
    identified — the first time, and again every time the sidebar
    selection changes. This is plain Python string formatting, not a
    model call: it's instant, free, and always says exactly what we want
    it to say."""
    first_name = user["name"].split()[0]
    return {
        "role": "assistant",
        "content": f"Hi {first_name}! 👋 I'm your Netflix support assistant. How can I help you today?",
    }


# ---- Session state ------------------------------------------------------
# Initialized once per browser session.
# - messages: the whole conversation, sent to the model on every turn —
#   this list IS the chat's memory (see chatbot.py for how it's used).
# - active_user_id: who's identified right now. Starts as None — the chat
#   is usable right away for general questions with no one identified.
# - needs_identification: set to True the moment the chatbot actually
#   needs to know who's asking (see the chat_input handling below), so
#   the sidebar can make the name picker impossible to miss.
# - greeted_user_id: tracks who's already been greeted, so the "Hi
#   <name>!" message only fires once per identification, not every rerun.
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.active_user_id = None
    st.session_state.needs_identification = False
    st.session_state.greeted_user_id = None

# ---- Sidebar: identify yourself (only required once it matters) -----------
# The name picker is always present — that's what makes switching to a
# different customer mid-conversation possible later — but nothing forces
# you to use it until the chatbot actually needs to know who you are. Until
# then it's just an optional control with a low-key caption underneath it.
with st.sidebar:
    st.subheader("Your account")

    sorted_users = sorted(USERS_DB.items(), key=lambda item: item[1]["name"])
    label_to_id = {
        f"{info['name']} — {info['plan']} ({user_id})": user_id
        for user_id, info in sorted_users
    }

    if st.session_state.active_user_id:
        active_user = USERS_DB[st.session_state.active_user_id]
        st.caption(
            f"Chatting as **{active_user['name']}** ({st.session_state.active_user_id}) · "
            f"{active_user['plan']} · next billing {active_user['billing_date']}"
        )
    elif st.session_state.needs_identification:
        st.warning("To look that up, please select your name below.")
    else:
        st.caption(
            "You can start chatting right away for general questions. "
            "If you ask about your specific plan or billing, I'll ask you "
            "to select your name here."
        )

    selected_label = st.selectbox(
        "Search or select your name",
        options=[PLACEHOLDER] + list(label_to_id.keys()),
        index=0,
        key="active_user_label",
    )
    st.session_state.active_user_id = label_to_id.get(selected_label)
    if st.session_state.active_user_id:
        st.session_state.needs_identification = False

    st.divider()

    if st.button("Reset conversation"):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.greeted_user_id = None
        st.session_state.needs_identification = False
        st.rerun()

# ---- Greet the active customer -----------------------------------------
# Fires once whenever active_user_id changes to a real value — including
# the first time anyone is ever identified. Nothing is greeted while
# active_user_id is still None, since general chat doesn't require anyone
# to be identified at all.
if (
    st.session_state.active_user_id
    and st.session_state.active_user_id != st.session_state.greeted_user_id
):
    active_user = USERS_DB[st.session_state.active_user_id]
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
# Available immediately, with no identification required — general
# questions (plans, cancelling, payment methods, refunds, recommendations)
# work with active_user_id still set to None.
user_input = st.chat_input("Ask about plans, billing, or get a recommendation...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            st.session_state.messages, reply_text, needs_identification = get_assistant_reply(
                st.session_state.messages,
                active_user_id=st.session_state.active_user_id,
            )
        st.markdown(reply_text)

    if needs_identification:
        # Rerun so the sidebar's warning shows up immediately, right after
        # this reply, instead of waiting for the next interaction.
        st.session_state.needs_identification = True
        st.rerun()
