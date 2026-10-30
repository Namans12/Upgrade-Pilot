"""Runtime documentation retrieval with Tavily (search + extract)."""
import os

from tavily import TavilyClient

MAX_EXTRACT_CHARS = 60_000


def _client() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def search_docs(query: str, max_results: int = 4) -> list:
    """Basic-depth Tavily search; returns [{title, url, snippet}]."""
    res = _client().search(query, max_results=max_results, search_depth="basic")
    return [{"title": r["title"], "url": r["url"], "snippet": r["content"][:400]} for r in res["results"]]


def extract_page(url: str) -> str:
    res = _client().extract(urls=[url])
    if not res.get("results"):
        return ""
    return res["results"][0]["raw_content"][:MAX_EXTRACT_CHARS]


def find_migration_guide(package: str, old: str, new: str) -> dict:
    """Search for the official migration guide and extract the best page."""
    hits = search_docs(f"{package} {old} to {new} migration guide breaking changes")
    official = [h for h in hits if package in h["url"].split("/")[2] or "docs" in h["url"]] or hits
    page = extract_page(official[0]["url"]) if official else ""
    return {"query_hits": hits, "source_url": official[0]["url"] if official else None, "page": page}
