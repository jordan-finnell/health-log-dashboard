---
description: Audit the repo for leaked secrets or real health data before pushing or going public
allowed-tools: Bash(git ls-files*), Bash(git log*), Bash(git status*), Bash(uv run pre-commit*), Bash(git grep*), Bash(gitleaks*)
---

Audit this repo for anything that must not be public. Report findings only; do not modify files or rewrite history.

1. `git ls-files` — flag any tracked path under `data/`, any `*.csv`/`*.parquet`/`*.sqlite`, any `secrets.toml` (other than `*.example`), `.env*`, key or service-account JSON, or a real `config/metrics.toml`.
2. `uv run pre-commit run --all-files` — gitleaks, ruff and hygiene hooks must pass.
3. If `gitleaks` is available, scan the full history: `gitleaks git --redact`. Otherwise say it was skipped.
4. `git grep -nIE 'private_key|BEGIN (RSA |EC )?PRIVATE KEY|spreadsheets/d/[A-Za-z0-9_-]{20,}|[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com|iam\.gserviceaccount\.com'` across tracked files and `git log -p` for the same patterns — any hit is a finding.
5. Check that every number in the README, tests and fixtures comes from synthetic data and not from `data/`.
6. Check `.dockerignore` still excludes secrets and `data/`, and, if an image exists, that it contains neither.

End with a short verdict: SAFE TO PUSH, or a list of blocking findings with file and line. Never print a secret value; show only file, line and the kind of secret.
