# How It Works

This walks through the whole system in plain language: what happens, in
order, from opening the app to getting an answer.

## The journey of one message, step by step

1. **You open the app.** You see a sidebar with a dropdown of sample
   customer names. No one is selected yet — the chat area just asks you
   to pick a customer first. There's no chat box to type into until you do.

2. **You pick a name from the dropdown.** This tells the app "I'm
   chatting as this person." The chat immediately says "Hi \<name\>!" and
   the chat box appears. If you pick a different name later, the chat
   window will greet that new person too — you can switch at any point,
   mid-conversation, without losing what was said before.

3. **You type a message** and hit send, e.g. "What plan am I on?"

4. **The app sends the whole conversation so far to the AI model** —
   not just your latest message, but everything said up to this point,
   plus a short note reminding the model which customer it's currently
   talking to. This is what lets the chatbot remember earlier parts of the
   conversation (see "How the model remembers things" below).

5. **The model decides what to do.** It reads your message and either:
   - Answers directly in plain text, or
   - Decides it needs to use one of its tools first (see below)

6. **If it needs a tool**, the app runs that tool in the background —
   for example, looking up your plan in the sample database — and sends
   the result back to the model. The model then uses that result to write
   its actual answer. This can happen more than once in a row if the
   model needs several tools to fully answer you (e.g. looking up your
   plan *and* recommending a genre in the same reply).

7. **You see the final answer** appear in the chat window.

8. **The next time you type something**, the whole process repeats — and
   because the full conversation is sent again each time, the model still
   remembers everything from before.

## How the model remembers things

There's no separate "memory" system. The app just keeps a running list of
everything said in the conversation — your messages, the model's replies,
and the behind-the-scenes tool results — and sends that entire list every
time. The list *is* the memory. Nothing is ever summarized or forgotten
until you press "Reset conversation."

## How it decides which tool to use

The model isn't told "if the user says X, use tool Y." Instead, it's given
a short description of each available tool (what it does, what information
it needs) and it decides on its own, based on the conversation, whether a
tool would help. This means:
- If you don't ask anything that needs a tool, it just answers in text
- If you ask something that needs looked-up information, it calls the
  right tool by itself
- If it needs more than one tool, it can call several in a row before
  replying

## Staying on topic

The chatbot is instructed to only help with things related to this
service — plans, billing, and recommendations. If you ask it something
unrelated (write a poem, tell a joke, answer a trivia question), it
politely declines and points you back to what it can help with, every
time — even if you ask the same off-topic thing in a different way, or
ask more than once. This isn't a tool or a lookup; it's an instruction
built into how the chatbot is told to behave from the very start of the
conversation.

## What each file does

| File | What it's for, in plain terms |
|---|---|
| `app.py` | The chat screen itself — the part you actually see and click. |
| `chatbot.py` | The "brain" that talks to the AI model, decides when a tool needs to run, and runs it. Has no visual/screen code in it at all. |
| `tools.py` | The fake customer database, plus the actual tools (calculator, plan lookup, plan changer, recommender). |
| `config.py` | A small helper whose only job is finding the secret API key, wherever it's stored. |
| `.env` | Your private local copy of the secret key (never shared, never uploaded). |
| `DOCUMENTATION.md` | A deep, technical write-up of the whole project — useful for a detailed teardown. |
| `CONTEXT.md` | This project's "what and why," in plain language (you're reading its sibling file). |
| `ARCHITECTURE.md` | This file — the "how," in plain language. |

## The four tools, and when each one is used

| Tool | What it does | Gets used when you... |
|---|---|---|
| **Calculator** (`add`) | Adds two numbers together | Ask something involving billing math, like "what would two plans together cost?" |
| **Plan lookup** (`get_user_plan`) | Looks up which plan the currently-selected customer is on | Ask "what plan am I on?" or anything that needs to know your current plan first |
| **Plan changer** (`update_plan`) | Changes the currently-selected customer's plan in the sample database | Ask to switch/upgrade/downgrade your plan, and confirm you want to |
| **Recommender** (`recommend_genre`) | Suggests shows/movies from a small sample list, based on a genre you mention | Mention a genre you like, or ask for a recommendation |

Notice that the plan lookup and plan changer tools never ask you for an
account number — they automatically use whichever customer is currently
selected in the sidebar. You never have to tell the chatbot who you are in
the chat itself.

## Deployment: where the app lives, and where the secret key lives

The app is hosted on **Streamlit Community Cloud**, a free service that
runs Streamlit apps and gives you a public web link to share.

The secret API key (which lets the app talk to the AI model) is **never**
stored in the code itself, and never uploaded to GitHub. Instead:
- On your own computer, it lives in a private file called `.env`
- On the live, public version, it lives in Streamlit's own "Secrets"
  settings — a private area only the app owner can see or edit

This means anyone who visits the public link can use the chatbot without
ever needing their own key — they're using yours, safely, without ever
seeing it.

For the full technical detail behind any of this, see
[DOCUMENTATION.md](DOCUMENTATION.md).
