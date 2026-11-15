import unittest
import numpy as np
from server import calculate_ndvi_statistics, _validate_polygon

class NdviTests(unittest.TestCase):
    def test_pixel_formula_and_statistics(self):
        red = np.array([[0.2, 0.1], [0.3, 0.2]], dtype=np.float32)
        nir = np.array([[0.7, 0.3], [0.5, 0.6]], dtype=np.float32)
        quality = np.array([[True, True], [True, True]])
        ndvi, valid, stats = calculate_ndvi_statistics(red, nir, quality)
        self.assertEqual(stats['count'], 4)
        self.assertAlmostEqual(float(ndvi[0,0]), (0.7-0.2)/(0.7+0.2), places=5)
        self.assertAlmostEqual(stats['min'], float(np.min(ndvi)), places=6)
        self.assertAlmostEqual(stats['max'], float(np.max(ndvi)), places=6)
        self.assertAlmostEqual(stats['mean'], float(np.mean(ndvi)), places=6)

    def test_cloud_mask_excludes_pixel(self):
        red = np.array([[0.2, 0.2]], dtype=np.float32)
        nir = np.array([[0.6, 0.8]], dtype=np.float32)
        quality = np.array([[True, False]])
        _, valid, stats = calculate_ndvi_statistics(red, nir, quality)
        self.assertEqual(int(valid.sum()), 1)
        self.assertEqual(stats['count'], 1)

    def test_invalid_zero_denominator_is_excluded(self):
        red = np.array([[0.0, 0.2]], dtype=np.float32)
        nir = np.array([[0.0, 0.6]], dtype=np.float32)
        _, valid, stats = calculate_ndvi_statistics(red, nir, np.array([[True, True]]))
        self.assertEqual(stats['count'], 1)
        self.assertFalse(bool(valid[0,0]))

    def test_polygon_validation(self):
        poly = {"type":"Polygon", "coordinates":[[[16.0,-9.0],[16.1,-9.0],[16.1,-9.1],[16.0,-9.0]]]}
        self.assertEqual(_validate_polygon(poly).geom_type, 'Polygon')
        with self.assertRaises(ValueError):
            _validate_polygon({"type":"Point", "coordinates":[16,-9]})

if __name__ == '__main__': unittest.main()
