# Netflix Support Bot — Documentation

A Netflix-style customer support chatbot built on the Groq API, with dynamic
tool calling, multi-turn conversation memory, and a Streamlit chat UI.

This document is written so you can explain every part of this project —
what was built, why it was built that way, and how the pieces connect —
without needing to re-derive it from the code alone.

---

## 1. What was built, in order

The project started as a single Jupyter notebook (`Stage_1_3.ipynb`) that
already proved out the core mechanics by hand:

1. **Raw HTTP calls to Groq** using the `requests` library against
   `https://api.groq.com/openai/v1/chat/completions` — no SDK, so every part
   of the request/response is visible.
2. **Zero-shot and few-shot prompting** — a system prompt describing the
   assistant's role and Netflix's (fake) plans, followed by example
   user/assistant exchanges to steer the model's tone.
3. **A manual, hardcoded tool-calling proof of concept**: two tools
   (`add` and `get_user_plan`), where each tool call was inspected and
   executed cell-by-cell rather than in a loop.

From there, the project was extended in this order:

1. **Reviewed the existing notebook** and identified its structure and gaps
   (no loop, no dynamic routing, hardcoded history, an exposed API key).
2. **Rotated the exposed API key.** The original notebook had a live Groq
   key hardcoded in plaintext. It was revoked and replaced — see
   [Section 6](#6-security-notes).
3. **Extracted the fixed pieces into `tools.py`** — the fake database, the
   four tool functions, their JSON-schema descriptions, and a
   name-to-function lookup table.
4. **Built `config.py`** to load the API key from either a local `.env`
   file or Streamlit Cloud secrets, so the same code works locally and
   deployed without changes.
5. **Built `chatbot.py`** — the model-calling and tool-execution loop,
   generalized so it dynamically routes to *any* tool the model asks for,
   and repeats until the model has no more tool calls left to make.
6. **Added two new tools**: `update_plan` (changes a user's plan in the
   fake DB) and `recommend_genre` (suggests titles from a fake catalog).
7. **Built `app.py`**, a Streamlit chat UI that keeps conversation history
   in `st.session_state` and calls into `chatbot.py` for every turn.
8. **Tested end-to-end**: tool functions in isolation, a full multi-tool
   single turn, a 3-turn conversation that both read and wrote to the fake
   database, and the Streamlit server itself.
9. **Set up git and prepared for deployment** to Streamlit Community
   Cloud, with secrets handled outside of source control.
10. **Wrote this document.**

---

## 2. Project structure

```
Netflix_Chatbot/
├── app.py              # Streamlit UI — presentation only
├── chatbot.py           # Conversation loop + tool-call routing (no UI code)
├── tools.py              # Fake DB, tool functions, tool schemas, routing table
├── config.py              # Finds the Groq API key (local .env or Streamlit secrets)
├── requirements.txt        # streamlit, requests, python-dotenv
├── .env.example              # Template for the local secret file
├── .gitignore                  # Excludes .env, __pycache__, etc.
├── Stage_1_3.ipynb              # Original prototype notebook (key redacted)
└── DOCUMENTATION.md               # This file
```

Each file has exactly one job. That's the main organizing idea of the
whole project — see [Section 4](#4-why-these-design-decisions) for why.

---

## 3. Architecture: how a message flows through the system

### 3.1 The request path (one user turn)

```
User types in app.py's chat box
        │
        ▼
app.py appends {"role": "user", "content": ...} to st.session_state.messages
        │
        ▼
app.py calls chatbot.get_assistant_reply(messages)
        │
        ▼
chatbot.call_groq(messages) — sends the FULL history + tools list to Groq
        │
        ▼
Groq's model reads the conversation and decides ONE of two things:
        │
        ├─► "I can answer directly" → returns a normal text message
        │         │
        │         ▼
        │   get_assistant_reply() returns immediately with that text
        │
        └─► "I need a tool" → returns a message with tool_calls
                  │
                  ▼
            For each tool call, chatbot.execute_tool_call():
              1. Reads the tool name and arguments the model chose
              2. Looks up the matching Python function in
                 tools.TOOL_FUNCTIONS (dynamic routing — see 3.2)
              3. Calls it, catches errors, wraps the result as a
                 {"role": "tool", ...} message
                  │
                  ▼
            All tool results get appended to messages
                  │
                  ▼
            Loop back to chatbot.call_groq(messages) — the model now
            sees the tool results and either answers in text, or asks
            for another tool (up to a safety cap of 5 round-trips)
        │
        ▼
app.py receives the final text reply and renders it with st.chat_message
```

The same function (`get_assistant_reply`) handles both "the model answered
immediately" and "the model needed three tools chained together" — there's
no separate code path for either case.

### 3.2 How tool calls are decided and executed (dynamic routing)

Two things happen at different times and it's worth keeping them separate:

- **Deciding which tool to call is entirely the model's job.** We send it
  `tools.TOOLS`, a list of JSON schemas (name, description, expected
  arguments) for every tool that exists. The model reads the conversation
  and picks whichever tool(s) — zero, one, or several — fit the user's
  request. Our code never says "if the user mentions billing, call X."

- **Executing the tool the model picked is a dictionary lookup, not an
  if/elif chain.** `tools.TOOL_FUNCTIONS` maps each tool's name string to
  the actual Python function:

  ```python
  TOOL_FUNCTIONS = {
      "add": add,
      "get_user_plan": get_user_plan,
      "update_plan": update_plan,
      "recommend_genre": recommend_genre,
  }
  ```

  `chatbot.execute_tool_call()` does `TOOL_FUNCTIONS[name](**arguments)`.
  This is what "dynamic routing" means in this project: the routing logic
  doesn't need to know how many tools exist or what they're called. Adding
  a fifth tool means adding it to `tools.py` — `chatbot.py` doesn't change.

### 3.3 How conversation history is managed

`st.session_state.messages` is a single Python list that grows for the
life of a browser session. It holds every message type OpenAI-style chat
APIs use: `system` (once, at the start), `user`, `assistant` (including
the intermediate ones that only carry a tool request), and `tool` (the
result of each tool call, tagged with `tool_call_id` so the model can match
results back to its requests).

Because the **entire list** is sent to Groq on every request (not just the
newest message), the model has full context of everything said and done
so far — that's what makes plan changes, follow-up billing questions, and
"yes, go ahead" confirmations work correctly across turns. Streamlit reruns
`app.py` top-to-bottom on every interaction, but `st.session_state` is
Streamlit's mechanism for surviving those reruns, so the list isn't reset
each time the user sends a message.

### 3.4 How the UI connects to the backend

`app.py` never talks to Groq directly and never touches `tools.py`
directly (aside from reading `USERS_DB` to show sample IDs in the
sidebar). It only:

1. Owns `st.session_state.messages`.
2. Renders whatever's already in that list.
3. On new input, appends the user's message and calls
   `chatbot.get_assistant_reply(messages)`.
4. Renders whatever text comes back.

`chatbot.py` has no `import streamlit` anywhere in its logic — it's a
plain Python module that takes a list in and returns a list + string out.
That means the same `chatbot.py` would work behind a CLI loop, a Flask
route, or a test script with zero changes.

---

## 4. Why these design decisions

**Why raw `requests` instead of the official Groq SDK?**
The original notebook already used `requests` directly against the API
endpoint, and that was kept on purpose: it keeps the exact HTTP request and
JSON response visible and inspectable, rather than hidden behind an SDK's
objects. For a project meant to be explained line-by-line in an interview,
seeing the literal `headers`, `body`, and `response.json()` is more useful
than an abstraction layer.

**Why a dict lookup (`TOOL_FUNCTIONS`) instead of `if/elif` for routing?**
An `if/elif` chain has to be edited every time a tool is added or removed,
and it's easy for the schema list (`TOOLS`) and the dispatch code to drift
out of sync. A single dict keeps "what tools exist" defined in exactly one
place (`tools.py`), and makes the routing code in `chatbot.py` generic
enough that it never needs to change.

**Why a `while`-style loop (capped at 5 hops) instead of handling one tool
call and stopping?**
The original notebook manually re-ran cells to send tool results back and
get a second response — it only worked for a single tool call in isolation.
Real conversations sometimes need the model to call one tool, see the
result, and decide it needs another (e.g. look up the plan, then compute a
total). The loop in `get_assistant_reply()` keeps going until the model
stops asking for tools, so multi-tool turns "just work." The 5-hop cap is a
simple safety net against a runaway loop if the model kept requesting tools
indefinitely — it's not expected to be hit in normal use.

**Why split `tools.py`, `config.py`, `chatbot.py`, and `app.py` into
separate files instead of one script?**
Each file answers one question, which makes the whole thing easier to
trace: *What tools exist and what do they do?* (`tools.py`) *Where does the
secret key come from?* (`config.py`) *What's the conversation logic?*
(`chatbot.py`) *What does the user see?* (`app.py`). None of this is
premature abstraction for scale — it's the minimum split that lets you
point at one file and answer one question about the system.

**Why Streamlit for the UI?**
It turns a chat loop into a working web UI with almost no boilerplate
(`st.chat_message`, `st.chat_input`, `st.session_state`), and it has a free
hosting path (Streamlit Community Cloud) that deploys straight from a
GitHub repo — no server to manage.

**Why Streamlit Community Cloud for deployment, specifically?**
It's free, it deploys directly from a GitHub repo with no Dockerfile or
server config needed, and it has built-in encrypted secrets storage
(`st.secrets`) that's designed exactly for this use case: a public app that
needs a private API key. The alternative would be something like Render or
Railway, which work fine too but need more manual setup (build commands,
env var dashboards, sometimes a credit card) for the same outcome. For a
single Streamlit script with one secret, Community Cloud is the least
amount of setup for the same result.

**Why `update_plan` and `recommend_genre` as the two new tools, instead of
`get_billing_info`?**
The four tools now cover four distinct patterns worth being able to point
to individually: `add` is a **pure computation** (no data source),
`get_user_plan` is a **read** from the fake DB, `update_plan` is a
**write/mutation** to the fake DB, and `recommend_genre` is a
**recommendation** with no DB involved at all. That spread makes it easy to
explain "here's a tool that only computes, here's one that reads, here's
one that writes" as three genuinely different shapes of tool, rather than
two tools that both just read from the same dictionary.

---

## 5. Deployment setup

### 5.1 Where secrets live

- **Locally**: `.env` (already created, and already in `.gitignore` — it
  will never be committed). `config.py` loads it via `python-dotenv`.
- **On Streamlit Community Cloud**: the app's own **Secrets** panel
  (Settings → Secrets, in TOML format: `GROQ_API_KEY = "..."`). Streamlit
  Cloud injects these as `st.secrets` at runtime — they're encrypted at
  rest and never touch the GitHub repo. `config.py` checks `st.secrets`
  first, before falling back to `.env`, so the exact same code runs in
  both places.

### 5.2 How to redeploy after a code change

1. Commit and push changes to the `main` branch of the GitHub repo the app
   is connected to.
2. Streamlit Community Cloud auto-redeploys on every push to that branch —
   no manual redeploy step needed.
3. If a new environment variable or secret is ever needed, add it in the
   app's Secrets panel; the app restarts automatically when secrets change.

### 5.3 Redeploying from scratch (if the app is ever deleted)

1. Push this repo to GitHub (if not already there).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**, and pick this repo + `app.py` as the entry
   point.
3. Before or after the first deploy, open **Settings → Secrets** and add:
   ```
   GROQ_API_KEY = "your_key_here"
   ```
4. Deploy. The public URL Streamlit gives you is shareable as-is — anyone
   who opens it uses your app under your key; they never see or need their
   own.

---

## 6. Security notes

The original notebook had a real Groq API key hardcoded in plaintext in a
cell. That key was **revoked and rotated** during this project — the
notebook now reads `GROQ_API_KEY` from the environment via `python-dotenv`
instead. The lesson worth remembering (and worth mentioning if this comes
up in an interview): a secret that's ever been committed to a file or
pasted somewhere logged should be treated as compromised and rotated, not
just deleted from the file — deleting it from the current version doesn't
remove it from git history or from wherever else it was already exposed.

---

## 7. Talking points for an interview

If asked to walk through this project, the throughline is:

- **Started from a working prototype, not a blank page.** The notebook
  proved the API contract and tool-calling shape worked before any
  restructuring happened.
- **The core interesting mechanism is the tool-calling loop**: send
  messages + tool schemas → model decides whether it needs a tool → if so,
  look the function up by name and run it → feed the result back → repeat
  until the model is done. This is the same fundamental pattern used by
  every production agent framework (LangChain, the OpenAI/Anthropic tool-use
  loops, etc.), just written out explicitly instead of hidden inside a
  library.
- **Routing is data-driven, not control-flow-driven.** `TOOL_FUNCTIONS` is
  the single source of truth for "what tools exist"; nothing else needs
  updating to add a tool. This is the detail most worth highlighting if
  asked "how would you add a fifth tool?" — the answer is "write the
  function, add one schema entry, add one dict entry," not "find every
  if/elif branch that needs updating."
- **State lives in one place**: the growing `messages` list is the entire
  conversation state. There's no separate "memory" system — the list *is*
  the memory, which is also literally what gets sent to the model each
  time to give it context.
- **The fake DB is intentionally in-memory and non-persistent** — a
  `dict`, not a real database. `update_plan` mutates it directly, which is
  enough to demonstrate a write-tool without needing real
  infrastructure. If asked "how would this be production-ready," the
  honest answer is: swap `USERS_DB` for a real database call inside the
  same functions — the tool-calling loop and routing logic wouldn't need
  to change at all.
- **Deployment is deliberately the simplest option that meets the bar**
  (a public URL, secrets not exposed) — Streamlit Community Cloud over a
  custom server, because the goal was a shareable demo, not a scalable
  service.
