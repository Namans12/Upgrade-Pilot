from types import SimpleNamespace

from upgradepilot import ledger


def test_unpriced_model_uses_conservative_fallback(monkeypatch):
    monkeypatch.setattr(ledger, "_prices", {"known": (2e-6, 4e-6)})
    led = ledger.Ledger()
    usage = SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    known = led.record("a", "known", usage, 1.0)
    unknown = led.record("b", "mystery", usage, 1.0)
    assert (known.cost_usd, known.price_source) == (6.0, "catalog")
    assert unknown.cost_usd == 4.0 and unknown.price_source == "fallback"  # $1/M in + $3/M out, never free
    s = led.summary()
    assert s["est_cost_usd"] == 10.0 and s["fallback_priced_models"] == ["mystery"]
