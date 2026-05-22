# api_server.py
# Flask backend — receives prompt from UI via SSE, runs MCP + OpenAI loop,
# streams live tool events back to the browser.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   python api_server.py

import asyncio
import json
import os
import re
import queue
import threading

from flask import Flask, Response, request, send_from_directory
from flask_cors import CORS
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def parse_ms(val: str) -> float:
    return float(str(val).replace(" ms", "").strip())

def extract_employee_ids(prompt: str) -> list:
    return [int(n) for n in re.findall(r"\b\d+\b", prompt)]

def build_comparison_table(collected: dict) -> dict:
    rows = []

    if "bad_total_employees" in collected and "optimized_total_employees" in collected:
        bad_ms = parse_ms(collected["bad_total_employees"]["execution_time_ms"])
        opt_ms = parse_ms(collected["optimized_total_employees"]["execution_time_ms"])
        rows.append({
            "operation": "Total Employees",
            "bad_ms":    round(bad_ms, 2),
            "opt_ms":    round(opt_ms, 2),
            "saved_ms":  round(bad_ms - opt_ms, 2),
        })

    emp_ids = sorted({
        int(k.split("_")[-1])
        for k in collected
        if k.startswith("bad_get_employee_")
    })

    for eid in emp_ids:
        bad_key = f"bad_get_employee_{eid}"
        opt_key = f"optimized_get_employee_{eid}"
        if bad_key in collected and opt_key in collected:
            bad_ms = parse_ms(collected[bad_key]["execution_time_ms"])
            opt_ms = parse_ms(collected[opt_key]["execution_time_ms"])
            rows.append({
                "operation": f"Get Employee (ID={eid})",
                "bad_ms":    round(bad_ms, 2),
                "opt_ms":    round(opt_ms, 2),
                "saved_ms":  round(bad_ms - opt_ms, 2),
            })

    total_bad = sum(r["bad_ms"] for r in rows)
    total_opt = sum(r["opt_ms"] for r in rows)
    speedup   = round(total_bad / total_opt, 1) if total_opt > 0 else 0

    return {
        "rows":        rows,
        "total_bad":   round(total_bad, 2),
        "total_opt":   round(total_opt, 2),
        "total_saved": round(total_bad - total_opt, 2),
        "speedup":     speedup,
    }

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── async MCP + OpenAI runner ─────────────────────────────────────────────────

async def run_mcp_demo(prompt: str, q: queue.Queue):
    try:
        openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        server_params = StdioServerParameters(
            command="python", args=["main.py"]
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                mcp_tools = await session.list_tools()
                tools_info = [
                    {"name": t.name, "description": t.description or ""}
                    for t in mcp_tools.tools
                ]
                # ── STREAM: tools registered ──────────────────────────────
                q.put(sse("tools", {"tools": tools_info}))

                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema or {"type": "object", "properties": {}}
                        }
                    }
                    for t in mcp_tools.tools
                ]

                emp_ids = extract_employee_ids(prompt)
                # ── STREAM: IDs detected ──────────────────────────────────
                q.put(sse("ids_detected", {"ids": emp_ids}))

                system_prompt = f"""You are a database performance testing assistant.
For EVERY operation the user asks about, call BOTH the bad AND optimized versions.
Tools: bad_total_employees, optimized_total_employees, bad_get_employee, optimized_get_employee.
Employee IDs detected: {emp_ids if emp_ids else 'none'}.
Rules:
1. If total employees requested → call bad_total_employees AND optimized_total_employees
2. If employee details requested → call bad_get_employee AND optimized_get_employee for EACH ID
3. Always run bad versions first, then optimized
4. After all calls give a short plain-English summary"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt}
                ]

                collected: dict = {}

                while True:
                    response = await openai_client.chat.completions.create(
                        model="gpt-4o",
                        tools=openai_tools,
                        messages=messages,
                    )

                    choice = response.choices[0]
                    messages.append(choice.message.model_dump(exclude_unset=True))

                    if choice.finish_reason != "tool_calls":
                        # ── STREAM: summary token by token ────────────────
                        summary_text = choice.message.content or ""
                        words = summary_text.split(" ")
                        for i, word in enumerate(words):
                            chunk = word + ("" if i == len(words) - 1 else " ")
                            q.put(sse("summary_chunk", {"chunk": chunk}))
                            await asyncio.sleep(0.02)  # ~50 words/sec
                        q.put(sse("summary_done", {}))
                        break

                    tool_results = []

                    for tc in choice.message.tool_calls:
                        fn_name = tc.function.name
                        fn_args = json.loads(tc.function.arguments or "{}")

                        # ── STREAM: tool starting ─────────────────────────
                        q.put(sse("tool_start", {"name": fn_name, "args": fn_args}))

                        mcp_result  = await session.call_tool(fn_name, fn_args)
                        result_text = mcp_result.content[0].text

                        try:
                            parsed = json.loads(result_text)
                            emp_id = fn_args.get("employee_id")
                            key    = f"{fn_name}_{emp_id}" if emp_id else fn_name
                            collected[key] = parsed

                            # ── STREAM: tool done ─────────────────────────
                            q.put(sse("tool_done", {
                                "name": fn_name, "args": fn_args,
                                "key": key, "result": parsed
                            }))

                            # ── STREAM: partial table after every tool_done
                            # so the UI can update incrementally without
                            # waiting for all tools to finish
                            if len(collected) >= 2:
                                partial = build_comparison_table(collected)
                                if partial["rows"]:
                                    q.put(sse("partial_results", {
                                        "table": partial,
                                        "collected": collected
                                    }))

                        except json.JSONDecodeError:
                            q.put(sse("tool_done", {
                                "name": fn_name, "args": fn_args,
                                "key": fn_name, "result": {"raw": result_text}
                            }))

                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_text,
                        })

                    messages.extend(tool_results)

                # ── STREAM: final results (complete, authoritative) ────────
                if collected:
                    table = build_comparison_table(collected)
                    q.put(sse("results", {"table": table, "collected": collected}))

    except Exception as e:
        q.put(sse("error", {"message": str(e)}))

    finally:
        q.put(sse("done", {}))
        q.put(None)  # sentinel


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/run")
def run_stream():
    prompt = request.args.get("prompt", "").strip()
    if not prompt:
        return Response("data: {}\n\n", mimetype="text/event-stream")

    q = queue.Queue()

    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_mcp_demo(prompt, q))

    threading.Thread(target=thread_target, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",   # keep socket open for chunked stream
        }
    )


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "demo_ui.html")


if __name__ == "__main__":
    print("\n🚀 API Server running at http://localhost:5000")
    print("   Open demo_ui.html directly in your browser\n")
    app.run(
    host="0.0.0.0",
    port=5000,
    debug=False,
    threaded=True
)