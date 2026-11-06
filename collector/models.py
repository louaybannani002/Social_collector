"""Domain objects shared by collectors, pipeline and storage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Comment:
    comment_id: str
    text: str
    author: Optional[str] = None
    created_time: Optional[str] = None
    like_count: int = 0


@dataclass
class Post:
    platform: str
    post_id: str
    text: str
    image_urls: List[str]
    created_time: Optional[str] = None
    permalink: Optional[str] = None
    comments: List[Comment] = field(default_factory=list)
    topic: Optional[str] = None

    def to_document(self) -> Dict[str, Any]:
        """MongoDB document for the post (comments live in their own collection)."""
        return {
            "platform": self.platform,
            "post_id": self.post_id,
            "text": self.text,
            "created_time": self.created_time,
            "permalink": self.permalink,
            "image_urls": self.image_urls,
            "comments_count": len(self.comments),
            "topic": self.topic,
        }
