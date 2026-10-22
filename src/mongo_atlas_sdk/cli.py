"""Command line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from mongo_atlas_sdk import __version__
from mongo_atlas_sdk.config import Settings


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="mongo-atlas",
        description="MongoDB Atlas SDK command line tool.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    config_parser = subparsers.add_parser(
        "config",
        help="Print the resolved configuration.",
        description="Print the configuration resolved from environment variables.",
    )
    config_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Print API keys in clear text (never use in shared logs).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        settings = Settings.from_env()
        print(settings.describe(show_secrets=bool(args.show_secrets)))
        return 0

    parser.print_help()
    return 0
