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

Booleans in the config
- The example INI uses `ON`/`OFF` for boolean values. `ConfigParser.getboolean()` is
	case-insensitive and also accepts `true`/`false` and `1`/`0`, but the example
	uses `ON`/`OFF` for clarity.

Tests & CI
- Tests are provided under `tests/` and use `pytest`.
- A GitHub Actions workflow runs linting and tests on push/PR to `main`.

Dependencies
- See `requirements.txt` for runtime and test dependencies (requests, psutil, arrapi, chump, pytest).

License
- See `LICENSE` in the repo root.

## Development

If you want to develop or run tests locally, here are the recommended steps (fish shell):

Install runtime and test dependencies:

```fish
python3 -m pip install --user -r requirements.txt
# optional tools (format/lint) if you want to run them locally
python3 -m pip install --user black flake8 pytest
```

Run the test suite:

```fish
python3 -m pytest -q
```

Run the linter:

```fish
python3 -m flake8 app tests --max-line-length=79
```

Format (optional):

```fish
# Note: Black may have compatibility checks on certain Python patch versions.
python3 -m black app tests || true
```

Run the script (dry-run recommended first):

```fish
python3 app/sonarrdv_prune.py
```

Notes:
- Prefer Python 3.11 or Python 3.12.6+ if you want to run Black without the known 3.12.5 issue.
- Use `app/sonarrdv_prune.ini.example` as a starting point and copy it to `/config/sonarrdv_prune.ini`.
- Tests create temporary INI files and pass them into `SONARRPRUNE(config_path=...)`.
