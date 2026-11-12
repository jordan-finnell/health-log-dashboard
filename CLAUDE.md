# Health Log Dashboard

Private Streamlit dashboard that tracks, trends and visualizes a personal daily health log (Google Form → Google Sheet). It is also a **public GitHub portfolio piece**, so the repo must never contain real health data, the sheet ID, or credentials.

Single user. Runs on a Windows home PC: code and tooling in **WSL2**, the app served from **Docker Desktop**, opened from a phone on the home Wi-Fi. Full plan: `~/.claude/plans/i-want-to-spin-ethereal-island.md`.

## Status
Done: Phase 1 (repo hygiene), Phase 2 (data layer), Phase 3 (Streamlit UI, charts, password gate; screenshots in `docs/screenshots/`) and Phase 4 (the user set up real credentials and live mode). Phase 5: `Dockerfile` and `compose.yaml` are written and covered by text tests (`tests/test_deploy_files.py`) but have **not been built or run**, because Docker is not reachable from this WSL shell. Not started: CI workflow and portfolio polish (Phase 6). Paths marked *(planned)* do not exist yet.

Pipeline: `build_source(mode, config, secrets).load_raw()` → `to_daily(raw, config)` → analytics functions. `to_daily` returns one row per calendar day indexed by `date`, columns = metric keys, NaN for missed days.

## Commands
```bash
uv sync                                   # install deps (uv manages Python 3.13; system Python is 3.10)
uv run pytest                             # tests (run against synthetic data)
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files         # ruff, gitleaks, hygiene hooks
DEMO_MODE=1 uv run streamlit run app/Home.py   # dev server, then http://localhost:8501 in the Windows browser
docker compose up -d --build              # phone-reachable "prod" run, from the WSL shell (untested: no Docker here yet)
```
Add dependencies with `uv add` / `uv add --dev`, never by editing `uv.lock`.

## Architecture
- `src/health_log_dashboard/`: `config` (mode + metrics config), `sources` (`DataSource` protocol → `GSheetSource`, `CsvSource`, `SyntheticSource`), `synthetic`, `transform`, `analytics`, `charts` (Plotly figure builders + light/dark `Theme` tokens), `auth` (`verify_password`). None import Streamlit.
- `app/Home.py` + `app/pages/{1_Trends,2_Calendar,3_Patterns,4_Data}.py`: thin pages. `app/shared.py` holds `page_setup()` (config, mode, auth gate, sidebar), cached `load_daily()`, `range_filter()`, `show_chart()`, `table_view()`. Every page must call `shared.page_setup()` first and load data only after it returns, since that is what enforces the password gate.
- **Two schemas, kept separate.** Demo mode (and the README screenshots) use the generic five-metric schema in `config/demo.toml` (Sleep Quality, Energy Level, Focus higher-is-better; Stress, Muscle Soreness lower-is-better). Live mode uses the real log's schema from `config/metrics.toml` if present, else `config/metrics.example.toml`. `config.load_metrics_for(mode)` picks the file; `shared._config(mode)` caches it. A test enforces that the demo schema shares no keys, columns or labels with the real one, and another that demo pages never show the real labels. Never hard-code metric keys in `src/` or `app/`; derive them from the loaded config.
- Synthetic data: the last metric in the config is treated as a late survey addition (blank for the first half). Every metric has the shared burden signal (strong coupling) plus its own small slow drift, so metrics move together but can still diverge. `sources.DEMO_SEED` (19) is chosen so the overview shows both improving and worsening tiles; if you change the generator, re-check that mix (and regenerate `docs/screenshots/`).
- Tests live in `tests/`. `config` is the real-schema example file, `demo_config` is the demo schema; both use hand-written or synthetic frames only.
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

Scale: every metric is rated 0–10 (confirmed by the user). Values outside that range are treated as missing.

Quirks `transform.py` must handle:
- **Day rollover:** the user sometimes logs after midnight for the day that just ended, so a submission before noon (`transform.DAY_ROLLOVER_HOUR = 12`) belongs to the *previous* day. Date-only rows are never shifted. Synthetic data includes after-midnight second submissions to exercise this; hand-written test timestamps should be afternoon/evening so they stay on their own day.
- More than one submission on the same day (keep the latest) and days with no submission (reindex to the full calendar, leave NaN, do not interpolate silently).
- Column headers contain spaces and a slash. Map them to the snake_case keys above via `config/metrics.example.toml` rather than scattering header strings through the code.
- Rows are chronological in the sheet, but do not rely on it. Sort after parsing.

## Privacy rules (the repo is public)
- **`data/` is real private health data**, even `data/sample/`. It is gitignored. Read it only to learn the schema or profile quirks. Never copy values from it into committed files, tests, fixtures, docs or screenshots, and never send it to an external service.
- Tests, the README and screenshots use **synthetic data only** (`SyntheticSource`).
- Secrets live outside the repo at `~/.config/health-log-dashboard/secrets.toml` (service-account key, `sheet_id`, `worksheet`, `app_password`). Do not read, print or log it. Never put the sheet ID or any key in code, docs, commit messages or CI config.
- Column names are public (listed above). Everything else about the real log is not.
- Every commit passes pre-commit (gitleaks + ruff). Never use `--no-verify`. Before the repo goes public, scan the full history with `gitleaks git`.
- The service account is read-only (`spreadsheets.readonly`) on the one sheet. No write calls to Sheets.
- Nothing is exposed beyond the LAN: no router port-forwarding. The firewall rule is for the Private profile only.

## Environment notes
- Repo lives on the WSL Linux filesystem (`/home/jfinnell/project/pain_tracker`), not `/mnt/c`.
- Docker Desktop publishes ports on the Windows host, so the phone URL is `http://<Windows LAN IP>:8501` (from `ipconfig`, not the `172.x` address in WSL). No `netsh portproxy` or mirrored networking needed.
- The container user is **uid/gid 1000** so it can read the `chmod 600` secrets file bind-mounted from WSL.
- `docker` currently doesn't respond in this WSL shell. Enable Docker Desktop → Settings → Resources → WSL Integration for this distro, then build and verify the image (`docker compose up -d --build`, `docker compose ps` healthy, `docker run --rm --entrypoint ls <image> -a /app` shows no secrets).
- `compose.yaml` mounts only the secrets file (read-only, `create_host_path: false`). A private `config/metrics.toml` is mounted through a gitignored `compose.override.yaml`, never in the committed file. Never put secret values in `compose.yaml`, the Dockerfile, build args or labels.

## Conventions
- Default branch is **`trunk`**, not `master`/`main`.
- Commits use the user's global git identity. Keep messages short and imperative; explain why in the body.
- Python 3.13, type hints on public functions, ruff for lint and format.
- Charts: use the `dataviz` skill. Design for a phone screen first (single column, short labels, `width="stretch"`). Rules already encoded in `charts.py`: colour follows the metric (config order → categorical slot), one fixed 0–10 axis, no dual axes, missing is blank not zero, text never wears a series colour, colour scale placed above charts whose bottom edge has axis labels/titles. Add new metrics at the end of `metrics.example.toml` so existing colours don't shift.
- Verify UI changes by looking at them: run the app, screenshot with Playwright at phone width (400px) in light and dark. Headless `google-chrome --screenshot` does not wait for Streamlit's websocket, so use Playwright (`executablePath: /usr/bin/google-chrome`) and wait for `[data-testid="stMain"] h1`.
- `pkill -f` can match your own shell command line (exit 144). Kill the dev server in its own call with a pattern like `[s]treamlit.*8765`.
- Tests: `tests/test_app_smoke.py` and `tests/test_app_live_gate.py` use Streamlit's `AppTest` to run every page headlessly (demo mode and live mode with a fake source).
- GitHub: two accounts are logged into `gh`. Confirm `jordan-finnell` is the active one (`gh auth status`) before creating the repo, pushing, or opening PRs.
