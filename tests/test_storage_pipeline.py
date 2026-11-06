import mongomock
import mongomock.gridfs
import pytest

mongomock.gridfs.enable_gridfs_integration()

from collector.images import DownloadedImage
from collector.models import Comment, Post
from collector.pipeline import CollectionPipeline
from collector.storage import MongoStore


class StubCollector:
    platform = "facebook"

    def __init__(self, posts):
        self._posts = posts

    def collect(self, keywords, limit):
        return iter(self._posts[:limit])


class StubDownloader:
    def download(self, url):
        if "bad" in url:
            return None
        return DownloadedImage(url, b"binary-" + url.encode(), "image/jpeg", "sha-" + url)


@pytest.fixture
def store(monkeypatch):
    store = MongoStore("unused", "test_db", client=mongomock.MongoClient())

    # mongomock does not support recent pymongo's UpdateOne in bulk_write:
    # emulate bulk_write with individual upserts (real MongoDB uses the real one).
    def fake_bulk_write(operations, ordered=True):
        for op in operations:
            store._comments.update_one(op._filter, op._doc, upsert=True)

    monkeypatch.setattr(store._comments, "bulk_write", fake_bulk_write, raising=False)
    return store


def make_post():
    return Post(
        platform="facebook",
        post_id="P_1",
        text="Hommage à Chirac",
        image_urls=["https://i/ok.jpg", "https://i/bad.jpg"],
        comments=[Comment("c1", "RIP", "Ali")],
    )


def test_pipeline_stores_post_comments_and_images(store):
    pipeline = CollectionPipeline([StubCollector([make_post()])], store, StubDownloader())
    stats = pipeline.run("Chirac", ["Chirac"], limit_per_platform=10)

    assert stats == {"facebook": 1}
    doc = store._posts.find_one({"post_id": "P_1"})
    assert doc["topic"] == "Chirac"
    assert len(doc["image_ids"]) == 1  # the undownloadable image is skipped
    assert store._comments.count_documents({"post_id": "P_1"}) == 1


def test_rerunning_is_idempotent(store):
    pipeline = CollectionPipeline([StubCollector([make_post()])], store, StubDownloader())
    pipeline.run("Chirac", ["Chirac"], 10)
    pipeline.run("Chirac", ["Chirac"], 10)

    assert store._posts.count_documents({}) == 1
    assert store._comments.count_documents({}) == 1
    assert len(list(store._images.find({}))) == 1
