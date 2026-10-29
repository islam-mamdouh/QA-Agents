# Bug Report Template

Every field marked **(required)** must be filled before the bug is reported (error-proofing:
an incomplete report is the most common reason a bug is rejected or bounced back).
`run.py report` drafts these automatically in `bug_reports.md` for every failed test case.

| Field | Value |
|---|---|
| Title **(required)** | [Area] What is wrong, where, under which condition |
| Story **(required)** | Story / issue key |
| Test case | Test case ID, if found by a test case |
| Environment **(required)** | Build / version, URL or app version, browser or device, OS |
| Severity **(required)** | critical / major / minor / trivial (impact on the system) |
| Priority | high / medium / low (how soon it must be fixed) |
| Root cause | requirements / design / code / environment / data / integration / test / other |

**Preconditions (required)**
- User role, account state, existing data

**Test data**
- Exact values used

**Steps to reproduce (required)**
1. One action per step
2. ...

**Expected result (required):** what the requirement says should happen

**Actual result (required):** what happened, with error messages copied exactly

**Evidence (required):** screenshot, video, logs, request/response

**Reproducibility:** always / sometimes (x of y tries) / once

## Severity guide
- **critical**: money, legal/compliance, data loss, security, crash, core flow blocked, no workaround
- **major**: important feature broken or wrong result, a workaround exists
- **minor**: limited impact, small functional or validation problem
- **trivial**: cosmetic, text, alignment

## Before you submit
- [ ] Reproduced at least twice on the latest build
- [ ] Searched for duplicates
- [ ] One problem per report
- [ ] Steps can be followed by someone who has never seen the feature
