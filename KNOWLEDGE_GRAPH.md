# Codebase Knowledge Graph

How the four Python files actually connect — real imports, real function calls, real data reads/writes — traced from the code, not summarized from memory. For what each file is *for*, see [ARCHITECTURE.md](ARCHITECTURE.md); this is the *wiring diagram*.

```mermaid
flowchart TD
    subgraph APP["app.py — Streamlit UI"]
        A_input["st.chat_input()<br/>user types a message"]
        A_append["append user message to<br/>st.session_state.messages"]
        A_call["get_assistant_reply(messages, active_user_id)"]
        A_render["_render_chat_text()<br/>st.markdown(escaped text)"]
        A_check{"needs_identification?"}
        A_rerun["set flag + st.rerun()<br/>sidebar shows warning"]
        A_sidebar["sidebar: st.selectbox<br/>lists USERS_DB by name"]
        A_greet["_greeting_message(user)<br/>on selection change"]
    end

    subgraph BOT["chatbot.py — conversation engine"]
        B_entry["get_assistant_reply()"]
        B_build["_build_request_messages()"]
        B_ctx["_active_user_context()"]
        B_loop{{"tool-call loop<br/>up to 5 round-trips"}}
        B_groq["call_groq(request_messages)"]
        B_try{"request succeeded?"}
        B_err["return API_ERROR_MESSAGE"]
        B_hastools{"reply has tool_calls?"}
        B_exec["execute_tool_call()<br/>for each tool call"]
        B_needsid{"needs identity,<br/>none active?"}
        B_idmsg["return IDENTIFICATION_<br/>NEEDED_MESSAGE"]
        B_final["return final reply text"]
    end

    subgraph TOOLS["tools.py — data + tool functions"]
        T_db[("USERS_DB<br/>40 fake customers")]
        T_genre[("GENRE_CATALOG /<br/>PLAN_PRICES")]
        T_schemas["TOOLS[]<br/>schemas sent to Groq"]
        T_registry["TOOL_FUNCTIONS{}<br/>name to function"]
        T_add["add(a, b)"]
        T_plan["get_user_plan(user_id)"]
        T_update["update_plan(user_id, new_plan)"]
        T_rec["recommend_genre(preference, user_id)"]
    end

    subgraph CFG["config.py"]
        C_key["get_api_key()<br/>st.secrets, then .env"]
    end

    GROQ[("Groq API<br/>chat/completions")]

    %% main path: one user message
    A_input --> A_append --> A_call --> B_entry
    B_entry --> B_build --> B_ctx
    B_ctx -. reads .-> T_db
    B_build --> B_loop --> B_groq
    B_groq -. "gets key" .-> C_key
    T_schemas -. "sent as tools param" .-> B_groq
    B_groq -->|"POST"| GROQ
    GROQ -->|"JSON response"| B_groq
    B_groq --> B_try

    B_try -->|"no: 429 / timeout / bad shape"| B_err
    B_err --> A_render

    B_try -->|yes| B_hastools
    B_hastools -->|no| B_final
    B_final --> A_render

    B_hastools -->|yes| B_exec
    B_exec -. "looks up by name" .-> T_registry
    T_registry --> T_add
    T_registry --> T_plan
    T_registry --> T_update
    T_registry --> T_rec
    T_plan -. reads .-> T_db
    T_update -. "reads + writes" .-> T_db
    T_rec -. reads .-> T_db
    T_rec -. reads .-> T_genre
    B_exec --> B_needsid

    B_needsid -->|yes| B_idmsg
    B_idmsg --> A_render

    B_needsid -->|no| B_loop

    A_render --> A_check
    A_check -->|true| A_rerun
    A_check -->|false| A_input

    %% identification / greeting path — no API call involved
    A_sidebar -. reads .-> T_db
    A_sidebar --> A_greet --> A_append
```

### Reading the diagram

- **Boxes grouped in a shaded rectangle** = one file. **Solid arrows** = a function calling another function, or control flow. **Dotted arrows** = an import, a data read/write, or "this value gets used over there" rather than a direct call.
- **The critical path** is `app.py → chatbot.py → tools.py`, and back up the same way. `app.py` never talks to Groq or to individual tool functions directly — everything about *deciding and running tools* is chatbot.py's job, and everything about *what tools actually do* is tools.py's job.
- **The tool-call loop** (`B_loop` → `call_groq` → tool_calls? → `execute_tool_call` → back to `B_loop`) is the one part of the diagram that can cycle — this is what lets the model chain multiple tools (e.g. look up a plan *and* get a recommendation) before answering, up to a 5-round-trip safety cap.
- **Two dead ends that skip Groq entirely**: the sidebar's greeting (`A_sidebar → A_greet`) is plain string formatting, and a failed request (`B_try` → `B_err`) or a missing identity (`B_needsid` → `B_idmsg`) both return a *fixed* message instead of asking the model to phrase one — deliberate, not a shortcut (see `DOCUMENTATION.md` §3.6–3.8 for why).
- **`config.py`** is the only file that reaches back out to `streamlit` from the "backend" side (checking `st.secrets`), which is why it's drawn as its own small file rather than folded into `chatbot.py`.
