from pathlib import Path
import unittest


class StaticAssetHeadersTests(unittest.TestCase):
    def test_manifest_is_cross_origin_readable_and_not_cached(self):
        headers = (Path(__file__).resolve().parents[1] / "public" / "_headers").read_text(encoding="utf-8")
        manifest = headers.split("/world-map/manifest.json", 1)[1].split("\n\n", 1)[0]

        self.assertIn("Access-Control-Allow-Origin: *", manifest)
        self.assertIn("Access-Control-Allow-Methods: GET, HEAD, OPTIONS", manifest)
        self.assertIn("Cache-Control: no-store", manifest)

    def test_versioned_assets_are_cross_origin_and_immutable(self):
        headers = (Path(__file__).resolve().parents[1] / "public" / "_headers").read_text(encoding="utf-8")
        versioned = headers.split("/world-map/versions/*", 1)[1].split("\n\n", 1)[0]

        self.assertIn("Access-Control-Allow-Origin: *", versioned)
        self.assertIn("Cache-Control: public, max-age=31536000, immutable", versioned)
        self.assertIn("X-Content-Type-Options: nosniff", versioned)


if __name__ == "__main__":
    unittest.main()
