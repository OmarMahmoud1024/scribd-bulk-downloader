#!/usr/bin/env python3
"""
CLI entrypoint.

    python main.py scrape --keywords keywords.txt [--max-pages 20]
    python main.py download [--input data/metadata.jsonl]
    python main.py status
"""
import argparse

from src import config
from src.auth_manager import AuthManager
from src import scraper, downloader


def cmd_scrape(args):
    with open(args.keywords, "r", encoding="utf-8") as f:
        keywords = [line.strip() for line in f if line.strip()]
    scraper.run(keywords, max_pages_per_keyword=args.max_pages)


def cmd_download(args):
    downloader.run(metadata_path=args.input)


def cmd_status(_args):
    auth = AuthManager()
    for entry in auth.status():
        print(f"{entry['account_id']:>20}  used {entry['used_today']:>4} / "
              f"{config.DAILY_LIMIT_PER_ACCOUNT}  (remaining {entry['remaining']})")


def main():
    parser = argparse.ArgumentParser(description="Scribd bulk metadata scraper & downloader")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="Phase 1: keyword search -> metadata.jsonl")
    p_scrape.add_argument("--keywords", required=True, help="Path to a text file, one keyword per line")
    p_scrape.add_argument("--max-pages", type=int, default=20)
    p_scrape.set_defaults(func=cmd_scrape)

    p_download = sub.add_parser("download", help="Phase 2: metadata.jsonl -> downloaded files")
    p_download.add_argument("--input", default=None)
    p_download.set_defaults(func=cmd_download)

    p_status = sub.add_parser("status", help="Show remaining daily download budget per account")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
