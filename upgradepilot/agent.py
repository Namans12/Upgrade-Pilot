"""The upgrade pipeline: baseline -> bump -> research -> repair loop -> verify -> report."""
import difflib
import json
import os
import re
import time
from pathlib import Path
from typing import Callable

from openai import OpenAI

from . import research, sandbox, verify
from .ledger import BASE_URL, Ledger

SYSTEM = """You are UpgradePilot, an engineer migrating a Python project from {pkg} {old} to {pkg} {new}.
The project's tests are the specification and MUST NOT be changed. Fix the source files under app/ only.
Rules:
- Use native {pkg} {new} APIs. Do not import pydantic.v1 and do not leave deprecated v1 spellings
  (.dict, .parse_obj, .json, .copy, .from_orm, @validator, @root_validator, class Config, __root__).
- Keep behaviour that the tests describe, e.g. numeric ids coerced to strings, immutability, error codes.
- Work in small steps: read the failing output, read the relevant files, write the fix, run_tests.
- If a test fails and you don't know why, use run_python to print the real values (for example the actual
  validation error `type` strings) instead of guessing. Never re-run tests without changing something first.
- When run_tests reports all tests passed, reply with a one-paragraph summary and stop calling tools.
Migration notes retrieved from the official documentation:
{notes}"""

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List project files.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a project file (app/ or tests/).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file",
        "description": "Overwrite a source file under app/ with new full contents.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run the test suite on the target version.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "run_python",
        "description": "Run a short diagnostic Python snippet in the project directory on the target version, "
                       "e.g. to print real validation error types. Do not use it to edit files.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "search_docs",
        "description": "Search the web for migration documentation (Tavily).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


def failure_score(output: str) -> int:
    """Number of failing tests + collection errors in pytest's summary line."""
    return sum(int(n) for n, _ in re.findall(r"(\d+) (failed|errors?)\b", output))


STALL_RUNS = 3  # identical failure counts across this many test runs = stalled


class Pipeline:
    def __init__(self, fixture: Path, venv_old: Path, venv_new: Path, model: str, helper_model: str,
                 emit: Callable[..., None] = lambda *a, **k: None, max_turns: int = 40, budget_usd: float = 0.5,
                 fallback_model: str | None = None):
        self.fixture, self.model, self.helper_model = fixture, model, helper_model
        self.fallback_model, self.scores = fallback_model, []
        self.py_old, self.py_new = venv_old / "bin" / "python", venv_new / "bin" / "python"
        self.emit, self.max_turns, self.budget = emit, max_turns, budget_usd
        self.ledger = Ledger()
        self.client = OpenAI(base_url=BASE_URL, api_key=os.environ["NEBIUS_API_KEY"], timeout=120)
        self.sources: list = []

    # -- model plumbing ---------------------------------------------------------------
    def _chat(self, step: str, model: str, **kw):
        t = time.time()
        r = self.client.chat.completions.create(model=model, **kw)
        call = self.ledger.record(step, model, r.usage, time.time() - t)
        self.emit("model_call", step=step, model=model, prompt_tokens=call.prompt_tokens,
                  completion_tokens=call.completion_tokens, seconds=call.seconds, cost_usd=call.cost_usd)
        return r.choices[0].message

    def _over_budget(self) -> bool:
        return self.ledger.summary()["est_cost_usd"] > self.budget

    # -- tools --------------------------------------------------------------------------
    def _safe(self, work: Path, rel: str, write: bool) -> Path:
        p = (work / rel).resolve()
        root = work.resolve()
        if root not in p.parents:
            raise PermissionError("path outside project")
        top = p.relative_to(root).parts[0]
        if write and top != "app":
            raise PermissionError("writes are limited to files under app/")
        if not write and top not in ("app", "tests", "requirements.txt"):
            raise PermissionError("only app/, tests/ and requirements.txt are readable")
        return p

    def _tool(self, work: Path, name: str, args: dict) -> str:
        try:
            if name == "list_files":
                return "\n".join(sorted(str(f.relative_to(work)) for f in work.rglob("*.py")))
            if name == "read_file":
                return self._safe(work, args["path"], False).read_text()
            if name == "write_file":
                p = self._safe(work, args["path"], True)
                p.write_text(args["content"])
                return f"wrote {args['path']} ({len(args['content'])} chars)"
            if name == "run_tests":
                res = sandbox.run_tests(work, self.py_new)
                self.emit("tests", phase="repair", status=res["status"], output=res["output"])
                self.scores.append(failure_score(res["output"]))
                return f"[{res['status']}]\n{res['output']}"
            if name == "run_python":
                return sandbox.run_python(work, self.py_new, args["code"])
            if name == "search_docs":
                hits = research.search_docs(args["query"])
                self.sources += [h["url"] for h in hits]
                self.emit("search", query=args["query"], urls=[h["url"] for h in hits])
                return json.dumps(hits)
            return f"unknown tool {name}"
        except Exception as e:  # tool errors go back to the model, never crash the run
            return f"ERROR: {type(e).__name__}: {e}"

    # -- pipeline -----------------------------------------------------------------------
    def run(self, package="pydantic", old="1.10.27", new="2.14.2") -> dict:
        work = sandbox.new_workdir(self.fixture)
        original = {f: p for f, p in sandbox.hash_tree(work).items()}
        tests_hash = sandbox.hash_tree(work / "tests")
        original_app = {f: (work / f).read_text() for f in original if f.startswith("app/")}

        self.emit("stage", name="baseline", detail=f"tests on {package} {old}")
        base = sandbox.run_tests(work, self.py_old)
        self.emit("tests", phase="baseline", status=base["status"], output=base["output"])
        if base["status"] != "passed":
            return self._report(work, original_app, "inconclusive", "baseline tests are not green")

        self.emit("stage", name="bump", detail=f"tests on {package} {new}, source unchanged")
        broken = sandbox.run_tests(work, self.py_new)
        self.emit("tests", phase="bump", status=broken["status"], output=broken["output"])

        self.emit("stage", name="research", detail="Tavily search + extract")
        guide = research.find_migration_guide(package, old, new)
        self.sources.append(guide["source_url"])
        self.emit("search", query="migration guide", urls=[h["url"] for h in guide["query_hits"]],
                  extracted=guide["source_url"], chars=len(guide["page"]))
        notes = self._condense(guide["page"], broken["output"], package, old, new)
        self.emit("notes", text=notes)

        self.emit("stage", name="repair", detail=f"{self.model}")
        messages = [
            {"role": "system", "content": SYSTEM.format(pkg=package, old=old, new=new, notes=notes)},
            {"role": "user", "content": f"The tests now fail on {package} {new}:\n\n{broken['output']}\n\nFix the source."},
        ]
        outcome, reason = "inconclusive", "turn limit reached"
        for turn in range(self.max_turns):
            if self._over_budget():
                reason = "budget cap reached"
                break
            msg = self._chat(f"repair turn {turn + 1}", self.model, messages=messages, tools=TOOLS,
                             tool_choice="auto", max_tokens=6000, temperature=0.2)
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                self.emit("model_says", text=msg.content or "")
                v = verify.check(work, self.py_new, tests_hash, new)
                if v["ok"]:
                    outcome, reason = "success", "all checks passed"
                    break
                messages.append({"role": "user", "content": "Not done yet. Failed checks: " + json.dumps(
                    [c for c in v["checks"] if not c["ok"]])})
                continue
            tests_passed = False
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                self.emit("tool", name=tc.function.name, args={k: (v if len(str(v)) < 200 else str(v)[:200] + "…")
                                                               for k, v in args.items()})
                result = self._tool(work, tc.function.name, args)
                tests_passed = tests_passed or (tc.function.name == "run_tests" and result.startswith("[passed]"))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result[:8000]})
            if (self.fallback_model and self.model != self.fallback_model and len(self.scores) >= STALL_RUNS
                    and len(set(self.scores[-STALL_RUNS:])) == 1 and self.scores[-1] > 0):
                self.emit("escalate", from_model=self.model, to_model=self.fallback_model,
                          reason=f"{self.scores[-1]} failures unchanged across {STALL_RUNS} test runs")
                self.model = self.fallback_model
            if tests_passed:
                v = verify.check(work, self.py_new, tests_hash, new)
                if v["ok"]:
                    outcome, reason = "success", "all checks passed"
                    break
                messages.append({"role": "user", "content": "Tests pass but verification failed: " + json.dumps(
                    [c for c in v["checks"] if not c["ok"]])})
        v = verify.check(work, self.py_new, tests_hash, new)
        if outcome == "success" and not v["ok"]:
            outcome, reason = "inconclusive", "final verification failed"
        self.emit("verify", **v)
        return self._report(work, original_app, outcome, reason, v)

    def _condense(self, page: str, failures: str, package: str, old: str, new: str) -> str:
        msg = self._chat("condense docs", self.helper_model, max_tokens=3000, temperature=0.1, messages=[
            {"role": "system", "content": "You extract concise migration checklists from documentation."},
            {"role": "user", "content": f"Official {package} {old}->{new} migration page (may be truncated):\n\n{page}\n\n"
                f"Test failures observed after the bump:\n{failures[:2500]}\n\n"
                "List, as short bullets, ONLY the breaking changes relevant to these failures, each with the exact "
                "old -> new spelling. No preamble."}])
        return msg.content or ""

    def _report(self, work: Path, original_app: dict, outcome: str, reason: str, v: dict | None = None) -> dict:
        diff = []
        for rel, old_text in original_app.items():
            new_text = (work / rel).read_text() if (work / rel).exists() else ""
            old_text = old_text if old_text.endswith("\n") or not old_text else old_text + "\n"
            new_text = new_text if new_text.endswith("\n") or not new_text else new_text + "\n"
            diff += difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True), f"a/{rel}", f"b/{rel}")
        report = {"outcome": outcome, "reason": reason, "diff": "".join(diff), "verification": v,
                  "sources": sorted(set(s for s in self.sources if s)), "ledger": self.ledger.summary(),
                  "calls": [c.__dict__ for c in self.ledger.calls]}
        self.emit("done", **{k: report[k] for k in ("outcome", "reason", "ledger")})
        return report
