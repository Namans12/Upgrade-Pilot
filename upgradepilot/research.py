"""Runtime documentation retrieval with Tavily (search + extract)."""
import os

from tavily import TavilyClient

MAX_EXTRACT_CHARS = 60_000


def _client() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def search_docs(query: str, max_results: int = 4, domains: list | None = None) -> list:
    """Basic-depth Tavily search; returns [{title, url, snippet}]. `domains` restricts it to official docs,
    falling back to an open search only when the restricted one finds nothing."""
    res = {"results": []}
    if domains:
        res = _client().search(query, max_results=max_results, search_depth="basic", include_domains=domains)
    if not res["results"]:
        res = _client().search(query, max_results=max_results, search_depth="basic")
    return [{"title": r["title"], "url": r["url"], "snippet": r["content"][:400]} for r in res["results"]]


def extract_page(url: str) -> str:
    res = _client().extract(urls=[url])
    if not res.get("results"):
        return ""
    return res["results"][0]["raw_content"][:MAX_EXTRACT_CHARS]


def find_migration_guide(package: str, old: str, new: str) -> dict:
    """Search for the official migration guide (official docs domain first) and extract the best page."""
    query = f"{package} migration guide {old} to {new} breaking changes"
    hits = []
    try:
        hits = _client().search(query, max_results=5, search_depth="basic", include_domains=[f"docs.{package}.dev"])["results"]
        hits = [{"title": r["title"], "url": r["url"], "snippet": r["content"][:400]} for r in hits]
    except Exception:
        pass
    if not hits:
        hits = search_docs(query)
    official = [h for h in hits if package in h["url"].split("/")[2] or "docs" in h["url"]] or hits
    url = official[0]["url"].split("#")[0] if official else None
    page = extract_page(url) if url else ""
    return {"query_hits": hits, "source_url": url, "page": page}
