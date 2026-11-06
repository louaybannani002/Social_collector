"""Orchestration: collectors -> image download -> MongoDB."""
from __future__ import annotations

import logging
from typing import Dict, Sequence

from .base import BaseCollector
from .graph_client import GraphAPIError, GraphRateLimitError
from .images import ImageDownloader
from .models import Post
from .storage import MongoStore

logger = logging.getLogger(__name__)


class CollectionPipeline:
    def __init__(
        self,
        collectors: Sequence[BaseCollector],
        store: MongoStore,
        downloader: ImageDownloader,
    ) -> None:
        self._collectors = collectors
        self._store = store
        self._downloader = downloader

    def run(self, topic: str, keywords: Sequence[str], limit_per_platform: int) -> Dict[str, int]:
        """Collect and store posts; return the number of posts saved per platform."""
        stats: Dict[str, int] = {}
        for collector in self._collectors:
            saved = 0
            try:
                for post in collector.collect(keywords, limit_per_platform):
                    post.topic = topic
                    self._persist(post)
                    saved += 1
            except GraphRateLimitError as exc:
                logger.warning("%s: rate limit reached, stopping (%s)", collector.platform, exc)
            except GraphAPIError as exc:
                logger.error("%s: API error, stopping (%s)", collector.platform, exc)
            stats[collector.platform] = saved
            logger.info("%s: %d post(s) saved", collector.platform, saved)
        return stats

    def _persist(self, post: Post) -> None:
        image_ids = []
        for url in post.image_urls:
            image = self._downloader.download(url)
            if image is not None:
                image_ids.append(self._store.save_image(post.platform, post.post_id, image))
        self._store.save_post(post, image_ids)
