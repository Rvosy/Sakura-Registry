import base64
import copy
import io
import json
import unittest
import zipfile

from registry.core import RegistryError
from registry.submissions import (
    apply_candidate, approved_candidate, create_pull_request, prepare_candidate, require_maintainer,
)
from test_registry import COMMIT, MANIFEST, archive, records


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
    manifest = json.dumps(MANIFEST).encode()
    return FakeGitHub({
        ("GET", "repos/example/notes/commits/v1.0.0"): {"sha": COMMIT},
        ("GET", "repos/example/notes/releases/latest"): {"tag_name": "v1.0.0"},
        ("GET", f"repos/example/notes/contents/plugin.yaml?ref={COMMIT}"): {
            "type": "file", "size": len(manifest), "content": base64.b64encode(manifest).decode()},
    })


def candidate():
    return {"issue_number": 7, "issue_body": BODY, "operation": "submit", "plugin": records()["plugins"][0]}


class SubmissionTests(unittest.TestCase):
    def test_submission_resolves_tag_and_packages_that_exact_commit(self):
        calls = []
        def fetch(repo, commit):
            calls.append((repo, commit))
            return archive()
        result, package = prepare_candidate(issue(), empty(), source_api(), fetch)
        self.assertEqual(result["plugin"]["versions"][0]["commit"], COMMIT)
        self.assertEqual(result["plugin"]["versions"][0]["notes"], "")
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
                              lambda *_: self.fail("must fail before source download"))

    def test_issue_text_is_not_an_arbitrary_download_address(self):
        for repo in ("http://127.0.0.1/internal", "https://github.com/example/notes; echo secret"):
            with self.subTest(repo=repo), self.assertRaisesRegex(RegistryError, "REPOSITORY_INVALID"):
                prepare_candidate(issue(BODY.replace("https://github.com/example/notes", repo)), empty(),
                                  FakeGitHub({}), lambda *_: self.fail("invalid repository fetched"))

    def test_new_version_keeps_existing_records_and_rejects_duplicates(self):
        proposal = candidate()
        proposal["plugin"]["versions"][0].update(version="1.1.0", commit="b" * 40)
        proposal["plugin"]["versions"][0]["manifest"]["version"] = "1.1.0"
        result = apply_candidate(records(), proposal)
        self.assertEqual(result["plugins"][0]["versions"][0], records()["plugins"][0]["versions"][0])
        self.assertEqual(len(result["plugins"][0]["versions"]), 2)
        with self.assertRaisesRegex(RegistryError, "VERSION_ALREADY_LISTED"):
            apply_candidate(records(), candidate())

    def test_yank_needs_no_upstream_and_restore_checks_original_source(self):
        body = "### 插件 ID\n\nnotes\n\n### 操作\n\n撤回版本\n\n### 版本号\n\n1.0.0\n\n### 原因或说明\n\nBroken\n"
        proposal, package = prepare_candidate(issue(body), records(), FakeGitHub({}),
                                              lambda *_: self.fail("yank must not download"))
        self.assertIsNone(package)
        yanked = apply_candidate(records(), proposal)
        self.assertTrue(yanked["plugins"][0]["versions"][0]["yanked"])
        calls = []
        def fetch(repo, commit):
            calls.append(commit)
            return archive()
        restored, package = prepare_candidate(issue(body.replace("撤回版本", "恢复版本")), yanked, FakeGitHub({}), fetch)
        self.assertEqual(calls, [COMMIT])
        self.assertFalse(apply_candidate(yanked, restored)["plugins"][0]["versions"][0]["yanked"])

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
        pull, actual_branch = create_pull_request(api, REPO, candidate(), "123")
        self.assertEqual(actual_branch, branch)
        tree = next(data for method, path, data in api.calls if method == "POST" and path.endswith("/git/trees"))
        self.assertEqual([entry["path"] for entry in tree["tree"]], ["plugins.json"])
        self.assertEqual(json.loads(tree["tree"][0]["content"]), records())
        ref = next(data for method, path, data in api.calls if method == "POST" and path.endswith("/git/refs"))
        self.assertEqual(ref, {"ref": f"refs/heads/{branch}", "sha": "new-commit"})
        routes[("GET", f"repos/{REPO}/pulls?state=all&head=example%3Aregistry%2Fissue-7-run-123")] = [pull]
        again = FakeGitHub(routes)
        self.assertEqual(create_pull_request(again, REPO, candidate(), "123")[0], pull)
        self.assertEqual(len(again.calls), 1)


if __name__ == "__main__":
    unittest.main()
