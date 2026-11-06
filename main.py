"""Command line entry point.

Example:
    python main.py --topic "Décès de Jacques Chirac" \
        --keywords "Jacques Chirac" "Chirac" \
        --fb-pages 123456789 \
        --ig-user-id 17841400000000000 --ig-hashtags jacqueschirac
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from collector.base import BaseCollector
from collector.config import ConfigError, Settings
from collector.facebook import FacebookCollector
from collector.graph_client import GraphClient
from collector.images import ImageDownloader
from collector.instagram import InstagramCollector
from collector.pipeline import CollectionPipeline
from collector.storage import MongoStore
from pymongo.errors import PyMongoError


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Facebook/Instagram posts about a topic into MongoDB.")
    parser.add_argument("--topic", required=True, help='Topic label, e.g. "Décès de Jacques Chirac"')
    parser.add_argument("--keywords", nargs="+", required=True, help="Keywords used to filter posts")
    parser.add_argument("--platform", choices=("facebook", "instagram", "all"), default="all")
    parser.add_argument("--limit", type=positive_int, default=50, help="Max posts per platform (default: 50)")
    parser.add_argument("--fb-pages", nargs="*", default=[], help="Facebook Page IDs to scan")
    parser.add_argument("--ig-user-id", help="Instagram Business account ID (required for Instagram)")
    parser.add_argument("--ig-hashtags", nargs="*", default=[], help="Hashtags to search (without #)")
    parser.add_argument("--ig-own-media", action="store_true", help="Also scan the account's own media")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def build_collectors(args: argparse.Namespace, client: GraphClient) -> List[BaseCollector]:
    collectors: List[BaseCollector] = []
    if args.platform in ("facebook", "all"):
        if args.fb_pages:
            collectors.append(FacebookCollector(client, args.fb_pages))
        else:
            logging.warning("Facebook skipped: no --fb-pages given")
    if args.platform in ("instagram", "all"):
        if args.ig_user_id and (args.ig_hashtags or args.ig_own_media):
            collectors.append(
                InstagramCollector(client, args.ig_user_id, args.ig_hashtags, args.ig_own_media)
            )
        else:
            logging.warning("Instagram skipped: need --ig-user-id and --ig-hashtags/--ig-own-media")
    return collectors


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        logging.error("%s", exc)
        return 2

    client = GraphClient(
        settings.access_token,
        version=settings.graph_version,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
    )
    collectors = build_collectors(args, client)
    if not collectors:
        logging.error("Nothing to collect: check your arguments.")
        return 2

    store: Optional[MongoStore] = None
    try:
        store = MongoStore(settings.mongo_uri, settings.mongo_db)
        pipeline = CollectionPipeline(collectors, store, ImageDownloader(timeout=settings.request_timeout))
        stats = pipeline.run(args.topic, args.keywords, args.limit)
    except PyMongoError as exc:
        logging.error("MongoDB operation failed: %s", type(exc).__name__)
        return 1
    finally:
        if store is not None:
            store.close()

    logging.info("Done: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
