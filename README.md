# Pain Tracker

A private, self-hosted Streamlit dashboard for tracking, trending and visualizing a personal daily health log. A Google Form feeds a Google Sheet; the app reads that sheet (read-only) and turns it into trends, calendar heatmaps and pattern analysis, viewable from a laptop or a phone on the home network.

> **Status: in development.** The data layer is next, then the UI. See the roadmap below.

The repo is public, but the author's data is not in it. With no credentials configured the app runs in **demo mode** on synthetic data, so everything here can be tried without access to any real log.

## What it shows
- **Overview:** latest values and 7-day averages compared with the previous 7 days
- **Trends:** each metric over time with 7- and 30-day rolling means
- **Calendar:** GitHub-style heatmap per metric, plus logging streaks
- **Patterns:** correlations between metrics and day-of-week profiles
- **Data:** filterable table of the underlying log (live mode only, behind a password)

## Data model
One row per form submission, six daily 0–10 style ratings:

| Column | Meaning | Better when |
|---|---|---|
| `Timestamp` | When the form was submitted | n/a |
| `Headache Severity` | Headache | lower |
| `Fatigue / Body Aches` | Fatigue and body aches | lower |
| `Depression` | Depressed mood | lower |
| `Anxiety` | Anxiety | lower |
| `Excitement` | Excitement and positive drive | higher |
| `Neck Pain` | Neck pain (added later, so earlier days are blank) | lower |

Real-world logs are messy, and the transform layer handles it: several submissions on one day, skipped days, mixed timestamp formats, and a metric that starts partway through the log. Missing values stay missing rather than being treated as zero.

## Design
- **Config-driven metrics:** column headers map to stable keys in `config/metrics.example.toml`, so renaming a survey question doesn't touch the code.
- **Pluggable sources:** a `DataSource` interface with Google Sheets, CSV and synthetic implementations.
- **Logic separate from UI:** analytics live in a plain Python package with tests. Streamlit pages stay thin.
- **Mobile first:** layouts are designed for a phone screen.

## Privacy and security
- Access to the sheet uses a Google Cloud **service account** with the read-only Sheets scope, shared on that single sheet as Viewer. It can be revoked at any time by un-sharing.
- Credentials, the sheet ID and the app password live **outside the repository** in `~/.config/pain-tracker/secrets.toml` and are bind-mounted read-only into the container. They never enter the image or git history.
- Live mode is behind a password gate. The server is reachable only on the home LAN: no port-forwarding, firewall rule for the Private network profile only.
- Real data is fetched into memory and cached briefly. Local data and key files are gitignored and dockerignored.
- Every commit is scanned for secrets with [gitleaks](https://github.com/gitleaks/gitleaks) via pre-commit, and again in CI.

## Quick start *(demo mode)*
Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone <this repo> && cd pain_tracker
uv sync
DEMO_MODE=1 uv run streamlit run app/Home.py
```
Then open <http://localhost:8501>. *(Available once the UI phase lands.)*

## Self-hosting on Windows (WSL + Docker Desktop) *(planned)*
The author runs this on a Windows PC with the code in WSL2 and the app in Docker Desktop:

1. In Docker Desktop, enable Settings → Resources → WSL Integration for your distro, and "Start Docker Desktop when you sign in".
2. Create a Google Cloud service account, enable the Sheets API, and share your sheet with the service account as Viewer.
3. Save the key, sheet ID and an app password in `~/.config/pain-tracker/secrets.toml` (`chmod 600`). See `.streamlit/secrets.toml.example`.
4. Copy `config/metrics.example.toml` to `config/metrics.toml` and adjust it if your headers differ.
5. From WSL: `docker compose up -d`.
6. In an admin PowerShell, allow the port on private networks only:
   `New-NetFirewallRule -DisplayName "Pain Tracker 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow -Profile Private`
7. On your phone, open `http://<your PC's LAN IP>:8501`. Find the IP with `ipconfig` in Windows (not the address shown inside WSL), and give the PC a DHCP reservation so it stays stable.

The PC must be awake and signed in for the app to be reachable.

## Development
```bash
uv run pytest                        # tests, using synthetic data
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files    # lint + secret scan
```

## Roadmap
- [x] Repo hygiene: gitignore, dockerignore, pre-commit with secret scanning
- [ ] Data layer: sources, transform, analytics, synthetic generator, tests
- [ ] Streamlit UI in demo mode
- [ ] Live Google Sheets mode with password gate
- [ ] Docker Compose deployment for LAN/phone access
- [ ] CI, screenshots, optional hosted demo
