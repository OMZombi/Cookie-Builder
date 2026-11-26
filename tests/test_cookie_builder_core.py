import unittest

import numpy as np

from cookie_builder_core import generate_model


class CookieBuilderCoreTests(unittest.TestCase):
    def test_square_mask_generates_mesh(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255

        result = generate_model(
            mask=mask,
            size_mm=60,
            wall_mm=1,
            cutter_height_mm=12,
            emboss_mm=1,
            base_mm=2,
            simplify_mm=0.25,
        )

        self.assertGreater(len(result.mesh.faces), 0)
        self.assertGreater(result.mesh.volume, 0)

    def test_too_large_wall_is_rejected(self):
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[8:12, 8:12] = 255

        with self.assertRaises(ValueError):
            generate_model(
                mask=mask,
                size_mm=20,
                wall_mm=5,
                cutter_height_mm=12,
                emboss_mm=1,
                base_mm=2,
                simplify_mm=0.25,
            )


if __name__ == "__main__":
    unittest.main()
