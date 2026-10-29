# QA Agents — ZATCA configuration

Copy this file to `config.md` in the same folder and edit the YAML block below.
`config.md` is git-ignored because it holds credentials.

Secrets can be written directly or referenced as `${ENV_VAR}`. Environment variables are
read from your shell, from `.env` in this folder, or from `.env` in the repository root.
Relative paths (secrets, runs) are relative to this folder.

```yaml
# Agents run through the Claude Code CLI with your Claude login (subscription), no API key.
# Log in once: run `claude`, then /login. Check with: python3 run.py check --project <name>
claude_code:
  command: claude               # path to the Claude Code CLI if it is not on PATH
  timeout_seconds: 900          # max time for one agent call

source: jira                    # where the stories come from: jira | linear

models:
  main: claude-opus-5           # story analysis, test plan, test cases, report
  reviewer: claude-sonnet-5     # all reviewers
  max_tokens: 16000             # max output tokens per call

jira:
  base_url: https://your-company.atlassian.net
  email: you@company.com
  api_token: ${JIRA_API_TOKEN}
  jql: project = ZATCA AND sprint in openSprints() AND issuetype = Story ORDER BY rank
  max_stories: 50
  description_max_chars: 2500           # long descriptions are trimmed to save tokens
  acceptance_criteria_field: ""         # e.g. customfield_10045, leave empty if AC is in the description
  dependency_link_types: [blocks]       # "blocks"-style link types: A blocks B  =>  B depends on A

google_sheets:
  service_account_file: ./secrets/service_account.json
  spreadsheet_id: your-spreadsheet-id   # from the sheet URL: /spreadsheets/d/<THIS>/edit
  worksheet_prefix: ZATCA                  # tabs are created as "ZATCA Results <run-id>" and "ZATCA Summary <run-id>"

flow:
  max_review_rounds: 3        # reviewer loop exit: no major issues, or this many rounds
  max_fire_back: 2            # times an agent is asked to fix an unusable reply
  api_retries: 4              # retries for network / rate-limit / server errors (Claude, Jira, Sheets)
  analysis_batch_size: 5      # stories per story-analysis call
  cases_batch_size: 3         # stories per test-case-writing call
  report_batch_size: 40       # result rows per report call
  runs_dir: runs
  strict_results: true        # error-proofing: Fail rows need actual_result, bug_id and root_cause

# Short product description given to every agent. Keep it brief: it is sent with every call.
project_context: |
  ZATCA e-invoicing (Fatoora) for Saudi Arabia, tested for QPros. Covers standard (B2B) and
  simplified (B2C) tax invoices, credit and debit notes, UBL 2.1 XML, QR codes, cryptographic
  stamps, device onboarding (CSID), clearance and reporting flows, and 15% VAT calculations.
  Compliance with ZATCA rules, correct totals and rejection handling are business critical.
```
