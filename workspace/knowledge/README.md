# System knowledge

Every `*.md` file in this folder (except this README) is added to every agent's instructions,
so the agents know the real screens, APIs, database tables and status codes of the system
under test.

- Keep files short and factual: every character is sent with every agent call.
- Good content: systems and who uses them, screen names, main business flows, API endpoints or
  integration messages, DB tables/columns and what each status code means, environment notes.
- Never put passwords, tokens or other credentials here; write "see team chat".
- These files are git-ignored (only this README is committed), because they often describe
  internal systems. Keep them on your machine only.
- When you switch to another product, replace these files and the `project_context` in config.md.
