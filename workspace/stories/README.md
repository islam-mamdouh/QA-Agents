# User stories

One file per user story: `<STORY-ID>.md` (for example `US-1234.md`). There is no integration with
Jira, Azure DevOps or any other tracker: copy the story by hand and paste it here - title,
description, acceptance criteria, business rules, attachment notes and relevant comments.

Then run: `python3 run.py design --story US-1234`

These files are git-ignored (only this README is committed), because stories are often
client or company documents.
