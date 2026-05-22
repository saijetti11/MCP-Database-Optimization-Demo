# demo_performance.py
# Dynamic version — handles any number of employee IDs from the prompt.
# Also writes results to demo_results.json for the UI to consume.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   python demo_performance.py

import asyncio
import json
import os
import re

from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ── helpers ───────────────────────────────────────────────────────────────────

def parse_ms(val: str) -> float:
    return float(str(val).replace(" ms", "").strip())


def extract_employee_ids(prompt: str) -> list[int]:
    """Pull every integer that looks like an employee ID from the user prompt."""
    return [int(n) for n in re.findall(r"\b\d+\b", prompt)]


def build_comparison_table(collected: dict) -> dict:
    """
    collected = {
        "bad_total_employees":      {...},
        "optimized_total_employees":{...},
        "bad_get_employee_1":       {...},
        "optimized_get_employee_1": {...},
        "bad_get_employee_2":       {...},
        "optimized_get_employee_2": {...},
        ...
    }
    Returns a structured dict ready for JSON / UI rendering.
    """
    rows = []

    # Total employees row
    if "bad_total_employees" in collected and "optimized_total_employees" in collected:
        bad_ms = parse_ms(collected["bad_total_employees"]["execution_time_ms"])
        opt_ms = parse_ms(collected["optimized_total_employees"]["execution_time_ms"])
        rows.append({
            "operation": "Total Employees",
            "bad_ms":    round(bad_ms, 2),
            "opt_ms":    round(opt_ms, 2),
            "saved_ms":  round(bad_ms - opt_ms, 2),
            "data": {
                "bad": collected["bad_total_employees"],
                "opt": collected["optimized_total_employees"],
            }
        })

    # One row per employee ID
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
                "data": {
                    "bad": collected[bad_key],
                    "opt": collected[opt_key],
                }
            })

    total_bad = sum(r["bad_ms"] for r in rows)
    total_opt = sum(r["opt_ms"] for r in rows)
    speedup   = round(total_bad / total_opt, 1) if total_opt > 0 else 0

    return {
        "rows":       rows,
        "total_bad":  round(total_bad, 2),
        "total_opt":  round(total_opt, 2),
        "total_saved":round(total_bad - total_opt, 2),
        "speedup":    speedup,
    }


def print_table(table: dict):
    print("\n" + "=" * 70)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 70)
    print(f"\n{'Operation':<30} {'❌ BAD':>12} {'✅ OPTIMIZED':>14} {'Saved':>10}")
    print("-" * 70)
    for row in table["rows"]:
        print(
            f"{row['operation']:<30}"
            f" {row['bad_ms']:>10.2f}ms"
            f" {row['opt_ms']:>12.2f}ms"
            f" {row['saved_ms']:>8.2f}ms"
        )
    print("-" * 70)
    print(
        f"{'TOTAL':<30}"
        f" {table['total_bad']:>10.2f}ms"
        f" {table['total_opt']:>12.2f}ms"
        f" {table['total_saved']:>8.2f}ms"
    )
    print(f"\n⚡ Optimized version is {table['speedup']}x faster")
    print(f"💾 Total time saved: {table['total_saved']}ms")
    print("=" * 70)


# ── main ──────────────────────────────────────────────────────────────────────

async def run_demo():

    openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    server_params = StdioServerParameters(
        command="python",
        args=["main.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            mcp_tools = await session.list_tools()

            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema or {"type": "object", "properties": {}}
                    }
                }
                for tool in mcp_tools.tools
            ]

            print("\n" + "=" * 70)
            print("🚀 DATABASE OPTIMIZATION DEMO  (OpenAI + MCP)")
            print("=" * 70)
            print("\n📊 AVAILABLE TOOLS:\n")
            for t in mcp_tools.tools:
                print(f"  • {t.name}")

            # ── prompt ────────────────────────────────────────────────────────

            user_prompt = input("\n🗣️  Your prompt: ").strip()
            if not user_prompt:
                user_prompt = (
                    "Get total employees and details for employee id 1 and id 2. "
                    "Use both bad and optimized versions for every operation."
                )
                print(f"   (using default: {user_prompt})")

            emp_ids = extract_employee_ids(user_prompt)

            # Build a detailed system prompt so the LLM knows to call both
            # bad + optimized variants for every requested operation
            system_prompt = f"""You are a database performance testing assistant.

The user wants to compare BAD vs OPTIMIZED database tool performance.

For EVERY operation the user asks about, you MUST call BOTH the bad version AND the optimized version.

Tools available:
- bad_total_employees         → gets total employee count (slow, new session)
- optimized_total_employees   → gets total employee count (fast, shared session)
- bad_get_employee            → gets employee by ID (slow, new session)
- optimized_get_employee      → gets employee by ID (fast, shared session)

Employee IDs detected in the user request: {emp_ids if emp_ids else "none specifically mentioned"}

Rules:
1. If the user asks for total employees → call bad_total_employees AND optimized_total_employees
2. If the user asks for employee details → call bad_get_employee AND optimized_get_employee for EACH ID
3. Always run bad versions first, then optimized versions
4. After all tool calls, give a short plain-English summary of what you found
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ]

            print(f"\n🔍 Detected employee IDs: {emp_ids}\n")

            # ── agentic loop ──────────────────────────────────────────────────

            # key = "bad_total_employees" | "bad_get_employee_{id}" | etc.
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
                    print("\n🤖 Assistant:\n")
                    print(choice.message.content)
                    break

                tool_results = []

                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments or "{}")

                    print(f"  🔧 Calling: {fn_name}  args={fn_args}")

                    mcp_result  = await session.call_tool(fn_name, fn_args)
                    result_text = mcp_result.content[0].text

                    try:
                        parsed = json.loads(result_text)
                        print(f"     ↳ result: {json.dumps(parsed, indent=6)}\n")

                        # Build a unique key so we can track per-ID results
                        emp_id = fn_args.get("employee_id")
                        key    = f"{fn_name}_{emp_id}" if emp_id else fn_name
                        collected[key] = parsed

                    except json.JSONDecodeError:
                        print(f"     ↳ {result_text}\n")

                    tool_results.append({
                        "role":         "tool",
                        "tool_call_id": tc.id,
                        "content":      result_text,
                    })

                messages.extend(tool_results)

            # ── comparison table ──────────────────────────────────────────────

            if collected:
                table = build_comparison_table(collected)
                print_table(table)

                # Write results to JSON for the UI
                output = {
                    "prompt":    user_prompt,
                    "emp_ids":   emp_ids,
                    "collected": collected,
                    "table":     table,
                }
                with open("demo_results.json", "w") as f:
                    json.dump(output, f, indent=2)

                print("\n📁 Results saved to demo_results.json")
                print("🌐 Open demo_ui.html in your browser to see the visual report.\n")


if __name__ == "__main__":
    asyncio.run(run_demo())