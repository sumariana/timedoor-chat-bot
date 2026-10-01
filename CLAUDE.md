# Project Rules

## Secrets

- NEVER read, print, cat, or output the contents of `.env` (or any file holding
  real credentials) into the conversation — not via Read, Bash `cat`/`type`,
  PowerShell `Get-Content`, or any other tool.
- To debug an env var, check only whether it's set/non-empty
  (e.g. `os.getenv("X") is not None`) — never its value.
- If asked to "check my .env" or similar, explain this restriction and ask
  the user to confirm values themselves, or check presence/length only.
- `.env` is already git-ignored — that protects against commits, not against
  the value leaking into this chat. This rule covers the chat-leak case.
