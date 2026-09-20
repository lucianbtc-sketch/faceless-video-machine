"""Optional Wikimedia Commons metadata search adapter.

This module searches file metadata only. It never downloads media files.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .asset_sourcing import AssetSourceError, AssetSourceProvider
from .models import AssetCandidate, AssetManifestEntry, AssetSource

DEFAULT_API_URL = "https://commons.wikimedia.org/w/api.php"
SOURCE = AssetSource(
    source_id="wikimedia-commons",
    name="Wikimedia Commons",
    source_url="https://commons.wikimedia.org/",
    license_policy_url="https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia",
    source_kind="other",
)


class AssetSourceConfigurationError(AssetSourceError):
    """The adapter configuration is missing or invalid."""


class AssetSourceNetworkError(AssetSourceError):
    """The adapter could not complete its HTTP request."""


class AssetSourceRateLimitError(AssetSourceError):
    """The provider requested that the client slow down or retry later."""


class AssetSourceResponseError(AssetSourceError):
    """The provider response was not a usable API response."""


@dataclass(slots=True)
class WikimediaCommonsConfig:
    api_url: str = DEFAULT_API_URL
    user_agent: str = ""
    timeout_seconds: float = 10.0
    request_interval_seconds: float = 1.0
    max_results: int = 10

    def __post_init__(self) -> None:
        if not self.api_url.strip():
            raise AssetSourceConfigurationError("Wikimedia Commons API URL cannot be empty")
        if not self.user_agent.strip():
            raise AssetSourceConfigurationError("FVM_WIKIMEDIA_USER_AGENT is required")
        if self.timeout_seconds <= 0 or self.request_interval_seconds < 0:
            raise AssetSourceConfigurationError("timeout and request interval values are invalid")
        if self.max_results <= 0 or self.max_results > 50:
            raise AssetSourceConfigurationError("max_results must be between 1 and 50")

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None, user_agent: str | None = None) -> "WikimediaCommonsConfig":
        values = os.environ if environ is None else environ
        return cls(
            api_url=values.get("FVM_WIKIMEDIA_API_URL", DEFAULT_API_URL),
            user_agent=user_agent if user_agent is not None else values.get("FVM_WIKIMEDIA_USER_AGENT", ""),
            timeout_seconds=float(values.get("FVM_WIKIMEDIA_TIMEOUT_SECONDS", "10")),
            request_interval_seconds=float(values.get("FVM_WIKIMEDIA_REQUEST_INTERVAL_SECONDS", "1")),
            max_results=int(values.get("FVM_WIKIMEDIA_MAX_RESULTS", "10")),
        )


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _clean(value: object) -> str:
    if not isinstance(value, str):
        return ""
    parser = _TextParser()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def _metadata(info: dict[str, object], name: str) -> str:
    metadata = info.get("extmetadata", {})
    if not isinstance(metadata, dict):
        return ""
    value = metadata.get(name, {})
    if isinstance(value, dict):
        return _clean(value.get("value", ""))
    return _clean(value)


def query_for_requirement(requirement: AssetManifestEntry) -> str:
    """Build a conservative file search query without asserting licensing."""
    description = re.sub(r"\b(primary visual asset|supporting asset)\b", "", requirement.description, flags=re.IGNORECASE)
    description = " ".join(description.split())
    return description or requirement.asset_type.replace("_", " ")


def _default_open(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()


class WikimediaCommonsProvider(AssetSourceProvider):
    """Search Wikimedia Commons file metadata through its public Action API."""

    source = SOURCE

    def __init__(
        self,
        config: WikimediaCommonsConfig,
        opener: Callable[[Request, float], bytes] = _default_open,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._opener = opener
        self._sleep = sleep
        self._has_requested = False

    def _request(self, query: str, continuation: dict[str, object] | None = None) -> dict[str, object]:
        if self._has_requested and self.config.request_interval_seconds:
            self._sleep(self.config.request_interval_seconds)
        self._has_requested = True
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": query,
            "gsrlimit": str(self.config.max_results),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": "640",
        }
        if continuation:
            params.update({key: str(value) for key, value in continuation.items()})
        request = Request(f"{self.config.api_url}?{urlencode(params)}", headers={"User-Agent": self.config.user_agent})
        try:
            payload = self._opener(request, self.config.timeout_seconds)
        except HTTPError as error:
            if error.code in (429, 503):
                raise AssetSourceRateLimitError(f"Wikimedia Commons rate limit or service delay: HTTP {error.code}") from error
            raise AssetSourceNetworkError(f"Wikimedia Commons HTTP error: {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise AssetSourceNetworkError(f"Wikimedia Commons network error: {error}") from error
        try:
            data = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            raise AssetSourceResponseError("Wikimedia Commons returned invalid JSON") from error
        if not isinstance(data, dict):
            raise AssetSourceResponseError("Wikimedia Commons returned a non-object response")
        api_error = data.get("error")
        if isinstance(api_error, dict):
            code = api_error.get("code", "unknown")
            if code in ("ratelimited", "maxlag"):
                raise AssetSourceRateLimitError(f"Wikimedia Commons API rate error: {code}")
            raise AssetSourceResponseError(f"Wikimedia Commons API error: {code}")
        return data

    def find_candidates(self, requirement: AssetManifestEntry) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        continuation: dict[str, object] | None = None
        while len(candidates) < self.config.max_results:
            data = self._request(query_for_requirement(requirement), continuation)
            query = data.get("query", {})
            pages = query.get("pages", {}) if isinstance(query, dict) else {}
            if not isinstance(pages, dict):
                raise AssetSourceResponseError("Wikimedia Commons response has invalid pages")
            for page in pages.values():
                if not isinstance(page, dict):
                    continue
                page_id = page.get("pageid")
                title = _clean(page.get("title", ""))
                imageinfo = page.get("imageinfo", [])
                if not isinstance(page_id, int) or not title or not isinstance(imageinfo, list) or not imageinfo:
                    continue
                info = imageinfo[0]
                if not isinstance(info, dict):
                    continue
                file_url = _clean(info.get("descriptionurl", ""))
                preview_url = _clean(info.get("thumburl", ""))
                media_url = _clean(info.get("url", ""))
                if not file_url:
                    continue
                creator = _metadata(info, "Artist") or _metadata(info, "Author")
                license_name = _metadata(info, "LicenseShortName")
                usage = _metadata(info, "UsageTerms") or _metadata(info, "Permission")
                mime = _clean(info.get("mime", ""))
                notes = "Original media URL recorded in metadata; this adapter does not download media."
                if mime:
                    notes += f" MIME type: {mime}."
                attribution = f"{creator} / {title} / Wikimedia Commons" if creator else ""
                candidates.append(
                    AssetCandidate(
                        candidate_id=f"wikimedia-commons-{page_id}",
                        asset_id=requirement.asset_id,
                        source_id=self.source.source_id,
                        source_name=self.source.name,
                        url=file_url,
                        title=title,
                        creator=creator,
                        license_name=license_name,
                        license_url=_metadata(info, "LicenseUrl"),
                        usage_information=usage,
                        preview_url=preview_url,
                        attribution=attribution,
                        rights_note="Verify the file page, license, attribution, and other restrictions before reuse; no legal clearance is provided.",
                        notes=notes + (f" Media URL: {media_url}." if media_url else ""),
                    )
                )
                if len(candidates) >= self.config.max_results:
                    break
            continuation_data = data.get("continue", {})
            if len(candidates) >= self.config.max_results or not isinstance(continuation_data, dict):
                break
            continuation = {key: value for key, value in continuation_data.items() if key in ("gsroffset", "continue")}
            if not continuation:
                break
        return candidates