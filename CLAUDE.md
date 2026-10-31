# Instructions for Claude Code

This project is a Python 3 multi-agent manual-testing workflow. See README.md for the full picture.
It serves the ZATCA e-invoicing project only (Jira, QPros). Its config, secrets and runs live in
`projects/zatca/`.

## Running it
- Activate the venv first: `source .venv/bin/activate`.
- Commands: `python3 run.py check | design | resume | report | status`
  (add `--run <id>` for a specific run).
- `design` and `report` can take several minutes; run them in the background and report progress
  from their output.
- After a failure: read `projects/zatca/runs/<id>/incidents.md` and `last_error.txt`, explain the cause,
  fix it if it is in config or code, then run `python3 run.py resume --run <id>`.
  Never delete a run folder or `state.json` to "fix" a run: that throws away paid work.
- After `design` finishes, stop and tell the user to fill in `projects/zatca/runs/<id>/results.csv`.
  Run `report` only when the user says the results are ready.
  Remind the user to fill `root_cause` (and `bug_status` when known) for every Fail row:
  the quality KPIs and Pareto analysis depend on them.

- Monthly report: `python3 run.py monthly [--month YYYY-MM]`. Bugs found after
  release go in `projects/zatca/escaped_defects.csv`.

## Rules
- Run the tests after every code change: `python3 -m unittest discover -s tests -t .`
  Add or update a test for every behaviour you change.
- Never print, log or commit any `config.md`, `.env` or `secrets/` folder.
- Everything in the repository (code, comments, prompts, docs, commit messages) is in English.
- Keep the code simple and readable; prefer editing a prompt file over adding code.
- When changing an agent's JSON output format, update its validator in `qa_flow/orchestrator.py`
  and its rendering in `qa_flow/render.py`.
