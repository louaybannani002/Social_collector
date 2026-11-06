"""MongoDB persistence: posts and comments as documents, images in GridFS."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlsplit

import gridfs
from bson import ObjectId
from pymongo import ASCENDING, TEXT, MongoClient, UpdateOne

from .images import DownloadedImage
from .models import Post

logger = logging.getLogger(__name__)


class MongoStore:
    """
    Collections:
      posts     one document per post, with `image_ids` pointing to GridFS files
      comments  one document per comment, linked by (platform, post_id)
      images.*  GridFS bucket holding the image binaries (deduplicated by SHA-256)

    All writes are upserts, so re-running a collection never creates duplicates.
    """

    def __init__(self, uri: str, db_name: str, client: Optional[MongoClient] = None) -> None:
        self._client = client or MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = self._client[db_name]
        self._posts = db["posts"]
        self._comments = db["comments"]
        self._images = gridfs.GridFS(db, collection="images")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._posts.create_index([("platform", ASCENDING), ("post_id", ASCENDING)], unique=True)
        self._posts.create_index([("text", TEXT)], default_language="french")
        self._comments.create_index([("platform", ASCENDING), ("comment_id", ASCENDING)], unique=True)
        self._comments.create_index([("platform", ASCENDING), ("post_id", ASCENDING)])

    def save_image(self, platform: str, post_id: str, image: DownloadedImage) -> ObjectId:
        existing = self._images.find_one({"sha256": image.sha256})
        if existing is not None:
            return existing._id
        return self._images.put(
            image.content,
            filename=image.sha256,
            content_type=image.content_type,
            sha256=image.sha256,
            platform=platform,
            post_id=post_id,
            source_url=urlsplit(image.url)._replace(query="").geturl(),
        )

    def save_post(self, post: Post, image_ids: List[ObjectId]) -> None:
        document = post.to_document()
        document["image_ids"] = image_ids
        document["collected_at"] = datetime.now(timezone.utc)
        self._posts.update_one(
            {"platform": post.platform, "post_id": post.post_id},
            {"$set": document},
            upsert=True,
        )
        self._save_comments(post)

    def _save_comments(self, post: Post) -> None:
        if not post.comments:
            return
        operations = [
            UpdateOne(
                {"platform": post.platform, "comment_id": c.comment_id},
                {
                    "$set": {
                        "platform": post.platform,
                        "post_id": post.post_id,
                        "comment_id": c.comment_id,
                        "text": c.text,
                        "author": c.author,
                        "created_time": c.created_time,
                        "like_count": c.like_count,
                    }
                },
                upsert=True,
            )
            for c in post.comments
        ]
        self._comments.bulk_write(operations, ordered=False)

    def close(self) -> None:
        self._client.close()
