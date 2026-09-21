# What This Project Is

## The short version

This is a customer support chatbot styled after Netflix's support chat. You
type a question ("what plan am I on?", "recommend me a comedy") and it
answers you — looking things up or making changes for you where needed,
instead of just guessing.

It's a **learning project**, built to practice a specific skill in AI
engineering: teaching a chatbot to use "tools" (small helper functions) to
look up real information and take real actions, instead of only generating
text.

## What problem does it solve?

Left on its own, a chatbot can only make things up or repeat what it
already knows from training — it has no way to check your actual account,
do exact math, or change anything for you. This project solves that by
giving the chatbot a small toolbox: a calculator, a way to look up a
customer's plan, a way to change a customer's plan, and a way to recommend
shows. The chatbot decides on its own, based on what you asked, which tool
(if any) it needs to use.

That's the core thing this project demonstrates: **a chatbot that can take
real actions, not just talk.**

## Who are the "users"?

There's no real login system. Instead, there's a list of about 40 made-up
sample customers (names like "Priya Nair" or "Rohan Mehta"), each with a
fake subscription plan, billing date, and payment method. You pick one from
a dropdown in the sidebar to say "I'm chatting as this person," and the
chatbot treats you as that customer for the rest of the conversation. You
can switch to a different person at any time.

With a customer selected, you can:
- Ask what plan you're on
- Ask to change your plan (e.g. "switch me to Premium")
- Ask billing questions that need math (e.g. "what would Premium plus an
  extra member cost?")
- Ask for a show or movie recommendation based on a genre you like

## What's fake, and what's real?

| | Status |
|---|---|
| The customers, their plans, billing info | **Fake.** Made-up data, generated for this project. |
| Netflix's actual plans/shows/prices | **Not used.** Pricing in this project is a plausible made-up example, not real Netflix pricing. |
| The chatbot itself (the AI model) | **Real.** It's a real AI model (via the Groq API) making real decisions about what to say and which tool to use. |
| Any connection to the real Netflix company | **None.** This project isn't affiliated with, endorsed by, or built using any real Netflix data. It's a "Netflix-style" demo, not the real thing. |

## Why this matters as a learning project

Building this required understanding a few core ideas that show up in most
real-world AI products:
- How to hand a chatbot a set of tools and let *it* decide when to use them
- How to keep a conversation's memory going across multiple messages
- How to build a simple, working interface around it
- How to safely handle a secret API key, both while developing and after
  putting the app online for others to use

Those ideas are explained in more detail, step by step, in
[ARCHITECTURE.md](ARCHITECTURE.md).
