# ---------------------------------------------------------------------------
# chatbot.py
#
# The core conversation engine. This file knows nothing about Streamlit —
# it just takes a list of chat messages, talks to Groq, runs whatever tools
# the model decides to call, and returns the updated conversation.
#
# That separation is deliberate: app.py (the UI) could be swapped for a
# command-line loop or a different framework without touching this file.
# ---------------------------------------------------------------------------

import json

import requests

from config import get_api_key
from tools import TOOLS, TOOL_FUNCTIONS

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are a polite, on-topic customer support assistant for a Netflix-style streaming service. Stay focused on topics related to the service: plans, billing, accounts, and content recommendations.

Plans and pricing:
- Standard with ads: $8.99/month, 1080p, 2 simultaneous streams
- Standard: $19.99/month, ad-free, 1080p, 2 simultaneous streams
- Premium: $26.99/month, ad-free, 4K + HDR, 4 simultaneous streams
- Extra member add-on: $7.99/month (with ads) or $9.99/month (ad-free) — Standard/Premium only
- No free trial is currently offered. Subscriptions can be cancelled or paused anytime.

You have tools for looking up a user's plan, changing a user's plan, doing billing math, and recommending shows or movies. Use a tool whenever it would give a more accurate answer than guessing — look up the user's real plan instead of assuming it, do billing math with the calculator tool instead of in your head, and only change a plan after the user has clearly confirmed the new plan they want.

If a request needs something none of your tools can do (refunds, payment disputes, fraud, account recovery), tell the user to contact Netflix customer care.

Keep responses friendly and concise. Where it fits naturally, ask what genre the user enjoys so you can recommend something with the recommend_genre tool.
"""


def call_groq(messages):
    """Sends the current conversation (plus the tool list) to Groq and
    returns the parsed JSON response."""
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


def execute_tool_call(tool_call):
    """Runs a single tool call the model asked for and packages the result
    as a 'tool' message ready to send back to Groq.

    This is the "dynamic routing" step: we don't check `if name == "add"`
    or `elif name == "get_user_plan"`. We just look the name up in
    TOOL_FUNCTIONS. Adding a new tool to tools.py makes it usable here
    automatically, with no changes needed in this file.
    """
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

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


def get_assistant_reply(messages, max_tool_hops=5):
    """Runs one full user turn: call the model, and if it asks for tools,
    run them and call the model again, repeating until it gives a plain
    text answer (or we hit the safety cap on tool round-trips).

    `messages` is mutated in place and also returned, along with the final
    reply text, so callers can keep using the same list across turns —
    that running list IS the conversation history.
    """
    for _ in range(max_tool_hops):
        response = call_groq(messages)
        message = response["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # No tool calls means the model is done — this is the final
            # answer for this turn.
            return messages, message.get("content", "")

        # The model can ask for more than one tool in a single turn
        # (e.g. look up the plan AND recommend a genre). Run each one and
        # feed every result back before asking the model to continue.
        for tool_call in tool_calls:
            messages.append(execute_tool_call(tool_call))

    return messages, "Sorry, I'm having trouble completing that request right now. Please contact customer care."
