"""HTTP client for ERSE's dynamically published ZIP catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
from homeassistant.util import dt as dt_util

from .const import SOURCE_SETTINGS_URL, SOURCE_USER_AGENT
from .models import Catalog
from .parser import CatalogParseError, parse_catalog

MAX_RESPONSE_BYTES = 12 * 1024 * 1024


class ErseClientError(Exception):
    """The source could not be fetched or validated."""


@dataclass(slots=True)
class ErseResult:
    catalog: Catalog | None
    not_modified: bool
    etag: str | None
    source_url: str


class ErseClient:
    """Fetch source settings and the current full ZIP."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_fetch(self, etag: str | None = None, etag_url: str | None = None) -> ErseResult:
        headers = {"User-Agent": SOURCE_USER_AGENT, "Accept": "application/json"}
        try:
            async with self._session.get(SOURCE_SETTINGS_URL, headers=headers) as response:
                response.raise_for_status()
                if response.content_length and response.content_length > 64 * 1024:
                    raise ErseClientError("ERSE settings response exceeds the size limit")
                settings_chunks = []
                settings_size = 0
                async for chunk in response.content.iter_chunked(4096):
                    settings_size += len(chunk)
                    if settings_size > 64 * 1024:
                        raise ErseClientError("ERSE settings response exceeds the size limit")
                    settings_chunks.append(chunk)
                settings_payload = b"".join(settings_chunks)
                if len(settings_payload) > 64 * 1024:
                    raise ErseClientError("ERSE settings response exceeds the size limit")
                settings = json.loads(settings_payload.decode("utf-8-sig"))
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as err:
            raise ErseClientError(f"Could not fetch ERSE settings: {err}") from err
        csv_path = settings.get("csvPath") if isinstance(settings, dict) else None
        if not isinstance(csv_path, str) or not csv_path.strip():
            raise ErseClientError("ERSE settings do not contain a valid csvPath")
        zip_url = urljoin(SOURCE_SETTINGS_URL, csv_path)
        if not zip_url.startswith("https://"):
            raise ErseClientError("ERSE csvPath must use HTTPS")
        download_headers = {
            "User-Agent": SOURCE_USER_AGENT,
            "Accept": "*/*",
        }
        if etag and etag_url == zip_url:
            download_headers["If-None-Match"] = etag
        try:
            async with self._session.get(zip_url, headers=download_headers) as response:
                if response.status == 304:
                    return ErseResult(None, True, etag, zip_url)
                response.raise_for_status()
                if response.content_length and response.content_length > MAX_RESPONSE_BYTES:
                    raise ErseClientError("ERSE ZIP exceeds the download size limit")
                chunks = []
                total_bytes = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_RESPONSE_BYTES:
                        raise ErseClientError("ERSE ZIP exceeds the download size limit")
                    chunks.append(chunk)
                payload = b"".join(chunks)
                response_etag = response.headers.get("ETag")
        except ErseClientError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ErseClientError(f"Could not download ERSE catalog: {err}") from err
        try:
            catalog = parse_catalog(payload, zip_url, dt_util.now())
        except CatalogParseError as err:
            raise ErseClientError(f"ERSE catalog validation failed: {err}") from err
        return ErseResult(catalog, False, response_etag, zip_url)
