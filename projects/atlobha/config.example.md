# QA Agents — Atlobha configuration

Copy this file to `config.md` in the same folder and edit the YAML block below.
`config.md` is git-ignored because it holds credentials.

Secrets can be written directly or referenced as `${ENV_VAR}`. Environment variables are
read from your shell, from `.env` in this folder, or from `.env` in the repository root.
Relative paths (secrets, runs) are relative to this folder.

```yaml
# Leave this section out (or api_key empty) to use the credentials already active for the
# Claude Code CLI harness (ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN env var, or an
# `ant auth login` profile) - no separate API key needed. Set api_key only to use a
# different key than the CLI's.
anthropic:
  api_key: ""

source: linear                  # where the stories come from: jira | linear

models:
  main: claude-opus-5           # story analysis, test plan, test cases, report
  reviewer: claude-sonnet-5     # all reviewers
  max_tokens: 16000             # max output tokens per call

linear:
  api_key: ${LINEAR_API_KEY}            # Linear > Settings > Security & access > Personal API keys
  team_key: ATL                         # the prefix of your issue IDs (ATL-123)
  active_cycle_only: true               # only issues in the current cycle
  states: [Todo, In Progress]           # issue states to pick up; empty list = all states
  labels: []                            # e.g. [qa] to pick up only labelled issues; empty = all
  max_stories: 50
  description_max_chars: 2500           # long descriptions are trimmed to save tokens

google_sheets:
  service_account_file: ./secrets/service_account.json
  spreadsheet_id: your-spreadsheet-id   # from the sheet URL: /spreadsheets/d/<THIS>/edit
  worksheet_prefix: ATL                  # tabs are created as "ATL Results <run-id>" and "ATL Summary <run-id>"

flow:
  max_review_rounds: 3        # reviewer loop exit: no major issues, or this many rounds
  max_fire_back: 2            # times an agent is asked to fix an unusable reply
  api_retries: 4              # retries for network / rate-limit / server errors (Claude, Linear, Sheets)
  analysis_batch_size: 5      # stories per story-analysis call
  cases_batch_size: 3         # stories per test-case-writing call
  report_batch_size: 40       # result rows per report call
  runs_dir: runs
  strict_results: true        # error-proofing: Fail rows need actual_result, bug_id and root_cause

# Short product description given to every agent. Keep it brief: it is sent with every call.
project_context: |
  Atlobha is a Saudi automotive e-commerce platform (web + Android app) for ordering
  car spare parts and maintenance services. Users: customers, vendors, admins.
  Payment, delivery tracking and VAT invoices are business critical.
```
