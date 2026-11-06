# Security

ARSNEL runs locally. It has no server component, accounts or API keys.

- Keep ollama bound to `127.0.0.1` (its default). Do not set `OLLAMA_HOST=0.0.0.0` on a shared network.
- ARSNEL prints a warning if `llm.host` points anywhere other than this machine.
- The organizer only moves files inside the folder you give it and never deletes anything.
- The installers in `scripts/` never use sudo or administrator rights. They install into `~/.arsnel`, accept only `https://` repositories, and support `ARSNEL_DRY_RUN=1` to preview every step.
- `config.yaml` is git-ignored. Do not commit personal paths or resumes.

## Reporting a vulnerability

Please open a private advisory under the repository's Security tab ("Report a vulnerability")
instead of a public issue.
