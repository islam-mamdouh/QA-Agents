# QA Agents — ZATCA Customs Clearance configuration

Copy this file to `config.md` in the same folder and edit the YAML block below.
`config.md` is git-ignored. No credentials are needed and none may be written here:
agents run through your Claude Code login, CR text is pasted by hand (no Jira integration)
and all deliverables are local files.

Relative paths are relative to this folder (`projects/zatca/`).

```yaml
# Agents run through the Claude Code CLI with your Claude login (subscription), no API key.
# Log in once: run `claude`, then /login. Check with: python3 run.py check
claude_code:
  command: claude               # path to the Claude Code CLI if it is not on PATH
  timeout_seconds: 900          # max time for one agent call

models:
  main: claude-opus-5-5         # CR analysis, test plan, test cases, report rows, UAT summary
  reviewer: claude-sonnet-5-5   # all reviewers
  max_tokens: 16000             # max output tokens per call

inputs:
  crs_dir: crs                  # one file per CR: crs/<CR-ID>.md with the CR text copied from Jira
  knowledge_dir: knowledge      # *.md system knowledge given to every agent (git-ignored, keep it short)
  cr_max_chars: 30000           # longer CR text is trimmed (an incident is logged)

# Shown in bug reports and the POT. Name only; never put credentials here.
test_environment: QA environment

flow:
  max_review_rounds: 3        # reviewer loop exit: no major issues, or this many rounds
  max_fire_back: 2            # times an agent is asked to fix an unusable reply
  api_retries: 4              # retries for temporary Claude Code errors
  cases_batch_size: 4         # CR requirements per test-case-writing call
  report_batch_size: 40       # result rows per report call
  runs_dir: runs
  strict_results: true        # error-proofing: executed cases need evidence; Fail needs actual_result, bug_id, root_cause

# Short product description given to every agent (sent with every call, keep it brief).
# Put detailed system knowledge (screens, EDI message types, DB tables and status codes)
# in knowledge/*.md instead; that folder is git-ignored.
project_context: |
  ZATCA Customs Clearance: the Fasah platform and the connected customs systems (Saudi Arabia).
  Shipment journey: the shipping agent files the manifest (vessel, route, containers, bills of
  lading) -> EDI message and customs reply (A accepted / R rejected) -> the broker files an import,
  export or transit declaration linked to a B/L -> back-office receiving (accept/reject, container
  selection, inspection group) -> inspection, samples and X-ray -> customs fee collection -> release.
  Transit adds entry-port steps (truck entry movement, inspection and sealing, X-ray) and exit-port
  steps (exit movement, gate pass, closing).
  Users: brokers, shipping agents, receiving officers, inspectors. Wrong status, blocked clearance,
  wrong release and wrong fees are business critical.
```
