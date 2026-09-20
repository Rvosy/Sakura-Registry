import tempfile
import unittest
from pathlib import Path

from registry.core import build_catalog
from tools.release_assets import prepare
from test_registry import archive, records


class ReleaseAssetTests(unittest.TestCase):
    def test_release_assets_keep_metadata_and_package_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            distribution, output = Path(tmp) / "dist", Path(tmp) / "assets"
            original = build_catalog(records(), distribution, "https://example.invalid", lambda *_: archive())
            catalog = prepare(distribution, output, "https://github.com/example/registry/releases/download/catalog-1")
            release = catalog["plugins"][0]["versions"][0]
            old = original["plugins"][0]["versions"][0]
            self.assertEqual(release["manifest"], old["manifest"])
            self.assertEqual((output / release["package"]["path"]).read_bytes(), (distribution / old["package"]["path"]).read_bytes())
            self.assertEqual(release["package"]["url"].rsplit("/", 1)[1], release["package"]["path"])
            self.assertTrue((output / "catalog.json").is_file())
