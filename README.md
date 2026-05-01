# sonarr_prune

Small tool to automatically prune old seasons from a Sonarr library once they have been complete for a configurable time. It supports dry-run, optional “keep” tags, mail, and Pushover.

## Project layout

| Path | Role |
|------|------|
| `app/sonarrdv_prune.py` | Entry point: config, I/O, Sonarr/Emby calls, logging, notifications |
| `app/sonarr_client.py` | Minimal Sonarr REST client (`/api/v3`) |
| `app/sonarr_prune_logic.py` | Pure prune rules (age, warning window, keep-tags) — no network or filesystem |
| `app/sonarrdv_prune.ini.example` | Example configuration |
| `app/version.py` | Version number (`__version__`, semantic versioning) |
| `tests/` | `pytest` unit tests |

Prune **decisions** live in `sonarr_prune_logic.py`; the main script maps Sonarr data and paths into that logic and performs deletes, logs, and notifications.

## Requirements

- Python 3.11+ (CI tests 3.11 and 3.12)
- Dependencies: see [`requirements.txt`](requirements.txt) (`httpx`, `chump`; `pytest` for tests)

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start

1. Copy the example config and edit URLs, tokens, and prune settings:

   ```bash
   cp app/sonarrdv_prune.ini.example /config/sonarrdv_prune.ini
   # edit /config/sonarrdv_prune.ini
   ```

2. Run with **`DRY_RUN = ON`** first and inspect the log output.

3. Default paths expect a container-style layout:

   - Config: `/config/sonarrdv_prune.ini`
   - Log: `/var/log/sonarr_prune.log`

   From the repository root (with those paths available or adjusted in your environment):

   ```bash
   python3 app/sonarrdv_prune.py
   ```

   Print the version and exit:

   ```bash
   python3 app/sonarrdv_prune.py --version
   # or: -V
   ```

   In code: `from app.version import __version__` or `import app` then `app.__version__`.

   For automated tests or embedding, you can pass a config path into `SONARRPRUNE(config_path="...")` in code; there is no `--config` CLI flag.

4. Use a scheduler (cron, systemd timer, etc.) if you want periodic pruning.

## Configuration

Full options and comments: [`app/sonarrdv_prune.ini.example`](app/sonarrdv_prune.ini.example).

Highlights:

| Section | Purpose |
|---------|---------|
| **SONARRDV** | `ENABLED`, base **URL** (e.g. `http://host:8989`, no `/api` suffix), **TOKEN** (API key) |
| **PRUNE** | `ENABLED`, `DRY_RUN`, `REMOVE_SERIES_AFTER_DAYS`, `WARN_DAYS_INFRONT`, `TAGS_KEEP_MOVIES_ANYWAY`, verbosity and mail options |
| **EMBY1 / EMBY2** | Optional library refresh after a run |
| **PUSHOVER** | Optional notifications |

Booleans accept values such as `ON`/`OFF`, `true`/`false`, `1`/`0`.

**Sonarr URL:** must be the instance root (scheme + host + port). The client calls `/api/v3/...` itself.

## Behaviour (short)

- Pruning removes complete seasons once they are older than `REMOVE_SERIES_AFTER_DAYS`.
- A season folder must be **complete** in Sonarr (all episodes have files) and tracked with a `.firstcomplete` marker file for “first complete” time.
- Series with any of the configured **keep** tag labels are skipped.
- After changes, the script can trigger a Sonarr series refresh and optional Emby refreshes.

## Logging

- Messages use prefixes such as `PRUNE: COMPLETE`, `PRUNE: WARNING`, `PRUNE: REMOVED`, `PRUNE: ACTIVE`, and `Prune - KEEPING`.
- With mail enabled, the log file can be attached to the outgoing message.

## Development

Run tests from the repo root:

```bash
pip install -r requirements.txt
pytest
```

Lint (optional):

```bash
pip install flake8
python3 -m flake8 app tests --max-line-length=79
```

CI (GitHub Actions) runs tests on push/PR to `main`.

## Troubleshooting

- **Cannot connect to Sonarr:** check `SONARRDV` **URL** and **TOKEN**, and that the host running the script can reach Sonarr.
- **Nothing is pruned:** confirm seasons are complete in Sonarr, old enough for `REMOVE_SERIES_AFTER_DAYS`, and not protected by keep-tags.
- **Emby / mail / Pushover issues:** verify URLs, API keys, and firewall rules.

## Contributing

Issues and pull requests are welcome. For behaviour changes, add or extend tests (especially in `tests/test_sonarr_prune_logic.py` for pure rules).

## License

See [`LICENSE`](LICENSE) in the repository root.
