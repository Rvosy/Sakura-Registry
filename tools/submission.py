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
    merge_submission_pull, open_submission_pulls, read_registry, require_maintainer,
    submission_revision,
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
    if mode == "finish":
        run_url = f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        if release := os.environ["CATALOG_RELEASE"]:
            api.request("PATCH", endpoint, {"state": "closed", "state_reason": "completed"})
            body = f"已发布到插件市场。[查看目录发布记录]({release})。"
        else:
            body = f"{os.environ['FAILED_STAGE']}失败。[查看运行记录]({run_url})。"
        api.request("POST", endpoint + "/comments", {"body": body})
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
                    f"维护者确认后评论 `/approve {run_id}`，校验通过后自动合并并发布。")
            write_json(output / "result.json", {"body": body})
        elif mode == "moderate":
            require_maintainer(api, repository, event["sender"]["login"])
            command = event["comment"]["body"].strip()
            approval = re.fullmatch(r"/approve ([0-9]+)", command)
            if approval:
                run_id = approval[1]
                require_unchanged_issue(issue, event["issue"])
                candidate = approved_candidate(api, repository, run_id, issue)
                pull = create_pull_request(api, repository, candidate, run_id)
                head, base = submission_revision(api, repository, pull, candidate)
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as outputs:
                    outputs.write(f"pull_request={pull['number']}\nhead_sha={head}\nbase_sha={base}\n")
                print(pull["html_url"])
            elif command == "/reject" or command.startswith("/reject "):
                if issue["state"] == "closed":
                    return 0
                reason = command.removeprefix("/reject").strip() or "本次投稿未收录。"
                for pull in open_submission_pulls(api, repository, number):
                    api.request("PATCH", f"repos/{repository}/pulls/{pull['number']}", {"state": "closed"})
                api.request("POST", endpoint + "/comments", {"body": reason})
                api.request("PATCH", endpoint, {"state": "closed", "state_reason": "not_planned"})
            else:
                raise RegistryError("COMMAND_INVALID: /approve 检查编号 或 /reject 原因")
        elif mode == "merge":
            require_unchanged_issue(issue, event["issue"])
            merge_submission_pull(api, repository, os.environ["PULL_REQUEST"], os.environ["HEAD_SHA"],
                                  event["repository"]["default_branch"])
    except (RegistryError, GitHubError, OSError, ValueError) as error:
        if mode == "check":
            body = f"处理失败：\n\n```text\n{error}\n```\n\n修正后编辑 Issue 或评论 `/recheck` 重新检查。"
            write_json(output / "result.json", {"body": body})
        print(str(error), file=sys.stderr)
        return 1
    return 0


def require_unchanged_issue(issue, approved_issue):
    if issue["state"] != "open" or issue["body"] != approved_issue["body"]:
        raise RegistryError("ISSUE_CHANGED_RECHECK_REQUIRED")


if __name__ == "__main__":
    raise SystemExit(main())
