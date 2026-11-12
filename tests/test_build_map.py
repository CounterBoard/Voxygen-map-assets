import unittest

from tools.build_map import coordinate_system_for_dimensions


class WorldMapCoordinateSystemTests(unittest.TestCase):
    def test_coordinate_origin_and_limits_match_pixel_centers(self):
        geometry = coordinate_system_for_dimensions(6001, 6001)
        self.assertEqual(geometry, {
            "type": "minecraft-block-pixel-centers",
            "originX": 3000,
            "originY": 3000,
            "minX": -3000,
            "maxX": 3000,
            "minZ": -3000,
            "maxZ": 3000,
            "width": 6001,
            "height": 6001,
        })

    def test_non_square_or_different_resolution_is_rejected(self):
        for dimensions in ((6000, 6000), (6001, 6000), (6001, 6002)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(ValueError):
                    coordinate_system_for_dimensions(*dimensions)


if __name__ == "__main__":
    unittest.main()
