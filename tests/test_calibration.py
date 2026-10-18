"""Run from a project or staging directory with the project's Python environment."""
import math
import unittest

from calibration import calibrated_rows, make_calibration


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.result = {'original_size': (800, 600), 'objects': [
            {'id': 1, 'metrics': {'area_px2': 10000.0, 'perimeter_px': 400.0,
                                 'equivalent_diameter_px': 100.0, 'circularity': 0.785}},
            {'id': 2, 'metrics': {'area_px2': 0.123456789, 'perimeter_px': 4.123456789,
                                 'equivalent_diameter_px': 0.396477, 'circularity': 0.091}}
        ]}

    def test_known_scale_and_units(self):
        scale = make_calibration(100, 200, (800, 600))
        self.assertEqual(scale['um_per_pixel'], 0.5)
        rows = calibrated_rows(self.result, ['2'], scale)
        self.assertEqual(rows[0], [1, '待核对', 2500, 200, 50, 0.785])
        self.assertEqual(rows[1][0:2], [2, '已排除'])
        self.assertAlmostEqual(rows[1][2], 0.123456789 * 0.25, places=7)
        self.assertEqual(self.result['objects'][0]['metrics']['area_px2'], 10000)

    def test_scale_doubling(self):
        a = calibrated_rows(self.result, [], make_calibration(100, 200, (800, 600)))[0]
        b = calibrated_rows(self.result, [], make_calibration(200, 200, (800, 600)))[0]
        self.assertEqual(b[2], a[2] * 4)
        self.assertEqual(b[3], a[3] * 2)
        self.assertEqual(b[4], a[4] * 2)
        self.assertEqual(b[5], a[5])

    def test_invalid_scales(self):
        for a, b in [(None, 200), (100, None), (0, 200), (-1, 200), (100, 0),
                     (100, -2), (100, 0.5), (math.inf, 200), (100, math.nan),
                     ('100', 200), (True, 200), (100, 1000), (1e308, 1), (1e-200, 1)]:
            with self.subTest(real=a, pixels=b), self.assertRaises(ValueError):
                make_calibration(a, b, (800, 600))
        self.assertEqual(calibrated_rows(self.result, [], None), [])

    def test_wrong_dimensions(self):
        scale = make_calibration(100, 200, (801, 600))
        with self.assertRaises(ValueError):
            calibrated_rows(self.result, [], scale)

    def test_ui_clearing_and_recalibration(self):
        import app
        scale, message, table = app.apply_calibration(100, 200, self.result, ['2'])
        self.assertEqual(scale['um_per_pixel'], 0.5)
        self.assertTrue(table['visible'])
        self.assertEqual(table['value'][1][1], '已排除')
        self.assertIn('0.5 µm/px', message)
        for args in [(0, 200, self.result, []), (100, None, self.result, []), (100, 200, None, [])]:
            result = app.apply_calibration(*args)
            self.assertIsNone(result[0])
            self.assertFalse(result[2]['visible'])
            self.assertEqual(result[2]['value'], [])
        reset = app.reset_image()
        self.assertEqual(len(reset), 10)
        self.assertIsNone(reset[4])  # analysis state
        self.assertIsNone(reset[5])  # calibration state
        self.assertEqual(reset[7]['value'], [])
        self.assertFalse(reset[7]['visible'])
        self.assertEqual(reset[8:], (None, None))  # scale inputs
        self.assertEqual(app.clear_calibration()[0:3], (None, None, None))
        self.assertEqual(app.analyze_for_ui(None, 5000, 0)[7]['value'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
