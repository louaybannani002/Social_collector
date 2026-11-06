"""Smoke test against the REAL MongoDB (local or Atlas) configured in .env.

Checks the connection, then saves a fake post + comment + image through MongoStore,
reads them back, and finally deletes the temporary database.

Usage:  python check_mongo.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

from collector.config import mongo_uri_from_env
from collector.images import DownloadedImage
from collector.models import Comment, Post
from collector.storage import MongoStore

TEST_DB = "social_collector_smoke_test"


def main() -> int:
    load_dotenv()
    uri = mongo_uri_from_env()
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)

    try:
        version = client.server_info()["version"]
    except Exception as exc:  # never print the URI: it contains the password
        print(f"[FAIL] Connection failed: {type(exc).__name__}")
        print("  - Atlas: is the cluster resumed, and is your IP in Network Access?")
        print("  - Is the password correct (special characters must be URL-encoded)?")
        client.close()
        return 1
    print(f"[OK] Connected to MongoDB {version}")

    try:
        store = MongoStore(uri, TEST_DB, client=client)
        post = Post(
            platform="test",
            post_id="smoke_1",
            text="Hommage à Jacques Chirac",
            image_urls=["https://example.com/a.jpg"],
            comments=[Comment("c1", "RIP", "tester")],
            topic="smoke test",
        )
        image = DownloadedImage("https://example.com/a.jpg", b"fake-image-bytes", "image/jpeg", "sha-smoke")
        image_id = store.save_image("test", "smoke_1", image)
        store.save_post(post, [image_id])
        store.save_post(post, [image_id])  # second save must not create duplicates

        db = client[TEST_DB]
        assert db["posts"].count_documents({}) == 1, "post duplicated or missing"
        assert db["comments"].count_documents({}) == 1, "comment duplicated or missing"
        assert db["images.files"].count_documents({}) == 1, "image duplicated or missing"
        print("[OK] Post, comment and image stored; re-saving created no duplicates")
        return 0
    except Exception as exc:
        print(f"[FAIL] Storage check failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        client.drop_database(TEST_DB)
        client.close()
        print("[OK] Temporary database removed")


if __name__ == "__main__":
    sys.exit(main())
