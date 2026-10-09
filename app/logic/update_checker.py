"""Check published fork releases without suggesting version downgrades."""

import re
from urllib.parse import unquote

import requests

from app.release_endpoints import FORK_REPO_URL, UPDATE_URL


def _version_number(value):
    match = re.fullmatch(r"[vV]?(\d+)\.(\d+)(?:\.(\d+))?", str(value).strip())
    if not match:
        raise ValueError("发布信息中的版本号无效，请到 fork 仓库查看版本。")
    return tuple(int(part or 0) for part in match.groups())


def _check_release_page(current_version):
    # GitHub 未登录 API 有请求次数限制，网页的 latest 跳转仍可定位正式发布。
    response = requests.get(FORK_REPO_URL + "/releases/latest", timeout=5)
    response.raise_for_status()
    url = response.url
    if url.rstrip("/") == FORK_REPO_URL + "/releases":
        return {"status": "unpublished"}
    prefix = FORK_REPO_URL + "/releases/tag/"
    if not url.startswith(prefix):
        raise ValueError("无法定位 fork 的发布版本，请到 fork 仓库查看。")
    version = unquote(url[len(prefix):])
    if _version_number(version) <= _version_number(current_version):
        return {"status": "latest"}
    return {
        "status": "update",
        "version": version.lstrip("vV"),
        "update_log": "请查看 fork 仓库的发布说明。",
        "download_url": url,
    }


def check_fork_update(current_version):
    """Return update/latest/unpublished/error for the fork's latest release."""

    try:
        response = requests.get(
            UPDATE_URL,
            timeout=5,
            proxies={"http": None, "https": None},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CS2Toolkit-fork"},
        )
        if response.status_code == 404:
            return {"status": "unpublished"}
        if response.status_code in (403, 429):
            return _check_release_page(current_version)
        response.raise_for_status()
        release = response.json()
        if not isinstance(release, dict):
            raise ValueError("发布信息格式无效，请到 fork 仓库查看版本。")
        if release.get("draft") or release.get("prerelease"):
            return {"status": "unpublished"}

        version = release.get("tag_name")
        if _version_number(version) <= _version_number(current_version):
            return {"status": "latest"}

        release_url = release.get("html_url", "")
        if not isinstance(release_url, str) or not release_url.startswith(FORK_REPO_URL + "/releases/"):
            release_url = FORK_REPO_URL + "/releases/latest"
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            assets = []
        candidates = [
            asset for asset in assets
            if isinstance(asset, dict)
            and str(asset.get("name", "")).lower().endswith(".zip")
            and isinstance(asset.get("browser_download_url"), str)
            and asset["browser_download_url"].startswith(FORK_REPO_URL + "/releases/download/")
        ]
        candidates.sort(key=lambda asset: "portable" not in asset["name"].lower())
        return {
            "status": "update",
            "version": str(version).lstrip("vV"),
            "update_log": release.get("body") or "请查看 fork 仓库的发布说明。",
            "download_url": candidates[0]["browser_download_url"] if candidates else release_url,
        }
    except (requests.RequestException, ValueError) as error:
        return {"status": "error", "message": f"检查 fork 更新失败：{error}"}
