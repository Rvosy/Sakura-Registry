"""Prepare GitHub Release assets from a previously built distribution."""
import argparse
import copy
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry.core import read_json, write_json, validate_base_url


def prepare(distribution: Path, output: Path, base_url: str) -> dict:
    validate_base_url(base_url)
    output.mkdir(parents=True, exist_ok=False)
    catalog = copy.deepcopy(read_json(distribution / "catalog/v1/catalog.json"))
    for plugin in catalog["plugins"]:
        for release in plugin["versions"]:
            package = release["package"]
            if package is None:
                continue
            source = (distribution / package["path"]).resolve(strict=True)
            if not source.is_relative_to(distribution.resolve()):
                raise ValueError("PACKAGE_OUTSIDE_DISTRIBUTION")
            name = f"{plugin['id']}_{release['version']}_{release['commit']}.zip"
            if Path(name).name != name or "\\" in name:
                raise ValueError("PACKAGE_NAME_INVALID")
            shutil.copyfile(source, output / name)
            package.update(path=name, url=f"{base_url.rstrip('/')}/{name}")
    write_json(output / "catalog.json", catalog)
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    prepare(args.distribution, args.output, args.base_url)
