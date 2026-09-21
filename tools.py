# ---------------------------------------------------------------------------
# tools.py
#
# Every tool the chatbot can use lives here: the fake data it works on, the
# plain Python functions that do the work, the JSON-schema descriptions that
# tell the model the tools exist, and a name -> function lookup table.
#
# Nothing in this file talks to Groq, and nothing in this file talks to
# Streamlit. That keeps it simple to test and explain in isolation.
# ---------------------------------------------------------------------------

# ---- Fake "database" -------------------------------------------------------
# In a real product this would be a call to a customer database. Here it's
# just a dict in memory, so changes made by update_plan() reset every time
# the app process restarts.
#
# USERS_DB is generated from a name list below instead of written out by
# hand as 40 separate dict entries. That's purely to keep this file
# readable — the generation logic (_generate_users) is the only part
# that's slightly clever, and it's simple: walk the name list once,
# cycling through plans/payment methods/billing days as we go, so every
# user ends up with a plausible, varied profile.

FIRST_NAMES = [
    "Aditi", "Rohan", "Priya", "Karan", "Neha", "Vikram", "Ananya", "Arjun", "Ishita", "Aditya",
    "Sneha", "Rahul", "Pooja", "Siddharth", "Meera", "Varun", "Kavya", "Nikhil", "Riya", "Aman",
    "Divya", "Suresh", "Lakshmi", "Manoj", "Shreya", "Abhishek", "Nisha", "Rajesh", "Tanvi", "Yash",
    "Simran", "Harsh", "Alisha", "Vivek", "Pallavi", "Gaurav", "Swati", "Deepak", "Radhika", "Ashish",
]

LAST_NAMES = [
    "Sharma", "Mehta", "Nair", "Kapoor", "Verma", "Singh", "Gupta", "Reddy", "Iyer", "Joshi",
    "Malhotra", "Chatterjee", "Bose", "Rao", "Desai", "Kulkarni", "Chauhan", "Mishra", "Pillai", "Agarwal",
]

# The three plan tiers. "Standard with ads" is the entry-level / "Basic"
# tier — kept under this exact name so it matches PLAN_PRICES and the
# pricing described in the system prompt.
PLAN_CYCLE = ["Premium", "Standard", "Standard with ads"]

PLAN_PRICES = {
    "Standard with ads": 8.99,
    "Standard": 19.99,
    "Premium": 26.99,
}

PAYMENT_METHODS = [
    "Visa ending in 4242",
    "Mastercard ending in 7788",
    "PayPal",
    "Amex ending in 1005",
    "UPI",
]


# A tiny fake content catalog, keyed by genre, for recommend_genre().
# Defined before _generate_users() so each sample user can be assigned a
# favorite genre straight from these same keys.
GENRE_CATALOG = {
    "action": ["Extraction", "Red Notice", "6 Underground"],
    "comedy": ["Murder Mystery", "Family Switch", "Do Revenge"],
    "drama": ["The Crown", "Ozark", "The Queen's Gambit"],
    "thriller": ["Mindhunter", "You", "Fool Me Once"],
    "romance": ["To All the Boys I've Loved Before", "Purple Hearts"],
    "sci-fi": ["Stranger Things", "Black Mirror", "3 Body Problem"],
    "horror": ["The Haunting of Hill House", "Fear Street"],
    "documentary": ["Our Planet", "Tiger King", "American Murder"],
}

GENRE_CYCLE = list(GENRE_CATALOG.keys())


def _generate_users():
    """Builds the fake customer database: one entry per name in FIRST_NAMES,
    cycling deterministically through plans, payment methods, billing days,
    and favorite genres so the data looks varied without any randomness
    (randomness would make the "database" different every time the app
    process restarts, which makes testing and demoing annoying)."""
    users = {}
    for i, first_name in enumerate(FIRST_NAMES):
        last_name = LAST_NAMES[i % len(LAST_NAMES)]
        user_id = f"U{101 + i}"
        plan = PLAN_CYCLE[i % len(PLAN_CYCLE)]
        billing_day = (i % 28) + 1

        # Every 6th user has no saved favorite genre, so the "genuinely
        # missing — ask instead" path has real sample data to exercise,
        # not just the happy path where a saved preference always exists.
        favorite_genre = None if i % 6 == 5 else GENRE_CYCLE[i % len(GENRE_CYCLE)]

        users[user_id] = {
            "name": f"{first_name} {last_name}",
            "email": f"{first_name.lower()}.{last_name.lower()}@gmail.com",
            "plan": plan,
            "billing_date": f"2026-10-{billing_day:02d}",
            "amount": PLAN_PRICES[plan],
            "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
            "favorite_genre": favorite_genre,
        }
    return users


USERS_DB = _generate_users()


# ---- Tool functions ---------------------------------------------------------
# Each function below is a normal Python function. The only thing that makes
# it a "tool" is that it's listed in TOOLS (so the model knows it exists) and
# in TOOL_FUNCTIONS (so our code can call it by name).
#
# get_user_plan and update_plan both take a user_id — but the model is
# never asked to supply one (see TOOLS below: neither schema lists
# user_id as a parameter). Instead chatbot.py fills it in automatically
# from whichever customer is selected in the Streamlit sidebar. The
# functions themselves still accept user_id as a normal argument, which
# keeps them simple to call directly and test on their own.


def add(a, b):
    """Adds two numbers. Used for billing math, e.g. plan price + add-on."""
    return a + b


def get_user_plan(user_id):
    """Looks up a user's current subscription plan."""
    if user_id is None:
        return {"error": "No customer is currently selected. Ask them to choose their name in the sidebar."}
    user = USERS_DB.get(user_id)
    if user is None:
        return {"error": f"No user found with id '{user_id}'"}
    return {"user_id": user_id, "name": user["name"], "plan": user["plan"]}


def update_plan(user_id, new_plan):
    """Changes a user's subscription plan in the fake database."""
    if user_id is None:
        return {"error": "No customer is currently selected. Ask them to choose their name in the sidebar."}
    if user_id not in USERS_DB:
        return {"error": f"No user found with id '{user_id}'"}
    if new_plan not in PLAN_PRICES:
        return {
            "error": f"'{new_plan}' is not a valid plan.",
            "valid_plans": list(PLAN_PRICES.keys()),
        }

    USERS_DB[user_id]["plan"] = new_plan
    USERS_DB[user_id]["amount"] = PLAN_PRICES[new_plan]

    return {
        "user_id": user_id,
        "new_plan": new_plan,
        "new_monthly_amount": PLAN_PRICES[new_plan],
        "message": "Plan updated successfully.",
    }


def recommend_genre(preference=None, user_id=None):
    """Suggests titles from the fake catalog. If the customer stated a
    genre this turn, `preference` is used as-is — that always wins, even
    if it differs from what's on file. Otherwise, if a customer is
    identified and has a saved favorite_genre, that's used automatically.
    Only if neither is available does this ask for one."""
    used_saved_preference = False

    if not preference and user_id and user_id in USERS_DB:
        preference = USERS_DB[user_id].get("favorite_genre")
        used_saved_preference = preference is not None

    if not preference:
        return {
            "error": "No genre preference given, and none saved for this customer.",
            "message": "Ask the customer what genre they enjoy, then call this tool again with it.",
        }

    preference_lower = preference.lower().strip()

    for genre, titles in GENRE_CATALOG.items():
        if genre in preference_lower or preference_lower in genre:
            result = {"matched_genre": genre, "recommendations": titles}
            if used_saved_preference:
                result["note"] = "Based on this customer's saved favorite genre."
            return result

    # No keyword matched anything in the catalog: fall back to a
    # generally popular pick instead of returning an empty result.
    return {
        "matched_genre": None,
        "recommendations": GENRE_CATALOG["drama"],
        "note": f"No exact genre match for '{preference}', showing popular picks instead.",
    }


# ---- Tool registry -----------------------------------------------------------
# TOOLS is sent to Groq so the model knows what tools exist and how to call
# them (name, description, expected arguments).
#
# Note that "get_user_plan" and "update_plan" do NOT list user_id as a
# parameter here. That's what stops the model from ever asking the
# customer "what's your account ID?" in the chat — as far as the model is
# concerned, those tools just don't take one. chatbot.py fills user_id in
# automatically before calling the real Python function (see
# chatbot.execute_tool_call).
#
# TOOL_FUNCTIONS maps each tool's name to the Python function that implements
# it. This dict is what makes tool routing "dynamic": the code that executes
# a tool call (see chatbot.py) just does TOOL_FUNCTIONS[name](**arguments) —
# there's no if/elif chain to update every time a tool is added.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Adds two numbers together. Use for billing math, like combining a plan price with an add-on fee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_plan",
            "description": "Looks up which subscription plan the currently-selected customer is on. Takes no arguments — the customer is already known from the session.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Changes the currently-selected customer's subscription plan. Only call this after the customer has clearly confirmed which plan they want.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_plan": {
                        "type": "string",
                        "description": "One of: 'Standard with ads', 'Standard', 'Premium'.",
                    },
                },
                "required": ["new_plan"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_genre",
            "description": "Suggests shows/movies for the customer. If they stated a genre this turn, pass it as `preference`. If they didn't, call this tool anyway with no `preference` — it will automatically use the identified customer's saved favorite genre if they have one on file, or tell you to ask them if not.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {
                        "type": "string",
                        "description": "The genre the customer explicitly mentioned in this message. Omit entirely if they didn't state one.",
                    },
                },
                "required": [],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "add": add,
    "get_user_plan": get_user_plan,
    "update_plan": update_plan,
    "recommend_genre": recommend_genre,
}

# Tools that operate on "the current customer" rather than arguments the
# model supplies. chatbot.execute_tool_call() auto-injects user_id for
# any tool name in this set before calling it. If no one is identified
# yet, these tools are refused up front with a "please identify yourself"
# response — see chatbot.py.
USER_SCOPED_TOOLS = {"get_user_plan", "update_plan"}

# Tools that USE the identified customer's account when one is available,
# but work fine without one too — they just fall back to asking instead of
# refusing outright. Unlike USER_SCOPED_TOOLS, these never trigger the
# "please identify yourself" response; user_id is passed in as None if
# nobody's identified, and the tool itself decides what to do with that.
OPTIONAL_USER_SCOPED_TOOLS = {"recommend_genre"}
