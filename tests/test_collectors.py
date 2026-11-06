from collector.facebook import FacebookCollector
from collector.graph_client import GraphAPIError
from collector.instagram import InstagramCollector


class FakeClient:
    """Maps an API path to the list of items `paginate` should return."""

    def __init__(self, edges, single=None):
        self._edges = edges
        self._single = single or {}

    def paginate(self, path, params=None, max_items=None):
        value = self._edges.get(path, [])
        if isinstance(value, Exception):
            raise value
        return iter(value[:max_items] if max_items else value)

    def get(self, path, params=None):
        return self._single[path]


def fb_post(post_id, message, image="https://img/1.jpg"):
    return {
        "id": post_id,
        "message": message,
        "created_time": "2026-01-01T00:00:00+0000",
        "permalink_url": f"https://fb/{post_id}",
        "attachments": {"data": [{"media": {"image": {"src": image}}}]},
    }


def test_facebook_keeps_only_on_topic_posts_with_images_and_comments():
    client = FakeClient(
        {
            "P/posts": [
                fb_post("P_1", "Hommage à Jacques Chirac"),
                fb_post("P_2", "Recette de crêpes"),
                {"id": "P_3", "message": "Chirac sans image"},
            ],
            "P_1/comments": [{"id": "c1", "message": "RIP", "from": {"name": "Ali"}, "like_count": 2}],
        }
    )
    posts = list(FacebookCollector(client, ["P"]).collect(["Chirac"], limit=10))
    assert [p.post_id for p in posts] == ["P_1"]
    assert posts[0].image_urls == ["https://img/1.jpg"]
    assert posts[0].comments[0].author == "Ali"


def test_facebook_respects_limit_and_survives_page_error():
    client = FakeClient(
        {
            "BAD/posts": GraphAPIError("forbidden"),
            "P/posts": [fb_post(f"P_{i}", "Chirac") for i in range(5)],
        }
    )
    posts = list(FacebookCollector(client, ["BAD", "P"]).collect(["Chirac"], limit=2))
    assert len(posts) == 2


def test_instagram_hashtag_collects_images_and_carousel_children_only():
    media = [
        {"id": "1", "caption": "#chirac", "media_type": "IMAGE", "media_url": "https://i/1.jpg", "comments_count": 1},
        {"id": "2", "caption": "video", "media_type": "VIDEO", "media_url": "https://i/2.mp4"},
        {"id": "4", "caption": "unrelated caption", "media_type": "IMAGE", "media_url": "https://i/4.jpg"},
        {
            "id": "3",
            "caption": "album #chirac",
            "media_type": "CAROUSEL_ALBUM",
            "children": {"data": [
                {"media_type": "IMAGE", "media_url": "https://i/3a.jpg"},
                {"media_type": "VIDEO", "media_url": "https://i/3b.mp4"},
            ]},
        },
    ]
    client = FakeClient(
        {"H/recent_media": media, "H/top_media": media[:1], "1/comments": [{"id": "c", "text": "ok", "username": "bob"}]},
        single={"ig_hashtag_search": {"data": [{"id": "H"}]}},
    )
    posts = list(InstagramCollector(client, "IG", hashtags=["#chirac"]).collect(["chirac"], limit=10))
    assert [p.post_id for p in posts] == ["1", "3"]  # duplicate "1" and the video are dropped
    assert posts[1].image_urls == ["https://i/3a.jpg"]
    assert posts[0].comments[0].author == "bob"


def test_instagram_comments_error_does_not_drop_the_post():
    media = [{"id": "1", "caption": "x", "media_type": "IMAGE", "media_url": "https://i/1.jpg", "comments_count": 3}]
    client = FakeClient(
        {"H/recent_media": media, "1/comments": GraphAPIError("not allowed")},
        single={"ig_hashtag_search": {"data": [{"id": "H"}]}},
    )
    posts = list(InstagramCollector(client, "IG", hashtags=["x"]).collect(["x"], limit=5))
    assert len(posts) == 1 and posts[0].comments == []


def test_collectors_return_no_posts_for_nonpositive_limits():
    fb_client = FakeClient({"P/posts": [fb_post("P_1", "Chirac")]})
    ig_client = FakeClient(
        {"H/recent_media": [{"id": "1", "caption": "x", "media_type": "IMAGE", "media_url": "https://i/1.jpg"}]},
        single={"ig_hashtag_search": {"data": [{"id": "H"}]}},
    )

    assert list(FacebookCollector(fb_client, ["P"]).collect(["Chirac"], 0)) == []
    assert list(InstagramCollector(ig_client, "IG", hashtags=["x"]).collect(["x"], 0)) == []


def test_facebook_handles_null_attachments():
    raw = {"id": "P_1", "message": "Chirac", "attachments": None}

    post = FacebookCollector(FakeClient({}), ["P"], require_image=False)._build_post(raw, ["Chirac"])

    assert post is not None
    assert post.image_urls == []
