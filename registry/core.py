"""Build data and ZIPs only; never import or execute plugin code."""

from __future__ import annotations

import io
import json
import re
import stat
import unicodedata
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import yaml

MAX_SOURCE_BYTES = 64 * 1024 * 1024
# Match Sakura's installer limits for files that actually enter the package.
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 512
MAX_MANIFEST_BYTES = 64 * 1024
ID = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,62}[A-Za-z0-9_-])?")
COMMIT = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"https://github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9_.-]{1,100})")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")
PYTHON_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
EXCLUDED = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ds_store", "logs", "tmp", "temp"}


class RegistryError(ValueError):
    """Stable failure codes, with no partial catalog publication."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RegistryError(code)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_parts(name: str) -> tuple[str, ...]:
    require(isinstance(name, str) and bool(name), "PATH_INVALID")
    parts = tuple(name.split("/"))
    for part in parts:
        require(bool(part) and part not in {".", ".."} and not part.endswith((".", " "))
                and not re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', part)
                and part.split(".")[0].casefold() not in RESERVED
                and len(part.encode("utf-8")) <= 240, "PATH_INVALID")
    return parts


def excluded(parts: tuple[str, ...]) -> bool:
    return any(p.casefold() in EXCLUDED or p.casefold() == ".env" or p.casefold().startswith(".env.")
               or p.casefold().endswith(".pyc")
               or p.casefold() in {"id_rsa", "id_ed25519", ".npmrc", ".pypirc"} for p in parts)


def version_match(value: str):
    require(isinstance(value, str), "VERSION_INVALID")
    match = VERSION.fullmatch(value)
    require(match is not None, "VERSION_INVALID")
    require(not match[4] or all(not p.isdigit() or p == "0" or not p.startswith("0")
                               for p in match[4].split(".")), "VERSION_INVALID")
    return match


def validate_manifest(manifest: dict) -> None:
    require(isinstance(manifest, dict), "MANIFEST_INVALID")
    require(not {"plugin_id", "api_version", "optional"} & manifest.keys(), "MANIFEST_INVALID")
    require(type(manifest.get("api")) is int and manifest["api"] == 4, "API_UNSUPPORTED")
    require(isinstance(manifest.get("id"), str) and ID.fullmatch(manifest["id"]) is not None, "ID_INVALID")
    safe_parts(manifest["id"])
    version_match(manifest.get("version"))
    require(not manifest.get("required", False), "REQUIRED_PLUGIN_FORBIDDEN")
    entry = manifest.get("entry", "")
    require(isinstance(entry, str), "ENTRY_INVALID")
    module, sep, cls = entry.partition(":")
    require(sep == ":" and all(PYTHON_NAME.fullmatch(p) for p in module.split("."))
            and PYTHON_NAME.fullmatch(cls) is not None, "ENTRY_INVALID")
    # Snapshots must remain JSON values; YAML timestamps or cycles are not wire data.
    try:
        json.dumps(manifest, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise RegistryError("MANIFEST_NOT_JSON") from error


def parse_manifest(data: bytes) -> dict:
    require(len(data) <= MAX_MANIFEST_BYTES, "MANIFEST_TOO_LARGE")
    try:
        value = yaml.safe_load(data.decode("utf-8"))
    except (yaml.YAMLError, UnicodeError, RecursionError) as error:
        raise RegistryError("MANIFEST_INVALID") from error
    validate_manifest(value)
    return value


def validate_registry(value: dict) -> None:
    require(isinstance(value, dict) and set(value) == {"schema_version", "plugins"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and isinstance(value["plugins"], list), "REGISTRY_INVALID")
    seen = set()
    for plugin in value["plugins"]:
        require(isinstance(plugin, dict) and set(plugin) == {"id", "repository", "versions"}, "PLUGIN_INVALID")
        pid = plugin["id"]
        require(isinstance(pid, str) and ID.fullmatch(pid) is not None, "ID_INVALID")
        safe_parts(pid)
        require(pid.casefold() not in seen, "DUPLICATE_PLUGIN")
        seen.add(pid.casefold())
        repo = plugin["repository"]
        require(isinstance(repo, str) and REPOSITORY.fullmatch(repo) is not None
                and repo.rsplit("/", 1)[1] not in {".", ".."} and not repo.endswith(".git"), "REPOSITORY_INVALID")
        versions = plugin["versions"]
        require(isinstance(versions, list) and bool(versions), "VERSIONS_INVALID")
        numbers = set()
        for release in versions:
            require(isinstance(release, dict) and set(release) == {
                "version", "commit", "manifest", "notes", "yanked", "yank_reason"}, "VERSION_RECORD_INVALID")
            number = release["version"]
            version_match(number)
            require(number.casefold() not in numbers, "DUPLICATE_VERSION")
            numbers.add(number.casefold())
            require(isinstance(release["commit"], str) and COMMIT.fullmatch(release["commit"]) is not None,
                    "EXACT_COMMIT_REQUIRED")
            validate_manifest(release["manifest"])
            require(release["manifest"]["id"] == pid and release["manifest"]["version"] == number,
                    "MANIFEST_IDENTITY_MISMATCH")
            require(isinstance(release["notes"], str) and type(release["yanked"]) is bool
                    and isinstance(release["yank_reason"], str), "VERSION_RECORD_INVALID")
            require(bool(release["yank_reason"].strip()) == release["yanked"], "YANK_REASON_INVALID")


def validate_history(current: dict, previous: dict) -> None:
    validate_registry(current)
    validate_registry(previous)
    by_id = {p["id"]: p for p in current["plugins"]}
    for old in previous["plugins"]:
        new = by_id.get(old["id"])
        require(new is not None and new["repository"] == old["repository"], "PLUGIN_HISTORY_REWRITTEN")
        versions = {v["version"]: v for v in new["versions"]}
        for release in old["versions"]:
            candidate = versions.get(release["version"])
            require(candidate is not None and all(candidate[k] == release[k]
                    for k in ("commit", "manifest")), "VERSION_HISTORY_REWRITTEN")


def source_url(repository: str, commit: str) -> str:
    # Repository and commit have already been checked by validate_registry.
    return f"https://codeload.github.com/{repository.removeprefix('https://github.com/')}/zip/{commit}"


def download_source(repository: str, commit: str) -> bytes:
    request = urllib.request.Request(source_url(repository, commit), headers={"User-Agent": "Sakura-Registry/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_SOURCE_BYTES + 1)
    require(len(data) <= MAX_SOURCE_BYTES, "SOURCE_TOO_LARGE")
    return data


def package_source(data: bytes, repository: str, release: dict) -> bytes:
    require(len(data) <= MAX_SOURCE_BYTES, "SOURCE_TOO_LARGE")
    prefix = f"{repository.rsplit('/', 1)[1]}-{release['commit']}"
    files = {}
    paths = set()
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            for info in source.infolist():
                root, separator, relative = info.orig_filename.partition("/")
                require(root == prefix, "SOURCE_ROOT_MISMATCH")
                if info.is_dir() or (separator and excluded(tuple(relative.split("/")))):
                    continue
                # ZipInfo normalizes backslashes on Windows and truncates NUL.
                # Validate the wire name before trusting its normalized filename.
                require(info.orig_filename == info.filename, "PATH_INVALID")
                parts = safe_parts(relative)
                mode = stat.S_IFMT(info.external_attr >> 16)
                require(mode in {0, stat.S_IFREG, stat.S_IFDIR}, "SOURCE_SPECIAL_FILE")
                require(not info.flag_bits & 1, "SOURCE_ENCRYPTED")
                key = unicodedata.normalize("NFC", relative).casefold()
                require(key not in paths, "SOURCE_PATH_COLLISION")
                paths.add(key)
                require(info.file_size <= MAX_FILE_BYTES, "FILE_TOO_LARGE")
                total += info.file_size
                require(total <= MAX_PACKAGE_BYTES and len(files) < MAX_FILES, "PACKAGE_TOO_LARGE")
                files["/".join(parts)] = source.read(info)
            for key in paths:
                parts = key.split("/")
                require(all("/".join(parts[:i]) not in paths for i in range(1, len(parts))),
                        "SOURCE_PATH_COLLISION")
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise RegistryError("SOURCE_ZIP_INVALID") from error
    require("plugin.yaml" in files, "MANIFEST_MISSING")
    require(all(name == "plugin.yaml" or name.rsplit("/", 1)[-1].casefold() != "plugin.yaml" for name in files),
            "NESTED_MANIFEST")
    manifest = parse_manifest(files["plugin.yaml"])
    require(manifest == release["manifest"], "MANIFEST_SNAPSHOT_MISMATCH")
    module = manifest["entry"].partition(":")[0].replace(".", "/") + ".py"
    require(module in files, "ENTRY_MISSING")
    visuals = manifest.get("visuals", [])
    require(isinstance(visuals, list), "VISUALS_INVALID")
    for visual in visuals:
        require(isinstance(visual, dict), "VISUALS_INVALID")
        for field in ("renderer", "editor"):
            if field in visual:
                safe_parts(visual[field])
                require(visual[field] in files, "VISUAL_ASSET_MISSING")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(f"{manifest['id']}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content)
    return output.getvalue()


def validate_base_url(base_url: str) -> None:
    url = urlsplit(base_url)
    require(url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
            and not url.query and not url.fragment and not any(c.isspace() for c in base_url), "BASE_URL_INVALID")


def build_catalog(records: dict, output: Path, base_url: str, fetch=download_source) -> dict:
    validate_registry(records)
    validate_base_url(base_url)
    # Each invocation owns a fresh staging directory. On failure there is no catalog.
    output.mkdir(parents=True, exist_ok=False)
    catalog = {"schema_version": 1, "plugins": []}
    for plugin in records["plugins"]:
        result = {"id": plugin["id"], "repository": plugin["repository"], "versions": []}
        for release in plugin["versions"]:
            item = {**release, "prerelease": bool(version_match(release["version"])[4]), "package": None}
            if not release["yanked"]:
                data = fetch(plugin["repository"], release["commit"])
                package = package_source(data, plugin["repository"], release)
                path = f"plugins/{plugin['id']}/{release['version']}/{release['commit']}/plugin.zip"
                target = output / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package)
                item["package"] = {"path": path, "url": f"{base_url.rstrip('/')}/{path}", "size": len(package)}
            result["versions"].append(item)
        catalog["plugins"].append(result)
    write_json(output / "catalog/v1/catalog.json", catalog)
    return catalog
