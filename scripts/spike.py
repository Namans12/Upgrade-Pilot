"""Throwaway feasibility spike: Nemotron tool calling + Tavily search/extract."""
import json, os, sys, time
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

load_dotenv("../.env")
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1", api_key=os.environ["NEBIUS_API_KEY"])

TOOLS = [{"type": "function", "function": {
    "name": "edit_file",
    "description": "Replace text in a file",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
        "required": ["path", "old", "new"]}}}]

def tool_test(model):
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=model, max_tokens=400, tools=TOOLS, tool_choice="auto",
            messages=[{"role": "user", "content":
                "In app/models.py, rename the pydantic v1 call `.dict()` to the v2 equivalent `.model_dump()` "
                "on the line `return user.dict()`. Use the edit_file tool."}])
        m = r.choices[0].message
        print(f"[{model}] {time.time()-t:.1f}s usage={r.usage.prompt_tokens}/{r.usage.completion_tokens}")
        print("  tool_calls:", [(c.function.name, c.function.arguments) for c in (m.tool_calls or [])])
        if not m.tool_calls: print("  content:", (m.content or "")[:200])
    except Exception as e:
        print(f"[{model}] ERROR {type(e).__name__}: {str(e)[:300]}")

for m in sys.argv[1:]:
    tool_test(m)

tv = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
try:
    s = tv.search("pydantic v1 to v2 migration guide breaking changes", max_results=3, search_depth="basic")
    for x in s["results"]: print("TAVILY", x["url"])
    e = tv.extract(urls=[s["results"][0]["url"]])
    print("EXTRACT ok chars:", len(e["results"][0]["raw_content"]) if e.get("results") else e)
except Exception as ex:
    print("TAVILY ERROR", type(ex).__name__, str(ex)[:300])
