# Monthly Internal Audit Checklist (test process)

Internal audit of my own test process for the customs clearance project, in the style of
ISO 19011: check the process against what it should do, collect evidence, record findings and
follow up corrective actions. `run.py monthly` answers the automatic checks; this list covers
the rest. Copy it each month.

Month: ______  Auditor: ______  Date: ______

## 1. CR review (QA before QC)
- [ ] Every CR was analysed before development finished
- [ ] Gaps were sent to the BA/dev team and the answers recorded in `requirement_gaps.csv`
- [ ] Unclear customs rules were confirmed with the BA or official documentation, not guessed

## 2. Planning and test design
- [ ] Every CR has a test plan with scope, entry and exit criteria
- [ ] Requirements were risk-rated and the highest risks were tested first
- [ ] Test cases cover positive, negative, boundary and validation scenarios
- [ ] Traceability is complete: every CR requirement has test cases
- [ ] Test cases were entered into Jira from `test_cases.xlsx`

## 3. Execution and evidence (POT)
- [ ] Every executed case has a recorded result
- [ ] Every executed case has a screenshot reference and reference/message numbers in the POT
- [ ] Results were verified in UI, EDI and DB where the flow allows it
- [ ] Blocked cases have a recorded reason and were retried when unblocked

## 4. Defects
- [ ] Bug reports follow `templates/bug_report_template.md` (no missing mandatory field)
- [ ] Rejected bugs were reviewed: why were they rejected, what to change
- [ ] Every escaped or critical defect has a 5 Whys analysis and a fishbone category
- [ ] Fixed bugs were retested and regression run around them (focus on Pareto vital-few modules)

## 5. UAT review
- [ ] Every CR had a UAT meeting with the summary and POT
- [ ] UAT findings were logged and followed up

## 6. Lean waste
- [ ] Time lost waiting for environments or builds was recorded (blocked cases, notes)
- [ ] No bug bounced back for an unclear report
- [ ] No rework caused by missing test data (test data prepared before execution)

## 7. Security and confidentiality
- [ ] No passwords or credentials in test cases, bug reports, POT, docs or memory
- [ ] No data from other projects in this project's files

## 8. Measurement and improvement
- [ ] Monthly KPIs reviewed against last month
- [ ] Control chart signals (builds above UCL) investigated as process problems
- [ ] Improvement actions from last month: done / in progress / dropped (with reason)

## Findings
| # | Finding | Evidence | Corrective action | Owner | Due date | Status |
|---|---------|----------|-------------------|-------|----------|--------|
| 1 | | | | | | |
