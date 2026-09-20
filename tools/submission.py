"""GitHub Actions entrypoints for Issue checks, reports and maintainer commands."""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry.core import RegistryError, write_json
from registry.submissions import (
    GitHub, GitHubError, approved_candidate, create_pull_request, prepare_candidate,
    open_submission_pulls, read_registry, require_maintainer,
)


def main():
    mode = sys.argv[1]
    api = GitHub()
    repository = os.environ["GITHUB_REPOSITORY"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    number = event["issue"]["number"]
    endpoint = f"repos/{repository}/issues/{number}"
    output = Path(".local/submission")
    if mode == "report":
        report = json.loads((output / "result.json").read_text(encoding="utf-8"))
        api.request("POST", endpoint + "/comments", {"body": report["body"]})
        return 0
    issue = api.request("GET", endpoint)
    if "pull_request" in issue:
        return 0
    try:
        if mode == "check":
            # Rechecks are available to the author and repository maintainers.
            if os.environ["GITHUB_EVENT_NAME"] == "issue_comment" and event["sender"]["login"] != issue["user"]["login"]:
                require_maintainer(api, repository, event["sender"]["login"])
            default = api.request("GET", f"repos/{repository}")["default_branch"]
            candidate, package = prepare_candidate(issue, read_registry(api, repository, default), api)
            write_json(output / "candidate.json", candidate)
            if package is not None:
                (output / "plugin.zip").write_bytes(package)
            plugin = candidate["plugin"]
            version, commit = next(iter(plugin["versions"].items()))
            run_id = os.environ["GITHUB_RUN_ID"]
            body = (f"检查通过：`{plugin['id']}` / `{version}`。\n\n"
                    f"固定源码：{plugin['repository']}/tree/{commit}\n\n"
                    f"[检查与预览包](https://github.com/{repository}/actions/runs/{run_id})\n\n"
                    f"维护者确认后评论 `/approve {run_id}`，生成收录 PR。")
            write_json(output / "result.json", {"body": body})
        elif mode == "moderate":
            require_maintainer(api, repository, event["sender"]["login"])
            command = event["comment"]["body"].strip()
            approval = re.fullmatch(r"/approve ([0-9]+)", command)
            if approval:
                run_id = approval[1]
                candidate = approved_candidate(api, repository, run_id, issue)
                pull, branch = create_pull_request(api, repository, candidate, run_id)
                # GitHub gates GITHUB_TOKEN-created PR workflows on approval.
                # workflow_dispatch runs immediately, so validate this branch explicitly.
                api.request("POST", f"repos/{repository}/actions/workflows/validate.yml/dispatches",
                            {"ref": branch, "inputs": {"base_sha": pull["base"]["sha"]}})
                api.request("POST", endpoint + "/comments", {"body": f"已生成收录 PR：{pull['html_url']}\n\n校验通过后由维护者合并。"})
                print(pull["html_url"])
            elif command == "/reject" or command.startswith("/reject "):
                reason = command.removeprefix("/reject").strip() or "本次投稿未收录。"
                for pull in open_submission_pulls(api, repository, number):
                    api.request("PATCH", f"repos/{repository}/pulls/{pull['number']}", {"state": "closed"})
                api.request("POST", endpoint + "/comments", {"body": reason})
                api.request("PATCH", endpoint, {"state": "closed", "state_reason": "not_planned"})
            else:
                raise RegistryError("COMMAND_INVALID: /approve 检查编号 或 /reject 原因")
    except (RegistryError, GitHubError, OSError, ValueError) as error:
        body = f"处理失败：\n\n```text\n{error}\n```\n\n修正后编辑 Issue 或评论 `/recheck` 重新检查。"
        if mode == "check":
            write_json(output / "result.json", {"body": body})
        else:
            api.request("POST", endpoint + "/comments", {"body": body})
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
