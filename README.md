# QA Agents — manual testing workflow driven by user stories

A multi-agent manual-testing workflow that works for any business or product. One run = one
**user story**:

1. you paste the user story text into a file (no integration with Jira, Azure DevOps or any tracker);
2. the agents analyse the story, write a test plan and test cases in an Excel file you enter or
   import into your test management tool;
3. you run the cases manually and record the results;
4. the agents produce the POT (proof of testing), bug reports ready to paste into your tracker,
   a one-page UAT / review meeting summary and a quality report.

The business is described in `workspace/config.md` (`project_context`) and, optionally, in
short system-knowledge files. To use it for another product, change those two; the code and
the prompts stay the same.

```
User story file (you paste it, 0 tokens)
   │
   ▼
Orchestrator ──► Story analysis (Opus) ⇄ Reviewer (Sonnet)  flow steps, systems, requirements,
            │                                               risk, regression areas, gaps for the BA/dev
            ──► Test plan (Opus)      ⇄ Reviewer (Sonnet)    flow order, systems, entry/exit criteria
            ──► Test cases (Opus)     ⇄ Reviewer (Sonnet)    per batch of requirements + regression
            ──► test_cases.xlsx  story_analysis.md  requirement_gaps.csv  results.csv
            ── PAUSE: send gaps to the BA/dev, run the cases, fill results.csv ──
            ──► Report rows (Opus) ──► UAT summary (Opus)
            ──► pot.xlsx  bug_reports.md  uat_summary.md  quality.md
Monthly: all story runs of the month + escaped defects ──► monthly_report.md + monthly.xlsx
```

Review loop exit: the reviewer finds no **major** issues, or `max_review_rounds` is reached
(then the latest version is used and the open issues are written as "Reviewer notes").

Quality practices built in: QA before QC (story review and gap log before development finishes),
risk-based testing, requirements traceability (ISO 9001, plan-do-check-act), error-proofing of
results and bug reports (Poka-Yoke), Pareto by module and root cause, root cause analysis
(5 Whys, fishbone categories), control chart of defects per build, Lean waste, and a monthly
internal process audit (ISO 19011).

## Rules this tool follows

- No tracker integration: stories are pasted into files by hand, and test cases, bugs and evidence
  are entered into the tracker by hand from the generated files.
- Deliverables are in English. Unclear business rules become questions for the BA / product owner,
  the dev team or the documentation, never guesses.
- No credentials anywhere (config, docs, test cases, bug reports). Accounts are named by role,
  with "credentials: see team chat".
- Story files and system knowledge often describe company systems, so they are git-ignored and
  stay on your machine.

## Setup

The agents run through the **Claude Code CLI** with your Claude login. No API key is needed.

```bash
claude            # then type /login once and follow the steps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp workspace/config.example.md workspace/config.md   # then describe your product in it
python3 run.py check     # tests the config, the Claude Code login and the stories folder
```

Optional but recommended: put short system-knowledge notes (screens, APIs, DB tables and status
codes) in `workspace/knowledge/*.md`. Every agent reads them.

```
workspace/
  config.md       your settings and product description (git-ignored)
  stories/        one <STORY-ID>.md per user story (git-ignored)
  knowledge/      system knowledge for the agents (git-ignored)
  runs/           one folder per story run (git-ignored)
  monthly/        monthly reports (git-ignored)
  escaped_defects.csv   defects found after release (git-ignored)
```

## Usage

| Command | What it does |
|---------|--------------|
| `python3 run.py design --story US-1234` | New run for `stories/US-1234.md`: story analysis, test plan, test cases |
| `python3 run.py design --story US-1234 --file path/to/story.md` | Same, reading the story from another file |
| `python3 run.py report --story US-1234` | Reads your `results.csv` and writes POT, bug reports, UAT summary, quality report |
| `python3 run.py resume --story US-1234` | Continues a stopped or failed run from its last checkpoint |
| `python3 run.py status --story US-1234` | Steps, review rounds, token usage, incident count |
| `python3 run.py monthly` | Monthly quality report for the current month (`--month 2026-11` for another) |

`--story` picks the latest run of that story; `--run <run-id>` picks a specific run; with neither,
the latest run is used. `--results <file>` reads results from another CSV.

### After design
- `test_cases.xlsx` - sheet **Test Cases** has the usual test-case fields: Test ID, Summary, Module,
  System, Preconditions, Test Steps, Test Data, Expected Result (with UI / API / DB checks), Type
  (positive / negative / boundary), Priority. Enter or import them into your test management tool.
  Other sheets: Traceability, Gaps for BA-Dev, Exploratory Charters.
- `story_analysis.md` - flow steps and systems touched, requirements with risk, regression areas,
  gaps, exploratory charters, test data. `test_plan.md` - the plan.
- `requirement_gaps.csv` - send the gaps to the BA/dev team, then record each answer and set
  `status` to `open`, `answered` or `closed`. Answers are kept if design runs again.

### Recording results (`runs/<run-id>/results.csv`)
Open it in Excel and save as CSV. For each test case:

| Column | What to write |
|---|---|
| `status` | Pass, Fail, Blocked, Skipped (empty = Not Run) |
| `actual_result` | what happened, in your own words (the report agent rewrites it) |
| `evidence` | screenshot file name(s) for the POT - required for Pass and Fail |
| `reference_numbers` | record / order / transaction / request IDs created in the test |
| `bug_id` | bug key in your tracker - required for Fail |
| `severity` | optional: critical, major, minor, trivial (otherwise the agent proposes one) |
| `root_cause` | required for Fail: requirements, code, environment, data, test, people |
| `bug_status` | when known: open, fixed, rejected, reopened (for rejection and reopen rates) |
| `build` | build / version tested (for the control chart per build) |
| `notes` | anything else; why a case is Blocked |

Error-proofing: with `strict_results: true` the report stops and lists every row that misses a
required field. You can edit the file and run `report` again; the report is regenerated.

### After report
- `pot.xlsx` - POT: one row per test case with result, actual result, screenshot reference,
  reference numbers, bug ID and build; plus Traceability and Summary sheets.
- `bug_reports.md` - one report per failed case with title, environment, preconditions, steps,
  expected, actual, evidence reference, severity and priority; critical bugs get a 5 Whys block.
- `uat_summary.md` - one page for the UAT / review meeting: what changed, how it was tested,
  results, exit criteria, open bugs, open questions, recommendation.
- `quality.md` - KPIs, Pareto by module and root cause, severity, traceability matrix.

## Monthly quality report

```bash
python3 run.py monthly                  # current month
python3 run.py monthly --month 2026-11
```

Defects found after release (UAT or production) go in `workspace/escaped_defects.csv`
(created empty the first time) with `root_cause` and `five_whys` (`why1 > why2 > ... > root cause`,
see `templates/rca_5_whys.md`). The report (`workspace/monthly/<month>/`) contains KPIs with
last month's value (defect leakage, detection effectiveness, rejection and reopen rates,
requirements coverage, execution and pass rate, POT evidence), a control chart of defects per build,
Pareto by module and root cause, escaped defects and an automatic process audit. Use
`templates/monthly_audit_checklist.md` for the manual part of the audit.

## Run folder

```
workspace/runs/<YYYYMMDD-HHMMSS>-<STORY-ID>/
  story_analysis.md  test_plan.md  test_cases.xlsx  requirement_gaps.csv  results.csv
  pot.xlsx  bug_reports.md  uat_summary.md  quality.md
  incidents.md      retries, fire-backs, review limits, failures
  state.json        checkpoint: step status, review round, token usage per model
  artifacts/        JSON output of every step
```

## Reliability

- **Checkpoints / failover**: every step and every review round is saved (atomic writes).
  After a crash, `Ctrl+C` or an error, `resume` continues from the exact point - finished
  steps and rounds are never paid for twice.
- **Retries**: temporary Claude Code errors and timeouts are retried with exponential backoff
  (`api_retries`).
- **Claude usage limit / not logged in**: the run stops with a clear message instead of retrying.
  Log in (`claude`, then /login) or wait for the limit to reset, then `resume`.
- **Fire-back**: if an agent's reply is not valid JSON or misses required content (a requirement
  without test cases, a case without expected result...), its reply is sent back with the problem
  to fix (`max_fire_back`).
- **Incidents**: one table per run in `incidents.md`; failures also write `last_error.txt`.

## Token savings

- Story intake, IDs, statistics, traceability, KPIs, POT, bug reports and Excel files are plain Python.
- Agents receive compact JSON and only what they need (the test plan gets scenario titles, not the
  full analysis; test cases are written per batch of requirements).
- A revision gets the input + its last output + reviewer issues, not the whole history.
- Each agent call runs `claude -p` with the agent's own system prompt and no tools, MCP servers,
  settings or CLAUDE.md. Repeated system prompts are cached by Claude Code.
- Only failed, blocked or annotated result rows go to the report agent.

## Editing

| To change | Edit |
|-----------|------|
| The product under test | `workspace/config.md` (`project_context`) and `workspace/knowledge/*.md` |
| What an agent does | `prompts/<agent>.md` |
| Rules every agent follows | `prompts/project_rules.md` |
| What a reviewer checks | `prompts/review_<stage>.md` (shared rules: `reviewer_base.md`) |
| Models, batch sizes, rounds, retries | `workspace/config.md` |
| Step order / flow and validators | `qa_flow/orchestrator.py` |
| Excel columns and style | `qa_flow/excel.py` |
| Markdown outputs (analysis, bug reports, UAT summary) | `qa_flow/render.py` |
| Results columns, root causes, bug statuses | `qa_flow/results.py` |
| KPIs and Pareto | `qa_flow/quality.py` |
| Traceability matrix and gaps | `qa_flow/traceability.py` |
| Monthly report and process audit | `qa_flow/monthly.py`, `prompts/monthly_summary.md` |
| Bug report, 5 Whys and audit templates | `templates/` |

If you change a prompt's JSON output format, update the matching `check_*` validator in
`orchestrator.py` and the rendering in `render.py` / `excel.py`.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

Covers configuration, story intake, results checks, risk, KPIs, Pareto, traceability, Excel output,
monthly report, Claude Code calls (mocked) and a full user-story design-to-report run with fake
agents. No network, Claude login or tracker access is needed.
