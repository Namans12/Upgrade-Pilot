# Feedback on Nebius Token Factory, NVIDIA Nemotron and Tavily

Notes from building UpgradePilot on 30 October 2026. Observed, not assumed; please correct anything we misread.

## Token Factory

1. **Model ID friction.** The IDs returned by `/v1/models` mix casing and separators: `nvidia/Nemotron-3_5-Lightning` (underscore, display name "Nemotron-3.5-Lightning"), `nvidia/nemotron-3-super-120b-a12b` (lowercase), `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/Nemotron-3.5-Super-VL`. The agent-cost cookbook lists IDs without the `nvidia/` prefix. A copy-paste ID per model on the catalog page would remove a 10-minute detour. *Suggestion:* show the exact API string next to each model with a copy button.
2. **Pricing is hard to find programmatically.** The public pricing page rendered no text for our fetch. The `GET /v1/models?verbose=true` response includes `pricing` (prompt, completion, `input_cache_read`) per token, context length and rate limits, which is exactly what we needed for a live cost ledger, but we only found it by trying the flag. *Suggestion:* document `verbose=true` in the quickstart.
3. **`usage` is present on every response**, so a measured token ledger was trivial. Good.
4. **Cookbook inconsistency.** The invoice-validation cookbook says the script default is MiniMax-M3 in one place and the retired Qwen2.5-VL-72B in another. Users following it hit a retired model.
5. **Latency was fine.** Lightning and Super answered tool-call requests in roughly 1.2–1.7 s for ~500-token prompts.
6. **Input tokens dominate agent cost.** A 27–30 call repair run used ~240–330k prompt tokens versus 8–10k completion tokens. The catalog lists an `input_cache_read` price; it was not obvious how to make a loop benefit from it (is prefix caching automatic? what prefix length qualifies?). *Suggestion:* a short doc and a cached-token field in `usage` for agent loops.

## NVIDIA Nemotron

1. **Tool calling worked first try** on Lightning and Super: valid JSON arguments for a function schema on the first request.
2. **Lightning is cheap but stalls on multi-file repairs.** In our fixture it fixed models and tags, then re-ran the same failing tests without editing. It passed 0 of 5 repeated runs (all hit the 40-turn limit, ~$0.03 each), and 0 of 2 more when allowed to escalate to Super. Super passed 5 of 5 in the benchmark (mean $0.079, 44–80 s) and 16 of 17 counting every run of the final repair loop (only the 5 benchmark runs are archived in the repo; the rest are from our terminal logs); the one failure ran 41 calls for $0.23 before the turn limit, so runaway cost is a real tail risk for agent loops.
3. **Ultra did not help here.** It passed 0 of 3 (41 calls each, $0.47–$0.71, roughly 6–9× a Super run) and hit the turn limit every time. One task and few runs, so we make no general claim. It may do better with a different prompt or harness; we did not tune per model.
4. **Reasoning/`<think>` handling.** We did not need to strip reasoning from responses, but we did not test long-running reasoning modes. Nothing to report.
5. **Avoid `deepagents` with Ultra.** The agent-cost cookbook documents a `NemotronPolicyNudgeMiddleware` issue (deepagents issue 5982). We sidestepped it by writing a small tool loop directly against the OpenAI SDK, which also made token accounting simple.

## Tavily

1. Search plus extract on the official Pydantic migration page worked on the first call: the right page ranked first and extract returned ~49k characters.
2. Extract output is large; we truncate to 60k characters and have a cheap model condense it. A relevance-filtered extract (return only sections matching a query) would save a model call.
3. The free dashboard shows 1,000 credits per month and no card needed, which made the hackathon integration painless. The Builder Program credit email said "within two business days", too late for a one-day event; pointing participants to the free Tavily signup would help.

## Docs and process

- The hackathon page said "about 20 hours to deadline" while the Official Rules gave 10:00 am PT; they agree (10:30 pm IST), but the time zone on the Devpost page was easy to misread.

## Tavily: result relevance
An unrestricted search for "pydantic migration guide 1.10.27 to 2.14.2" returned blogs and a Pydantic *AI* changelog on our first deployed run, and the agent still passed but cited the wrong page. Using `include_domains=["docs.pydantic.dev"]` returned the official migration page first. A documented pattern for "official docs only" retrieval would help agent builders.
