# Bug Report Template (Jira)

Every field marked **(required)** must be filled before the bug is logged in Jira (error-proofing:
an incomplete report is the most common reason a bug is rejected or bounced back).
`run.py report` drafts these automatically in `bug_reports.md` for every failed test case.
Never put passwords or credentials in a bug report; write "credentials: see team chat".

| Field | Value |
|---|---|
| Title **(required)** | [Module] What is wrong, where, under which condition |
| CR **(required)** | Change Request key |
| Test case | Test case ID (e.g. CR-1234-TC-007) |
| Environment **(required)** | QA environment, build / version, port or QA schema, browser |
| System **(required)** | Fasah portal / EDI dashboard / back office / inspector app / X-ray / database / legacy |
| Severity **(required)** | critical / major / minor / trivial (impact on the system) |
| Priority **(required)** | high / medium / low (how soon it must be fixed) |
| Root cause | requirements / code / environment / data / test / people |

**Preconditions (required)**
- User role (no credentials), existing records (manifest, B/L, declaration) and their status

**Test data**
- Exact values used

**Steps to reproduce (required)**
1. One action per step
2. ...

**Expected result (required):** what the CR / business rule says should happen (UI, EDI, DB)

**Actual result (required):** what happened, with error messages copied exactly

**Evidence reference (required):** screenshot file names, EDI message numbers, declaration /
manifest / B/L numbers, DB query result

**Reproducibility:** always / sometimes (x of y tries) / once

## Severity guide
- **critical**: clearance blocked, shipment wrongly released, wrong fees, data loss, security, no workaround
- **major**: important function broken or wrong status/result, a workaround exists
- **minor**: limited impact, small functional or validation problem
- **trivial**: cosmetic, text, alignment

## Before you log it
- [ ] Reproduced at least twice on the latest build
- [ ] Checked UI, EDI message and DB where relevant
- [ ] Searched Jira for duplicates
- [ ] One problem per report
- [ ] Steps can be followed by someone who has never seen the feature
- [ ] Critical bug: 5 Whys started (`templates/rca_5_whys.md`)
