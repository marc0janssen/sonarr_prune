# sonarr_prune

Small tool to automatically prune old seasons from a Sonarr (Radarr-style) library

Quick start
1. Copy the example config and edit values:
	- `cp app/sonarrdv_prune.ini.example /config/sonarrdv_prune.ini`
	- Edit API keys, URLs and prune settings in the config file.

2. Run (dry-run recommended first):
	- `python3 app/sonarrdv_prune.py`

Configuration
- See `app/sonarrdv_prune.ini.example` for all available settings and descriptions.
- Key settings: `REMOVE_SERIES_AFTER_DAYS`, `REMOVE_SERIES_DISK_PERCENTAGE`, `DRY_RUN` and `ENABLED`.

Tests & CI
- Tests are provided under `tests/` and use `pytest`.
- A GitHub Actions workflow runs linting and tests on push/PR to `main`.

Dependencies
- See `requirements.txt` for runtime and test dependencies (requests, psutil, arrapi, chump, pytest).

License
- See `LICENSE` in the repo root.
# sonarr_prune

A small, focused tool to automatically prune old seasons from a Sonarr (or Sonarr DV) library.

This repository provides a configurable script (`app/sonarrdv_prune.py`) that:
- Evaluates seasons by age and optionally by disk usage.
- Marks or removes seasons according to your configuration (supports dry-run).
- Integrates with Sonarr, optionally triggers Emby/Sonarr/Media server updates, and can notify via mail or Pushover.

## Quickstart

1. Copy the example configuration and edit values:

```fish
cp app/sonarrdv_prune.ini.example /config/sonarrdv_prune.ini
# edit /config/sonarrdv_prune.ini to set your API keys, URLs and prune rules
```

2. Run a dry-run first to see what would be removed:

```fish
python3 app/sonarrdv_prune.py --config /config/sonarrdv_prune.ini
```

3. When you're comfortable with the output, disable dry-run in the config and run again.

Notes:
- By default the script reads `app/sonarrdv_prune.ini.example` if no `--config` is provided.
- Use a scheduler (cron/systemd timer) if you want periodic pruning.

## Configuration (high level)

See `app/sonarrdv_prune.ini.example` for the full set of options. Important highlights:

- ENABLED: ON/OFF — whether pruning is active. The code accepts ON/OFF, true/false, 1/0.
- DRY_RUN: ON/OFF — if ON the script only logs planned removals.
- REMOVE_SERIES_AFTER_DAYS: integer — age threshold (in days) after which seasons are eligible for removal.
- REMOVE_SERIES_DISK_PERCENTAGE: integer — if disk usage goes above this percentage, pruning may be triggered.

Boolean values in the example config use `ON` / `OFF` for clarity. The code's parser accepts these as well as common boolean variants.

Other integrations:
- SONARR_API_KEY and SONARR_URL — for querying Sonarr.
- EMBY options — if you want the script to tell Emby to update its library after removals.
- MAIL_* and PUSHOVER_* — optional notification channels.

## Usage / Examples

Dry-run (preferred for first runs):

```fish
python3 app/sonarrdv_prune.py --config /config/sonarrdv_prune.ini
```

Run for real (set `DRY_RUN = OFF` in the config):

```fish
python3 app/sonarrdv_prune.py --config /config/sonarrdv_prune.ini
```

Run in verbose mode (prints more details):

```fish
python3 app/sonarrdv_prune.py --config /config/sonarrdv_prune.ini --verbose
```

Tip: Redirect or monitor the log file. The script uses a rotating file handler and also prints to stdout.

## Logging

- Logs are written to the configured log file (see the config). A rotating file handler is used to avoid unbounded log files.
- Log messages contain a short prefix (e.g. `PRUNE: REMOVED`, `PRUNE: WARNING`, `PRUNE: COMPLETE`) to make post-run searches easier.

## Testing and CI

- Unit tests live in `tests/` and use `pytest`.
- A GitHub Actions workflow runs linting and tests on push/PR to `main`.

To run tests locally (fish shell):

```fish
python3 -m pip install --user -r requirements.txt
python3 -m pytest -q
```

Run linting:

```fish
python3 -m pip install --user flake8
python3 -m flake8 app tests --max-line-length=79
```

Black formatting note: Black may abort on some Python patch releases (e.g. old 3.12.x warns). Prefer Python 3.11 or 3.12.6+ if you plan to run Black.

## Troubleshooting

- If Sonarr API calls fail: verify `SONARR_URL` and `SONARR_API_KEY` in your config and that Sonarr is reachable from the host running this script.
- If disk checks behave unexpectedly: ensure the path configured for Sonarr's root folder exists and the user running the script has read access.
- If Emby or other integrations fail: confirm the target service URLs and API keys, and check the network/firewall rules.

Common gotchas:
- Remember to set `DRY_RUN = OFF` only when you are ready to actually remove files.
- Test configuration changes by running a single dry-run and inspecting logged `PRUNE:` messages.

## Contributing

Patches, issues, and suggestions are welcome. Recommended workflow:

1. Open an issue describing the bug or enhancement.
2. Create a branch, add tests for behavior changes, and open a PR.

## License

See the `LICENSE` file in the repository root.

## Contact

If you want help configuring or testing the script, open an issue or reach out via the repo. Please include a copy of the config (remove secrets) and a short excerpt of the logs when asking for help.
