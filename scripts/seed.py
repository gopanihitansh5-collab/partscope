"""Generate the deterministic demo dataset, synthetic images and retrieval index."""

from __future__ import annotations

import argparse
import json
import time

from src.common.db import SessionLocal, init_db
from src.common.logging import get_logger
from src.retrieval import service as retrieval_service
from src.seed.generator import dataset_summary, generate_images, seed_database

log = get_logger("seed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the PartScope demo dataset")
    parser.add_argument("--no-reset", action="store_true", help="Keep existing rows")
    parser.add_argument("--no-images", action="store_true", help="Skip image rendering")
    parser.add_argument("--no-index", action="store_true", help="Skip retrieval indexing")
    args = parser.parse_args()

    started = time.perf_counter()
    init_db()

    stats = seed_database(reset=not args.no_reset)
    log.info("database_seeded", **stats.__dict__)

    if not args.no_images:
        images = generate_images()
        log.info("images_rendered", images=images)

    if not args.no_index:
        with SessionLocal() as session:
            index = retrieval_service.build_index(session)
            log.info("retrieval_indexed", chunks=index.chunks, vocab=index.vocab_size)

    summary = dataset_summary()
    summary["seconds"] = round(time.perf_counter() - started, 2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
