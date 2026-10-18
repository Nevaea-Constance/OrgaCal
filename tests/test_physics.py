import math
import time
import unittest

from physics import SUPPORTED_GEOMETRY, estimate_shear, reset_shear, shear_for_ui


class ShearScaleTests(unittest.TestCase):
    def setUp(self):
        self.args = [SUPPORTED_GEOMETRY, 20, 60, 20, math.pi, 1, 2, 37]

    def test_independent_si_example(self):
        # 20 mm well + pi mL -> 10 mm depth; 20 mm orbit at 1 Hz -> 0.02*pi m/s.
        result = estimate_shear(*self.args)
        self.assertAlmostEqual(result['depth_mm'], 10)
        self.assertAlmostEqual(result['orbital_speed_m_s'], math.pi * 0.02)
        self.assertAlmostEqual(result['shear_low_mpa'], 2 * math.pi)
        self.assertAlmostEqual(result['shear_high_mpa'], 4 * math.pi)

    def test_scaling_with_input_parameters(self):
        base = estimate_shear(*self.args)['shear_low_mpa']
        for index, expected_ratio in [(1, 2), (2, 2), (3, 4), (4, 0.5), (5, 2)]:
            args = self.args.copy()
            args[index] *= 2
            self.assertAlmostEqual(estimate_shear(*args)['shear_low_mpa'] / base, expected_ratio)

    def test_geometry_scale_invariance(self):
        args = self.args.copy()
        args[1] *= 3
        args[3] *= 3
        args[4] *= 27
        self.assertAlmostEqual(estimate_shear(*args)['shear_low_mpa'], 2 * math.pi)

    def test_zero_speed_and_equal_viscosities(self):
        args = self.args.copy()
        args[2] = 0
        result = estimate_shear(*args)
        self.assertEqual(result['shear_low_mpa'], 0)
        self.assertEqual(result['shear_high_mpa'], 0)
        self.assertIn('其他流动未计入', shear_for_ui(*args)[1])
        args = self.args.copy()
        args[6] = args[5]
        self.assertIn('范围重合', shear_for_ui(*args)[0])

    def test_invalid_inputs_and_cleared_results(self):
        for index in range(1, 8):
            for invalid in (None, '', True, float('nan'), float('inf'), -1, 'bad'):
                with self.subTest(index=index, invalid=invalid):
                    args = self.args.copy()
                    args[index] = invalid
                    with self.assertRaises(ValueError):
                        estimate_shear(*args)
                    output = shear_for_ui(*args)
                    self.assertEqual((output[0], output[2], output[3]), ('', [], ''))
        for index in (1, 3, 4, 5, 6):
            args = self.args.copy()
            args[index] = 0
            with self.assertRaises(ValueError):
                estimate_shear(*args)
        args = self.args.copy()
        args[5] = 3
        with self.assertRaises(ValueError):
            estimate_shear(*args)
        args[0] = 'unsupported'
        with self.assertRaises(ValueError):
            estimate_shear(*args)
        self.assertEqual((reset_shear()[0], reset_shear()[2], reset_shear()[3]), ('', [], ''))

    def test_extreme_numeric_inputs(self):
        for index, value in [(3, 1e-300), (3, 1e308), (4, 1e308), (2, 1e308), (5, 1e-320)]:
            args = self.args.copy()
            args[index] = value
            try:
                result = estimate_shear(*args)
            except ValueError:
                continue
            for key in ('depth_mm', 'orbital_speed_m_s', 'shear_low_mpa', 'shear_high_mpa'):
                self.assertTrue(math.isfinite(result[key]))

    def test_temperature_is_metadata_and_assumptions_explicit(self):
        args = self.args.copy()
        args[7] = 25
        self.assertEqual(estimate_shear(*args)['shear_low_mpa'], estimate_shear(*self.args)['shear_low_mpa'])
        output = shear_for_ui(*args)
        self.assertIn('25 °C只记录', output[3])
        self.assertIn('未通过流场测量校准', output[3])
        self.assertIn('不包含模型误差', output[1])


if __name__ == '__main__':
    begin = time.perf_counter()
    for _ in range(1000):
        estimate_shear(SUPPORTED_GEOMETRY, 25, 80, 35, 3, 0.7, 1, 37)
    print(f'1000 calculations: {time.perf_counter() - begin:.4f} s')
    unittest.main(verbosity=2)
