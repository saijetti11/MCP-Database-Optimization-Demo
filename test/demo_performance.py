# demo_performance.py
# Natural language interface — OpenAI decides which MCP tools to call.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   python demo_performance.py

import asyncio
import json
import os

from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_ms(val: str) -> float:
    return float(str(val).replace(" ms", "").strip())


def print_comparison(results: dict):
    """Print a side-by-side timing table from collected tool results."""
    try:
        bad_total_ms = parse_ms(results["bad_total_employees"]["execution_time_ms"])
        bad_emp_ms   = parse_ms(results["bad_get_employee"]["execution_time_ms"])
        opt_total_ms = parse_ms(results["optimized_total_employees"]["execution_time_ms"])
        opt_emp_ms   = parse_ms(results["optimized_get_employee"]["execution_time_ms"])

        bad_combined = bad_total_ms + bad_emp_ms
        opt_combined = opt_total_ms + opt_emp_ms
        saved_ms     = bad_combined - opt_combined
        speedup      = bad_combined / opt_combined if opt_combined > 0 else float("inf")

        print("\n" + "=" * 70)
        print("📈 PERFORMANCE COMPARISON")
        print("=" * 70)
        print(f"\n{'Operation':<30} {'❌ BAD':>12} {'✅ OPTIMIZED':>14} {'Saved':>10}")
        print("-" * 70)
        print(
            f"{'Total Employees':<30}"
            f" {bad_total_ms:>10.2f}ms"
            f" {opt_total_ms:>12.2f}ms"
            f" {bad_total_ms - opt_total_ms:>8.2f}ms"
        )
        print(
            f"{'Get Employee (ID=1)':<30}"
            f" {bad_emp_ms:>10.2f}ms"
            f" {opt_emp_ms:>12.2f}ms"
            f" {bad_emp_ms - opt_emp_ms:>8.2f}ms"
        )
        
        print("-" * 70)
        print(
            f"{'TOTAL':<30}"
            f" {bad_combined:>10.2f}ms"
            f" {opt_combined:>12.2f}ms"
            f" {saved_ms:>8.2f}ms"
        )
        print(f"\n⚡ Optimized version is {speedup:.1f}x faster")
        print(f"💾 Total time saved: {saved_ms:.2f}ms")
        print(
            "\n💡 Why? BAD version opens a new DB session per request (+2 s overhead each).\n"
            "   OPTIMIZED version reuses the shared session from the MCP lifespan context."
        )
        print("=" * 70)

    except KeyError as e:
        print(f"\n⚠️  Missing tool result for comparison: {e}")


# ── main ─────────────────────────────────────────────────────────────────────

async def run_demo():

    openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    server_params = StdioServerParameters(
        command="python",
        args=["main.py"]
    )

    async with stdio_client(server_params) as (read, write): 
        async with ClientSession(read, write) as session:

            await session.initialize()

            # ── 1. Fetch MCP tools and convert to OpenAI format ──────────────

            mcp_tools  = await session.list_tools()

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

            # ── 2. User prompt ────────────────────────────────────────────────

            user_prompt = (
                "First use the bad versions to get the total number of employees "
                "and to fetch employee with ids 1 and 2. "
                "Then use the optimized versions to do the same two operations. "
                "Finally, summarise what you found."
            )

            print(f"\n🗣️  User: {user_prompt}\n")

            messages = [{"role": "user", "content": user_prompt}]

            # ── 3. Agentic loop — keep going until no more tool calls ─────────

            collected_results: dict = {}   # tool_name -> parsed JSON result

            while True:

                response = await openai_client.chat.completions.create(
                    model="gpt-4o",
                    tools=openai_tools,
                    messages=messages,
                )

                choice = response.choices[0]

                # Append assistant message
                messages.append(choice.message.model_dump(exclude_unset=True))

                # No more tool calls → print final answer and stop
                if choice.finish_reason != "tool_calls":
                    print("\n🤖 Assistant:\n")
                    print(choice.message.content)
                    break

                # ── Execute every tool call OpenAI requested ─────────────────

                tool_results = []

                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments or "{}")

                    print(f"  🔧 Calling tool: {fn_name}  args={fn_args}")

                    mcp_result = await session.call_tool(fn_name, fn_args)
                    result_text = mcp_result.content[0].text

                    # Pretty-print what the tool returned
                    try:
                        parsed = json.loads(result_text)
                        print(f"     ↳ {json.dumps(parsed, indent=6)}\n")
                        # Collect for comparison table
                        collected_results[fn_name] = parsed
                    except json.JSONDecodeError:
                        print(f"     ↳ {result_text}\n")

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })

                # Feed all tool results back into the conversation
                messages.extend(tool_results)

            # ── 4. Performance comparison table ──────────────────────────────

            if len(collected_results) == 4:
                print_comparison(collected_results)


if __name__ == "__main__":
    asyncio.run(run_demo())