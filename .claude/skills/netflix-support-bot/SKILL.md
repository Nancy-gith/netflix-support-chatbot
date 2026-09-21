---
name: netflix-support-bot
description: Use this whenever working on the Netflix support bot project (this repo) — a learning project demonstrating AI tool-calling via a Netflix-style customer support chatbot. Covers standing rules for code style, fake data only, keeping docs in sync, and deployment/secrets handling.
---

# Netflix Support Bot — Project Conventions

This project is a **learning project**. The person maintaining it will be
explaining the code themselves — to a reviewer, an interviewer, or in a
teardown — so these rules exist to keep the project explainable, not just
functional. When in doubt, favor whatever makes the project easier to
walk through out loud.

## 1. Simple and readable over clever

- Prefer the obvious, slightly longer way of writing something over a
  compact or "smart" one-liner.
- Don't introduce abstractions, helper layers, or config options that
  aren't needed by the current feature. Three similar lines of code beat
  a premature helper function.
- Comments should explain *why*, not *what* — only add one when the
  reasoning isn't obvious from reading the code itself.
- If a change makes a file harder to explain out loud than it was before,
  that's a signal to simplify it, even if the code "works."

## 2. Only fake / sample data — never real Netflix data

- The customer database, plans, prices, and content catalog are all
  made up for this project. Keep it that way.
- Never pull in, reference, or hardcode real Netflix pricing, real show
  titles sourced as "current Netflix catalog," or any real customer data.
- It's fine for fake data to *resemble* real-world plans/pricing for
  realism — just don't present it as accurate to the real service.
- Any new sample data (more fake users, more fake content, etc.) should
  stay clearly fake and be easy to tell apart from a real data source at
  a glance.

## 3. Keep docs in sync — after every change, check three files

After making a change to this project, check whether these are still
accurate, and update them if not:

- **`CONTEXT.md`** — the plain-language "what this project is and why."
  Update if the change affects what the project does, who the sample
  users are, or what's fake vs. real.
- **`ARCHITECTURE.md`** — the plain-language "how it works" walkthrough.
  Update if the change affects the message flow, the tools, the files
  involved, or how deployment/secrets work.
- **`DOCUMENTATION.md`** — the full technical write-up (build history,
  architecture detail, design rationale, deployment steps, interview
  talking points). Update if the change is architecturally significant —
  new tool, new flow, new design decision — following the same structure
  already used in that file (what was built → architecture → why →
  deployment → talking points).

Small changes (e.g. adjusting a prompt string, fixing a typo) don't need
a docs update. When unsure whether a change is "significant enough,"
lean toward updating — these docs are the primary way the project gets
explained to someone else.

## 4. Deployment and secrets

- **Where it's deployed:** Streamlit Community Cloud, connected to the
  GitHub repo. Pushing to the `master` branch auto-redeploys the live
  app — no manual redeploy step.
- **Where the secret API key lives:**
  - Locally: in a `.env` file (never committed — it's listed in
    `.gitignore`).
  - On the live app: in Streamlit Community Cloud's own **Secrets**
    panel (Settings → Secrets), which Streamlit exposes to the app as
    `st.secrets`.
- `config.py` is the only place that should ever read the API key — it
  checks `st.secrets` first, then falls back to `.env`. Don't read the
  key directly from `os.environ` anywhere else; route through
  `config.get_api_key()` instead.
- Never hardcode an API key in any file, ever — including notebooks,
  scratch scripts, or comments. If a key is ever accidentally exposed
  (committed, pasted, logged), treat it as compromised: it must be
  rotated in the Groq console, not just removed from the file.

## 5. Tool-calling pattern

- New tools go in `tools.py`: a plain function, a JSON-schema entry in
  `TOOLS`, and an entry in `TOOL_FUNCTIONS` mapping its name to the
  function. Don't add `if/elif` branches anywhere to route tool calls —
  routing is a dictionary lookup by design, so it never needs to change
  when a tool is added.
- If a new tool needs to know "who the current customer is," add its
  name to `tools.USER_SCOPED_TOOLS` and leave `user_id` out of its
  schema in `TOOLS` — `chatbot.execute_tool_call()` will inject it
  automatically from the sidebar selection. Tools should never rely on
  the model to ask the customer for their account ID.
