import copy
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from registry.core import (
    RegistryError, build_catalog, package_source, parse_manifest,
    read_json, validate_history, validate_registry,
)


COMMIT = "a" * 40
MANIFEST = {"api": 4, "id": "notes", "version": "1.0.0", "entry": "plugin:Plugin",
            "provides": ["notes"], "requires": [], "enabled": True}


def records():
    return {"schema_version": 1, "plugins": [{"id": "notes", "repository": "https://github.com/example/notes",
            "versions": {"1.0.0": COMMIT}}]}


def archive(extra=(), manifest=None):
    out = io.BytesIO()
    prefix = f"notes-{COMMIT}/"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(prefix + "plugin.yaml", json.dumps(manifest or MANIFEST))
        # Packaging must never import this code or execute a build script.
        z.writestr(prefix + "plugin.py", "raise RuntimeError('must not execute')")
        for name, data in extra:
            if isinstance(name, zipfile.ZipInfo):
                z.writestr(name, data)
            else:
                info = zipfile.ZipInfo()
                # ZipInfo(name) normalizes backslashes on Windows; preserve the
                # hostile wire filename so both CI platforms test the same ZIP.
                info.filename = prefix + name
                z.writestr(info, data)
    return out.getvalue()


class RegistryTests(unittest.TestCase):
    def package(self, source):
        return package_source(source, "https://github.com/example/notes", COMMIT)[0]

    def test_package_preserves_resources_but_removes_local_config(self):
        data = archive([("LICENSE", "license"), ("vendor/runtime.js", "runtime"), ("dist/ui.js", "built UI"),
                        (".env", "SECRET"), ("sub/.env.production", "SECRET"),
                        (".github/workflows/build.yml", "untrusted"), ("logs/run.log", "private"),
                        ("id_rsa", "private key"), ("__pycache__/x.pyc", "cache"),
                        ("vendor/ca.pem", "public certificate"), ("assets/map.key", "resource")])
        first = self.package(data)
        self.assertEqual(first, self.package(data))
        with zipfile.ZipFile(io.BytesIO(first)) as z:
            self.assertEqual(set(z.namelist()), {"notes/plugin.yaml", "notes/plugin.py", "notes/LICENSE",
                                               "notes/vendor/runtime.js", "notes/dist/ui.js",
                                               "notes/vendor/ca.pem", "notes/assets/map.key"})
            self.assertEqual(z.read("notes/vendor/runtime.js"), b"runtime")

    def test_paths_unsafe_on_windows_or_posix_are_rejected(self):
        for name in ("../escape.py", "/absolute", "a\\b", "CON.txt", "a:stream", "a//b", "a/./b", "file. "):
            with self.subTest(name=name), self.assertRaisesRegex(RegistryError, "PATH_INVALID"):
                self.package(archive([(name, "x")]))

    def test_case_and_unicode_collisions_are_rejected(self):
        for names in (("plugin.PY",), ("caf\u00e9.txt", "cafe\u0301.txt"), ("dir", "dir/file")):
            with self.subTest(names=names), self.assertRaisesRegex(RegistryError, "COLLISION"):
                self.package(archive([(n, "x") for n in names]))

    def test_symlink_in_package_is_rejected(self):
        info = zipfile.ZipInfo(f"notes-{COMMIT}/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(RegistryError, "SPECIAL_FILE"):
            self.package(archive([(info, "../../secret")]))

    def test_excluded_files_do_not_affect_package_validation(self):
        info = zipfile.ZipInfo(f"notes-{COMMIT}/.github/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        data = archive([(info, "../../secret"), ("logs/CON.log", "log")])
        self.assertEqual(self.package(data), self.package(archive()))

    def test_nested_manifest_is_rejected(self):
        with self.assertRaisesRegex(RegistryError, "NESTED_MANIFEST"):
            self.package(archive([("another/plugin.yaml", "{}")]))

    def test_catalog_identity_must_match_fixed_source(self):
        for manifest in ({**MANIFEST, "id": "other"}, {**MANIFEST, "version": "2.0.0"}):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "out"
                with self.assertRaisesRegex(RegistryError, "IDENTITY_MISMATCH"):
                    build_catalog(records(), output, "https://downloads.example.test",
                                  lambda *_: archive(manifest=manifest))
                self.assertFalse((output / "catalog/v1/catalog.json").exists())

    def test_entry_and_visual_assets_must_be_in_package(self):
        for manifest, error in (({**MANIFEST, "entry": "missing:Plugin"}, "ENTRY_MISSING"),
                                ({**MANIFEST, "visuals": [{"renderer": ".env"}]}, "VISUAL_ASSET_MISSING")):
            with self.subTest(error=error), self.assertRaisesRegex(RegistryError, error):
                self.package(archive(manifest=manifest))

    def test_file_count_and_size_limits_are_enforced(self):
        for limit, value, code in (("MAX_SOURCE_BYTES", 10, "SOURCE_TOO_LARGE"),
                                   ("MAX_FILES", 1, "PACKAGE_TOO_LARGE"),
                                   ("MAX_PACKAGE_BYTES", 10, "PACKAGE_TOO_LARGE"),
                                   ("MAX_FILE_BYTES", 10, "FILE_TOO_LARGE")):
            with self.subTest(limit=limit), patch(f"registry.core.{limit}", value), self.assertRaisesRegex(RegistryError, code):
                self.package(archive())

    def test_manifest_uses_safe_yaml_and_accepts_standard_aliases(self):
        text = ('api: 4\nid: notes\nversion: 1.0.0\nentry: plugin:Plugin\n'
                'provides: &services [notes]\nrequires: *services\n')
        self.assertEqual(parse_manifest(text.encode())["requires"], ["notes"])
        with self.assertRaisesRegex(RegistryError, "MANIFEST_INVALID"):
            parse_manifest(b"!!python/object/apply:os.system [echo unsafe]")
        with self.assertRaisesRegex(RegistryError, "MANIFEST_NOT_JSON"):
            parse_manifest((json.dumps(MANIFEST)[:-1] + ', "x": .nan}').encode())

    def test_registry_rejects_invalid_versions_commits_and_yanks(self):
        for versions in ({"1.0.0": "main"}, {"1.0.0": "a" * 7}, {"../1.0.0": COMMIT},
                         {"1.0.0-01": COMMIT}, {"1.0.0-A": COMMIT, "1.0.0-a": COMMIT}):
            current = records()
            current["plugins"][0]["versions"] = versions
            with self.subTest(versions=versions), self.assertRaises(RegistryError):
                validate_registry(current)
        for yanked in ({"1.0.0": ""}, {"1.0.0": False}, {"2.0.0": "Broken"}):
            current = records()
            current["plugins"][0]["yanked"] = yanked
            with self.subTest(yanked=yanked), self.assertRaisesRegex(RegistryError, "YANK_REASON_INVALID"):
                validate_registry(current)

    def test_history_can_yank_but_cannot_rewrite_or_delete(self):
        previous = records()
        current = copy.deepcopy(previous)
        current["plugins"][0]["yanked"] = {"1.0.0": "Broken settings"}
        validate_history(current, previous)
        for mutate in (
            lambda c: c["plugins"][0]["versions"].update({"1.0.0": "b" * 40}),
            lambda c: c["plugins"][0].update(versions={"2.0.0": COMMIT}),
            lambda c: c["plugins"][0].update(repository="https://github.com/other/notes"),
            lambda c: c.update(plugins=[]),
        ):
            current = copy.deepcopy(previous)
            mutate(current)
            with self.assertRaisesRegex(RegistryError, "HISTORY_REWRITTEN"):
                validate_history(current, previous)

    def test_catalog_has_exact_origin_and_real_zip_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "distribution"
            calls = []
            def fetch(repo, commit):
                calls.append((repo, commit))
                return archive()
            catalog = build_catalog(records(), output, "https://downloads.example.test", fetch)
            release = catalog["plugins"][0]["versions"][0]
            package = release["package"]
            self.assertEqual(calls, [("https://github.com/example/notes", COMMIT)])
            self.assertEqual(package["size"], (output / package["path"]).stat().st_size)
            self.assertEqual(release["manifest"], MANIFEST)
            self.assertFalse(release["prerelease"])
            self.assertEqual(catalog, read_json(output / "catalog/v1/catalog.json"))
            with self.assertRaises(FileExistsError):
                build_catalog(records(), output, "https://downloads.example.test", fetch)

    def test_failed_download_never_produces_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "distribution"
            def fail(*_):
                raise OSError("offline")
            with self.assertRaisesRegex(OSError, "offline"):
                build_catalog(records(), output, "https://downloads.example.test", fail)
            self.assertFalse((output / "catalog/v1/catalog.json").exists())

    def test_yanked_versions_preserve_history_without_download(self):
        current = records()
        current["plugins"][0]["yanked"] = {"1.0.0": "Broken"}
        with tempfile.TemporaryDirectory() as tmp:
            catalog = build_catalog(current, Path(tmp) / "out", "https://downloads.example.test",
                                    lambda *_: self.fail("must not download yanked source"))
            item = catalog["plugins"][0]["versions"][0]
            self.assertIsNone(item["package"])
            self.assertIsNone(item["manifest"])
            self.assertEqual(item["commit"], COMMIT)
            self.assertEqual(item["yank_reason"], "Broken")

    def test_invalid_download_base_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for url in ("http://example.com", "https://user:password@example.com", "https://example.com/?query=1"):
                with self.subTest(url=url), self.assertRaisesRegex(RegistryError, "BASE_URL_INVALID"):
                    build_catalog(records(), Path(tmp) / "out", url)
            self.assertFalse((Path(tmp) / "out").exists())


if __name__ == "__main__":
    unittest.main()
