import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import download_release_asset as downloader


class FakeResponse:
    def __init__(self, status=200, headers=None, chunks=()):
        self.status_code = status
        self.headers = headers or {}
        self.chunks = list(chunks)
        self.closed = False

    @property
    def is_redirect(self):
        return self.status_code in {301, 302, 303, 307, 308}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self.chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        return self.responses.pop(0)


class ReleaseAssetDownloadTests(unittest.TestCase):
    SOURCE_URL = (
        "https://github.com/CounterBoard/Voxygen-map-storage/releases/"
        "download/world-map/test-map.png"
    )

    def test_source_url_must_be_exact_release_asset_route(self):
        invalid_urls = [
            "http://github.com/CounterBoard/Voxygen-map-storage/releases/download/tag/map.png",
            "https://evil.example/CounterBoard/Voxygen-map-storage/releases/download/tag/map.png",
            "https://github.com/Other/repo/releases/download/tag/map.png",
            self.SOURCE_URL + "?redirect=https://evil.example",
            "https://user@github.com/CounterBoard/Voxygen-map-storage/releases/download/tag/map.png",
            "https://github.com/CounterBoard/Voxygen-map-storage/releases/download/tag/sub/map.png",
            "https://github.com/CounterBoard/Voxygen-map-storage/releases/download/tag/map.gif",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    downloader.validate_source_url(url)

    def test_download_uses_allowlisted_https_redirect_and_does_not_forward_token(self):
        redirect = FakeResponse(
            302,
            {"Location": "https://release-assets.githubusercontent.com/assets/map.png?sig=abc"},
        )
        asset = FakeResponse(200, {"Content-Length": "8"}, [b"map", b"-data"])
        session = FakeSession(redirect, asset)

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source-map"
            size = downloader.download_release_asset(
                self.SOURCE_URL, destination, token="source-token", session=session
            )
            self.assertEqual(size, 8)
            self.assertEqual(destination.read_bytes(), b"map-data")

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[0][1]["headers"]["Authorization"], "Bearer source-token"
        )
        self.assertNotIn("Authorization", session.calls[1][1]["headers"])
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertFalse(session.calls[1][1]["allow_redirects"])
        self.assertTrue(redirect.closed)
        self.assertTrue(asset.closed)

    def test_untrusted_or_insecure_redirect_is_rejected(self):
        for location in [
            "http://release-assets.githubusercontent.com/map.png",
            "https://evil.example/map.png",
            "https://user@release-assets.githubusercontent.com/map.png",
        ]:
            with self.subTest(location=location):
                redirect = FakeResponse(302, {"Location": location})
                session = FakeSession(redirect)
                with tempfile.TemporaryDirectory() as temp_dir:
                    with self.assertRaises(ValueError):
                        downloader.download_release_asset(
                            self.SOURCE_URL, Path(temp_dir) / "source", session=session
                        )
                self.assertEqual(len(session.calls), 1)
                self.assertTrue(redirect.closed)

    def test_second_redirect_is_rejected(self):
        redirect = FakeResponse(302, {"Location": "https://objects.githubusercontent.com/a"})
        second_redirect = FakeResponse(
            302, {"Location": "https://release-assets.githubusercontent.com/b"}
        )
        session = FakeSession(redirect, second_redirect)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "second redirect"):
                downloader.download_release_asset(
                    self.SOURCE_URL, Path(temp_dir) / "source", session=session
                )
        self.assertTrue(second_redirect.closed)

    def test_declared_and_streamed_size_limits_are_enforced(self):
        too_large = FakeResponse(
            200, {"Content-Length": str(downloader.MAX_SOURCE_BYTES + 1)}, []
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "between 1"):
                downloader.download_release_asset(
                    self.SOURCE_URL,
                    Path(temp_dir) / "source",
                    session=FakeSession(too_large),
                )

        streamed = FakeResponse(200, {}, [b"1234", b"5678"])
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source"
            with patch.object(downloader, "MAX_SOURCE_BYTES", 7):
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    downloader.download_release_asset(
                        self.SOURCE_URL, destination, session=FakeSession(streamed)
                    )
            self.assertFalse(destination.exists())
        self.assertTrue(streamed.closed)

    def test_empty_download_is_rejected(self):
        empty = FakeResponse(200, {}, [b"", b""])
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source"
            with self.assertRaisesRegex(ValueError, "empty"):
                downloader.download_release_asset(
                    self.SOURCE_URL, destination, session=FakeSession(empty)
                )
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
