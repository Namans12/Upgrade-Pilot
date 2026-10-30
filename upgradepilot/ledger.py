"""Token and cost ledger. Token counts are measured (API `usage`); dollar costs
are estimates computed from the Token Factory catalog's per-token prices."""
import os
import time
from dataclasses import dataclass, field

import httpx

BASE_URL = "https://api.tokenfactory.nebius.com/v1"
_prices: dict = {}
# Conservative per-token price for models missing from the catalog ($1.00/M input, $3.00/M output),
# so the budget cap still bites instead of seeing a free model.
FALLBACK_PRICE = (1.00 / 1e6, 3.00 / 1e6)


def load_prices() -> dict:
    """{model_id: (prompt_price, completion_price)} per token, from the verbose catalog."""
    if not _prices:
        r = httpx.get(f"{BASE_URL}/models", params={"verbose": "true"}, timeout=30,
                      headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}"})
        r.raise_for_status()
        for m in r.json()["data"]:
            p = m.get("pricing") or {}
            if p.get("prompt") is not None:
                _prices[m["id"]] = (float(p["prompt"]), float(p["completion"]))
    return _prices


@dataclass
class Call:
    step: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    cost_usd: float
    price_source: str = "catalog"  # "fallback" = model not in the catalog, cost is a conservative estimate


@dataclass
class Ledger:
    calls: list = field(default_factory=list)

    def record(self, step: str, model: str, usage, seconds: float) -> Call:
        prices = load_prices()
        (pp, cp), source = (prices[model], "catalog") if model in prices else (FALLBACK_PRICE, "fallback")
        pt, ct = usage.prompt_tokens, usage.completion_tokens
        call = Call(step, model, pt, ct, round(seconds, 2), pt * pp + ct * cp, source)
        self.calls.append(call)
        return call

    def summary(self) -> dict:
        by_model: dict = {}
        for c in self.calls:
            m = by_model.setdefault(c.model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
            m["calls"] += 1
            m["prompt_tokens"] += c.prompt_tokens
            m["completion_tokens"] += c.completion_tokens
            m["cost_usd"] += c.cost_usd
        return {"calls": len(self.calls),
                "prompt_tokens": sum(c.prompt_tokens for c in self.calls),
                "completion_tokens": sum(c.completion_tokens for c in self.calls),
                "est_cost_usd": round(sum(c.cost_usd for c in self.calls), 6),
                "seconds": round(sum(c.seconds for c in self.calls), 1),
                "fallback_priced_models": sorted({c.model for c in self.calls if c.price_source == "fallback"}),
                "by_model": by_model}


def now() -> float:
    return time.time()
