"""Run Sakura's real installer in disposable roots, never start a plugin."""
import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sakura-root", required=True, type=Path)
    parser.add_argument("--distribution", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.sakura_root.resolve(strict=True)))
    from app.plugins.discovery import PluginDiscovery
    from app.plugins.installer import LocalPluginInstaller
    from app.storage.runtime_roots import RuntimeRoots

    distribution = args.distribution.resolve(strict=True)
    catalog = json.loads((distribution / "catalog/v1/catalog.json").read_text(encoding="utf-8"))
    checked = 0
    for plugin in catalog["plugins"]:
        for release in plugin["versions"]:
            if release["package"] is None:
                continue
            package = (distribution / release["package"]["path"]).resolve(strict=True)
            if not package.is_relative_to(distribution):
                raise ValueError("PACKAGE_OUTSIDE_DISTRIBUTION")
            if package.stat().st_size != release["package"]["size"]:
                raise ValueError("PACKAGE_SIZE_MISMATCH")
            with zipfile.ZipFile(package) as archive:
                # Dependency setup can execute external build tools. The Phase 1
                # sample has no Python dependencies; don't run them in this probe.
                if any(Path(n).name in {"requirements.txt", "requirements.lock", "pyproject.toml"} for n in archive.namelist()):
                    raise ValueError("INSTALL_PROBE_DEPENDENCIES_UNSUPPORTED")
            with tempfile.TemporaryDirectory(prefix="sakura-registry-install-") as tmp:
                roots = RuntimeRoots(Path(tmp) / "distribution", Path(tmp) / "user")
                installer = LocalPluginInstaller(roots)
                result = installer.install(package, "zip")
                if result.plugin_id != plugin["id"]:
                    raise AssertionError("INSTALL_ID_MISMATCH")
                specs = PluginDiscovery(roots).discover()
                if len(specs) != 1 or specs[0].version != release["version"] or specs[0].enabled:
                    raise AssertionError("INSTALL_STATE_MISMATCH")
                print(f"PASS {result.plugin_id} {specs[0].version}: installed disabled")
                checked += 1
    if not checked:
        raise ValueError("NO_PACKAGES_VERIFIED")


if __name__ == "__main__":
    main()
