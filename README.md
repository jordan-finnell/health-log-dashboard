# Pain Tracker

A private, self-hosted Streamlit dashboard for tracking, trending and visualizing a personal daily health log. A Google Form feeds a Google Sheet; the app reads that sheet (read-only) and turns it into trends, calendar heatmaps and pattern analysis, viewable from a browser on the home network.

> **Status: in development.** The data layer and the demo-mode UI work end to end. Live Google Sheets mode and Docker deployment come next. See the roadmap below.

<table>
  <tr>
    <td><img src="docs/screenshots/overview.png" alt="Overview: a stat tile per metric with 7-day change and sparkline" width="220"></td>
    <td><img src="docs/screenshots/trends.png" alt="Trends: three metrics overlaid on a shared 0-10 axis" width="220"></td>
    <td><img src="docs/screenshots/calendar.png" alt="Calendar: weeks by weekday heatmap" width="220"></td>
    <td><img src="docs/screenshots/patterns.png" alt="Patterns: correlation matrix, weekday profile, rating co-occurrence" width="220"></td>
  </tr>
</table>

*Screenshots are taken in demo mode and show synthetic data only.*

The repo is public, but the author's data is not in it. With no credentials configured the app runs in **demo mode** on synthetic data, so everything here can be tried without access to any real log.

## What it shows
- **Overview:** latest values and 7-day averages compared with the previous 7 days
- **Trends:** each metric over time with 7- and 30-day rolling means
- **Calendar:** GitHub-style heatmap per metric, plus logging streaks
- **Patterns:** correlations between metrics and day-of-week profiles
- **Data:** filterable table of the underlying log (live mode only, behind a password)

## Data model
One row per form submission, with a timestamp and a handful of daily 0–10 scores. The metrics are configuration, not code. The demo (and the screenshots above) use five generic wellbeing scores, three where higher is better and two where lower is better:

| Column | Meaning | Better when |
|---|---|---|
| `Timestamp` | When the form was submitted | n/a |
| `Sleep Quality` | How well you slept | higher |
| `Energy Level` | Energy through the day | higher |
| `Focus` | Ability to concentrate | higher |
| `Stress` | Felt stress | lower |
| `Muscle Soreness` | Aches after activity (added later in the demo log, so earlier days are blank) | lower |

The direction matters: the app colours a change as "good" or "bad" using each metric's own better-when flag, so a rising Stress score and a falling Sleep Quality score both read as worsening.

Real-world logs are messy, and the transform layer handles it: several submissions on one day, skipped days, mixed timestamp formats, and a metric that starts partway through the log. Missing values stay missing rather than being treated as zero.

## Design
- **Config-driven metrics:** column headers map to stable keys, labels, scales and a better-when direction in TOML (`config/demo.toml` for the demo, `config/metrics.example.toml` for a real sheet), so changing or renaming a survey question never touches the code.
- **Pluggable sources:** a `DataSource` interface with Google Sheets, CSV and synthetic implementations.
- **Logic separate from UI:** analytics live in a plain Python package with tests. Streamlit pages stay thin.
- **Mobile first:** layouts are designed for a phone screen. Charts disable drag-zoom so touch scrolling still works, and tapping shows a tooltip listing every series for that date.
- **Honest charts:** one axis and a fixed 0–10 scale; a metric keeps the same colour whatever is selected; missing days are blank, never zero; every chart has a table view; colours are validated for colour-blind separation in both light and dark themes.

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
Then open <http://localhost:8501>. Every page works in demo mode with generated data; nothing connects to Google.

Dark and light themes follow your browser/OS setting.

## Self-hosting on Windows (WSL + Docker Desktop) *(planned)*
The author runs this on a Windows PC with the code in WSL2 and the app in Docker Desktop:

1. In Docker Desktop, enable Settings → Resources → WSL Integration for your distro, and "Start Docker Desktop when you sign in".
2. Create a Google Cloud service account, enable the Sheets API, and share your sheet with the service account as Viewer.
3. Save the key, sheet ID and an app password in `~/.config/pain-tracker/secrets.toml` (`chmod 600`). See `.streamlit/secrets.toml.example`.
4. Copy `config/metrics.example.toml` to `config/metrics.toml` (gitignored) and edit it so each metric's `column` matches your sheet's header, with the label, scale and `higher_is_better` you want. Demo mode ignores this file and always uses `config/demo.toml`.
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
- [x] Data layer: sources, transform, analytics, synthetic generator, tests
- [x] Streamlit UI in demo mode (overview, trends, calendar, patterns, data)
- [ ] Live Google Sheets mode with password gate (implemented and tested against a fake sheet; still to be verified with real credentials)
- [ ] Docker Compose deployment for LAN/phone access
- [ ] CI, screenshots, optional hosted demo
