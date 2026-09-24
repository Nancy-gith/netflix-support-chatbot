# 🎬 Netflix Support Bot

A Netflix-styled customer support chatbot built to demonstrate **LLM tool-calling** — a chatbot that doesn't just talk, but decides on its own when to look things up or take real actions using a small set of tools.

> **Fake data only.** Every customer, plan, and price in this project is made up for demo purposes. This project is not affiliated with, endorsed by, or built using any real Netflix data.

**🔗 Live demo:** [add your Streamlit Cloud URL here]

---

## Key features

- **General questions, no login required** — plan info, cancelling, payment methods, and refund policy are all answered immediately, for anyone.
- **Identification only when it matters** — asking about *your* specific plan, or changing it, prompts you to pick your name from a sidebar dropdown. Once picked, it's remembered for the rest of the session.
- **Smart recommendations, two ways** — ask for a recommendation with nothing specific in mind ("recommend me something") and it uses your saved profile; name a genre, theme, or region ("comedy," "a movie about hackers," "Bollywood action") and it answers from the model's own general knowledge instead of a tiny fixed catalog.
- **Dynamic tool routing** — the model decides *which* tool to call (or none at all) based on the conversation. Nothing is hardcoded as "if user says X, do Y."
- **Reliability where it counts** — off-topic requests are refused consistently, identity-dependent lookups never guess, and a code-level safety net backs up the model's tool-calling judgment on a demoed feature that needs to always work, not usually work.

## Tech stack

- **Python**
- **[Groq API](https://groq.com/)** — fast LLM inference, used here for tool-calling (`openai/gpt-oss-20b`)
- **[Streamlit](https://streamlit.io/)** — the chat UI, deployed on Streamlit Community Cloud

## Running it locally

```bash
git clone https://github.com/Nancy-gith/netflix-support-chatbot.git
cd netflix-support-chatbot
pip install -r requirements.txt
```

Then set up your API key:

```bash
cp .env.example .env
# edit .env and add your own Groq API key (get one free at console.groq.com)
```

And run it:

```bash
streamlit run app.py
```

## Architecture

This README stays intentionally short. For the full picture:

- **[CONTEXT.md](CONTEXT.md)** — what this project is, why it exists, and what's fake vs. real, in plain language.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how a message actually flows through the system, step by step, also in plain language.
- **[DOCUMENTATION.md](DOCUMENTATION.md)** — the full technical write-up: build history, design rationale, deployment details, and interview talking points.
- **[KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md)** — a Mermaid diagram of the actual function-level call graph between files.

## What I learned building this

This started as a small notebook experiment and grew into a project that taught me more about the *edges* of tool-calling than the happy path:

- **Tool-calling reliability isn't binary.** A well-written system prompt gets a model to call the right tool *most* of the time — but "most of the time" isn't good enough for a feature people will actually see. The biggest lesson of this project was learning where a soft prompt instruction is enough, and where it isn't.
- **Prompt-level vs. code-level guarantees are a real design decision, not just an implementation detail.** Off-topic refusal, identity checks, and a personalized-recommendation feature all *looked* like they'd work fine from a well-worded prompt — and mostly did, right up until they didn't. Each one eventually got a deterministic, code-level backstop instead of relying purely on the model's judgment in the moment. Knowing which behaviors are correctness-critical enough to deserve that is its own skill.
- **Rate limits are a real constraint, not an edge case.** Building against a free-tier API meant hitting token-per-minute, request, and token-per-day limits directly during development — which turned into a genuine debugging exercise (measuring exact token overhead, finding that tool-using turns cost roughly double, and trimming a system prompt by ~31% without breaking anything it was protecting).
- **Trimming a prompt isn't like trimming dead code.** Shortening instructions can quietly change how reliably the model follows them. One trimming pass introduced a real regression that only showed up under a specific multi-turn scenario — a reminder that prompt changes need behavioral re-testing, not just a read-through.
