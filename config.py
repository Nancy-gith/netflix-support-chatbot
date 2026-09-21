# ---------------------------------------------------------------------------
# config.py
#
# One job: find the Groq API key, wherever it happens to be stored, and
# hand it back as a string. Keeping this in its own file means chatbot.py
# doesn't need to know or care whether it's running locally or deployed.
# ---------------------------------------------------------------------------

import os


def get_api_key():
    """
    Returns the Groq API key.

    Checks two places, in order:
    1. Streamlit secrets (used automatically when deployed on Streamlit
       Community Cloud — see DOCUMENTATION.md for how secrets are set there).
    2. A local .env file (used when running on your own machine), read via
       python-dotenv into a normal environment variable.

    Never hardcode the key itself in this file or any other — that's how
    the original notebook's key ended up exposed.
    """
    # 1. Streamlit Cloud secrets (only exists when running inside Streamlit)
    try:
        import streamlit as st

        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        # Not running inside Streamlit, or no secrets configured yet.
        # Fall through to the .env / environment variable check below.
        pass

    # 2. Local .env file
    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ.get("GROQ_API_KEY")

    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not found. Create a .env file locally with "
            "GROQ_API_KEY=your_key_here (see .env.example), or set it in "
            "Streamlit Cloud's app settings under Secrets when deployed."
        )

    return key
