# Root Cause Analysis - 5 Whys

Use for every escaped defect (found in UAT or production) and every critical defect.
Record the result in `projects/zatca/escaped_defects.csv` (`root_cause` and `five_whys` columns)
so the monthly report can check it.

| Field | Value |
|---|---|
| Bug ID / CR | |
| Found by / when | UAT / production / testing - date |
| Severity | |
| Module / system | |

## Problem statement
What happened, where, and the impact (one or two sentences).

## 5 Whys
1. Why did the defect happen?
2. Why?
3. Why?
4. Why?
5. Why? -> root cause

## Fishbone category (pick one)
requirements / code / environment / data / test / people

## Why was it not caught earlier?
Which review or test should have caught it (CR review, test case, regression, UAT)?

## Actions
| Action | Type (correct / prevent) | Owner | Due date | Status |
|---|---|---|---|---|
| | | | | |

`five_whys` column format: `why1 > why2 > why3 > why4 > root cause`
