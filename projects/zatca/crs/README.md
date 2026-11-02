# Change Requests

One file per CR: `<CR-ID>.md` (for example `CR-1234.md`). There is no Jira integration:
copy the CR from Jira by hand and paste it here - title, description, acceptance criteria,
business rules, attachment notes and relevant comments.

Then run: `python3 run.py design --cr CR-1234`

These files are git-ignored (only this README is committed) because CRs are client documents.
