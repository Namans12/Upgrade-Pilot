# Devpost submission text (draft)

**Track:** Coding and Agentic Engineering · **Also eligible for:** Best Use of Tavily

## Tagline
An agent that migrates a breaking dependency upgrade and proves it with the project's own unchanged tests.

## What it does
Dependency bots open a pull request that goes red and stop, because the breaking changes live in a migration guide the tooling never reads. UpgradePilot takes a project and a breaking version bump, searches and extracts the official migration guide with Tavily, has a Nemotron model edit the source with tools, runs the project's tests on the real target version, and loops until they pass. It then checks it didn't cheat: tests run with `--noconftest`, every file outside `app/` is hashed, writes are allowed only to `app/**/*.py`, the installed version is the target, the pass count equals the baseline count, and no deprecated or `pydantic.v1` escape hatch is left in the code. The result is a diff, cited sources, a failures-per-step strip and a measured token and cost ledger.

The bundled demo upgrades a small order service from pydantic 1.10.27 to 2.14.2: 21 tests pass before, the bump produces 3 collection errors (all 21 tests blocked) and later failures, and the agent repairs it to 21 of 21.

## How we built it
- **Models on Nebius Token Factory (OpenAI-compatible API):** `Nemotron-3_5-Lightning` reads and condenses the retrieved documentation; `nemotron-3-super-120b-a12b` runs the repair loop with tool calling (`read_file`, `write_file`, `run_tests`, `run_python`, `search_docs`).
- **Tavily:** search plus extract at runtime for every run, and again on demand inside the repair loop.
- **Verification:** deterministic checks in `verify.py` (hash of everything outside `app/`, `--noconftest`, exact baseline pass count, regex ban list for deprecated v1 APIs); a timeout or malformed output is reported as inconclusive, never as a pass.
- **Cost accounting:** token counts from each response's `usage`; prices read from Token Factory's `/v1/models?verbose=true`; costs labelled as estimates.
- **App:** FastAPI with server-sent events and a single-page UI (Research tab with Tavily hits and the checklist, a progress stepper, a failures-per-step strip, diff, sources, verification, ledger), Docker image with both environments prebuilt. 85 unit tests with no paid calls, run in GitHub Actions CI.

## What we measured
Same task, same 40-turn limit, repeated: Super passed 5 of 5 (mean about $0.08 per run, 44–80 s); Lightning passed 0 of 5 (about $0.03, stalls after fixing part of the code); Ultra passed 0 of 2 ($0.63–0.71). Counting every run of the final repair loop Super passed 16 of 17 (only the 5 benchmark runs are archived in the repo, the rest are from our own terminal logs), and its one failure cost $0.23. Ultra passed 0 of 3 counting a later run. Small samples on one task, reported as such.

## Challenges
- A first demo built on `.dict()` / `.parse_obj()` would have stayed green, since v2 only deprecates them. We rebuilt the project around real breaking changes and verified the failures before writing any agent code.
- Preventing a dishonest green: tests run with `--noconftest`, everything outside `app/` is hashed, and the agent can only write `app/**/*.py` through its tools.
- Run-to-run variance: we report failures and put a spend cap on live runs.

## Limitations
Not a security sandbox: sandboxed code gets a scrubbed environment and, in Docker, runs as an unprivileged uid (a mitigation; the Docker path was exercised only on the deployed Render instance). Bundled project only, one migration, Python only. "Passes this regression suite" is not "behaviour preserved": in the recorded run the agent's `errors.py` dropped the `value_error.number.not_ge -> too_small` mapping, which no test covers. The regex ban list is bypassable. The free Render instance sleeps, so the first load can be slow.

## What's next
Arbitrary repositories in a real container sandbox, more migrations, opening pull requests, and a router that escalates between Nemotron sizes only when a cheaper model stalls.

## Built with
Nebius Token Factory, NVIDIA Nemotron (Lightning, Super), Tavily, FastAPI, Python, uv, Docker, Render.

## Testing instructions for judges
Open https://upgradepilot.onrender.com and press **Play recorded run** (a real run captured earlier, labelled *Recorded*). For a live run, enter the access code given in the Devpost testing instructions field and press **Run live** (one at a time, daily cap, spend cap per run). The first load may take up to a minute if the free instance is asleep.
