"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mongo_atlas_sdk import __version__
from mongo_atlas_sdk.config import Settings
from mongo_atlas_sdk.crawler import (
    SPEC_URL,
    SpecSourceError,
    extract_api_docs,
    fetch_spec,
    load_spec,
    write_json_document,
)
from mongo_atlas_sdk.generator import LANGUAGES, GeneratorError, generate, get_target
from mongo_atlas_sdk.normalizer import normalize_api_docs

DEFAULT_OUTPUT = Path(".data/api_docs.json")
DEFAULT_NORMALIZED_OUTPUT = Path(".data/normalized_api_docs.json")


def _add_generation_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_NORMALIZED_OUTPUT,
        help="Normalized document to read (default: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Package directory to generate into (default: the language target).",
    )
    parser.add_argument(
        "--package",
        default=None,
        help="Import name of the generated package (default: the language target).",
    )


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

    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Crawl the Atlas API docs into .data/api_docs.json.",
        description=(
            "Download the official Atlas OpenAPI document and project it onto the "
            "raw intermediate structure used by the SDK generator."
        ),
    )
    crawl_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output path (default: %(default)s).",
    )
    crawl_parser.add_argument(
        "--source",
        default=SPEC_URL,
        help="OpenAPI document URL (default: %(default)s).",
    )
    crawl_parser.add_argument(
        "--spec",
        type=Path,
        help="Read a local OpenAPI file instead of downloading it.",
    )

    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize .data/api_docs.json into .data/normalized_api_docs.json.",
        description=(
            "Resolve $ref/allOf/oneOf and emit the closed, generator-facing API document."
        ),
    )
    normalize_parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Raw document to read (default: %(default)s).",
    )
    normalize_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_NORMALIZED_OUTPUT,
        help="Output path (default: %(default)s).",
    )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate an SDK for a supported target language.",
        description="Render an SDK from .data/normalized_api_docs.json.",
    )
    generate_parser.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        default="python",
        help="Target language (default: %(default)s).",
    )
    _add_generation_arguments(generate_parser)

    pygen_parser = subparsers.add_parser(
        "pygen",
        help="Alias for `generate --language python`.",
        description="Render the Python SDK from .data/normalized_api_docs.json.",
    )
    _add_generation_arguments(pygen_parser)
    return parser


def _crawl(args: argparse.Namespace) -> int:
    try:
        if args.spec is not None:
            spec = load_spec(args.spec)
            source = str(args.spec)
        else:
            spec = fetch_spec(args.source)
            source = str(args.source)
    except SpecSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    docs = extract_api_docs(spec, source_url=source)
    write_json_document(docs, args.output)
    endpoints = sum(len(category["endpoints"]) for category in docs["categories"])
    print(f"wrote {args.output} ({len(docs['categories'])} categories, {endpoints} endpoints)")
    return 0


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(document, dict):
        print(f"error: {path} must contain a JSON object", file=sys.stderr)
        return None
    return document


def _normalize(args: argparse.Namespace) -> int:
    docs = _load_json_object(args.input)
    if docs is None:
        return 1
    if "schemas" not in docs:
        print(
            f"error: {args.input} has no 'schemas' section; re-run `mongo-atlas crawl`",
            file=sys.stderr,
        )
        return 1

    normalized = normalize_api_docs(docs)
    write_json_document(normalized, args.output)
    stats = normalized["meta"]["stats"]
    print(
        f"wrote {args.output} ({stats['categories']} categories, "
        f"{stats['endpoints']} endpoints, {stats['types']} types)"
    )
    warnings = normalized["meta"]["warnings"]
    if warnings:
        print(f"warnings: {len(warnings)}", file=sys.stderr)
    return 0


def _generate(args: argparse.Namespace, language: str) -> int:
    docs = _load_json_object(args.input)
    if docs is None:
        return 1
    if "types" not in docs or "categories" not in docs:
        print(
            f"error: {args.input} is not a normalized document; re-run `mongo-atlas normalize`",
            file=sys.stderr,
        )
        return 1

    try:
        target = get_target(language)
        output = args.output if args.output is not None else target.default_output
        stats = generate(language, docs, output_root=output, package=args.package)
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"wrote {output} ({stats['models']} models, "
        f"{stats['resources']} resources, {stats['methods']} methods)"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        settings = Settings.from_env()
        print(settings.describe(show_secrets=bool(args.show_secrets)))
        return 0

    if args.command == "crawl":
        return _crawl(args)

    if args.command == "normalize":
        return _normalize(args)

    if args.command == "generate":
        return _generate(args, str(args.language))

    if args.command == "pygen":
        return _generate(args, "python")

    parser.print_help()
    return 0
