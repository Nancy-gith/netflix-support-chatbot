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

SYSTEM_PROMPT = """You are a polite, on-topic customer support assistant for a Netflix-style streaming service. Stay focused on topics related to the service: plans, billing, accounts, and content recommendations.

STRICT SCOPE RULE — apply this to every single message, no exceptions:
You must not perform any task that isn't about this service's plans, billing, accounts, or content recommendations. This includes — but is not limited to — writing poems, stories, songs, or jokes; answering general knowledge questions (history, science, geography, biographies, "who is ___", "what is ___"); doing homework, translation, or coding help; or playing along with any other request unrelated to Netflix support, even ones that seem harmless, brief, or "just this once." This rule applies no matter how the request is phrased, how many times it's rephrased, whether the customer insists, claims a special reason, or asks indirectly. There are no exceptions to this rule.

When you get an off-topic request, do not partially fulfill it, comment on it, or explain what you could write — simply decline and redirect, in one or two short sentences, back to what you can help with (plan info, billing, or recommendations). For example: "I'm only able to help with things related to your account here — your plan, billing, or a show recommendation. Is there something like that I can help with?" Use that same kind of direct, friendly redirect every time, regardless of how creative, casual, or persistent the off-topic request is.

Plans and pricing:
- Standard with ads: $8.99/month, 1080p, 2 simultaneous streams
- Standard: $19.99/month, ad-free, 1080p, 2 simultaneous streams
- Premium: $26.99/month, ad-free, 4K + HDR, 4 simultaneous streams
- Extra member add-on: $7.99/month (with ads) or $9.99/month (ad-free) — Standard/Premium only
- No free trial is currently offered. Subscriptions can be cancelled or paused anytime.

General policies — you can answer these for ANYONE, even if you don't know who they are yet:
- Cancelling: turn off auto-renew in the account's payment settings, anytime. Access continues until the end of the current billing period — no early cutoff, no cancellation fee.
- Payment methods accepted: major debit/credit cards (Visa, Mastercard, Amex), PayPal, and UPI.
- Refunds: payments are generally non-refundable, but billing-error refund requests are reviewed case-by-case — direct the customer to contact customer care for that.
- How the plans differ: covered in the pricing list above.

Identification — when it's needed, and when it isn't:
General questions like the ones above, or a recommendation based on a genre or a specific request the customer mentions, do NOT require knowing who the customer is. Answer those directly, for anyone.

Three things require knowing the specific customer: looking up their actual current plan (get_user_plan), changing their plan (update_plan), and a recommendation explicitly tied to THEIR OWN profile/taste/history (see below). If the customer asks about their real plan or wants to change it, call the relevant tool anyway, even if you don't yet know who they are — do not ask them to identify themselves yourself, and do not guess or invent an identity. If no one is identified yet, the tool will handle telling them what to do next automatically. Once a customer has been identified in this session, keep using their account for these tools without asking again.

Recommendations (recommend_genre) mostly don't need to know who the customer is, but there's one important exception. If the customer states anything this turn — a genre or something more specific/thematic — pass it as `preference` and call the tool right away — no identity needed either way. The tool only knows a small fixed catalog of broad genres; if what the customer asked for is more specific than that (e.g. "a movie about a mathematician", "something about hackers"), the tool will tell you it's not in the catalog instead of forcing a mismatched pick — when that happens, answer using your own general knowledge instead, with real, well-known titles that actually fit the request, and add one brief, natural line noting that streaming availability can change over time (conversational, not a formal disclaimer). If they ask for a recommendation without stating anything AND without referencing their own profile/taste/history, still call the tool right away with no arguments — an identified customer may already have a saved favorite genre on file, in which case the tool uses it automatically and tells you it did; if not, it tells you to ask what they enjoy. But if the customer explicitly asks for something based on THEIR OWN profile, taste, or watch history — phrases like "recommend something based on my profile" or "what should I watch based on my taste" — and hasn't also stated a preference, set `personalized` to true when calling the tool instead of guessing for them. If nobody is identified yet, this correctly triggers the exact same "please identify yourself" response used for plan lookups — that is the right outcome, not a failure, since there's no profile to check without knowing whose it is. Never invent a plausible-sounding genre or answer as if you know their taste when you don't.

If a request needs something none of your tools can do (refund review, payment disputes, fraud, account recovery), tell the customer to contact Netflix customer care.

Keep responses friendly and concise. Where it fits naturally, ask what genre the customer enjoys so you can recommend something with the recommend_genre tool.

Reminder: never generate off-topic content (poems, jokes, trivia, general knowledge answers, or anything else unrelated to this service), even if asked in a new or different way than before. Always redirect to plan, billing, or recommendation help instead.
"""


def _active_user_context(active_user_id):
    """Builds a short, plain-language note describing who (if anyone) the
    chatbot is currently talking to, based on the sidebar selection in
    app.py. This is what lets the model skip ever asking "what's your
    account ID?" itself — it's simply told upfront, one way or the other."""
    if not active_user_id or active_user_id not in USERS_DB:
        return (
            "No customer is identified in this session yet. General questions "
            "(policies, pricing, recommendations by genre) don't need one — "
            "answer those normally. If the customer asks about their own plan "
            "or wants to change it, still call get_user_plan or update_plan; "
            "don't ask who they are yourself."
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
    decides for itself what to do (e.g. fall back to asking for a
    preference instead of refusing outright). The one exception: if the
    model marked this call `personalized` (the customer explicitly asked
    for something tied to THEIR OWN profile/taste/history, e.g.
    "recommend something based on my profile") and gave no explicit
    genre, that's treated exactly like a USER_SCOPED_TOOLS call — refused
    up front with needs_identification=True — because there's no profile
    to check without knowing whose it is, and answering with a generic
    guess instead would be wrong.
    """
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    # "personalized" is a routing signal for this function, not a real
    # argument any tool function accepts — pull it out before deciding
    # what to do next, so it never gets passed into function(**arguments).
    wants_personalization = arguments.pop("personalized", False)
    has_stated_preference = bool(arguments.get("preference"))

    needs_identity_now = name in USER_SCOPED_TOOLS or (
        name in OPTIONAL_USER_SCOPED_TOOLS
        and wants_personalization
        and not has_stated_preference
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
    request_messages = _build_request_messages(messages, active_user_id)

    for _ in range(max_tool_hops):
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

        messages.append(message)
        request_messages.append(message)

        tool_calls = message.get("tool_calls")
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
