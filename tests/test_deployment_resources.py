"""Cloud uploader regressions: missing folders must not prevent startup."""
import base64
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import deployment_resources as resources


class DeploymentResourceTests(unittest.TestCase):
    def test_restore_missing_nested_resources_exactly(self):
        with tempfile.TemporaryDirectory() as folder:
            restored = resources.ensure_resources(folder)
            self.assertEqual(set(restored), set(resources._MANIFEST))
            for name, expected in resources._MANIFEST.items():
                actual = hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, name)
            self.assertEqual(resources.ensure_resources(folder), [])

    def test_existing_custom_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            css = Path(folder) / 'assets/workbench.css'
            css.parent.mkdir()
            css.write_text('/* local customization */', encoding='utf-8')
            restored = resources.ensure_resources(folder)
            self.assertNotIn('assets/workbench.css', restored)
            self.assertEqual(css.read_text(encoding='utf-8'), '/* local customization */')

    def test_paths_cannot_escape_restore_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(resources, '_MANIFEST', {'../outside.css': 'invalid'}):
                with self.assertRaisesRegex(ValueError, 'path'):
                    resources.ensure_resources(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_corrupt_content_is_rejected_before_writing(self):
        changed = io.BytesIO()
        with zipfile.ZipFile(changed, 'w') as bundle:
            bundle.writestr('assets/workbench.css', b'corrupt')
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(resources, '_MANIFEST', {'assets/workbench.css': resources._MANIFEST['assets/workbench.css']}), patch.object(resources, '_PAYLOAD', base64.b64encode(changed.getvalue()).decode()):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    resources.ensure_resources(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
