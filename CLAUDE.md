# Instructions for Claude Code

This project is a Python 3 multi-agent manual-testing workflow that works for any business or
product. One run = one user story. See README.md for the full picture.
The product under test is described in `workspace/config.md` (`project_context`) and
`workspace/knowledge/*.md`; settings, story files and runs also live in `workspace/`.

## Hard rules
- No tracker integration. Never add Jira, Azure DevOps or other tracker API calls, connectors or
  automated sync. User stories are pasted by hand into `workspace/stories/<STORY-ID>.md`; test
  cases, bugs and evidence are entered into the tracker by hand from the generated files.
- Keep the code and prompts business-neutral: product-specific knowledge belongs only in
  `workspace/config.md` and `workspace/knowledge/`, never in code, prompts or templates.
- Never store passwords or credentials in code, config, docs, prompts, test cases or outputs;
  refer to "team chat" instead. Never print, log or commit `config.md`, `.env`, `stories/` or
  `knowledge/` (company documents and internal system details).
- Everything in the repository and every deliverable (test cases, bug reports, POT, UAT summaries,
  code, comments, prompts, docs, commit messages) is in English.

## Running it
- Activate the venv first: `source .venv/bin/activate`.
- New story: make sure `workspace/stories/<STORY-ID>.md` exists, then
  `python3 run.py design --story <STORY-ID>`.
- Other commands: `python3 run.py check | resume | report | status [--story <STORY-ID> | --run <id>]`.
- `design` and `report` can take several minutes; run them in the background and report progress
  from their output.
- After a failure: read `workspace/runs/<id>/incidents.md` and `last_error.txt`, explain the cause,
  fix it if it is in config or code, then run `python3 run.py resume --run <id>`.
  Never delete a run folder or `state.json` to "fix" a run: that throws away paid work.
- After `design` finishes, stop and tell the user to: send the gaps in `requirement_gaps.csv` to the
  BA/dev team, enter `test_cases.xlsx` into the test management tool, run the cases and fill
  `results.csv` (evidence for every executed case; actual_result, bug_id and root_cause for every Fail).
  Run `report` only when the user says the results are ready.
- Monthly report: `python3 run.py monthly [--month YYYY-MM]`. Defects found after release go in
  `workspace/escaped_defects.csv` with a root cause and a 5 Whys analysis.

## Code rules
- Run the tests after every code change: `python3 -m unittest discover -s tests -t .`
  Add or update a test for every behaviour you change.
- Keep the code simple and readable; prefer editing a prompt file over adding code.
- When changing an agent's JSON output format, update its validator in `qa_flow/orchestrator.py`
  and its rendering in `qa_flow/render.py` / `qa_flow/excel.py`.
