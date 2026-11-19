import base64
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from registry.core import RegistryError
from registry.submissions import (
    apply_candidate, approved_candidate, create_pull_request, merge_submission_pull,
    prepare_candidate, require_maintainer, submission_revision,
)
from test_registry import COMMIT, archive, records
from tools import submission


REPO = "example/registry"
BODY = "### 插件 ID\n\nnotes\n\n### GitHub 仓库\n\nhttps://github.com/example/notes\n\n### 要收录的版本\n\nv1.0.0\n\n### 补充说明\n\n_No response_\n"


def issue(body=BODY):
    return {"number": 7, "body": body, "state": "open", "user": {"login": "author"}}


def empty():
    return {"schema_version": 1, "plugins": []}


class FakeGitHub:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, path, data=None, **kwargs):
        self.calls.append((method, path, data))
        result = self.routes[(method, path)]
        return result(data) if callable(result) else copy.deepcopy(result)


def source_api():
    return FakeGitHub({
        ("GET", "repos/example/notes/commits/v1.0.0"): {"sha": COMMIT},
        ("GET", "repos/example/notes/releases/latest"): {"tag_name": "v1.0.0"},
    })


def candidate():
    return {"issue_number": 7, "issue_body": BODY, "operation": "submit", "plugin": records()["plugins"][0]}


def run_submission(mode, api, event, **env):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_EVENT_PATH": str(path), **env}), \
                patch("sys.argv", ["submission.py", mode]), patch.object(submission, "GitHub", return_value=api):
            return submission.main()


class SubmissionTests(unittest.TestCase):
    def test_submission_resolves_tag_and_packages_that_exact_commit(self):
        calls = []
        def fetch(repo, commit):
            calls.append((repo, commit))
            return archive()
        result, package = prepare_candidate(issue(), empty(), source_api(), fetch)
        self.assertEqual(result["plugin"], records()["plugins"][0])
        self.assertEqual(calls, [("https://github.com/example/notes", COMMIT)])
        with zipfile.ZipFile(io.BytesIO(package)) as built:
            self.assertIn("notes/plugin.py", built.namelist())

    def test_blank_version_uses_latest_release_or_default_branch(self):
        body = BODY.replace("v1.0.0", "_No response_")
        api = source_api()
        prepare_candidate(issue(body), empty(), api, lambda *_: archive())
        self.assertTrue(any(path.endswith("commits/v1.0.0") for _, path, _ in api.calls))
        api = source_api()
        api.routes[("GET", "repos/example/notes/releases/latest")] = None
        api.routes[("GET", "repos/example/notes/commits/HEAD")] = {"sha": COMMIT}
        prepare_candidate(issue(body), empty(), api, lambda *_: archive())
        self.assertTrue(any(path.endswith("commits/HEAD") for _, path, _ in api.calls))

    def test_release_url_is_resolved_as_tag(self):
        body = BODY.replace("\n\nv1.0.0", "\n\nhttps://github.com/example/notes/releases/tag/v1.0.0")
        prepare_candidate(issue(body), empty(), source_api(), lambda *_: archive())

    def test_submission_id_must_match_source(self):
        with self.assertRaisesRegex(RegistryError, "IDENTITY_MISMATCH"):
            prepare_candidate(issue(BODY.replace("\n\nnotes\n", "\n\nother\n")), empty(), source_api(),
                              lambda *_: archive())

    def test_issue_text_is_not_an_arbitrary_download_address(self):
        for repo in ("http://127.0.0.1/internal", "https://github.com/example/notes; echo secret"):
            with self.subTest(repo=repo), self.assertRaisesRegex(RegistryError, "REPOSITORY_INVALID"):
                prepare_candidate(issue(BODY.replace("https://github.com/example/notes", repo)), empty(),
                                  FakeGitHub({}), lambda *_: self.fail("invalid repository fetched"))

    def test_new_version_keeps_existing_records_and_rejects_duplicates(self):
        proposal = candidate()
        proposal["plugin"]["versions"] = {"1.1.0": "b" * 40}
        result = apply_candidate(records(), proposal)
        self.assertEqual(result["plugins"][0]["versions"]["1.0.0"], COMMIT)
        self.assertEqual(len(result["plugins"][0]["versions"]), 2)
        with self.assertRaisesRegex(RegistryError, "VERSION_ALREADY_LISTED"):
            apply_candidate(records(), candidate())

    def test_yank_needs_no_upstream_and_restore_checks_original_source(self):
        body = "### 插件 ID\n\nnotes\n\n### 操作\n\n撤回版本\n\n### 版本号\n\n1.0.0\n\n### 原因或说明\n\nBroken\n"
        proposal, package = prepare_candidate(issue(body), records(), FakeGitHub({}),
                                              lambda *_: self.fail("yank must not download"))
        self.assertIsNone(package)
        yanked = apply_candidate(records(), proposal)
        self.assertEqual(yanked["plugins"][0]["yanked"], {"1.0.0": "Broken"})
        calls = []
        def fetch(repo, commit):
            calls.append(commit)
            return archive()
        restored, package = prepare_candidate(issue(body.replace("撤回版本", "恢复版本")), yanked, FakeGitHub({}), fetch)
        self.assertEqual(calls, [COMMIT])
        self.assertEqual(apply_candidate(yanked, restored), records())

    def test_only_actual_repository_writers_can_approve(self):
        for permission in ("read", "triage", "none"):
            api = FakeGitHub({("GET", f"repos/{REPO}/collaborators/author/permission"): {"permission": permission}})
            with self.subTest(permission=permission), self.assertRaisesRegex(RegistryError, "MAINTAINER_REQUIRED"):
                require_maintainer(api, REPO, "author")
        api = FakeGitHub({("GET", f"repos/{REPO}/collaborators/owner/permission"): {"permission": "admin"}})
        require_maintainer(api, REPO, "owner")

    def approval_api(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w") as z:
            z.writestr("candidate.json", json.dumps(candidate()))
        return FakeGitHub({
            ("GET", f"repos/{REPO}"): {"default_branch": "main"},
            ("GET", f"repos/{REPO}/actions/runs/123"): {
                "path": ".github/workflows/submission.yml", "head_branch": "main", "event": "issues",
                "conclusion": "success", "head_repository": {"full_name": REPO}},
            ("GET", f"repos/{REPO}/actions/runs/123/artifacts"): {"artifacts": [{"id": 9, "name": "submission", "expired": False}]},
            ("GET", f"repos/{REPO}/actions/artifacts/9/zip"): bundle.getvalue(),
        })

    def test_approval_uses_checked_snapshot_and_rejects_edited_issue(self):
        self.assertEqual(approved_candidate(self.approval_api(), REPO, "123", issue()), candidate())
        with self.assertRaisesRegex(RegistryError, "ISSUE_CHANGED"):
            approved_candidate(self.approval_api(), REPO, "123", issue(BODY + "edited"))

    def test_failed_or_untrusted_run_cannot_supply_approval(self):
        for key, value in (("conclusion", "failure"), ("head_branch", "untrusted"),
                           ("event", "pull_request"), ("path", ".github/workflows/other.yml")):
            api = self.approval_api()
            api.routes[("GET", f"repos/{REPO}/actions/runs/123")][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RegistryError, "CHECK_RUN_INVALID"):
                approved_candidate(api, REPO, "123", issue())

    def test_expired_check_requires_recheck(self):
        api = self.approval_api()
        api.routes[("GET", f"repos/{REPO}/actions/runs/123/artifacts")]["artifacts"][0]["expired"] = True
        with self.assertRaisesRegex(RegistryError, "CHECK_EXPIRED"):
            approved_candidate(api, REPO, "123", issue())

    def test_pr_creation_writes_only_records_to_a_new_branch(self):
        branch = "registry/issue-7-run-123"
        routes = {
            ("GET", f"repos/{REPO}/pulls?state=all&head=example%3Aregistry%2Fissue-7-run-123"): [],
            ("GET", f"repos/{REPO}/pulls?state=open&per_page=100"): [],
            ("GET", f"repos/{REPO}"): {"default_branch": "main"},
            ("GET", f"repos/{REPO}/git/ref/heads/main"): {"object": {"sha": "base"}},
            ("GET", f"repos/{REPO}/contents/plugins.json?ref=base"): {"content": base64.b64encode(json.dumps(empty()).encode()).decode()},
            ("GET", f"repos/{REPO}/git/ref/heads/{branch}"): None,
            ("GET", f"repos/{REPO}/git/commits/base"): {"tree": {"sha": "base-tree"}},
            ("POST", f"repos/{REPO}/git/trees"): {"sha": "new-tree"},
            ("POST", f"repos/{REPO}/git/commits"): {"sha": "new-commit"},
            ("POST", f"repos/{REPO}/git/refs"): {},
            ("POST", f"repos/{REPO}/pulls"): {"number": 8, "state": "open"},
        }
        api = FakeGitHub(routes)
        pull = create_pull_request(api, REPO, candidate(), "123")
        tree = next(data for method, path, data in api.calls if method == "POST" and path.endswith("/git/trees"))
        self.assertEqual([entry["path"] for entry in tree["tree"]], ["plugins.json"])
        self.assertEqual(json.loads(tree["tree"][0]["content"]), records())
        ref = next(data for method, path, data in api.calls if method == "POST" and path.endswith("/git/refs"))
        self.assertEqual(ref, {"ref": f"refs/heads/{branch}", "sha": "new-commit"})
        routes[("GET", f"repos/{REPO}/pulls?state=all&head=example%3Aregistry%2Fissue-7-run-123")] = [pull]
        again = FakeGitHub(routes)
        self.assertEqual(create_pull_request(again, REPO, candidate(), "123"), pull)
        self.assertEqual(len(again.calls), 1)
        routes[("GET", f"repos/{REPO}/pulls?state=all&head=example%3Aregistry%2Fissue-7-run-123")] = []
        routes[("GET", f"repos/{REPO}/pulls?state=open&per_page=100")] = [
            {"html_url": "https://github.com/example/registry/pull/10",
             "head": {"repo": {"full_name": REPO}, "ref": "registry/issue-7-run-122"}}]
        conflict = FakeGitHub(routes)
        with self.assertRaisesRegex(RegistryError, "已有收录 PR"):
            create_pull_request(conflict, REPO, candidate(), "123")
        self.assertTrue(all(method == "GET" for method, _, _ in conflict.calls))

    def test_existing_pr_must_match_approved_records_before_validation(self):
        pull = {"base": {"sha": "main"}, "head": {"sha": "head"}}
        api = FakeGitHub({
            ("GET", f"repos/{REPO}/compare/main...head"): {
                "merge_base_commit": {"sha": "base"}, "files": [{"filename": "plugins.json"}]},
            ("GET", f"repos/{REPO}/contents/plugins.json?ref=base"): {
                "content": base64.b64encode(json.dumps(empty()).encode()).decode()},
            ("GET", f"repos/{REPO}/contents/plugins.json?ref=head"): {
                "content": base64.b64encode(json.dumps(records()).encode()).decode()},
        })
        self.assertEqual(submission_revision(api, REPO, pull, candidate()), ("head", "base"))
        api.routes[("GET", f"repos/{REPO}/contents/plugins.json?ref=head")] = {
            "content": base64.b64encode(json.dumps(empty()).encode()).decode()}
        with self.assertRaisesRegex(RegistryError, "SUBMISSION_PR_DIFFERS_FROM_APPROVAL"):
            submission_revision(api, REPO, pull, candidate())

    def test_merge_uses_validated_head_and_can_resume_after_merge(self):
        endpoint = f"repos/{REPO}/pulls/8"
        pull = {"base": {"ref": "main"}, "head": {"sha": "other"}, "merged": False}
        api = FakeGitHub({
            ("GET", endpoint): pull,
            ("PUT", endpoint + "/merge"): {"merged": True},
        })
        with self.assertRaisesRegex(RegistryError, "SUBMISSION_PR_CHANGED_AFTER_VALIDATION"):
            merge_submission_pull(api, REPO, 8, "head", "main")
        self.assertEqual([method for method, _, _ in api.calls], ["GET"])
        pull["head"]["sha"] = "head"
        merge_submission_pull(api, REPO, 8, "head", "main")
        self.assertEqual(api.calls[-1], ("PUT", endpoint + "/merge", {"sha": "head", "merge_method": "squash"}))
        pull["merged"] = True
        merge_submission_pull(api, REPO, 8, "head", "main")
        self.assertEqual(sum(method == "PUT" for method, _, _ in api.calls), 1)

    def test_reviewed_issue_merges_after_ci_only_if_still_current(self):
        endpoint = f"repos/{REPO}/pulls/8"
        event = {"issue": issue(), "repository": {"default_branch": "main"}}
        routes = {
            ("GET", f"repos/{REPO}/issues/7"): issue(),
            ("GET", endpoint): {"base": {"ref": "main"}, "head": {"sha": "head"}, "merged": False},
            ("PUT", endpoint + "/merge"): {"merged": True},
        }
        api = FakeGitHub(routes)
        self.assertEqual(run_submission("merge", api, event, PULL_REQUEST="8", HEAD_SHA="head"), 0)
        self.assertEqual(api.calls[-1][0], "PUT")

        routes[("GET", f"repos/{REPO}/issues/7")] = issue(BODY + "edited")
        api = FakeGitHub(routes)
        with patch("sys.stderr", new_callable=io.StringIO) as log:
            self.assertEqual(run_submission("merge", api, event, PULL_REQUEST="8", HEAD_SHA="head"), 1)
        self.assertIn("ISSUE_CHANGED_RECHECK_REQUIRED", log.getvalue())
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_issue_is_closed_only_after_publication(self):
        endpoint = f"repos/{REPO}/issues/7"
        release = f"https://github.com/{REPO}/releases/tag/catalog"
        for stage, published in (("校验收录 PR", ""), ("发布市场目录", ""), ("", release)):
            with self.subTest(stage=stage, published=published):
                api = FakeGitHub({("POST", endpoint + "/comments"): {}, ("PATCH", endpoint): {}})
                self.assertEqual(run_submission("finish", api, {"issue": issue()}, GITHUB_RUN_ID="123",
                                                FAILED_STAGE=stage, CATALOG_RELEASE=published), 0)
                self.assertEqual(any(method == "PATCH" for method, _, _ in api.calls), bool(published))
                self.assertIn(published or "/actions/runs/123", api.calls[-1][2]["body"])

    def test_reject_closes_only_this_issues_generated_pr(self):
        endpoint = f"repos/{REPO}/issues/7"
        api = FakeGitHub({
            ("GET", endpoint): issue(),
            ("GET", f"repos/{REPO}/collaborators/owner/permission"): {"permission": "admin"},
            ("GET", f"repos/{REPO}/pulls?state=open&per_page=100"): [
                {"number": 8, "head": {"repo": {"full_name": REPO}, "ref": "registry/issue-7-run-123"}},
                {"number": 9, "head": {"repo": {"full_name": REPO}, "ref": "registry/issue-70-run-124"}},
            ],
            ("PATCH", f"repos/{REPO}/pulls/8"): {},
            ("POST", endpoint + "/comments"): {},
            ("PATCH", endpoint): {},
        })
        event = {"issue": issue(), "sender": {"login": "owner"}, "comment": {"body": "/reject Needs fixes"}}
        self.assertEqual(run_submission("moderate", api, event), 0)
        changed = [(path, data) for method, path, data in api.calls if method == "PATCH"]
        self.assertEqual(changed, [(f"repos/{REPO}/pulls/8", {"state": "closed"}),
                                   (endpoint, {"state": "closed", "state_reason": "not_planned"})])


if __name__ == "__main__":
    unittest.main()
