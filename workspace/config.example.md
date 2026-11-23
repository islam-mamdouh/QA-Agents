# QA Agents — configuration

Copy this file to `config.md` in the same folder and edit the YAML block below.
`config.md` is git-ignored. No credentials are needed and none may be written here:
agents run through your Claude Code login, user stories are pasted by hand (no tracker
integration) and all deliverables are local files.

Relative paths are relative to this folder (`workspace/`).

```yaml
# Agents run through the Claude Code CLI with your Claude login (subscription), no API key.
# Log in once: run `claude`, then /login. Check with: python3 run.py check
claude_code:
  command: claude               # path to the Claude Code CLI if it is not on PATH
  timeout_seconds: 900          # max time for one agent call

models:
  main: claude-opus-5-5         # story analysis, test plan, test cases, report rows, UAT summary
  reviewer: claude-sonnet-5-5   # all reviewers
  max_tokens: 16000             # max output tokens per call

inputs:
  stories_dir: stories          # one file per user story: stories/<STORY-ID>.md
  knowledge_dir: knowledge      # *.md system knowledge given to every agent (git-ignored, keep it short)
  story_max_chars: 30000        # longer story text is trimmed (an incident is logged)

# Shown in bug reports and the POT. Name only; never put credentials here.
test_environment: QA environment

flow:
  max_review_rounds: 3        # reviewer loop exit: no major issues, or this many rounds
  max_fire_back: 2            # times an agent is asked to fix an unusable reply
  api_retries: 4              # retries for temporary Claude Code errors
  cases_batch_size: 4         # story requirements per test-case-writing call
  report_batch_size: 40       # result rows per report call
  runs_dir: runs
  strict_results: true        # error-proofing: executed cases need evidence; Fail needs actual_result, bug_id, root_cause

# Describe the system under test in a few lines. It is given to every agent with every call,
# so keep it brief. Put details (screens, APIs, DB tables, status codes) in knowledge/*.md.
# Replace this example with your own product.
project_context: |
  Example: an HR self-service web and mobile app. Employees submit leave and expense requests,
  managers approve or reject them, and HR manages balances and policies. Integrates with the
  payroll system and sends email and push notifications.
  Users: employees, managers, HR admins. Wrong balances, wrong approvals, wrong payroll data
  and access to other people's data are business critical.
```
