# System knowledge

Every `*.md` file in this folder (except this README) is added to every agent's instructions,
so the agents know the real screens, EDI message types, database tables and status codes.

- Keep files short and factual: every character is sent with every agent call.
- Good content: systems and who uses them, screen names, EDI message types and replies,
  DB tables/columns and what each status code means, per-port differences.
- Never put passwords, tokens or other credentials here; write "see team chat".
- These files are git-ignored (only this README is committed), because they describe the
  client's internal systems. Keep them on your machine only.
- Update them when new walkthrough videos or system knowledge come in.
