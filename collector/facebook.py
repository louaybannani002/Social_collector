"""Facebook collector: posts of Pages (Graph API), filtered by topic keywords."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional, Sequence

from .base import BaseCollector
from .graph_client import GraphAPIError, GraphClient, GraphRateLimitError
from .models import Comment, Post
from .text_utils import matches_topic

logger = logging.getLogger(__name__)

POST_FIELDS = (
    "id,message,created_time,permalink_url,full_picture,"
    "attachments{media_type,media{image{src}},subattachments{media{image{src}}}}"
)
COMMENT_FIELDS = "id,message,created_time,from{name},like_count"


class FacebookCollector(BaseCollector):
    platform = "facebook"

    def __init__(
        self,
        client: GraphClient,
        page_ids: Sequence[str],
        max_comments: int = 100,
        max_scanned_per_page: int = 500,
        require_image: bool = True,
    ) -> None:
        self._client = client
        self._page_ids = list(page_ids)
        self._max_comments = max_comments
        self._max_scanned = max_scanned_per_page
        self._require_image = require_image

    def collect(self, keywords: Sequence[str], limit: int) -> Iterator[Post]:
        if limit <= 0:
            return
        collected = 0
        for page_id in self._page_ids:
            try:
                raw_posts = self._client.paginate(
                    f"{page_id}/posts",
                    {"fields": POST_FIELDS, "limit": 50},
                    max_items=self._max_scanned,
                )
                for raw in raw_posts:
                    post = self._build_post(raw, keywords)
                    if post is None:
                        continue
                    yield post
                    collected += 1
                    if collected >= limit:
                        return
            except GraphRateLimitError:
                raise
            except GraphAPIError as exc:
                logger.warning("Skipping Facebook page %s: %s", page_id, exc)

    def _build_post(self, raw: Dict[str, Any], keywords: Sequence[str]) -> Optional[Post]:
        text = raw.get("message", "")
        if not matches_topic(text, keywords):
            return None
        image_urls = self._extract_image_urls(raw)
        if self._require_image and not image_urls:
            return None
        return Post(
            platform=self.platform,
            post_id=raw["id"],
            text=text,
            image_urls=image_urls,
            created_time=raw.get("created_time"),
            permalink=raw.get("permalink_url"),
            comments=self._fetch_comments(raw["id"]),
        )

    @staticmethod
    def _extract_image_urls(raw: Dict[str, Any]) -> List[str]:
        urls: List[str] = []
        attachments = raw.get("attachments") or {}
        for attachment in attachments.get("data") or []:
            subattachments = attachment.get("subattachments") or {}
            candidates = [attachment] + (subattachments.get("data") or [])
            for item in candidates:
                media = item.get("media") or {}
                image = media.get("image") or {}
                src = image.get("src")
                if src and src not in urls:
                    urls.append(src)
        if not urls and raw.get("full_picture"):
            urls.append(raw["full_picture"])
        return urls

    def _fetch_comments(self, post_id: str) -> List[Comment]:
        comments: List[Comment] = []
        try:
            for raw in self._client.paginate(
                f"{post_id}/comments",
                {"fields": COMMENT_FIELDS, "filter": "stream", "limit": 100},
                max_items=self._max_comments,
            ):
                comments.append(
                    Comment(
                        comment_id=raw["id"],
                        text=raw.get("message", ""),
                        author=(raw.get("from") or {}).get("name"),
                        created_time=raw.get("created_time"),
                        like_count=raw.get("like_count", 0),
                    )
                )
        except GraphRateLimitError:
            raise
        except GraphAPIError as exc:
            logger.warning("Could not fetch comments of %s: %s", post_id, exc)
        return comments
