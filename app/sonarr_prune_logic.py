"""
Pure prune decision rules for Sonarr seasons (no I/O, no API).

The driver maps Sonarr/filesystem state into datetimes and flags, then calls
decide_season_prune(). Side effects (delete, log, notify) stay outside.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, List, Mapping, Optional, Sequence


class SeasonActionKind(Enum):
    """Outcome for a season that has a tracked \"first complete\" date."""

    NOOP = "noop"  # No prune evaluation (e.g. no date / not applicable)
    ACTIVE = "active"  # Complete but not in warn/remove window yet
    WARN = "warn"  # Inside one-day warning window before removal eligibility
    REMOVE = "remove"  # Eligible for removal (disk full + age threshold)


@dataclass(frozen=True)
class SeasonDecision:
    kind: SeasonActionKind
    time_until_removal: Optional[timedelta] = None


def season_directory_name(season_number: int) -> str:
    return "Specials" if season_number == 0 else f"Season {season_number}"


def resolve_keep_tag_ids(
    tag_labels: Sequence[str],
    label_to_id: Mapping[str, int],
) -> List[int]:
    out: List[int] = []
    for label in tag_labels:
        tid = label_to_id.get(label)
        if tid is not None:
            out.append(tid)
    return out


def series_should_keep(
    series_tag_ids: Iterable[int],
    tags_ids_to_keep: Iterable[int],
) -> bool:
    return bool(set(series_tag_ids) & set(tags_ids_to_keep))


def decide_season_prune(
    now: datetime,
    season_first_complete_at: Optional[datetime],
    *,
    remove_after_days: int,
    warn_days_infront: int,
    is_disk_full: bool,
) -> SeasonDecision:
    """
    Decide what to do for a season that is complete on disk and has a
    \"first complete\" timestamp (mtime of the marker file).

    If season_first_complete_at is None, returns NOOP (caller handles paths).
    """
    if season_first_complete_at is None:
        return SeasonDecision(SeasonActionKind.NOOP)

    sd = season_first_complete_at
    remove_after = timedelta(days=remove_after_days)
    warn_infront = timedelta(days=warn_days_infront)

    # Warning window: still before removal date, but within WARN_DAYS_INFRONT
    # of it — matches original boolean logic.
    if (
        remove_after > now - sd
        and sd + remove_after - now <= warn_infront
        and sd + remove_after - now > warn_infront - timedelta(days=1)
    ):
        return SeasonDecision(
            SeasonActionKind.WARN,
            time_until_removal=sd + remove_after - now,
        )

    if now - sd >= remove_after and is_disk_full:
        return SeasonDecision(SeasonActionKind.REMOVE)

    return SeasonDecision(SeasonActionKind.ACTIVE)


def format_warning_time_left(time_left: timedelta) -> str:
    """Same formatting as legacy script ('h' between hours and minutes)."""
    return "h".join(str(time_left).split(":")[:2])
