# How It Works

This walks through the whole system in plain language: what happens, in
order, from opening the app to getting an answer.

## The journey of one message, step by step

1. **You open the app.** You can start typing immediately — no sign-in,
   no picking a name first. There's a customer dropdown in the sidebar,
   but nothing requires you to touch it yet.

2. **You type a general question** and hit send, e.g. "How do I cancel?"
   or "What payment methods do you accept?" These don't need to know who
   you are, so they're answered directly — no name needed at all.

3. **The app sends the whole conversation so far to the AI model** —
   not just your latest message, but everything said up to this point.
   This is what lets the chatbot remember earlier parts of the
   conversation (see "How the model remembers things" below).

4. **The model decides what to do.** It reads your message and either:
   - Answers directly in plain text (this covers most general questions), or
   - Decides it needs to use one of its tools first (see below)

5. **If the question is personal** — "what plan am I on," "switch my
   plan," anything tied to *your* specific account — the model reaches
   for a tool that needs to know who you are. Two things can happen:
   - **If nobody's identified yet**, the app doesn't guess or make
     something up. It replies: "To look that up, I'll need to know who
     you are — please select your name from the sidebar," and the
     sidebar's name picker becomes impossible to miss (see "Identifying
     yourself" below).
   - **If you're already identified** (see next step), it just answers,
     using your account automatically.

6. **You pick your name from the sidebar dropdown**, once asked. This
   tells the app "I'm chatting as this person" for the rest of the
   session. The chat immediately says "Hi \<name\>!" — and from this point
   on, the app won't ask again. Ask the same or a different personal
   question later, and it just answers, using your identified account.

7. **For any tool the model uses** (personal or general, like a
   recommendation), the app runs it in the background and sends the
   result back to the model, which uses that result to write its actual
   answer. This can happen more than once in a row if the model needs
   several tools to fully answer you (e.g. looking up your plan *and*
   recommending a genre in the same reply).

8. **You see the final answer** appear in the chat window.

9. **The next time you type something**, the whole process repeats — and
   because the full conversation is sent again each time, the model still
   remembers everything from before, including whether you've already
   been identified.

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

## Identifying yourself — only when it's actually needed

Most of what the chatbot can help with doesn't need to know who you are:
how plans work, how to cancel, what payment methods are accepted, the
refund policy, or a recommendation based on a genre you mention. All of
that works from the very first message, with no name picked.

Three things are tied to a specific person: looking up *your* current
plan, changing *your* plan, and a recommendation explicitly based on
*your own* profile or taste rather than a genre you just mentioned. The
moment you ask one of those and nobody's identified yet, the sidebar's
caption turns into a clear prompt, and the chat gives you the same
message directly: "please select your name from the sidebar." Once you
pick a name, that choice is remembered for the rest of the session —
every later personal question just works, without asking again — and you
can still pick a *different* name at any time if you want the chatbot to
switch who it's helping.

One deliberate detail: the "please select your name" message is always
worded exactly the same way, rather than left up to the model to phrase
however it likes in the moment. That's on purpose — it keeps the request
predictable and prevents the wording from drifting to something vaguer or
less helpful on a rephrased or repeated question.

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
| **Recommender** (`recommend_genre`) | Looks up a saved favorite genre from the sample database, or asks what genre you like | Only when you ask for a recommendation without saying what you want |

Notice that the plan lookup and plan changer tools never ask you to type
an account number into the chat — they either use whoever's identified in
the sidebar automatically, or (if nobody is yet) trigger the "please
select your name" prompt described above. You never type an ID yourself
either way.

**Recommendations split into two clearly different paths, and only one
of them touches a tool at all.**

If you say what you want — a genre ("comedy"), a theme ("a movie about
hackers"), a regional style ("Bollywood action"), or anything else
specific — the chatbot doesn't use the recommend_genre tool or the
sample catalog at all. It answers straight from its own general
knowledge, with real, well-known titles that actually fit what you
asked, plus a brief, natural line noting that streaming availability can
shift over time (since, unlike a sample-catalog pick, these aren't
titles this project claims are actually on the fake service). This is
true even for a plain genre name now — the sample catalog was too small
to be a good source once something specific was said, so the chatbot's
own broader knowledge is used instead.

The recommend_genre tool only comes into play when you *don't* say
anything specific:
- **"Recommend me something"** with nothing else said — the chatbot
  checks whether you're identified and have a saved favorite genre on
  file. If so, it recommends from the small sample catalog using that,
  automatically, without asking. If not, it just asks what genre you're
  in the mood for.
- **"Recommend something based on my profile"** or **"what should I
  watch based on my taste"** — an explicit ask to use *your* saved data.
  If nobody's identified yet, the chatbot doesn't guess or answer
  generically — it triggers the exact same "please identify yourself"
  prompt used for plan lookups, since there's no profile to check without
  knowing whose it is. Once identified, it works the same as the first
  case: your saved favorite genre, from the sample catalog.

Each sample customer has a made-up "favorite genre" on file for this
(a few don't, on purpose, so the "nothing saved — just ask" path has
real data to show too).

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
