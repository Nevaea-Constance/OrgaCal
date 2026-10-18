"""Checks for screening, DOI/PDF intake, run metadata, presentation and report wiring."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reportlab.pdfgen import canvas

import literature_inputs as li
from constraints import conditional_interval
from presentation import duration, overview, run_info, statistics_table, validation_panel
from reports import build_bundle
from run_metadata import timed_state
from screening import scan_conditions, scan_for_ui

BASE = {'orbit_mm': 25, 'vessel_mm': 35, 'volume_ml': 3, 'mu_low': .7, 'mu_high': 1, 'temperature_c': 37,
        'shear_limit_mpa': 45, 'diameter_um': 500, 'delta_rho': 40, 'rho': 1000, 'oxygen_q': .02,
        'bulk_oxygen': .2, 'critical_oxygen': .02, 'diffusivity': 3e-9, 'tissue_diffusivity': 2e-9,
        'beta_suspend': .05, 'beta_transfer': .01, 'max_rpm': 300, 'basis': 'test scenario'}


def interval():
    return conditional_interval(dict(BASE))


class ScreeningTests(unittest.TestCase):
    def test_scan_marks_only_in_interval_rpm_and_never_predicts_morphology(self):
        state = interval()
        result = scan_conditions(state, '25', 40, 160, 10)
        self.assertEqual(result['scan_count'], 13)
        for row in result['records']:
            inside = state['lower'] - 1e-9 <= row['rpm'] <= state['upper'] + 1e-9
            self.assertEqual(row['physical_feasible'], inside)
            self.assertIn('未预测', row['morphology_prediction'])
        self.assertEqual(result['paired_training_samples'], 0)
        self.assertIsNone(result['prediction_error'])
        self.assertGreater(result['feasible_count'], 0)

    def test_requires_interval_and_valid_numbers(self):
        with self.assertRaisesRegex(ValueError, '双边界'):
            scan_conditions(None)
        with self.assertRaisesRegex(ValueError, '有效数字'):
            scan_conditions(interval(), 'abc')
        with self.assertRaisesRegex(ValueError, '不能大于上限'):
            scan_conditions(interval(), '25', 100, 50, 10)
        with self.assertRaisesRegex(ValueError, '圆形度'):
            scan_conditions(interval(), '25', 40, 160, 10, 500, 1.5)

    def test_grid_limit_is_enforced(self):
        with self.assertRaisesRegex(ValueError, '300'):
            scan_conditions(interval(), '10,19,25,50', 0, 1000, 1)

    def test_ui_wrapper_returns_message_instead_of_raising(self):
        text, frame, fig, state = scan_for_ui(None, '25', 40, 160, 10, 500, .8)
        self.assertIn('未完成扫描', text)
        self.assertTrue(frame.empty)
        self.assertIsNone(fig)
        self.assertIsNone(state)


class DoiTests(unittest.TestCase):
    def test_accepts_doi_and_resolver_urls_only(self):
        self.assertEqual(li.normalize_doi('DOI: 10.1038/S41596-020-00471-4'), '10.1038/s41596-020-00471-4')
        self.assertEqual(li.normalize_doi('https://doi.org/10.1038/s44319-025-00619-x'), '10.1038/s44319-025-00619-x')
        for bad in ('https://evil.example/10.1038/x', 'https://doi.org/10.1038/x?next=http://a', 'not a doi', '10.1/x', 'x' * 301):
            with self.assertRaises(ValueError, msg=bad):
                li.normalize_doi(bad)

    def test_ui_reports_invalid_input_without_network(self):
        with patch.object(li.requests, 'get') as get:
            state, table, status = li.doi_for_ui('nope')
        get.assert_not_called()
        self.assertIsNone(state)
        self.assertTrue(table.empty)
        self.assertIn('DOI格式', status)

    def test_ui_reports_no_exact_match_and_network_failure(self):
        class Response:
            def raise_for_status(self): pass
            def json(self): return {'resultList': {'result': [{'doi': '10.1000/other'}]}}
        with patch.object(li.requests, 'get', return_value=Response()):
            state, _, status = li.doi_for_ui('10.1000/wanted')
        self.assertIsNone(state)
        self.assertIn('完全匹配', status)
        with patch.object(li.requests, 'get', side_effect=li.requests.ConnectionError()):
            state, _, status = li.doi_for_ui('10.1000/wanted')
        self.assertIsNone(state)
        self.assertIn('无法连接', status)


class PdfTests(unittest.TestCase):
    def make_pdf(self, folder, text):
        path = Path(folder) / 'paper.pdf'
        sheet = canvas.Canvas(str(path))
        if text:
            sheet.drawString(72, 760, text)
        else:
            sheet.rect(72, 700, 100, 40)  # a page with graphics but no text layer
        sheet.save()
        return path

    def test_text_pdf_yields_candidates_that_need_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_pdf(folder, 'Brain organoids were cultured on an orbital shaker at 80 rpm with 19 mm orbital diameter in 35 mm dishes.')
            state, table, status = li.pdf_for_ui(str(path))
        self.assertEqual(state['input_type'], 'pdf')
        row = table.iloc[0]
        self.assertIn('80', row['rpm'])
        self.assertIn('19 mm', row['orbit'])
        self.assertIn('待人工核对', row['extraction_status'])
        self.assertIn('未做OCR', status)

    def test_empty_text_layer_non_pdf_and_missing_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            blank = self.make_pdf(folder, '')
            self.assertIn('没有可提取的文字', li.pdf_for_ui(str(blank))[2])
            fake = Path(folder) / 'fake.pdf'
            fake.write_text('not a pdf', encoding='utf-8')
            self.assertIn('不是可读取的PDF', li.pdf_for_ui(str(fake))[2])
            self.assertIn('请先上传', li.pdf_for_ui(None)[2])
            self.assertIn('未找到', li.pdf_for_ui(str(Path(folder) / 'absent.pdf'))[2])
            other = Path(folder) / 'note.txt'
            other.write_text('x', encoding='utf-8')
            self.assertIn('请上传PDF', li.pdf_for_ui(str(other))[2])

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_pdf(folder, 'orbital shaker 80 rpm')
            with patch.object(li, 'MAX_PDF_BYTES', 10):
                self.assertIn('15MB', li.pdf_for_ui(str(path))[2])


class MetadataAndPresentationTests(unittest.TestCase):
    def test_timed_state_adds_runtime_only_to_dict_state(self):
        @timed_state(-1)
        def with_state():
            return 'text', {'a': 1}

        @timed_state(-1)
        def without_state():
            return 'text', None
        text, state = with_state()
        self.assertEqual(text, 'text')
        self.assertEqual(state['a'], 1)
        self.assertGreaterEqual(state['runtime_ms'], 0)
        self.assertIn('computed_at_utc', state)
        self.assertEqual(without_state(), ('text', None))

    def test_duration_and_run_info_never_invent_values(self):
        self.assertEqual(duration(None), '待运行')
        self.assertEqual(duration({'runtime_ms': 12.34}), '12.3 ms')
        self.assertEqual(duration({'runtime_ms': 2500}), '2.50 s')
        self.assertIn('待运行', run_info(None, 'batch'))
        self.assertIn('待人工核对', run_info({'records': [], 'runtime_ms': 1}, 'literature'))

    def test_overview_marks_unrun_modules_and_escapes_html(self):
        empty = overview()
        self.assertEqual(empty.count('待运行</span>'), 6)
        shown = overview(screening={'feasible_count': 6, 'scan_count': 52, 'runtime_ms': 3.2})
        self.assertIn('6 / 52', shown)
        self.assertEqual(shown.count('已运行'), 1)

    def test_validation_panel_states_zero_training_samples(self):
        panel = validation_panel()
        self.assertIn('0 组', panel)
        self.assertIn('不等于摇床流场标定', panel)

    def test_statistics_table_handles_empty(self):
        self.assertTrue(statistics_table(None).empty)
        frame = statistics_table({'summary': [{'condition': 'c', 'n': 3, 'cv_pct': 1.23456, 'relative_mad_pct': 2.0}]})
        self.assertEqual(list(frame.columns), ['条件', '目标数', 'CV (%)', '相对 MAD (%)'])


class BundleTests(unittest.TestCase):
    def read_all(self, files):
        return [Path(f).name for f in files if f]

    def test_bundle_labels_unrun_modules(self):
        files = build_bundle()
        self.assertTrue(files)
        report = next(Path(f) for f in files if str(f).endswith('.md'))
        text = report.read_text(encoding='utf-8')
        self.assertIn('尚未运行', text)
        self.assertIn('候选条件扫描', text)

    def test_bundle_includes_screening_when_run(self):
        state = scan_conditions(interval(), '25', 40, 160, 10)
        files = build_bundle(screening=state)
        report = next(Path(f) for f in files if str(f).endswith('.md'))
        text = report.read_text(encoding='utf-8')
        self.assertIn('条件-形态配对训练样本：0 组', text)
        self.assertIn('不预测形态达标', text)


if __name__ == '__main__':
    unittest.main()
