# Demo video script (target 2:30, hard limit 3:00)

Record the browser at https://upgradepilot.onrender.com with a voice-over. Wake the free instance first (open the URL once a minute before recording). Use 4x speed for the replay, or a live run if you have the access code.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:20 | Title and the four stat cards | "Dependency bots open a pull request that goes red and stop, because the breaking changes live in a migration guide nobody reads. UpgradePilot reads the guide, fixes the code, and proves it with the project's own unchanged tests." |
| 0:20–0:45 | Press Play recorded run; baseline 21 passed, then 3 errors after the bump | "This is a small order service on pydantic 1.10.27 with 21 passing tests. Bumping to 2.14.2 breaks it: three collection errors and many failures. These are real v2 changes, not renamed methods." |
| 0:45–1:15 | Timeline: Tavily search and extract, Lightning checklist | "It searches and extracts the official migration page with Tavily, then Nemotron Lightning on Nebius Token Factory condenses it into a checklist for the failures we actually saw." |
| 1:15–1:50 | Timeline: Super tool calls (read_file, write_file, run_tests) | "Nemotron Super runs the repair loop with tools: it reads files, edits only the app folder, and runs the tests on the real target version until they pass." |
| 1:50–2:15 | Integrity checks all passed, Verification tab | "Then it checks it didn't cheat: tests byte-identical, installed version is 2.14.2, and no deprecated v1 API or pydantic.v1 shim left in the code." |
| 2:15–2:40 | Diff tab, then Cost ledger tab | "The result is a diff, cited sources, and a measured token ledger. About eight cents per run. We tried Lightning and Ultra for the repair too: Lightning passed 0 of 5, Ultra 0 of 2, Super 5 of 5, and 10 of 11 counting every run. Small samples, reported as they came." |
| 2:40–2:55 | README limits section | "Limits: dependency isolation, not a security sandbox, one migration, and passing a test suite is not proof of preserved behaviour. Code is MIT on GitHub. Thanks." |

Notes:
- Say "Recorded run" aloud if you use the replay, so the label on screen matches what you say.
- If you do a live run, it takes 45–80 s; speed it up in editing or cut to the result.
- Upload to YouTube as **Public** (not Unlisted), title "UpgradePilot: Nemotron on Nebius migrates a breaking dependency upgrade".
