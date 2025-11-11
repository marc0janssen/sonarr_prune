from types import SimpleNamespace
import pytest

from app.sonarrdv_prune import SONARRPRUNE


def write_ini(path, content: str):
    path.write_text(content)


def make_sample_ini(tmp_path, remove_after_days=30, remove_percentage=90.0):
    content = (
        f"""
[SONARRDV]
ENABLED = true
URL = http://localhost:7878
TOKEN = secret

[EMBY1]
ENABLED = false
URL = http://localhost:8096
TOKEN =

[EMBY2]
ENABLED = false
URL = http://localhost:8096
TOKEN =

[PRUNE]
REMOVE_SERIES_AFTER_DAYS = {remove_after_days}
REMOVE_SERIES_DISK_PERCENTAGE = {remove_percentage}
WARN_DAYS_INFRONT = 1
DRY_RUN = false
TAGS_KEEP_MOVIES_ANYWAY = tag1, tag2
ENABLED = true
ONLY_SHOW_REMOVE_MESSAGES = false
VERBOSE_LOGGING = false
MAIL_ENABLED = false
ONLY_MAIL_WHEN_REMOVED = false
MAIL_PORT = 587
MAIL_SERVER = smtp.example.test
MAIL_LOGIN = user
MAIL_PASSWORD = pass
MAIL_SENDER = sender@example.test
MAIL_RECEIVER = a@example.test, b@example.test

[PUSHOVER]
ENABLED = false
USER_KEY =
TOKEN_API =
SOUND =
"""
    )
    ini = tmp_path / "test.ini"
    write_ini(ini, content)
    return ini


def test_config_parsing(tmp_path):
    ini = make_sample_ini(tmp_path)

    obj = SONARRPRUNE(config_path=str(ini))

    assert obj.sonarrdv_enabled is True
    assert obj.sonarrdv_url.startswith("http://")
    assert obj.remove_after_days == 30
    assert obj.remove_percentage == pytest.approx(90.0)
    assert isinstance(obj.tags_to_keep, list)
    assert obj.tags_to_keep == ["tag1", "tag2"]
    assert obj.mail_receiver == ["a@example.test", "b@example.test"]


def test_isDiskFull_true_and_false(tmp_path, monkeypatch):
    ini = make_sample_ini(
        tmp_path, remove_after_days=10, remove_percentage=75.0
    )
    obj = SONARRPRUNE(config_path=str(ini))

    # provide a fake sonarrNode with a root_folder method
    obj.sonarrNode = SimpleNamespace(
        root_folder=lambda: [SimpleNamespace(path=str(tmp_path))]
    )

    # fake disk usage object
    Disk = SimpleNamespace

    # Case: percent above threshold
    monkeypatch.setattr(
        "psutil.disk_usage",
        lambda p: Disk(total=0, used=0, free=0, percent=80),
    )
    is_full, percent = obj.isDiskFull()
    assert is_full is True
    assert percent == 80

    # Case: below threshold
    monkeypatch.setattr(
        "psutil.disk_usage",
        lambda p: Disk(total=0, used=0, free=0, percent=50),
    )
    is_full, percent = obj.isDiskFull()
    assert is_full is False
    assert percent == 50
