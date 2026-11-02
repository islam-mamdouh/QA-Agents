# Instructions for Claude Code

This project is a Python 3 multi-agent manual-testing workflow for the ZATCA Customs Clearance
project (Fasah platform and connected customs systems, QPros). See README.md for the full picture.
One run = one Change Request (CR). Config, CR files, system knowledge and runs live in `projects/zatca/`.

## Hard rules
- No AI integration with Jira. Never add Jira API calls, connectors or automated Jira sync, and
  never suggest them. CR text is pasted by hand into `projects/zatca/crs/<CR-ID>.md`; test cases,
  bugs and evidence are entered into Jira by hand from the generated files.
- Never store passwords or credentials in code, config, docs, prompts, test cases or outputs;
  refer to "team chat" instead. Never print, log or commit `config.md`, `.env`, `crs/` or `knowledge/`
  (client documents and internal system details).
- Customs clearance scope only. Never mix data or context from any other project.
- Everything in the repository and every deliverable (test cases, bug reports, POT, UAT summaries,
  code, comments, prompts, docs, commit messages) is in English.

## Running it
- Activate the venv first: `source .venv/bin/activate`.
- New CR: make sure `projects/zatca/crs/<CR-ID>.md` exists, then `python3 run.py design --cr <CR-ID>`.
- Other commands: `python3 run.py check | resume | report | status [--cr <CR-ID> | --run <id>]`.
- `design` and `report` can take several minutes; run them in the background and report progress
  from their output.
- After a failure: read `projects/zatca/runs/<id>/incidents.md` and `last_error.txt`, explain the cause,
  fix it if it is in config or code, then run `python3 run.py resume --run <id>`.
  Never delete a run folder or `state.json` to "fix" a run: that throws away paid work.
- After `design` finishes, stop and tell the user to: send the gaps in `requirement_gaps.csv` to the
  BA/dev team, enter `test_cases.xlsx` into Jira, run the cases and fill `results.csv`
  (evidence for every executed case; actual_result, bug_id and root_cause for every Fail).
  Run `report` only when the user says the results are ready.
- Monthly report: `python3 run.py monthly [--month YYYY-MM]`. Defects found after release go in
  `projects/zatca/escaped_defects.csv` with a root cause and a 5 Whys analysis.

## Code rules
- Run the tests after every code change: `python3 -m unittest discover -s tests -t .`
  Add or update a test for every behaviour you change.
- Keep the code simple and readable; prefer editing a prompt file over adding code.
- When changing an agent's JSON output format, update its validator in `qa_flow/orchestrator.py`
  and its rendering in `qa_flow/render.py` / `qa_flow/excel.py`.
