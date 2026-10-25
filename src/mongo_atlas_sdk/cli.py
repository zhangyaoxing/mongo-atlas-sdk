"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mongo_atlas_sdk import __version__
from mongo_atlas_sdk.apis import APIS, get_api
from mongo_atlas_sdk.config import Settings
from mongo_atlas_sdk.crawler import (
    SpecSourceError,
    extract_api_docs,
    fetch_spec,
    load_spec,
    write_json_document,
)
from mongo_atlas_sdk.generator import LANGUAGES, GeneratorError, generate_python
from mongo_atlas_sdk.normalizer import normalize_api_docs


def _add_generation_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--api",
        choices=sorted(APIS),
        default="admin",
        help="API to generate (default: %(default)s).",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="Normalized document to read (default: the API target).",
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
        "--api",
        choices=sorted(APIS),
        default="admin",
        help="API to crawl (default: %(default)s).",
    )
    crawl_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: the API target).",
    )
    crawl_parser.add_argument(
        "--source",
        default=None,
        help="OpenAPI document URL (default: the API target).",
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
        "--api",
        choices=sorted(APIS),
        default="admin",
        help="API to normalize (default: %(default)s).",
    )
    normalize_parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="Raw document to read (default: the API target).",
    )
    normalize_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: the API target).",
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
    api = get_api(args.api)
    source = args.source or api.spec_url
    output = args.output or api.raw_document
    try:
        if args.spec is not None:
            spec = load_spec(args.spec)
            source = str(args.spec)
        else:
            spec = fetch_spec(source)
    except SpecSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    docs = extract_api_docs(spec, source_url=source)
    write_json_document(docs, output)
    endpoints = sum(len(category["endpoints"]) for category in docs["categories"])
    print(f"wrote {output} ({len(docs['categories'])} categories, {endpoints} endpoints)")
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
    api = get_api(args.api)
    input_path = args.input or api.raw_document
    output = args.output or api.normalized_document
    docs = _load_json_object(input_path)
    if docs is None:
        return 1
    if "schemas" not in docs:
        print(
            f"error: {input_path} has no 'schemas' section; re-run `mongo-atlas crawl`",
            file=sys.stderr,
        )
        return 1

    normalized = normalize_api_docs(docs)
    write_json_document(normalized, output)
    stats = normalized["meta"]["stats"]
    print(
        f"wrote {output} ({stats['categories']} categories, "
        f"{stats['endpoints']} endpoints, {stats['types']} types)"
    )
    warnings = normalized["meta"]["warnings"]
    if warnings:
        print(f"warnings: {len(warnings)}", file=sys.stderr)
    return 0


def _generate(args: argparse.Namespace, language: str) -> int:
    api = get_api(args.api)
    input_path = args.input or api.normalized_document
    output = args.output or api.output_root
    docs = _load_json_object(input_path)
    if docs is None:
        return 1
    if "types" not in docs or "categories" not in docs:
        print(
            f"error: {input_path} is not a normalized document; re-run `mongo-atlas normalize`",
            file=sys.stderr,
        )
        return 1

    try:
        stats = generate_python(
            docs,
            output,
            package=args.package or api.package,
            client_class=api.client_class,
            base_url=api.base_url,
            auth_mode=api.auth_mode,
            path_prefix=api.path_prefix,
        )
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
