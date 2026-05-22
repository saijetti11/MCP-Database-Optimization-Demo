# ⚡ DB Connection Optimization Demo

See AI call your database tools live — and watch bad vs optimized queries race each other in real time.

---

## What is this?

This is a full-stack demo that shows **how MCP (Model Context Protocol) lets an AI decide which database tools to call** — and visualizes the performance difference between a bad and an optimized Postgres query, side by side, with live timing.

You type a prompt like:

> *"get total employees and details for employee id 1 and id 2"*

The AI reads your prompt, figures out which tools to call, calls them in order, and streams everything back to the browser live — tool by tool, result by result, with a comparison table that builds up in real time.

---

## How it works

```
You type a prompt
       ↓
Flask backend receives it
       ↓
OpenAI (GPT-4o) decides which tools to call
       ↓
MCP client calls your Postgres tools
       ↓
Results stream back to the browser via SSE (Server-Sent Events)
       ↓
UI updates live — tool cards, timing table, AI summary
```

There are 4 tools the AI can call:

| Tool | What it does |
|---|---|
| `bad_total_employees` | Counts rows with a slow unoptimized query |
| `optimized_total_employees` | Counts rows using an indexed, efficient query |
| `bad_get_employee` | Fetches an employee with a full table scan |
| `optimized_get_employee` | Fetches an employee using an indexed lookup |

The AI always calls the bad version first, then the optimized version, so you can see the timing difference clearly.

---

## Stack

- **MCP** — lets GPT-4o discover and call your tools dynamically
- **OpenAI GPT-4o** — decides which tools to call based on your prompt
- **Flask** — backend server that runs the MCP loop and streams events
- **SSE (Server-Sent Events)** — streams tool results to the browser in real time
- **PostgreSQL** — the database being queried (bad vs optimized)
- **Vanilla JS + HTML** — frontend UI, no framework needed

---

## Project structure

```
├── api_server.py     # Flask backend — runs the MCP + OpenAI loop, streams SSE
├── main.py           # MCP server — exposes the 4 DB tools
└── demo_ui.html      # Frontend — live tool cards, timing table, AI summary
```

---

## Getting started

**1. Clone and install dependencies**

```bash
pip install flask flask-cors openai mcp
```

**2. Set your OpenAI API key**

```bash
export OPENAI_API_KEY=sk-...
```

**3. Make sure your Postgres DB is running**

Update the connection config in `main.py` to point to your database.

**4. Start the server**

```bash
python api_server.py
```

**5. Open the UI**

Go to `http://localhost:5000` in your browser.

---

## What you'll see

- **Tool cards** light up one by one as the AI calls each tool
- **Timing results** appear as soon as each bad/optimized pair completes — no waiting for everything to finish
- **Comparison table** shows bad time, optimized time, and how much was saved
- **AI summary** types out word by word at the end, explaining what happened

---

## Why this is interesting

Most AI tool-use demos hardcode which tools get called. This one doesn't — **GPT-4o reads your prompt and decides**. If you only ask for total employees, it only calls the count tools. If you ask for specific employee IDs, it calls the lookup tools for each one. The AI adapts to what you ask.

The SSE streaming means you're not waiting for a batch response — you watch the AI work, tool by tool, in real time.

---

## Example prompts to try

```
total employees only
total employees + id 1
get details for id 1 and id 2
total employees + id 1, 2 and 3
```

---

## License

MIT — use it, modify it, learn from it.