# What This Project Is

## The short version

This is a customer support chatbot styled after Netflix's support chat. You
type a question ("what plan am I on?", "switch me to Premium") and it
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
fake subscription plan, billing date, payment method, and (for most of
them) a saved favorite genre.

You don't have to pick one to start chatting. General questions — how
plans work, how to cancel, what payment methods are accepted, the refund
policy — are answered right away, for anyone. So is a recommendation
where you say what you want, no matter how specific ("comedy," "a movie
about a mathematician," "Bollywood action") — the chatbot just answers
from its own knowledge, no account needed. Only when you ask something
tied to *your own* account (what plan am I on, switch my plan, or a
recommendation you explicitly tie to "my profile" or "my taste" instead
of naming something) does the chatbot ask you to pick your name from a
sidebar dropdown, so it knows who it's actually helping. Once picked, it
remembers that choice for the rest of the conversation — you won't be
asked again — and you can switch to a different person at any time.

So, without picking anyone, you can:
- Ask general questions about plans, cancelling, payment methods, and refunds
- Ask for a show or movie recommendation, saying what you want — a
  genre, a theme, a regional style, anything specific

If you *have* picked who you are, you can also ask for a recommendation
without saying what you want at all ("recommend me something" — uses
your saved favorite genre automatically, from this project's small
made-up catalog, if you have one on file) or explicitly ask for
something "based on my profile" or "based on my taste." Asking that
second kind of question *without* picking anyone first gets you the
identification prompt instead of a generic answer — the chatbot won't
pretend to know your taste when it doesn't. (A handful of sample
customers have no saved genre, on purpose, so the chatbot's fallback —
just asking — has real data to show too.)

And once you've picked who you are, you can also:
- Ask what plan you're on
- Ask to change your plan (e.g. "switch me to Premium")
- Ask billing questions that need math (e.g. "what would Premium plus an
  extra member cost?")

## What's fake, and what's real?

| | Status |
|---|---|
| The customers, their plans, billing info | **Fake.** Made-up data, generated for this project. |
| Netflix's actual plans/shows/prices | **Not used.** Pricing in this project is a plausible made-up example, not real Netflix pricing. |
| Recommendations where you say what you want (a genre, a theme, anything specific) | **Real.** The chatbot suggests actual, real, well-known titles from its own knowledge — with a note that streaming availability can change, since this project isn't claiming they're on the (fake) service. |
| Recommendations where you *don't* say what you want ("recommend me something," or "based on my profile" once identified) | **Fake.** Pulled from this project's own tiny made-up catalog of titles, using a saved favorite genre from the fake customer database. |
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
