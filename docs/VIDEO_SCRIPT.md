# Demo video script (target 2:30, hard limit 3:00)

The final video is produced with Remotion from a real recorded live run of the deployed UI (https://upgradepilot.onrender.com) plus Piper TTS narration. The table below is the narration source; the Remotion project and Piper scripts are kept outside this repository. If you record by hand instead, wake the free Render instance first (open the URL a minute before recording) and use the replay or a live run if you have the access code from the Devpost testing instructions.

| Time | On screen | Say |
|---|---|---|
| 0:00-0:20 | Title, links row, the stat cards | "Dependency bots open a pull request that goes red and stop, because the breaking changes live in a migration guide nobody reads. UpgradePilot reads the guide, fixes the code, and proves it with the project's own unchanged tests." |
| 0:20-0:45 | Run starts; baseline 21 passed, then 3 collection errors after the bump (stepper and failures strip) | "This is a small order service on pydantic 1.10.27 with 21 passing tests. Bumping to 2.14.2 breaks it: three collection errors block every test, and more failures appear after the first fix. These are real v2 changes, not renamed methods." |
| 0:45-1:15 | Research tab: Tavily hits, extracted page, Lightning checklist | "It searches and extracts the official migration page with Tavily, then Nemotron Lightning on Nebius Token Factory condenses it into a checklist for the failures we actually saw." |
| 1:15-1:50 | Timeline: Super tool calls (read_file, write_file, run_tests); failures strip falling | "Nemotron Super runs the repair loop with tools: it reads files, writes only Python files under the app folder, and runs the tests on the real target version until they pass." |
| 1:50-2:15 | Integrity checks all passed, Verification tab | "Then it checks it didn't cheat: tests run without conftest files, every file outside app is hashed, the installed version is 2.14.2, the pass count matches the baseline, and no deprecated v1 API or pydantic.v1 shim is left in the code." |
| 2:15-2:40 | Diff tab, then Cost ledger tab | "The result is a diff, cited sources, and a measured token ledger. About eight cents per run. We tried Lightning and Ultra for the repair too: Lightning passed 0 of 5, Ultra 0 of 3, Super 5 of 5 in the archived benchmark, and 16 of 17 counting every run of the final loop. Small samples, reported as they came." |
| 2:40-2:55 | README limits section | "Limits: not a security sandbox, one migration, and passing a test suite is not proof of preserved behaviour: in this very run the agent dropped an error-code mapping that no test covers. Code is MIT on GitHub. Thanks." |

Notes:
- If the video shows the replay rather than a live run, say "Recorded run" aloud so the label on screen matches what you say.
- A live run takes about 45-80 s of model time; speed it up in editing or cut to the result.
- Upload to YouTube as **Public** (not Unlisted), title "UpgradePilot: Nemotron on Nebius migrates a breaking dependency upgrade".
