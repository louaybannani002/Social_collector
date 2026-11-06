"""Image download with content-type and size checks."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass(frozen=True)
class DownloadedImage:
    url: str
    content: bytes
    content_type: str
    sha256: str


class ImageDownloader:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = 20,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_bytes = max_bytes

    def download(self, url: str) -> Optional[DownloadedImage]:
        """Return the image, or None if it cannot be fetched or is not a valid image."""
        host = urlsplit(url).netloc  # log the host only: CDN URLs carry signed params
        try:
            with self._session.get(url, timeout=self._timeout, stream=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    logger.warning("Not an image (%s) from %s", content_type or "unknown", host)
                    return None
                content = self._read_limited(response)
        except requests.RequestException as exc:
            logger.warning("Image download failed from %s: %s", host, type(exc).__name__)
            return None

        if content is None:
            logger.warning("Image from %s exceeds %d bytes, skipped", host, self._max_bytes)
            return None
        return DownloadedImage(url, content, content_type, hashlib.sha256(content).hexdigest())

    def _read_limited(self, response: requests.Response) -> Optional[bytes]:
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > self._max_bytes:
                return None
            chunks.append(chunk)
        return b"".join(chunks)
