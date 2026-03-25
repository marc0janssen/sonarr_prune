"""Unit tests for pure prune logic (no I/O)."""

from datetime import datetime, timedelta

import pytest

from app.sonarr_prune_logic import (
    SeasonActionKind,
    decide_season_prune,
    format_warning_time_left,
    resolve_keep_tag_ids,
    season_directory_name,
    series_should_keep,
)


def test_season_directory_name():
    assert season_directory_name(0) == "Specials"
    assert season_directory_name(3) == "Season 3"


def test_resolve_keep_tag_ids():
    m = {"a": 1, "b": 2}
    assert resolve_keep_tag_ids(["a", "x", "b"], m) == [1, 2]
    assert resolve_keep_tag_ids([], m) == []


def test_series_should_keep():
    assert series_should_keep([1, 2], [2, 3]) is True
    assert series_should_keep([1], [2, 3]) is False


def test_decide_noop():
    dec = decide_season_prune(
        datetime(2024, 1, 10),
        None,
        remove_after_days=30,
        warn_days_infront=1,
        is_disk_full=True,
    )
    assert dec.kind == SeasonActionKind.NOOP


def test_decide_remove_when_old_and_disk_full():
    first = datetime(2023, 1, 1)
    now = datetime(2023, 2, 5)  # > 30 days later
    dec = decide_season_prune(
        now,
        first,
        remove_after_days=30,
        warn_days_infront=1,
        is_disk_full=True,
    )
    assert dec.kind == SeasonActionKind.REMOVE


def test_decide_no_remove_when_disk_not_full():
    first = datetime(2023, 1, 1)
    now = datetime(2023, 2, 5)
    dec = decide_season_prune(
        now,
        first,
        remove_after_days=30,
        warn_days_infront=1,
        is_disk_full=False,
    )
    assert dec.kind == SeasonActionKind.ACTIVE


def test_decide_active_when_young():
    first = datetime(2023, 1, 20)
    now = datetime(2023, 1, 25)
    dec = decide_season_prune(
        now,
        first,
        remove_after_days=30,
        warn_days_infront=1,
        is_disk_full=True,
    )
    assert dec.kind == SeasonActionKind.ACTIVE


def test_format_warning_time_left():
    tl = timedelta(hours=12, minutes=30, seconds=45)
    s = format_warning_time_left(tl)
    assert "h" in s
    assert "12" in s


@pytest.mark.parametrize(
    "first,now,warn_days,expect_warn",
    [
        # Removal scheduled ~24h from now -> inside 1-day warn window
        (
            datetime(2024, 6, 1, 12, 0, 0),
            datetime(2024, 6, 30, 13, 0, 0),
            1,
            True,
        ),
    ],
)
def test_warn_window_example(first, now, warn_days, expect_warn):
    """Sanity check: WARN can occur when within warn_days of removal date."""
    dec = decide_season_prune(
        now,
        first,
        remove_after_days=30,
        warn_days_infront=warn_days,
        is_disk_full=True,
    )
    if expect_warn:
        assert dec.kind == SeasonActionKind.WARN
        assert dec.time_until_removal is not None
