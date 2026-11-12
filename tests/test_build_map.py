import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_map import coordinate_system_for_dimensions


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


if __name__ == "__main__":
    unittest.main()
