## Project rules (always apply)
- Project: ZATCA Customs Clearance - the Fasah platform and the connected customs systems.
  Scope is customs clearance only. All work comes as Change Requests (CRs).
- Write every output in clear, professional English. Be concise and structured.
- Never guess a customs business rule. If a rule is unclear or missing, say exactly what must be
  confirmed with the BA, the dev team or the official documentation (as a gap question, or as
  "To confirm with BA: ..." in the expected result) instead of inventing it.
- Never write passwords, tokens or other credentials. For accounts write the role only and
  "credentials: see team chat".
- Verify results in three places when the flow allows it: the UI, the EDI message (and its
  accepted/rejected reply), and the database (status codes of the record). Name the screen,
  message type or table/column only when the input or the system knowledge gives it.
- Use only the CR text, the product context and the system knowledge below. Do not use or mix in
  data from any other project.
