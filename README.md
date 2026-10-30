# UpgradePilot

**An agent that migrates a breaking dependency upgrade and proves it with the project's own, unchanged tests.**

Built for the Nebius x NVIDIA Global AI Hackathon · Track: Coding and Agentic Engineering · Runs on **Nebius Token Factory** with **NVIDIA Nemotron** models, and uses **Tavily** at runtime.

Dependency bots open a pull request that goes red and stop there, because the breaking changes live in a migration guide the tooling never reads. UpgradePilot reads the guide, edits the code, runs the tests on the real target version, and loops until they pass, then checks it didn't cheat.

## What happens in a run

```
1 baseline   tests on pydantic 1.10.27           must be green
2 bump        same tests on pydantic 2.14.2       3 collection errors / many failures
3 research    Tavily search + extract the official migration page
              → Nemotron Lightning condenses it into a checklist for the observed failures
4 repair      Nemotron Super edits app/*.py with tools (read_file, write_file, run_tests,
              run_python, search_docs) until the tests pass
5 verify      tests byte-identical · installed version is the target · no deprecated v1 API left
              in app/ · no pydantic.v1 shim · tests green on the target version
6 report      diff, cited sources, and a measured token / estimated cost ledger
```

The demo project (`demo/pydantic_service`) is a small order service written for pydantic v1 with 21 tests. The breakages are real v2 behaviour changes (`Field(regex=…)` and `min_items` removed, `__root__` models removed, `Optional[X]` now required, int→str coercion gone, `allow_mutation` removed, error `type` strings changed) mixed with deprecated-but-working calls as a control. A hand-written solution (`demo/pydantic_service_solution`) is used only to prove the task is solvable; the agent never sees it.

## How it uses Nebius and NVIDIA

| Role | Model on Token Factory | Why |
|---|---|---|
| Read docs, write the checklist | `nvidia/Nemotron-3_5-Lightning` | Cheapest model, long input, one call per run |
| Repair loop (tool calling) | `nvidia/nemotron-3-super-120b-a12b` | Most reliable at editing and iterating in our trials |

All calls go through the OpenAI-compatible endpoint `https://api.tokenfactory.nebius.com/v1`. Token counts come from each response's `usage` field. Dollar costs are **estimates** computed from per-token prices that Token Factory returns from `GET /v1/models?verbose=true`.

### Measured on this fixture (small samples, October 30 2026)

Counts are for the final version of the loop. Two earlier Super runs on a previous version (one reached green but the loop didn't notice, one stopped at a 25-turn limit with 20/21 passing) are excluded.

Each row is repeated independent runs of the same task with a 40-turn limit (`scripts/bench.py`, results in `runs/bench.json`).

| Repair model | Passed | Calls | Est. cost per run | Model time |
|---|---|---|---|---|
| Super (`nemotron-3-super-120b-a12b`) | **5 / 5** | 21–34 | $0.043–0.122 (mean $0.079) | 44–80 s |
| Lightning (`Nemotron-3_5-Lightning`) | 0 / 5, all hit the turn limit | 41 | $0.028–0.031 | 96–206 s |
| Ultra (`Nemotron-3-Ultra-550b-a55b`) | 0 / 2, both hit the turn limit | 41 | $0.634–0.709 | 100–107 s |

Earlier development runs agree (Super 3/3 more passes, Lightning with Super escalation 0/2, one more Ultra run 0/1 at $0.47) but are not included in the table. Five runs is not a rigorous benchmark and covers one task, but the gap is large. It is why Lightning does the cheap reading and Super does the repair, and why Ultra is not in the default path. Input tokens dominate cost (roughly 240–330k prompt tokens versus 8–10k completion tokens per run).

## Tavily

`upgradepilot/research.py` calls Tavily search and extract at runtime for every run to find and read the official migration page, and the agent can call `search_docs` again mid-repair. Retrieved URLs are listed in the result.

## Run it

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), a Nebius Token Factory key and a Tavily key.

```bash
git clone <this repo> && cd upgradepilot
cp .env.example .env            # add NEBIUS_API_KEY and TAVILY_API_KEY
uv sync
./scripts/build_envs.sh         # builds the pydantic 1.x and 2.x test environments
uv run python -m upgradepilot.cli                       # one live run in the terminal
UP_ACCESS_CODE=choose-a-code uv run uvicorn upgradepilot.server:app --port 8123   # web UI
```

Open the UI and press **Play recorded run** (a real run captured earlier, clearly labelled *Recorded*), or enter the access code and press **Run live**. Live runs are limited to one at a time and a daily cap, and each stops at a per-run spend cap.

Deploy: the `Dockerfile` bakes both environments into the image and reads `NEBIUS_API_KEY`, `TAVILY_API_KEY` and `UP_ACCESS_CODE` from the environment.

To re-record: `uv run python scripts/record.py`.

## Honest limits

- **Passing means** "passes this regression suite on the target version, tests unmodified", not that behaviour is preserved in general.
- **Not a security sandbox.** Model-edited code runs in a subprocess with a scrubbed environment (no API keys) and a timeout, in a prebuilt virtualenv. That isolates dependencies, not the host. For this reason only the bundled project can be upgraded; there is no arbitrary-repository input.
- One migration, Python only. Dependency pinning is read from prebuilt environments rather than resolved at run time.
- Model output varies from run to run. The diffs are real but not always elegant (one run used `object.__setattr__` to set a computed field on a frozen model); read them.
- The verification guard rejects deprecated v1 spellings in `app/`. That is a deliberate stricter-than-tests standard for "migrated".

## Layout

```
upgradepilot/   agent.py (pipeline + tools)  sandbox.py  research.py (Tavily)  verify.py  ledger.py  server.py  runner.py  cli.py
web/index.html  single-page UI (timeline, diff, verification, cost ledger)
demo/           pydantic_service (v1 project + tests) · pydantic_service_solution (reference only)
recordings/     a real run for replay
scripts/        build_envs.sh · record.py · spike.py (throwaway feasibility check)
docs/           FEEDBACK.md
```

License: MIT.
