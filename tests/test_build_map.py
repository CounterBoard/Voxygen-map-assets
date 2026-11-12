import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_map import coordinate_system_for_dimensions, main


class WorldMapCoordinateSystemTests(unittest.TestCase):
    def test_coordinate_origin_and_limits_match_pixel_centers(self):
        geometry = coordinate_system_for_dimensions(6016, 6016)
        self.assertEqual(geometry, {
            "type": "minecraft-block-pixel-centers",
            "originX": 3008,
            "originY": 3008,
            "minX": -3008,
            "maxX": 3007,
            "minZ": -3008,
            "maxZ": 3007,
            "width": 6016,
            "height": 6016,
        })

    def test_non_square_or_different_resolution_is_rejected(self):
        for dimensions in ((6015, 6015), (6016, 6015), (6016, 6017)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(ValueError):
                    coordinate_system_for_dimensions(*dimensions)

    def test_full_builder_publishes_manifest_preview_and_edge_tiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / "source.png"
            public_dir = root / "public"
            Image.new("RGB", (6016, 6016), (24, 48, 72)).save(source_image, optimize=True)

            with patch.dict(os.environ, {"MAP_VERSION": "integration-test"}):
                with patch.object(sys, "argv", ["build_map.py", str(source_image), str(public_dir)]):
                    self.assertEqual(main(), 0)

            manifest_path = public_dir / "world-map" / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source = manifest["source"]
            self.assertEqual(manifest["mapVersion"], "integration-test")
            self.assertEqual((source["width"], source["height"]), (6016, 6016))
            self.assertEqual(source["coordinateSystem"], coordinate_system_for_dimensions(6016, 6016))
            self.assertEqual(source["maxLevel"], 13)
            self.assertTrue((public_dir / "world-map" / "versions" / "integration-test" / "preview.webp").is_file())
            tiles_dir = public_dir / "world-map" / "versions" / "integration-test" / "tiles" / "13"
            self.assertTrue((tiles_dir / "0_0.webp").is_file())
            self.assertTrue((tiles_dir / "11_11.webp").is_file())
            self.assertGreater(manifest["generated"]["tileCount"], 0)


if __name__ == "__main__":
    unittest.main()
