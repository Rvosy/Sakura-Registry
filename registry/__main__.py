import argparse
import sys
from pathlib import Path

from .core import RegistryError, build_catalog, read_json, validate_history, validate_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Sakura Registry records or build a static distribution.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--registry", type=Path, default=Path("plugins.json"))
    validate.add_argument("--previous", type=Path)
    build = sub.add_parser("build")
    build.add_argument("--registry", type=Path, default=Path("plugins.json"))
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        records = read_json(args.registry)
        if args.command == "validate":
            if args.previous:
                validate_history(records, read_json(args.previous))
            else:
                validate_registry(records)
            print("Registry validated.")
        else:
            catalog = build_catalog(records, args.output, args.base_url)
            print(f"Built {len(catalog['plugins'])} plugin(s): {args.output / 'catalog/v1/catalog.json'}")
    except (RegistryError, OSError, ValueError) as error:
        print(f"Registry failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
