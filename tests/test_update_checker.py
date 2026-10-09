"""Fork release selection and failure handling with deterministic responses."""

import unittest
from unittest.mock import Mock, patch

import requests

from app.logic.update_checker import check_fork_update
from app.release_endpoints import FORK_REPO_URL, UPDATE_URL


class ForkUpdateTests(unittest.TestCase):
    def response(self, payload=None, status=200):
        response = Mock(status_code=status)
        response.json.return_value = payload
        return response

    def release(self, tag="v1.5.1", assets=None):
        return {"tag_name": tag, "body": "Fork fixes", "html_url": FORK_REPO_URL + "/releases/tag/" + tag,
                "assets": assets or []}

    def test_checks_only_fork_api(self):
        with patch("app.logic.update_checker.requests.get", return_value=self.response(status=404)) as get:
            self.assertEqual(check_fork_update("1.5.0")["status"], "unpublished")
        self.assertEqual(get.call_args.args[0], "https://api.github.com/repos/thok404/CS2Toolkit/releases/latest")
        self.assertEqual(UPDATE_URL, get.call_args.args[0])

    def test_equivalent_and_older_versions_do_not_prompt_downgrade(self):
        for tag in ("v1.5.0", "1.5", "v1.4.9"):
            with self.subTest(tag=tag), patch("app.logic.update_checker.requests.get", return_value=self.response(self.release(tag))):
                self.assertEqual(check_fork_update("1.5.0")["status"], "latest")

    def test_compares_version_numbers_numerically(self):
        with patch("app.logic.update_checker.requests.get", return_value=self.response(self.release("v1.10.0"))):
            result = check_fork_update("1.9.0")
        self.assertEqual(result["status"], "update")
        self.assertEqual(result["version"], "1.10.0")

    def test_prefers_fork_portable_zip_asset(self):
        base = FORK_REPO_URL + "/releases/download/v1.5.1/"
        assets = [
            {"name": "debug.zip", "browser_download_url": base + "debug.zip"},
            {"name": "CS2Toolkit_v1.5.1_portable.zip", "browser_download_url": base + "CS2Toolkit_v1.5.1_portable.zip"},
        ]
        with patch("app.logic.update_checker.requests.get", return_value=self.response(self.release(assets=assets))):
            result = check_fork_update("1.5.0")
        self.assertEqual(result["download_url"], assets[1]["browser_download_url"])
        self.assertEqual(result["update_log"], "Fork fixes")

    def test_no_assets_uses_fork_release_page(self):
        payload = self.release()
        with patch("app.logic.update_checker.requests.get", return_value=self.response(payload)):
            self.assertEqual(check_fork_update("1.5.0")["download_url"], payload["html_url"])

    def test_upstream_download_urls_are_not_selected(self):
        payload = self.release(assets=[{"name": "portable.zip", "browser_download_url": "https://github.com/clover-233/CS2Toolkit/releases/download/v1.5.1/app.zip"}])
        payload["html_url"] = "https://github.com/clover-233/CS2Toolkit/releases/tag/v1.5.1"
        with patch("app.logic.update_checker.requests.get", return_value=self.response(payload)):
            self.assertEqual(check_fork_update("1.5.0")["download_url"], FORK_REPO_URL + "/releases/latest")

    def test_unpublished_or_prerelease_is_not_offered(self):
        for flag in ("draft", "prerelease"):
            payload = self.release()
            payload[flag] = True
            with self.subTest(flag=flag), patch("app.logic.update_checker.requests.get", return_value=self.response(payload)):
                self.assertEqual(check_fork_update("1.5.0")["status"], "unpublished")

    def test_invalid_release_data_returns_error(self):
        for payload in ([], {}, self.release("not-a-version")):
            with self.subTest(payload=payload), patch("app.logic.update_checker.requests.get", return_value=self.response(payload)):
                self.assertEqual(check_fork_update("1.5.0")["status"], "error")

    def test_network_error_returns_error(self):
        with patch("app.logic.update_checker.requests.get", side_effect=requests.Timeout("timed out")):
            self.assertEqual(check_fork_update("1.5.0")["status"], "error")

    def test_http_error_is_not_reported_as_latest(self):
        response = self.response(status=503)
        response.raise_for_status.side_effect = requests.HTTPError("rate limited")
        with patch("app.logic.update_checker.requests.get", return_value=response):
            self.assertEqual(check_fork_update("1.5.0")["status"], "error")

    def test_api_rate_limit_uses_fork_latest_page(self):
        page = self.response()
        page.url = FORK_REPO_URL + "/releases/tag/v1.5.1"
        with patch("app.logic.update_checker.requests.get", side_effect=[self.response(status=403), page]) as get:
            result = check_fork_update("1.5.0")
        self.assertEqual(get.call_args_list[1].args[0], FORK_REPO_URL + "/releases/latest")
        self.assertEqual(result["status"], "update")
        self.assertEqual(result["download_url"], page.url)

    def test_rate_limit_fallback_handles_unpublished_fork(self):
        page = self.response()
        page.url = FORK_REPO_URL + "/releases"
        with patch("app.logic.update_checker.requests.get", side_effect=[self.response(status=429), page]):
            self.assertEqual(check_fork_update("1.5.0")["status"], "unpublished")


if __name__ == "__main__":
    unittest.main()
