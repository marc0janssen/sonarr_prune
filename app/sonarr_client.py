"""Minimal Sonarr REST API (v3) client — replaces arrapi for this project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import httpx


class SonarrClientError(Exception):
    """Raised when the Sonarr API returns an error or the request fails."""


@dataclass(frozen=True)
class RootFolder:
    path: str


@dataclass(frozen=True)
class Tag:
    id: int
    label: str


@dataclass(frozen=True)
class Season:
    seasonNumber: int
    totalEpisodeCount: int
    episodeFileCount: int


@dataclass(frozen=True)
class Series:
    sortTitle: str
    title: str
    year: int
    path: str
    tagsIds: List[int]
    seasons: List[Season]


class SonarrClient:
    """Thin wrapper around Sonarr `/api/v3` endpoints used by sonarrdv_prune."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 60.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session = httpx.Client(
            timeout=timeout,
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        self._verify_connection()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            r = self._session.request(method, self._url(path), **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            body = ""
            if e.response is not None and e.response.text:
                body = f" — {e.response.text[:500]}"
            raise SonarrClientError(
                f"HTTP {e.response.status_code}{body}"
            ) from e
        except httpx.RequestError as e:
            raise SonarrClientError(str(e)) from e

    def _get_json(self, path: str) -> Any:
        return self._request("GET", path).json()

    def _verify_connection(self) -> None:
        self._get_json("/api/v3/system/status")

    def root_folder(self) -> List[RootFolder]:
        raw = self._get_json("/api/v3/rootfolder")
        return [RootFolder(path=str(r["path"])) for r in raw]

    def all_tags(self) -> List[Tag]:
        raw = self._get_json("/api/v3/tag")
        return [Tag(id=int(t["id"]), label=str(t["label"])) for t in raw]

    def all_series(self) -> List[Series]:
        raw = self._get_json("/api/v3/series")
        out: List[Series] = []
        for s in raw:
            seasons: List[Season] = []
            for se in s.get("seasons") or []:
                stats = se.get("statistics") or {}
                seasons.append(
                    Season(
                        seasonNumber=int(se["seasonNumber"]),
                        totalEpisodeCount=int(stats.get("totalEpisodeCount", 0)),
                        episodeFileCount=int(stats.get("episodeFileCount", 0)),
                    )
                )
            title = s.get("title") or ""
            out.append(
                Series(
                    sortTitle=str(s.get("sortTitle") or title),
                    title=str(title),
                    year=int(s.get("year") or 0),
                    path=str(s.get("path") or ""),
                    tagsIds=[int(x) for x in (s.get("tags") or [])],
                    seasons=seasons,
                )
            )
        return out
