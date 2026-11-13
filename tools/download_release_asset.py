#!/usr/bin/env python3
"""Download a Voxygen source-map GitHub Release asset with strict bounds."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests

MAX_SOURCE_BYTES = 90_000_000
ALLOWED_DOWNLOAD_HOSTS = {
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-production-release-asset-2e65be.s3.amazonaws.com",
}
USER_AGENT = "Voxygen-Map-Pipeline/1.0"


def validate_source_url(url: str) -> None:
    parsed = urlsplit(str(url))
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The source image URL must be a plain HTTPS GitHub Release asset URL")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if (
        len(parts) != 6
        or parts[:4] != ["CounterBoard", "Voxygen-map-storage", "releases", "download"]
        or not parts[4]
        or not parts[5]
        or parts[4] in {".", ".."}
        or parts[5] in {".", ".."}
        or "/" in parts[4]
        or "/" in parts[5]
        or "\\" in parts[4]
        or "\\" in parts[5]
    ):
        raise ValueError("The source image must be an asset from CounterBoard/Voxygen-map-storage")


def validate_download_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("GitHub returned a download redirect to an untrusted host")


def download_release_asset(url: str, output_path: str | Path, token: str = "", session=None) -> int:
    validate_source_url(url)
    client = session or requests
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/octet-stream",
    }
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    response = client.get(
        url,
        headers=headers,
        stream=True,
        allow_redirects=False,
        timeout=(30, 300),
    )
    try:
        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                raise ValueError("GitHub returned a redirect without a Location header")
            download_url = urljoin(url, location)
            validate_download_url(download_url)
            response.close()
            # Never forward the GitHub API token to the signed asset host.
            response = client.get(
                download_url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
                stream=True,
                allow_redirects=False,
                timeout=(30, 300),
            )

        if response.is_redirect:
            raise ValueError("Unexpected second redirect while downloading the source image")
        response.raise_for_status()

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_length = int(content_length)
            except (TypeError, ValueError):
                raise ValueError("GitHub returned an invalid Content-Length")
            if declared_length <= 0 or declared_length > MAX_SOURCE_BYTES:
                raise ValueError(f"Source image must be between 1 and {MAX_SOURCE_BYTES} bytes")

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > MAX_SOURCE_BYTES:
                        raise ValueError(f"Source image exceeds the {MAX_SOURCE_BYTES}-byte limit")
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        if written <= 0:
            destination.unlink(missing_ok=True)
            raise ValueError("The downloaded source image is empty")
        return written
    finally:
        response.close()


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: download_release_asset.py RELEASE_ASSET_URL OUTPUT_PATH")
    try:
        size = download_release_asset(
            sys.argv[1],
            sys.argv[2],
            token=os.environ.get("MAP_SOURCE_GITHUB_TOKEN", ""),
        )
    except Exception as error:
        raise SystemExit(f"Source map download failed: {error}") from error
    print(f"Downloaded source map: {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
