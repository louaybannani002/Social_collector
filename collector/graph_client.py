"""Thin client for the Meta Graph API: auth, retries, error mapping, pagination."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Graph API error codes meaning "slow down" (app / user / page / business-use limits).
RATE_LIMIT_CODES = {4, 17, 32, 613}


class GraphAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class GraphRateLimitError(GraphAPIError):
    """The API asked us to stop sending requests for a while."""


class GraphClient:
    BASE_URL = "https://graph.facebook.com"

    def __init__(
        self,
        access_token: str,
        version: str = "v23.0",
        timeout: int = 20,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._token = access_token
        self._version = version
        self._timeout = timeout
        self._session = session or self._build_session(max_retries)

    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        retry = Retry(
            total=max_retries,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{self._version}/{path.lstrip('/')}"
        return self._request(url, params)

    def paginate(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_items: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield items of a list edge, following `paging.next` until exhausted."""
        if max_items is not None and max_items <= 0:
            return
        payload = self.get(path, params)
        yielded = 0
        while True:
            for item in payload.get("data", []):
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            next_url = payload.get("paging", {}).get("next")
            if not next_url:
                return
            parsed_url = urlsplit(next_url)
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "graph.facebook.com"
                or parsed_url.port not in (None, 443)
                or parsed_url.username is not None
                or parsed_url.password is not None
            ):
                raise GraphAPIError("Invalid pagination URL")
            payload = self._request(next_url)

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # The token goes in a header, never in the URL, so it cannot leak into logs.
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = self._session.get(url, params=params, headers=headers, timeout=self._timeout)
        except requests.RequestException as exc:
            # `from None`: the original message may embed a URL with credentials.
            raise GraphAPIError(f"Network error: {type(exc).__name__}") from None

        payload = self._parse_json(response)
        if response.status_code >= 400 or "error" in payload:
            error = payload.get("error", {})
            message = error.get("message", f"HTTP {response.status_code}")
            code = error.get("code")
            exc_class = GraphRateLimitError if code in RATE_LIMIT_CODES else GraphAPIError
            raise exc_class(message, response.status_code, code)
        return payload

    @staticmethod
    def _parse_json(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
