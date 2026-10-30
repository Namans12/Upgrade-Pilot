# Demo video narration

The demo video (about 2 minutes) shows a real live run on the deployed site (https://upgradepilot.onrender.com), time-lapsed through the repair step, with burned-in captions. It was produced with Remotion and Playwright's screen recording; the narration is synthetic (Kokoro TTS, open source). The video tooling is kept outside this repository.

Narration, in order:

1. Dependency upgrades break things. A bot opens a pull request, the tests go red, and it stops, because the fix lives in a migration guide nobody has read. UpgradePilot reads the guide, fixes the code, and proves it with the project's own, unchanged tests.
2. This is a real, live run on the deployed site. A small order service on pydantic one point ten has twenty one passing tests. UpgradePilot bumps it to pydantic two point fourteen, and the same tests break: three collection errors straight away.
3. Next, Tavily searches the official docs and extracts the migration page. Nemotron Lightning, on Nebius Token Factory, condenses it into a checklist for the failures we actually saw.
4. Then Nemotron Super takes over, with tools. It reads files, edits only the app folder, and runs the tests on the real target version, over and over. Watch the failures fall, until none are left.
5. Finally it checks that it did not cheat. The tests are byte for byte identical, the installed version is the target, and no deprecated version one code is left. Twenty one of twenty one pass, for under ten cents.
6. You get the diff, the cited source, and a measured token ledger. Token counts come straight from the API. Dollar figures are estimates from catalog prices.
7. We also compared models on the same task. Nemotron Super passed all five benchmark runs. Lightning is cheaper per run, but passed none. Ultra passed none, at six to nine times the cost. Small samples, one task.
8. A few limits. This isolates dependencies, it is not a security sandbox, and it handles one migration. And a green test suite shows the tests pass, not that every behaviour is preserved, so always review the diff.
9. UpgradePilot is open source under the MIT license. Try the recorded run at upgradepilot dot onrender dot com, and find the code on GitHub. Thanks for watching.

Notes:
- The footage is a live run, not the replay; the on-screen label says "LIVE RUN" and the repair stage is shown time-lapsed.
- A live run takes about 2.5 to 4.5 minutes end to end on the free Render instance.
