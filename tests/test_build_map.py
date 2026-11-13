import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_map import world_coordinate_system, main


class WorldMapCoordinateSystemTests(unittest.TestCase):
    def test_world_coordinate_system_is_fixed_and_not_raster_derived(self):
        self.assertEqual(world_coordinate_system(), {
            "type": "minecraft-world-block-centers",
            "minX": -3008,
            "maxX": 3007,
            "minZ": -3008,
            "maxZ": 3007,
        })
        # The coordinate-system helper takes no image dimensions by design.

    def test_full_builder_keeps_world_geometry_for_different_square_resolution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / "source.png"
            public_dir = root / "public"
            Image.new("RGB", (2048, 2048), (24, 48, 72)).save(source_image, optimize=True)

            with patch.dict(os.environ, {"MAP_VERSION": "integration-test"}):
                with patch.object(sys, "argv", ["build_map.py", str(source_image), str(public_dir)]):
                    self.assertEqual(main(), 0)

            manifest_path = public_dir / "world-map" / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source = manifest["source"]
            self.assertEqual(manifest["mapVersion"], "integration-test")
            self.assertEqual((source["width"], source["height"]), (2048, 2048))
            self.assertEqual(source["coordinateSystem"], world_coordinate_system())
            self.assertNotIn("width", source["coordinateSystem"])
            self.assertNotIn("height", source["coordinateSystem"])
            self.assertEqual(source["maxLevel"], 11)
            version_dir = public_dir / "world-map" / "versions" / "integration-test"
            self.assertTrue((version_dir / "preview.webp").is_file())
            tiles_dir = version_dir / "tiles" / "11"
            self.assertTrue((tiles_dir / "0_0.webp").is_file())
            self.assertTrue((tiles_dir / "3_3.webp").is_file())
            self.assertGreater(manifest["generated"]["tileCount"], 0)

    def test_builder_rejects_non_square_raster_without_redefining_world_coordinates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / "source.png"
            public_dir = root / "public"
            Image.new("RGB", (2048, 1024), (24, 48, 72)).save(source_image, optimize=True)

            with patch.dict(os.environ, {"MAP_VERSION": "non-square-test"}):
                with patch.object(sys, "argv", ["build_map.py", str(source_image), str(public_dir)]):
                    with self.assertRaises(SystemExit) as error:
                        main()
            self.assertIn("must be square", str(error.exception))


    def test_generated_pyramid_has_expected_tile_count_and_valid_webp_tiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / "source.png"
            public_dir = root / "public"
            Image.new("RGB", (2048, 2048), (90, 120, 150)).save(source_image)

            with patch.dict(os.environ, {"MAP_VERSION": "pyramid-test"}):
                with patch.object(sys, "argv", ["build_map.py", str(source_image), str(public_dir)]):
                    self.assertEqual(main(), 0)

            manifest = json.loads(
                (public_dir / "world-map" / "manifest.json").read_text(encoding="utf-8")
            )
            version_dir = public_dir / "world-map" / "versions" / "pyramid-test"
            tile_files = sorted((version_dir / "tiles").glob("*/*.webp"))

            # For a 2048px image and 512px tiles: ten 1-tile levels,
            # one 2x2 level, and one 4x4 level.
            self.assertEqual(manifest["generated"]["tileCount"], 30)
            self.assertEqual(len(tile_files), 30)
            for tile_path in tile_files:
                with Image.open(tile_path) as tile:
                    self.assertEqual(tile.format, "WEBP")
                    self.assertLessEqual(tile.width, 512)
                    self.assertLessEqual(tile.height, 512)
                    self.assertGreater(tile.width, 0)
                    self.assertGreater(tile.height, 0)

            with Image.open(version_dir / "preview.webp") as preview:
                self.assertEqual(preview.format, "WEBP")
                self.assertLessEqual(max(preview.size), 1200)

    def test_invalid_version_is_rejected_before_output_directory_is_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_image = root / "source.png"
            public_dir = root / "public"
            Image.new("RGB", (16, 16), (1, 2, 3)).save(source_image)

            with patch.dict(os.environ, {"MAP_VERSION": "../unsafe"}):
                with patch.object(sys, "argv", ["build_map.py", str(source_image), str(public_dir)]):
                    with self.assertRaisesRegex(SystemExit, "MAP_VERSION"):
                        main()

            self.assertFalse((public_dir / "world-map").exists())



if __name__ == "__main__":
    unittest.main()
