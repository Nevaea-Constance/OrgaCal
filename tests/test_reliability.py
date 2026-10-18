"""Numerical checks of repeated-measure agreement and descriptive sample CV."""
import io
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from consistency import sample_cv, summarize
from reliability import icc_two_way_absolute, reliability_for_ui, TEMPLATE_CSV


def long_table(matrix):
    return pd.DataFrame([
        {'target_id':f'T{i+1}', 'rater_id':f'R{j+1}', 'value':value}
        for i, row in enumerate(matrix) for j, value in enumerate(row)
    ])


class ReliabilityTests(unittest.TestCase):
    def test_perfect_agreement_and_anova(self):
        result = icc_two_way_absolute(long_table([[10,10],[20,20],[30,30]]))
        self.assertAlmostEqual(result['icc'], 1)
        self.assertAlmostEqual(result['MSR'], 200)
        self.assertAlmostEqual(result['MSC'], 0)
        self.assertAlmostEqual(result['MSE'], 0)
        self.assertEqual((result['n'], result['k']), (3,2))
        self.assertIsNone(result['confidence_interval'])

    def test_systematic_offset_lowers_absolute_agreement(self):
        # Hand calculation: MSR=2, MSC=1.5, MSE=0 => ICC=2/(2+1)=2/3.
        result = icc_two_way_absolute(long_table([[1,2],[2,3],[3,4]]))
        self.assertAlmostEqual(result['MSR'], 2)
        self.assertAlmostEqual(result['MSC'], 1.5)
        self.assertAlmostEqual(result['MSE'], 0)
        self.assertAlmostEqual(result['icc'], 2/3)
        self.assertLess(result['icc'], 1)

    def test_scale_translation_and_order_do_not_change_icc(self):
        matrix = np.array([[1,2,1.5],[2,2.5,1.8],[3,4,3.1],[4,3.6,4.5]])
        baseline = icc_two_way_absolute(long_table(matrix))['icc']
        transformed = long_table(matrix * 1000 + 50).sample(frac=1, random_state=12)
        self.assertAlmostEqual(icc_two_way_absolute(transformed)['icc'], baseline)

    def test_missing_duplicate_and_unpaired_rows_are_rejected(self):
        frame = long_table([[1,2],[2,3],[3,4]])
        with self.assertRaisesRegex(ValueError, '不完整或不平衡'):
            icc_two_way_absolute(frame.iloc[:-1])
        with self.assertRaisesRegex(ValueError, '重复'):
            icc_two_way_absolute(pd.concat([frame, frame.iloc[:1]], ignore_index=True))
        frame.loc[0, 'value'] = np.nan
        with self.assertRaisesRegex(ValueError, '缺失'):
            icc_two_way_absolute(frame)
        with self.assertRaisesRegex(ValueError, '不完整或不平衡'):
            icc_two_way_absolute(pd.DataFrame({
                'target_id':['a','b','c','d'], 'rater_id':['A','B','A','B'], 'value':[1,2,3,4]}))

    def test_insufficient_and_constant_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '至少需要3个目标'):
            icc_two_way_absolute(long_table([[1,1],[2,2]]))
        with self.assertRaisesRegex(ValueError, 'ICC'):
            icc_two_way_absolute(long_table([[7,7],[7,7],[7,7]]))
        with self.assertRaisesRegex(ValueError, '缺少必需列'):
            icc_two_way_absolute(pd.DataFrame({'area':[1,2,3]}))

    def test_negative_estimate_is_not_clipped(self):
        result = icc_two_way_absolute(long_table([[1,3],[2,2],[3,1]]))
        self.assertLess(result['icc'], 0)

    def test_ui_template_and_error_clear_state(self):
        parsed = pd.read_csv(io.StringIO(TEMPLATE_CSV))
        self.assertEqual(icc_two_way_absolute(parsed)['n_measurements'], 8)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'repeated.csv'
            path.write_text(TEMPLATE_CSV, encoding='utf-8')
            message, table, state = reliability_for_ui(path)
            self.assertIn('未计算95%', message)
            self.assertEqual(len(table), 3)
            self.assertEqual(state['n'], 4)
            path.write_text('target_id,rater_id,value\na,r1,1\n', encoding='utf-8')
            message, table, state = reliability_for_ui(str(path))
            self.assertIn('无法计算ICC', message)
            self.assertTrue(table.empty)
            self.assertIsNone(state)


class SampleCVTests(unittest.TestCase):
    def test_sample_sd_definition_and_missing_values(self):
        result = sample_cv([1,3,np.nan,np.inf])
        self.assertAlmostEqual(result['mean'], 2)
        self.assertAlmostEqual(result['sample_sd'], np.sqrt(2))
        self.assertAlmostEqual(result['cv_pct'], 100*np.sqrt(2)/2)
        self.assertIsNone(sample_cv([1])['sample_sd'])
        self.assertIsNone(sample_cv([1])['cv_pct'])
        self.assertIsNone(sample_cv([-1,1])['cv_pct'])
        self.assertIsNone(sample_cv([])['mean'])

    def test_summary_keeps_mad_and_adds_cv_by_batch(self):
        records = [{'object_key':str(index), 'batch':batch, 'area':value,
                    'condition':'c', 'day':'1', 'imaging_batch':'i', 'unit_basis':'px'}
                   for index, (batch,value) in enumerate([('A',1),('A',3),('B',10)])]
        result = summarize(records, features=['area'])
        first, second = result['summary']
        self.assertEqual(first['batch'], 'A')
        self.assertAlmostEqual(first['relative_mad_pct'], 50)
        self.assertAlmostEqual(first['cv_pct'], 100*np.sqrt(2)/2)
        self.assertEqual(second['n'], 1)
        self.assertIsNone(second['cv_pct'])
        self.assertTrue(any('ddof=1' in note for note in result['notes']))


if __name__ == '__main__':
    unittest.main()
