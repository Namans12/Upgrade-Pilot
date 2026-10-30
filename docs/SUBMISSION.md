# Devpost submission text (draft)

**Track:** Coding and Agentic Engineering · **Also eligible for:** Best Use of Tavily

## Tagline
An agent that migrates a breaking dependency upgrade and proves it with the project's own unchanged tests.

## What it does
Dependency bots open a pull request that goes red and stop, because the breaking changes live in a migration guide the tooling never reads. UpgradePilot takes a project and a breaking version bump, searches and extracts the official migration guide with Tavily, has a Nemotron model edit the source with tools, runs the project's tests on the real target version, and loops until they pass. It then checks it didn't cheat: tests byte-identical, installed version is the target, no deprecated or `pydantic.v1` escape hatch left in the code. The result is a diff, cited sources and a measured token and cost ledger.

The bundled demo upgrades a small order service from pydantic 1.10.27 to 2.14.2: 21 tests pass before, the bump produces collection errors and failures, and the agent repairs it to 21 of 21.

## How we built it
- **Models on Nebius Token Factory (OpenAI-compatible API):** `Nemotron-3_5-Lightning` reads and condenses the retrieved documentation; `nemotron-3-super-120b-a12b` runs the repair loop with tool calling (`read_file`, `write_file`, `run_tests`, `run_python`, `search_docs`).
- **Tavily:** search plus extract at runtime for every run, and again on demand inside the repair loop.
- **Verification:** deterministic checks in `verify.py`; a timeout or malformed output is reported as inconclusive, never as a pass.
- **Cost accounting:** token counts from each response's `usage`; prices read from Token Factory's `/v1/models?verbose=true`; costs labelled as estimates.
- **App:** FastAPI with server-sent events and a single-page UI (timeline, diff, verification, ledger), Docker image with both environments prebuilt.

## What we measured
Same task, same 40-turn limit, repeated: Super passed 5 of 5 (mean about $0.08 per run, 44–80 s); Lightning passed 0 of 5 (about $0.03, stalls after fixing part of the code); Ultra passed 0 of 2 ($0.63–0.71). Counting every run of the final loop Super passed 10 of 11, and its one failure cost $0.23. Small samples on one task, reported as such.

## Challenges
- A first demo built on `.dict()` / `.parse_obj()` would have stayed green, since v2 only deprecates them. We rebuilt the project around real breaking changes and verified the failures before writing any agent code.
- Preventing a dishonest green: tests are read-only and hash-checked, and the agent can only write under `app/`.
- Run-to-run variance: we report failures and put a spend cap on live runs.

## Limitations
Not a security sandbox (dependency isolation only, bundled project only). One migration, Python only. "Passes this regression suite" is not "behaviour preserved".

## What's next
Arbitrary repositories in a real container sandbox, more migrations, opening pull requests, and a router that escalates between Nemotron sizes only when a cheaper model stalls.

## Built with
Nebius Token Factory, NVIDIA Nemotron (Lightning, Super), Tavily, FastAPI, Python, uv, Docker, Render.

## Testing instructions for judges
Open https://upgradepilot.onrender.com and press **Play recorded run** (a real run captured earlier, labelled *Recorded*). For a live run, enter the access code `<ADD CODE HERE>` and press **Run live** (one at a time, daily cap, spend cap per run). The first load may take up to a minute if the free instance is asleep.
