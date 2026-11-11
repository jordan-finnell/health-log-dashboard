# Pain Tracker

Private Streamlit dashboard that tracks, trends and visualizes a personal daily health log (Google Form → Google Sheet). It is also a **public GitHub portfolio piece**, so the repo must never contain real health data, the sheet ID, or credentials.

Single user. Runs on a Windows home PC: code and tooling in **WSL2**, the app served from **Docker Desktop**, opened from a phone on the home Wi-Fi. Full plan: `~/.claude/plans/i-want-to-spin-ethereal-island.md`.

## Status
Phase 1 (repo hygiene) is done. Phases 2–6 are not started: data layer, UI, live Sheets mode, Docker, portfolio polish. Paths below marked *(planned)* do not exist yet.

## Commands
```bash
uv sync                                   # install deps (uv manages Python 3.13; system Python is 3.10)
uv run pytest                             # tests (run against synthetic data)
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files         # ruff, gitleaks, hygiene hooks
DEMO_MODE=1 uv run streamlit run app/Home.py   # (planned) dev server, then http://localhost:8501 in the Windows browser
docker compose up -d                      # (planned) phone-reachable "prod" run, from the WSL shell
```
Add dependencies with `uv add` / `uv add --dev`, never by editing `uv.lock`.

## Architecture *(planned)*
- `src/pain_tracker/`: `config` (mode + metrics config), `sources` (`DataSource` protocol → `GSheetSource`, `CsvSource`, `SyntheticSource`), `synthetic`, `transform`, `analytics`, `charts`, `auth`.
- `app/Home.py` + `app/pages/`: Trends, Calendar, Patterns, Data.
- **Mode:** live if `secrets.toml` is present, otherwise demo (synthetic data). `DEMO_MODE=1` forces demo. Live mode sits behind a password gate; demo mode does not.
- Keep logic in `src/` (testable, no Streamlit imports) and keep pages thin.

## Data schema
One row per form submission. Headers are exactly:

| Column | Key | Type | Notes |
|---|---|---|---|
| `Timestamp` | `timestamp` | datetime | Google Forms format `M/D/YYYY H:MM:SS`, no zero-padding, no timezone. A few early rows are date-only (`M/D/YYYY`), so parse with `format="mixed"` or handle both. |
| `Headache Severity` | `headache` | int | lower is better |
| `Fatigue / Body Aches` | `fatigue` | int | lower is better |
| `Depression` | `depression` | int | lower is better |
| `Anxiety` | `anxiety` | int | lower is better |
| `Excitement` | `excitement` | int | **higher is better** |
| `Neck Pain` | `neck_pain` | float | added mid-log, so blank for all earlier rows. Must be treated as missing, never as 0. |

Scale: observed values are 0–9, assumed to be a 0–10 scale. **Confirm with the user** before hard-coding the range.

Quirks `transform.py` must handle:
- More than one submission on the same day (keep the latest) and days with no submission (reindex to the full calendar, leave NaN, do not interpolate silently).
- Column headers contain spaces and a slash. Map them to the snake_case keys above via `config/metrics.example.toml` rather than scattering header strings through the code.
- Rows are chronological in the sheet, but do not rely on it. Sort after parsing.

## Privacy rules (the repo is public)
- **`data/` is real private health data**, even `data/sample/`. It is gitignored. Read it only to learn the schema or profile quirks. Never copy values from it into committed files, tests, fixtures, docs or screenshots, and never send it to an external service.
- Tests, the README and screenshots use **synthetic data only** (`SyntheticSource`).
- Secrets live outside the repo at `~/.config/pain-tracker/secrets.toml` (service-account key, `sheet_id`, `worksheet`, `app_password`). Do not read, print or log it. Never put the sheet ID or any key in code, docs, commit messages or CI config.
- Column names are public (listed above). Everything else about the real log is not.
- Every commit passes pre-commit (gitleaks + ruff). Never use `--no-verify`. Before the repo goes public, scan the full history with `gitleaks git`.
- The service account is read-only (`spreadsheets.readonly`) on the one sheet. No write calls to Sheets.
- Nothing is exposed beyond the LAN: no router port-forwarding. The firewall rule is for the Private profile only.

## Environment notes
- Repo lives on the WSL Linux filesystem (`/home/jfinnell/project/pain_tracker`), not `/mnt/c`.
- Docker Desktop publishes ports on the Windows host, so the phone URL is `http://<Windows LAN IP>:8501` (from `ipconfig`, not the `172.x` address in WSL). No `netsh portproxy` or mirrored networking needed.
- The container user is **uid/gid 1000** so it can read the `chmod 600` secrets file bind-mounted from WSL.
- `docker` currently doesn't respond in this WSL shell. Enable Docker Desktop → Settings → Resources → WSL Integration for this distro before Phase 5.

## Conventions
- Default branch is **`trunk`**, not `master`/`main`.
- Commits use the user's global git identity. Keep messages short and imperative; explain why in the body.
- Python 3.13, type hints on public functions, ruff for lint and format.
- Charts: use the `dataviz` skill. Design for a phone screen first (single column, short labels, `use_container_width`).
- GitHub: two accounts are logged into `gh`. Confirm `jordan-finnell` is the active one (`gh auth status`) before creating the repo, pushing, or opening PRs.
