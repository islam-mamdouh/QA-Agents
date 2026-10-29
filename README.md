# QA Agents — manual testing workflow

Multi-agent workflow that turns Jira or Linear stories into reviewed manual test cases, then
turns your execution results into a professional report in Google Sheets.

One engine serves several projects. Each project has its own folder with its own config,
credentials, Google Sheet and run history, so nothing is shared between them:

```
projects/
  zatca/      config.md (Jira)    .env  secrets/  runs/  monthly/  escaped_defects.csv
  atlobha/    config.md (Linear)  .env  secrets/  runs/  monthly/  escaped_defects.csv
```

To add a project, create `projects/<name>/`, copy a `config.example.md` into it as `config.md`
and edit it.

```
Stories agent: Jira or Linear (Python, 0 tokens)
   │ stories + dependency order
   ▼
Orchestrator ──► Story analysis (Opus) ⇄ Reviewer (Sonnet)     per batch: scenarios, risk rating, questions
            ──► Test plan (Opus)      ⇄ Reviewer (Sonnet)     risk-based execution order
            ──► Test cases (Opus)     ⇄ Reviewer (Sonnet)     per batch of stories
            ──► test_cases.md, results.csv, requirement gaps, traceability matrix
                ──► Google Sheets (Gaps + Traceability tabs)  ── send the gaps to the team
            ── PAUSE: you run the tests and fill results.csv ──
            ──► Report agent (Opus) ──► Google Sheets (Results, Summary, Quality,
                                        Traceability and Gaps tabs) + bug report drafts
Monthly: all runs of the month + escaped defects ──► monthly quality report
```

Quality practices built in (from quality control and assurance): risk-based testing,
requirements traceability (ISO 9001), early requirement gap detection (prevention),
error-proofing of results and bug reports (Poka-Yoke), Pareto and root cause analysis
(fishbone categories), control charts (statistical process control), defect leakage
and an internal process audit (ISO 19011).

Review loop exit: the reviewer finds no **major** issues, or `max_review_rounds` is reached
(then the latest version is used and the open issues are written as "Reviewer notes").

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# edit projects/zatca/config.md and projects/atlobha/config.md
python3 run.py check --project zatca     # tests Claude, Jira and Google Sheets access
python3 run.py check --project atlobha   # tests Claude, Linear and Google Sheets access
```

Google Sheets: create a service account in Google Cloud, enable the Google Sheets API,
download its JSON key to `projects/<name>/secrets/service_account.json`, and share that
project's spreadsheet with the service account's email as Editor.

Linear: create a personal API key (Settings > Security & access) and put it in
`projects/atlobha/.env` as `LINEAR_API_KEY=...`. The `linear` section picks the team, the
active cycle, states and labels. Linear "blocks" relations become story dependencies.

## Usage

| Command | What it does |
|---------|--------------|
| `python3 run.py design --project zatca` | New run: steps 1-13. Ends with `test_cases.md` and `results.csv` |
| `python3 run.py design --project zatca --jql "key in (ZT-1, ZT-2)"` | Same, for specific Jira stories |
| `python3 run.py design --project atlobha --keys ATL-1,ATL-2` | Same, for specific Linear issues |
| `python3 run.py report --project zatca` | Reads your `results.csv` and writes the report (steps 14-15) |
| `python3 run.py resume --project zatca` | Continues a stopped or failed run from its last checkpoint |
| `python3 run.py status --project zatca` | Steps, review rounds, token usage, incident count |
| `python3 run.py monthly --project zatca` | Monthly quality report for the current month (`--month 2026-11` for another) |

Every command needs `--project`.

Add `--run <run-id>` to target a run other than the project's latest. `--results <file>` reads results
from another CSV.

### Before testing: requirement gaps
`design` writes `requirement_gaps.csv` (and a **Gaps** tab in Google Sheets) with every question
found while analysing the stories. Send them to the BA/dev team, then record each answer in the
CSV and set `status` to `open`, `answered` or `closed`. Answers you entered are kept if design
runs again. Each gap caught here is a defect prevented before testing.

### Recording results
Open `projects/<name>/runs/<run-id>/results.csv` (Excel or Google Sheets, save as CSV). For each test case
fill `status` (Pass, Fail, Blocked, Skipped; empty = Not Run), `actual_result`, `bug_id`,
`notes` — in your own words, the report agent rewrites them professionally.

For every **Fail** row also fill:
- `root_cause` — where the defect came from (fishbone category): `requirements`, `design`, `code`,
  `environment`, `data`, `integration`, `test` or `other`.
- `bug_status` — when known: `open`, `fixed`, `rejected` (not a bug) or `reopened` (failed retest).

**Error-proofing** (`flow.strict_results: true`, the default): the report stops and lists the rows
to fix when a Fail row has no `actual_result`, `bug_id` or `root_cause`, or a Blocked row does
not say why. You can run `report` again after editing the file; the report is regenerated.

The report also writes `bug_reports.md`: a ready-to-paste bug report for every failed case
(steps, expected and actual result, severity, environment), following
`templates/bug_report_template.md`.

## Quality analysis

Every report includes a **Quality** tab in Google Sheets (and the same tables in `report.md`),
calculated in Python from the results, with no tokens spent:

| KPI | What it shows |
|-----|---------------|
| Requirements coverage | Stories in scope that have test cases |
| Scenario coverage | Analysed scenarios that have at least one test case |
| Stories fully executed | Stories whose test cases were all executed |
| Execution rate / Pass rate / Blocked rate | How much was tested and how it went |
| Defect density | Failed test cases per story |
| Critical + major share | How serious the failures are |
| Requirement gaps found early | Questions raised in story analysis, i.e. defects prevented before testing |
| Requirement gaps resolved | Gaps answered or closed by the team |
| Bug rejection rate | Bugs rejected as not a bug: lower means more accurate reporting |
| Bug reopen rate | Fixed bugs that failed retest |
| Root cause recorded | How complete the root cause data is |

- **Pareto (80/20)** by story and by root cause marks the "vital few" that cause about 80% of the
  failures: focus regression testing and process fixes there.
- **Severity distribution** of the failed cases.
- The report agent adds **improvement actions** aimed at the vital-few root causes
  (prevent the defect, not only fix it).

### Risk-based testing
The story analysis agent rates each story's **impact** and **likelihood** of defects (1-5).
Python calculates `risk score = impact x likelihood` (high >= 15, medium >= 8, low below).
Higher-risk stories are tested first and more deeply; the risk is shown in the test plan,
the test cases and the traceability matrix.

### Traceability matrix
`traceability.md` and the **Traceability** tab link every story to its scenarios, test cases,
results, bugs and open gaps, with a coverage status (Not covered, Covered - not executed yet,
Partially executed, Blocked, Failed, Passed). It is written after design and updated by the report.

## Monthly quality report

```bash
python3 run.py monthly --project zatca                  # current month
python3 run.py monthly --project zatca --month 2026-11
```

Add every bug found **after release** (by users, support, production) to
`projects/<name>/escaped_defects.csv` (created empty the first time):
`date` (YYYY-MM-DD), `bug_id`, `title`, `severity`, `story`, `root_cause`, `found_by`, `notes`.

The report (`projects/<name>/monthly/<month>/monthly_report.md` and a **Monthly** tab) contains:
- KPIs with last month's value: pass rate, coverage, defects found, **defect leakage**
  (escaped / all defects), **defect detection effectiveness**, gaps, rejection and reopen rates.
- **Control chart** (c-chart) of failed cases per run, with the centre line and 3-sigma limits;
  a run above the upper limit is a signal to investigate.
- **Pareto** by root cause over testing and escaped defects.
- An automatic **process audit** (Yes / No / n/a with evidence) and improvement actions from the agent.

For the manual part of the audit use `templates/monthly_audit_checklist.md`.

## Run folder

```
projects/<name>/runs/<run-id>/
  stories.md        stories with dependencies (step 1)
  test_plan.md      approved test plan
  test_cases.md     test cases to run
  results.csv       your results
  requirement_gaps.csv / .md   questions for the team, with status and answers
  traceability.md   requirements traceability matrix
  report.md         local copy of the report, including quality KPIs and Pareto
  bug_reports.md    bug report drafts for every failed case
  incidents.md      retries, fire-backs, review limits, failures
  state.json        checkpoint: step status, review round, token usage
  artifacts/        JSON output of every step
```

## Reliability

- **Checkpoints / failover**: every step and every review round is saved (atomic writes).
  After a crash, `Ctrl+C` or an error, `resume` continues from the exact point - finished
  batches and rounds are never paid for twice.
- **Retries**: network errors, rate limits (429) and server errors (5xx) from Claude, Jira, Linear and
  Google Sheets are retried with exponential backoff (`api_retries`), honouring `Retry-After`.
- **Fire-back**: if an agent's reply is not valid JSON or misses required content (e.g. a story
  was skipped), its reply is sent back with the problem to fix (`max_fire_back`).
- **Incidents**: one table per run in `incidents.md`; failures also write `last_error.txt`.

## Token savings

- Jira/Linear fetching and dependency ordering are plain Python (no LLM).
- Jira rich text is converted to plain text, long descriptions are trimmed, empty fields dropped.
- Agents receive compact JSON and only what they need (e.g. the test plan gets scenario titles,
  not full analyses; dependent stories are passed as key + summary only).
- Work is batched by story, so each call and each revision stays small.
- A revision gets the input + its last output + reviewer issues, not the whole history.
- System prompts are cached (prompt caching).
- Test case IDs, statistics and sheet formatting are done in Python; only rows with notes
  or failures go to the report agent.

## Editing

| To change | Edit |
|-----------|------|
| What an agent does | `prompts/<agent>.md` |
| What a reviewer checks | `prompts/review_<stage>.md` (shared rules: `reviewer_base.md`) |
| Models, batch sizes, rounds, retries, product context | `projects/<name>/config.md` |
| Where stories come from | `qa_flow/jira_agent.py`, `qa_flow/linear_agent.py` |
| Step order / flow | `qa_flow/orchestrator.py` |
| Markdown output layout | `qa_flow/render.py` |
| Sheet columns and style | `qa_flow/sheets.py` |
| Quality KPIs and Pareto | `qa_flow/quality.py` |
| Root cause and bug status options | `qa_flow/results.py` |
| Risk levels | `qa_flow/risk.py` |
| Traceability matrix and gaps | `qa_flow/traceability.py` |
| Monthly report and process audit | `qa_flow/monthly.py`, `prompts/monthly_summary.md` |
| Bug report and audit templates | `templates/` |

If you change a prompt's JSON output format, update the matching `check_*` validator in
`orchestrator.py` and `render.py`.

## Tests

The tool is tested itself: configuration, Jira and Linear parsing, results checks, risk, KPIs,
Pareto, traceability, monthly report, Google Sheets output and a full design-to-report run with
fake agents. No network, Claude or Google access is needed.

```bash
python3 -m unittest discover -s tests -t .
```

Run them after every change, before committing.
