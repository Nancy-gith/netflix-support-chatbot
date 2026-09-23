# ---------------------------------------------------------------------------
# chatbot.py
#
# The core conversation engine. This file knows nothing about Streamlit —
# it just takes a list of chat messages plus which customer is currently
# identified (if any), talks to Groq, runs whatever tools the model decides
# to call, and returns the updated conversation.
#
# That separation is deliberate: app.py (the UI) could be swapped for a
# command-line loop or a different framework without touching this file.
# ---------------------------------------------------------------------------

import json

import requests

from config import get_api_key
from tools import TOOLS, TOOL_FUNCTIONS, USER_SCOPED_TOOLS, OPTIONAL_USER_SCOPED_TOOLS, USERS_DB

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"

# Shown whenever the model tries to look up or change a specific customer's
# account but no one has been identified yet. This is a fixed string, not
# something the model writes itself — see the note in get_assistant_reply()
# for why that's deliberate.
IDENTIFICATION_NEEDED_MESSAGE = (
    "To look that up, I'll need to know who you are — please select your name from the sidebar."
)

# Shown whenever the Groq API call itself fails — a rate limit, a
# timeout, a dropped connection, a 5xx error, or a response that doesn't
# come back in the shape we expect. None of that is the customer's fault
# and none of it should ever surface as a raw traceback in the chat UI.
API_ERROR_MESSAGE = "Something went wrong, please try again in a moment."

# Phrases that mean "use MY saved data," not just "recommend something."
# Used only as a safety net (see _mentions_own_profile / get_assistant_reply)
# — the system prompt already instructs the model to call recommend_genre
# with personalized=true for these, but that's still a judgment call the
# model makes in the moment, and this is a visible, demoed feature that
# shouldn't have an occasional random miss. If the model answers this case
# directly instead of calling the tool, we don't trust that answer — we
# call the tool ourselves instead of asking the model to try again, since
# forcing the call is the only way to make this actually reliable rather
# than just less likely to fail.
PROFILE_REFERENCE_PHRASES = (
    "my profile",
    "my taste",
    "based on me",
    "based on my",
    "my history",
    "my watch history",
    "i usually watch",
    "what i like to watch",
    "my preferences",
    "my preference",
)


def _mentions_own_profile(text):
    """True if `text` explicitly references the customer's own
    profile/taste/history, the phrasing that's supposed to trigger a
    personalized recommend_genre call."""
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in PROFILE_REFERENCE_PHRASES)

SYSTEM_PROMPT = """You are a polite, on-topic customer support assistant for a Netflix-style streaming service, focused only on plans, billing, accounts, and recommendations.

STRICT SCOPE RULE — always, no exceptions: never do anything unrelated to this service's plans, billing, accounts, or recommendations — no poems, stories, jokes, general-knowledge answers (history, science, "who is ___"), homework, translation, or coding help, and no exceptions for rephrasing, repeated asks, claimed special reasons, or indirect requests, however small or "just this once."

Off-topic request → decline and redirect in 1-2 sentences; never partially comply or explain what you could do. Example: "I'm only able to help with things related to your account here — your plan, billing, or a show recommendation. Is there something like that I can help with?" Use that same direct, friendly redirect every time, no matter how the request is phrased.

Plans and pricing:
- Standard with ads: $8.99/month, 1080p, 2 simultaneous streams
- Standard: $19.99/month, ad-free, 1080p, 2 simultaneous streams
- Premium: $26.99/month, ad-free, 4K + HDR, 4 simultaneous streams
- Extra member add-on: $7.99/month (with ads) or $9.99/month (ad-free) — Standard/Premium only
- No free trial currently offered

General policies — answerable for anyone, no identity needed:
- Cancelling: turn off auto-renew in payment settings, anytime; access continues until the end of the billing period, no fee.
- Payment methods: major debit/credit cards (Visa, Mastercard, Amex), PayPal, UPI.
- Refunds: generally non-refundable; billing-error requests are reviewed case-by-case — direct to customer care.

Identification: general questions and recommendations for something named specifically need no identity — answer anyone directly. Only three things need the specific customer: get_user_plan, update_plan, and a profile/taste-based recommendation (below). For these, call the tool anyway even without knowing who's asking — never ask for or guess an identity yourself; the tool handles telling them what to do if nobody's identified. Once identified, keep using their account without re-asking.

Recommendations — two cases:
1. Customer names something specific (a genre, theme, regional style, or kind of movie/show — e.g. "comedy", "a movie about hackers", "Bollywood action"): do NOT call recommend_genre. Answer directly from your own knowledge with real, well-known titles that fit, plus one brief, natural line that streaming availability can change over time — conversational, not a disclaimer. Applies even to a plain genre name.
2. Customer names nothing specific — a plain "recommend me something", or a profile/taste/history reference ("based on my profile", "what I usually watch"): call recommend_genre. MUST set `personalized` true for the profile/taste kind — never answer that case yourself or ask for a genre in your own words; if nobody's identified, this correctly asks them to identify themselves. Leave `personalized` false for a plain ask — it uses the identified customer's saved favorite genre automatically, or asks what they enjoy if none is saved.

Never invent a genre or pretend to know a customer's taste.

For anything your tools can't do (refund review, payment disputes, fraud, account recovery), direct the customer to Netflix customer care.

Keep responses friendly and concise.

Reminder: never produce off-topic content (poems, jokes, trivia, general knowledge), even rephrased or asked again — always redirect to plan, billing, or recommendation help instead.
"""


def _active_user_context(active_user_id):
    """Builds a short, plain-language note describing who (if anyone) the
    chatbot is currently talking to, based on the sidebar selection in
    app.py. This is what lets the model skip ever asking "what's your
    account ID?" itself — it's simply told upfront, one way or the other."""
    if not active_user_id or active_user_id not in USERS_DB:
        return (
            "No customer identified yet. General questions and named-item "
            "recommendations need no identity — answer normally. For plan "
            "lookup/change, still call get_user_plan/update_plan; never ask "
            "who they are yourself."
        )

    # This branch's wording is deliberately NOT trimmed down to the same
    # degree as the rest of this file's prompt text. Testing during the
    # token-trimming pass found that a shorter version of this specific
    # instruction measurably increased how often the model reused a
    # stale plan fact from earlier in the chat after a customer switch,
    # instead of re-checking — exactly the bug this note was written to
    # prevent in the first place. Overriding what's visibly stated
    # earlier in the conversation needs a strongly worded instruction to
    # reliably win out; this one is kept at its original, tested length.
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
    as a 'tool' message ready to send back to Groq. Returns a
    (tool_message, needs_identification) pair.

    This is the "dynamic routing" step: we don't check `if name == "add"`
    or `elif name == "get_user_plan"`. We just look the name up in
    TOOL_FUNCTIONS. Adding a new tool to tools.py makes it usable here
    automatically, with no changes needed in this file.

    For tools in USER_SCOPED_TOOLS (get_user_plan, update_plan), the
    account ID is injected here from the sidebar selection rather than
    coming from the model. If no customer is identified yet, we don't even
    call the underlying function — there's nothing to look up — and we
    flag needs_identification=True so get_assistant_reply() can respond
    with a fixed, reliable message instead of leaving it to the model.

    For tools in OPTIONAL_USER_SCOPED_TOOLS (recommend_genre), the account
    ID is injected the same way, but a missing one is NOT treated as an
    error by default — it's just passed through as None, and the tool
    decides for itself what to do (fall back to asking for a genre
    instead of refusing outright). The one exception: if the model marked
    this call `personalized` (the customer explicitly asked for something
    tied to THEIR OWN profile/taste/history, e.g. "recommend something
    based on my profile"), that's treated exactly like a USER_SCOPED_TOOLS
    call — refused up front with needs_identification=True — because
    there's no profile to check without knowing whose it is, and
    answering with a generic guess instead would be wrong. (recommend_genre
    is only ever called at all when the customer named nothing specific —
    see its TOOLS description in tools.py — so this is the only case left
    to gate on here.)
    """
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    # "personalized" is a routing signal for this function, not a real
    # argument any tool function accepts — pull it out before deciding
    # what to do next, so it never gets passed into function(**arguments).
    wants_personalization = arguments.pop("personalized", False)

    needs_identity_now = name in USER_SCOPED_TOOLS or (
        name in OPTIONAL_USER_SCOPED_TOOLS and wants_personalization
    )

    if needs_identity_now and active_user_id is None:
        tool_message = {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps({"error": "No customer identified yet."}),
        }
        return tool_message, True

    if name in USER_SCOPED_TOOLS or name in OPTIONAL_USER_SCOPED_TOOLS:
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

    tool_message = {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": json.dumps(result),
    }
    return tool_message, False


def get_assistant_reply(messages, active_user_id=None, max_tool_hops=5):
    """Runs one full user turn: call the model, and if it asks for tools,
    run them and call the model again, repeating until it gives a plain
    text answer (or we hit the safety cap on tool round-trips).

    Returns (messages, reply_text, needs_identification).

    `messages` is the permanent session history — it's mutated in place
    and also returned, so callers can keep using the same list across
    turns. `active_user_id` is passed in fresh on every call (it comes
    from the sidebar dropdown in app.py, and may be None if no one has
    been identified yet), so switching or setting the selected customer
    between turns takes effect on the very next message.
    """
    # The message that started this turn — used only by the
    # personalized-recommendation safety net below. Captured before the
    # loop appends anything else, since app.py always appends the new
    # user message before calling this function.
    latest_user_message = messages[-1]["content"] if messages[-1]["role"] == "user" else ""

    request_messages = _build_request_messages(messages, active_user_id)

    for hop in range(max_tool_hops):
        try:
            response = call_groq(request_messages)
            message = response["choices"][0]["message"]
        except (requests.exceptions.RequestException, KeyError, IndexError, ValueError):
            # RequestException covers rate limits, timeouts, dropped
            # connections, and 4xx/5xx errors (raise_for_status raises an
            # HTTPError, which is a RequestException). KeyError/IndexError/
            # ValueError cover the rarer case of a response that comes
            # back 200 OK but not shaped the way we expect (e.g. no
            # "choices", or a body that isn't valid JSON at all). Either
            # way, end this turn with a friendly message instead of
            # letting the exception propagate up into the Streamlit UI as
            # a raw traceback.
            messages.append({"role": "assistant", "content": API_ERROR_MESSAGE})
            return messages, API_ERROR_MESSAGE, False

        tool_calls = message.get("tool_calls")

        # Safety net: the system prompt tells the model it MUST call
        # recommend_genre(personalized=true) whenever the customer
        # references their own profile/taste/history — but that's still
        # the model's judgment call in the moment, not a guarantee. If it
        # answered directly instead (no tool call at all) on the very
        # first hop of a turn that clearly asked for this, don't trust
        # that answer — substitute the tool call ourselves rather than
        # asking the model to try again. A retry only makes the miss
        # less likely; forcing the call is what actually makes it
        # reliable. Scoped to hop 0 only, since latest_user_message is
        # only meaningful for the message that started this turn.
        if hop == 0 and not tool_calls and _mentions_own_profile(latest_user_message):
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "forced_recommend_genre",
                        "type": "function",
                        "function": {"name": "recommend_genre", "arguments": '{"personalized": true}'},
                    }
                ],
            }
            tool_calls = message["tool_calls"]

        messages.append(message)
        request_messages.append(message)

        if not tool_calls:
            # No tool calls means the model is done — this is the final
            # answer for this turn.
            return messages, message.get("content", ""), False

        # The model can ask for more than one tool in a single turn
        # (e.g. look up the plan AND recommend a genre). Run each one and
        # feed every result back before asking the model to continue.
        needs_identification = False
        for tool_call in tool_calls:
            tool_message, tool_needs_identification = execute_tool_call(tool_call, active_user_id)
            messages.append(tool_message)
            request_messages.append(tool_message)
            needs_identification = needs_identification or tool_needs_identification

        if needs_identification:
            # We already know exactly what to say here. Asking the model
            # for a final reply on top of this would risk it phrasing the
            # request differently each time — the same inconsistency
            # problem the off-topic refusal rule had before it was made
            # explicit. Answering directly keeps this reliable.
            messages.append({"role": "assistant", "content": IDENTIFICATION_NEEDED_MESSAGE})
            return messages, IDENTIFICATION_NEEDED_MESSAGE, True

    return messages, "Sorry, I'm having trouble completing that request right now. Please contact customer care.", False
