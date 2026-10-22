"""Support ``python -m mongo_atlas_sdk``."""

from mongo_atlas_sdk.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
