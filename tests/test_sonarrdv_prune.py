from app.sonarrdv_prune import SONARRPRUNE


def write_ini(path, content: str):
    path.write_text(content)


def make_sample_ini(tmp_path, remove_after_days=30):
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
    assert isinstance(obj.tags_to_keep, list)
    assert obj.tags_to_keep == ["tag1", "tag2"]
    assert obj.mail_receiver == ["a@example.test", "b@example.test"]
