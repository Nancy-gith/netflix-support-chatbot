# ---------------------------------------------------------------------------
# tools.py
#
# Every tool the chatbot can use lives here: the fake data it works on, the
# plain Python functions that do the work, the JSON-schema descriptions that
# tell the model the tools exist, and a name -> function lookup table.
#
# Nothing in this file talks to Groq. That keeps it simple to test and
# explain in isolation.
# ---------------------------------------------------------------------------

# ---- Fake "database" -------------------------------------------------------
# In a real product this would be a call to a customer database. Here it's
# just a dict in memory, so changes made by update_plan() reset every time
# the app restarts.

USERS_DB = {
    "U101": {
        "name": "Aditi Sharma",
        "email": "aditi.sharma@gmail.com",
        "plan": "Premium",
        "billing_date": "2026-10-05",
        "amount": 26.99,
        "payment_method": "Visa ending in 4242",
    },
    "U102": {
        "name": "Rohan Mehta",
        "email": "rohan.mehta@gmail.com",
        "plan": "Standard with ads",
        "billing_date": "2026-10-12",
        "amount": 8.99,
        "payment_method": "Mastercard ending in 7788",
    },
    "U103": {
        "name": "Priya Nair",
        "email": "priya.nair@gmail.com",
        "plan": "Standard",
        "billing_date": "2026-10-20",
        "amount": 19.99,
        "payment_method": "PayPal",
    },
}

# Monthly price for each plan. update_plan() uses this to keep amount and
# plan in sync when a user switches plans.
PLAN_PRICES = {
    "Standard with ads": 8.99,
    "Standard": 19.99,
    "Premium": 26.99,
}

# A tiny fake content catalog, keyed by genre, for recommend_genre().
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


# ---- Tool functions ---------------------------------------------------------
# Each function below is a normal Python function. The only thing that makes
# it a "tool" is that it's listed in TOOLS (so the model knows it exists) and
# in TOOL_FUNCTIONS (so our code can call it by name).


def add(a, b):
    """Adds two numbers. Used for billing math, e.g. plan price + add-on."""
    return a + b


def get_user_plan(user_id):
    """Looks up a user's current subscription plan."""
    user = USERS_DB.get(user_id)
    if user is None:
        return {"error": f"No user found with id '{user_id}'"}
    return {"user_id": user_id, "name": user["name"], "plan": user["plan"]}


def update_plan(user_id, new_plan):
    """Changes a user's subscription plan in the fake database."""
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


def recommend_genre(preference):
    """Suggests titles from the fake catalog based on a genre the user mentions."""
    preference_lower = preference.lower().strip()

    for genre, titles in GENRE_CATALOG.items():
        if genre in preference_lower or preference_lower in genre:
            return {"matched_genre": genre, "recommendations": titles}

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
            "description": "Looks up which subscription plan a user is currently on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's account ID, e.g. 'U101'.",
                    },
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Changes a user's subscription plan. Only call this after the user has clearly confirmed which plan they want.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's account ID, e.g. 'U101'.",
                    },
                    "new_plan": {
                        "type": "string",
                        "description": "One of: 'Standard with ads', 'Standard', 'Premium'.",
                    },
                },
                "required": ["user_id", "new_plan"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_genre",
            "description": "Suggests shows/movies based on a genre or preference the user mentions (e.g. 'comedy', 'scary shows').",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {
                        "type": "string",
                        "description": "The genre or type of content the user said they like.",
                    },
                },
                "required": ["preference"],
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
