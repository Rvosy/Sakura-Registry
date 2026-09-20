"""Issue submissions become reviewed records; upstream code is never executed."""
from __future__ import annotations

import base64
import copy
import io
import json
import re
import subprocess
import zipfile
from urllib.parse import quote

from .core import (
    COMMIT, ID, REPOSITORY, RegistryError, download_source,
    package_source, require, validate_history, validate_registry,
)


class GitHubError(RuntimeError):
    pass


class GitHub:
    def request(self, method, path, data=None, *, missing_ok=False, binary=False):
        command = ["gh", "api", "--method", method, path]
        payload = None
        if data is not None:
            command += ["--input", "-"]
            payload = json.dumps(data).encode("utf-8")
        result = subprocess.run(command, input=payload, capture_output=True)
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")
            if missing_ok and "(HTTP 404)" in message:
                return None
            raise GitHubError(message.strip())
        if binary:
            return result.stdout
        return json.loads(result.stdout) if result.stdout else None


def fields_from_body(body):
    parts = re.split(r"(?m)^### (.+)\r?\n", body or "")
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def field(fields, name):
    value = fields.get(name, "")
    return "" if value == "_No response_" else value


def read_registry(api, repository, ref):
    content = api.request("GET", f"repos/{repository}/contents/plugins.json?ref={quote(ref, safe='')}")
    return json.loads(base64.b64decode(content["content"]))


def apply_candidate(records, candidate):
    updated = copy.deepcopy(records)
    plugin = candidate["plugin"]
    validate_registry({"schema_version": 1, "plugins": [plugin]})
    existing = next((p for p in updated["plugins"] if p["id"] == plugin["id"]), None)
    version, commit = next(iter(plugin["versions"].items()))
    if candidate["operation"] == "submit":
        if existing is None:
            updated["plugins"].append(copy.deepcopy(plugin))
        else:
            require(existing["repository"] == plugin["repository"], "REPOSITORY_CHANGED")
            require(version not in existing["versions"], "VERSION_ALREADY_LISTED")
            existing["versions"][version] = commit
    else:
        require(existing is not None and existing["repository"] == plugin["repository"], "PLUGIN_NOT_LISTED")
        require(version in existing["versions"], "VERSION_NOT_LISTED")
        require(existing["versions"][version] == commit, "VERSION_HISTORY_REWRITTEN")
        was_yanked = version in existing.get("yanked", {})
        is_yanked = version in plugin.get("yanked", {})
        require(was_yanked != is_yanked, "VERSION_STATE_UNCHANGED")
        if is_yanked:
            existing.setdefault("yanked", {})[version] = plugin["yanked"][version]
        else:
            del existing["yanked"][version]
            if not existing["yanked"]:
                del existing["yanked"]
    validate_history(updated, records)
    return updated


def prepare_candidate(issue, records, api, fetch=download_source):
    require(issue["state"] == "open" and "pull_request" not in issue, "ISSUE_NOT_OPEN")
    fields = fields_from_body(issue["body"])
    plugin_id = field(fields, "插件 ID")
    require(ID.fullmatch(plugin_id) is not None, "ID_INVALID")
    package = None
    if "GitHub 仓库" in fields:
        repository = field(fields, "GitHub 仓库").rstrip("/").removesuffix(".git")
        require(REPOSITORY.fullmatch(repository) is not None, "REPOSITORY_INVALID")
        slug = repository.removeprefix("https://github.com/")
        ref = field(fields, "要收录的版本")
        for prefix in (f"{repository}/releases/tag/", f"{repository}/tree/", f"{repository}/commit/"):
            if ref.startswith(prefix):
                from urllib.parse import unquote
                ref = unquote(ref.removeprefix(prefix))
                break
        if not ref:
            latest = api.request("GET", f"repos/{slug}/releases/latest", missing_ok=True)
            ref = latest["tag_name"] if latest else "HEAD"
        resolved = api.request("GET", f"repos/{slug}/commits/{quote(ref, safe='')}")
        commit = resolved["sha"]
        require(COMMIT.fullmatch(commit) is not None, "EXACT_COMMIT_REQUIRED")
        package, manifest = package_source(fetch(repository, commit), repository, commit)
        require(manifest["id"] == plugin_id, "MANIFEST_IDENTITY_MISMATCH")
        plugin = {"id": plugin_id, "repository": repository, "versions": {manifest["version"]: commit}}
        operation = "submit"
    else:
        action = field(fields, "操作")
        require(action in {"撤回版本", "恢复版本"}, "CHANGE_REQUIRES_MANUAL_REVIEW")
        existing = next((p for p in records["plugins"] if p["id"] == plugin_id), None)
        require(existing is not None, "PLUGIN_NOT_LISTED")
        version = field(fields, "版本号")
        commit = existing["versions"].get(version)
        require(commit is not None, "VERSION_NOT_LISTED")
        plugin = {"id": plugin_id, "repository": existing["repository"], "versions": {version: commit}}
        operation = "yank" if action == "撤回版本" else "restore"
        if operation == "yank":
            plugin["yanked"] = {version: field(fields, "原因或说明")}
        else:
            package, manifest = package_source(fetch(plugin["repository"], commit), plugin["repository"], commit)
            require(manifest["id"] == plugin_id and manifest["version"] == version, "MANIFEST_IDENTITY_MISMATCH")
    validate_registry({"schema_version": 1, "plugins": [plugin]})
    candidate = {"issue_number": issue["number"], "issue_body": issue["body"],
                 "operation": operation, "plugin": plugin}
    apply_candidate(records, candidate)
    return candidate, package


def require_maintainer(api, repository, login):
    permission = api.request("GET", f"repos/{repository}/collaborators/{quote(login, safe='')}/permission")
    require(permission["permission"] in {"admin", "maintain", "write"}, "MAINTAINER_REQUIRED")


def approved_candidate(api, repository, run_id, issue):
    run = api.request("GET", f"repos/{repository}/actions/runs/{run_id}")
    # Only our successful default-branch check can supply approval data.
    default = api.request("GET", f"repos/{repository}")["default_branch"]
    require(run["path"] == ".github/workflows/submission.yml" and run["head_branch"] == default
            and run["event"] in {"issues", "issue_comment"} and run["conclusion"] == "success"
            and run["head_repository"]["full_name"] == repository, "CHECK_RUN_INVALID")
    artifacts = api.request("GET", f"repos/{repository}/actions/runs/{run_id}/artifacts")["artifacts"]
    artifact = next((a for a in artifacts if a["name"] == "submission" and not a["expired"]), None)
    require(artifact is not None, "CHECK_EXPIRED_RECHECK_REQUIRED")
    archive = api.request("GET", f"repos/{repository}/actions/artifacts/{artifact['id']}/zip", binary=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        candidate = json.loads(bundle.read("candidate.json"))
    require(issue["state"] == "open" and candidate["issue_number"] == issue["number"]
            and candidate["issue_body"] == issue["body"], "ISSUE_CHANGED_RECHECK_REQUIRED")
    return candidate


def open_submission_pulls(api, repository, number):
    pulls = api.request("GET", f"repos/{repository}/pulls?state=open&per_page=100")
    return [pull for pull in pulls if pull["head"]["repo"]
            and pull["head"]["repo"]["full_name"] == repository
            and pull["head"]["ref"].startswith(f"registry/issue-{number}-run-")]


def create_pull_request(api, repository, candidate, run_id):
    number = candidate["issue_number"]
    branch = f"registry/issue-{number}-run-{run_id}"
    owner = repository.split("/")[0]
    pulls = api.request("GET", f"repos/{repository}/pulls?state=all&head={quote(owner + ':' + branch, safe='')}")
    if pulls:
        require(pulls[0]["state"] == "open", "SUBMISSION_PR_ALREADY_CLOSED")
        return pulls[0], branch
    pending = open_submission_pulls(api, repository, number)
    if pending:
        raise RegistryError(f"请先处理或关闭已有收录 PR：{pending[0]['html_url']}")
    default = api.request("GET", f"repos/{repository}")["default_branch"]
    base = api.request("GET", f"repos/{repository}/git/ref/heads/{default}")["object"]["sha"]
    records = read_registry(api, repository, base)
    updated = apply_candidate(records, candidate)
    head = api.request("GET", f"repos/{repository}/git/ref/heads/{branch}", missing_ok=True)
    if head is None:
        tree = api.request("GET", f"repos/{repository}/git/commits/{base}")["tree"]["sha"]
        new_tree = api.request("POST", f"repos/{repository}/git/trees", {
            "base_tree": tree, "tree": [{"path": "plugins.json", "mode": "100644", "type": "blob",
                                        "content": json.dumps(updated, ensure_ascii=False, indent=2) + "\n"}]})
        commit = api.request("POST", f"repos/{repository}/git/commits", {
            "message": f"feat: 处理插件投稿 #{number}", "tree": new_tree["sha"], "parents": [base]})
        api.request("POST", f"repos/{repository}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    plugin = candidate["plugin"]
    version, commit = next(iter(plugin["versions"].items()))
    action = {"submit": "收录", "yank": "撤回", "restore": "恢复"}[candidate["operation"]]
    pull = api.request("POST", f"repos/{repository}/pulls", {
        "title": f"{action}：{plugin['id']} {version}", "head": branch, "base": default,
        "body": f"{action} `{plugin['id']}` 的 `{version}` 版本。\n\n"
                f"源码：{plugin['repository']}/tree/{commit}\n\n"
                f"检查记录：https://github.com/{repository}/actions/runs/{run_id}\n\n"
                f"由维护者批准此检查记录后生成；尚未合并或发布。\n\nCloses #{number}\n"})
    return pull, branch
