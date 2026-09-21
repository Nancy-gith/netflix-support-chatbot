# ---------------------------------------------------------------------------
# chatbot.py
#
# The core conversation engine. This file knows nothing about Streamlit —
# it just takes a list of chat messages plus which customer is currently
# selected, talks to Groq, runs whatever tools the model decides to call,
# and returns the updated conversation.
#
# That separation is deliberate: app.py (the UI) could be swapped for a
# command-line loop or a different framework without touching this file.
# ---------------------------------------------------------------------------

import json

import requests

from config import get_api_key
from tools import TOOLS, TOOL_FUNCTIONS, USER_SCOPED_TOOLS, USERS_DB

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are a polite, on-topic customer support assistant for a Netflix-style streaming service. Stay focused on topics related to the service: plans, billing, accounts, and content recommendations.

Plans and pricing:
- Standard with ads: $8.99/month, 1080p, 2 simultaneous streams
- Standard: $19.99/month, ad-free, 1080p, 2 simultaneous streams
- Premium: $26.99/month, ad-free, 4K + HDR, 4 simultaneous streams
- Extra member add-on: $7.99/month (with ads) or $9.99/month (ad-free) — Standard/Premium only
- No free trial is currently offered. Subscriptions can be cancelled or paused anytime.

You have tools for looking up the current customer's plan, changing their plan, doing billing math, and recommending shows or movies. The customer's identity is already known from the session (shown to you in a short context note below the conversation) — never ask them for their account ID, and never ask "who am I speaking with." Use a tool whenever it would give a more accurate answer than guessing — look up the customer's real plan instead of assuming it, do billing math with the calculator tool instead of in your head, and only change a plan after the customer has clearly confirmed the new plan they want.

If a request needs something none of your tools can do (refunds, payment disputes, fraud, account recovery), tell the customer to contact Netflix customer care.

Keep responses friendly and concise. Where it fits naturally, ask what genre the customer enjoys so you can recommend something with the recommend_genre tool.
"""


def _active_user_context(active_user_id):
    """Builds a short, plain-language note describing who the chatbot is
    currently talking to, based on the sidebar selection in app.py. This
    is what lets the model skip ever asking "what's your account ID?" —
    it's simply told upfront."""
    if not active_user_id or active_user_id not in USERS_DB:
        return (
            "No customer is currently selected in the sidebar. If the "
            "request needs an account (plan lookup or plan change), ask "
            "the customer to select their name from the sidebar first."
        )

    user = USERS_DB[active_user_id]
    return (
        f"You are currently assisting {user['name']} (account ID {active_user_id}), "
        f"currently on the {user['plan']} plan. Automatically use this account for "
        "get_user_plan and update_plan — those tools don't take an account ID "
        "argument because you already know who you're talking to. This note "
        "always reflects who you're ACTUALLY talking to right now, even if the "
        "customer was switched partway through this conversation — if anything "
        "said earlier in the chat (a name or a plan) conflicts with this note, "
        "this note is correct and the earlier statement is about a different, "
        "previous customer. Call get_user_plan again rather than reusing an "
        "earlier turn's answer whenever you're not sure it's still current."
    )


def _build_request_messages(messages, active_user_id):
    """Returns a copy of the conversation to send to Groq, with the active
    customer's identity folded into the system message. The stored
    session history (`messages`) is left untouched, so switching customers
    mid-conversation only affects requests from that point on — it doesn't
    rewrite earlier turns."""
    system_with_context = {
        "role": "system",
        "content": messages[0]["content"] + "\n\n" + _active_user_context(active_user_id),
    }
    return [system_with_context] + messages[1:]


def call_groq(messages):
    """Sends a conversation (plus the tool list) to Groq and returns the
    parsed JSON response."""
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
    }
    response = requests.post(GROQ_URL, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


def execute_tool_call(tool_call, active_user_id):
    """Runs a single tool call the model asked for and packages the result
    as a 'tool' message ready to send back to Groq.

    This is the "dynamic routing" step: we don't check `if name == "add"`
    or `elif name == "get_user_plan"`. We just look the name up in
    TOOL_FUNCTIONS. Adding a new tool to tools.py makes it usable here
    automatically, with no changes needed in this file.

    For tools in USER_SCOPED_TOOLS (get_user_plan, update_plan), the
    account ID is injected here from the sidebar selection rather than
    coming from the model — the model was never given a user_id parameter
    to fill in for these tools in the first place.
    """
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    if name in USER_SCOPED_TOOLS:
        arguments["user_id"] = active_user_id

    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        result = {"error": f"Unknown tool requested by model: {name}"}
    else:
        try:
            result = function(**arguments)
        except Exception as exc:
            # A malformed argument shouldn't crash the app — hand the
            # error back to the model so it can recover or apologize.
            result = {"error": str(exc)}

    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": json.dumps(result),
    }


def get_assistant_reply(messages, active_user_id=None, max_tool_hops=5):
    """Runs one full user turn: call the model, and if it asks for tools,
    run them and call the model again, repeating until it gives a plain
    text answer (or we hit the safety cap on tool round-trips).

    `messages` is the permanent session history — it's mutated in place
    and also returned, so callers can keep using the same list across
    turns. `active_user_id` is passed in fresh on every call (it comes
    from the sidebar dropdown in app.py), so switching the selected
    customer between turns takes effect on the very next message.
    """
    request_messages = _build_request_messages(messages, active_user_id)

    for _ in range(max_tool_hops):
        response = call_groq(request_messages)
        message = response["choices"][0]["message"]
        messages.append(message)
        request_messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # No tool calls means the model is done — this is the final
            # answer for this turn.
            return messages, message.get("content", "")

        # The model can ask for more than one tool in a single turn
        # (e.g. look up the plan AND recommend a genre). Run each one and
        # feed every result back before asking the model to continue.
        for tool_call in tool_calls:
            tool_message = execute_tool_call(tool_call, active_user_id)
            messages.append(tool_message)
            request_messages.append(tool_message)

    return messages, "Sorry, I'm having trouble completing that request right now. Please contact customer care."
