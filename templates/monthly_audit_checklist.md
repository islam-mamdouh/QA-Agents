# Monthly Internal Audit Checklist (test process)

Internal audit of my own test process, in the style of ISO 19011: check the process against
what it should do, collect evidence, record findings and follow up corrective actions.
`run.py monthly` answers the automatic checks; this list covers the rest. Copy it each month.

Month: ______  Auditor: ______  Date: ______

## 1. Planning
- [ ] Every release/sprint had a test plan with scope, entry and exit criteria
- [ ] Stories were risk-rated and the highest risks were tested first
- [ ] Test environments and test data were ready before execution started

## 2. Requirements
- [ ] Every story was analysed before development finished
- [ ] Requirement gaps were sent to the team and answers recorded
- [ ] Traceability matrix is complete: no story without test cases

## 3. Execution and evidence
- [ ] Every executed case has a recorded result
- [ ] Every failed case has evidence, a bug ID and a root cause
- [ ] Blocked cases have a recorded reason and were retried when unblocked

## 4. Defects
- [ ] Bug reports follow `templates/bug_report_template.md`
- [ ] Rejected bugs were reviewed: why were they rejected, what to change
- [ ] Every escaped defect was analysed (5 Whys) and its root cause recorded
- [ ] Fixed bugs were retested and regression run around them

## 5. Measurement and improvement
- [ ] Monthly KPIs reviewed against last month
- [ ] Control chart signals (runs above UCL) investigated
- [ ] Improvement actions from last month: done / in progress / dropped (with reason)

## Findings
| # | Finding | Evidence | Corrective action | Owner | Due date | Status |
|---|---------|----------|-------------------|-------|----------|--------|
| 1 | | | | | | |
