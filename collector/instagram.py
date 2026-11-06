"""Instagram collector (Graph API): hashtag search and/or the account's own media."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set

from .base import BaseCollector
from .graph_client import GraphAPIError, GraphClient, GraphRateLimitError
from .models import Comment, Post
from .text_utils import matches_topic

logger = logging.getLogger(__name__)

MEDIA_FIELDS = (
    "id,caption,media_type,media_url,permalink,timestamp,comments_count,"
    "children{media_type,media_url}"
)
COMMENT_FIELDS = "id,text,timestamp,username,like_count"


class InstagramCollector(BaseCollector):
    platform = "instagram"

    def __init__(
        self,
        client: GraphClient,
        ig_user_id: str,
        hashtags: Sequence[str] = (),
        include_own_media: bool = False,
        max_comments: int = 100,
        max_items_per_edge: int = 200,
    ) -> None:
        self._client = client
        self._ig_user_id = ig_user_id
        self._hashtags = [h.lstrip("#") for h in hashtags if h.strip()]
        self._include_own_media = include_own_media
        self._max_comments = max_comments
        self._max_items = max_items_per_edge

    def collect(self, keywords: Sequence[str], limit: int) -> Iterator[Post]:
        if limit <= 0:
            return
        seen: Set[str] = set()
        collected = 0
        for raw in self._iter_raw_media():
            if not matches_topic(raw.get("caption", ""), keywords):
                continue
            media_id = raw.get("id")
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            post = self._build_post(raw)
            if post is None:
                continue
            yield post
            collected += 1
            if collected >= limit:
                return

    def _iter_raw_media(self) -> Iterator[Dict[str, Any]]:
        for tag in self._hashtags:
            try:
                yield from self._iter_hashtag(tag)
            except GraphRateLimitError:
                raise
            except GraphAPIError as exc:
                logger.warning("Skipping hashtag #%s: %s", tag, exc)

        if self._include_own_media:
            try:
                for raw in self._client.paginate(
                    f"{self._ig_user_id}/media",
                    {"fields": MEDIA_FIELDS, "limit": 50},
                    max_items=self._max_items,
                ):
                    yield raw
            except GraphRateLimitError:
                raise
            except GraphAPIError as exc:
                logger.warning("Could not read own Instagram media: %s", exc)

    def _iter_hashtag(self, tag: str) -> Iterator[Dict[str, Any]]:
        found = self._client.get("ig_hashtag_search", {"user_id": self._ig_user_id, "q": tag})
        results = found.get("data") or []
        if not results:
            logger.warning("Hashtag #%s not found", tag)
            return
        hashtag_id = results[0]["id"]
        for edge in ("recent_media", "top_media"):
            yield from self._client.paginate(
                f"{hashtag_id}/{edge}",
                {"user_id": self._ig_user_id, "fields": MEDIA_FIELDS, "limit": 50},
                max_items=self._max_items,
            )

    def _build_post(self, raw: Dict[str, Any]) -> Optional[Post]:
        image_urls = self._extract_image_urls(raw)
        if not image_urls:  # videos / reels are out of scope: we collect images
            return None
        comments: List[Comment] = []
        if raw.get("comments_count", 0) > 0:
            comments = self._fetch_comments(raw["id"])
        return Post(
            platform=self.platform,
            post_id=raw["id"],
            text=raw.get("caption", ""),
            image_urls=image_urls,
            created_time=raw.get("timestamp"),
            permalink=raw.get("permalink"),
            comments=comments,
        )

    @staticmethod
    def _extract_image_urls(raw: Dict[str, Any]) -> List[str]:
        media_type = raw.get("media_type")
        if media_type == "IMAGE" and raw.get("media_url"):
            return [raw["media_url"]]
        if media_type == "CAROUSEL_ALBUM":
            children = raw.get("children") or {}
            return [
                child["media_url"]
                for child in children.get("data") or []
                if child.get("media_type") == "IMAGE" and child.get("media_url")
            ]
        return []

    def _fetch_comments(self, media_id: str) -> List[Comment]:
        comments: List[Comment] = []
        try:
            for raw in self._client.paginate(
                f"{media_id}/comments",
                {"fields": COMMENT_FIELDS, "limit": 50},
                max_items=self._max_comments,
            ):
                comments.append(
                    Comment(
                        comment_id=raw["id"],
                        text=raw.get("text", ""),
                        author=raw.get("username"),
                        created_time=raw.get("timestamp"),
                        like_count=raw.get("like_count", 0),
                    )
                )
        except GraphRateLimitError:
            raise
        except GraphAPIError as exc:
            # Expected for other people's media: Meta does not expose their comments.
            logger.info("Comments not available for media %s: %s", media_id, exc)
        return comments
