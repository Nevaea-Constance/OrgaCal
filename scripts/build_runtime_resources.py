"""Build the standalone resource module for uploaders that omit subfolders."""
import base64
import hashlib
import io
from pathlib import Path
import pprint
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted(path for folder in ['assets', 'examples', 'data/reference']
               for path in (ROOT / folder).rglob('*') if path.is_file())
manifest = {}
archive = io.BytesIO()
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
    for path in FILES:
        name = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        manifest[name] = hashlib.sha256(data).hexdigest()
        entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        bundle.writestr(entry, data, compresslevel=9)
encoded = base64.b64encode(archive.getvalue()).decode('ascii')
loader = '''

def ensure_resources(root=None):
    """Restore only missing bundled public resources; preserve existing files."""
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent
    missing = [name for name in _MANIFEST if not (root / name).is_file()]
    if not missing:
        return []
    with ZipFile(BytesIO(b64decode(_PAYLOAD, validate=True))) as bundle:
        pending = []
        for name in missing:
            relative = PurePosixPath(name)
            target = (root / name).resolve()
            if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(root):
                raise ValueError('Invalid bundled resource path')
            data = bundle.read(name)
            if sha256(data).hexdigest() != _MANIFEST[name]:
                raise ValueError('Bundled resource checksum mismatch: ' + name)
            pending.append((target, data))
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + target.name + '.' + uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(data)
            replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return missing
'''
header = '''"""Generated public UI/data resources. Rebuild with scripts/build_runtime_resources.py.

Original assets and third-party notices remain authoritative. No credentials are bundled.
"""
from base64 import b64decode
from hashlib import sha256
from io import BytesIO
from os import replace
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile

'''
source = header + '_MANIFEST = ' + pprint.pformat(manifest, sort_dicts=True) + '\n\n_PAYLOAD = (\n'
source += ''.join('    ' + repr(line) + '\n' for line in textwrap.wrap(encoded, width=100))
source += ')\n' + loader
destination = ROOT / 'deployment_resources.py'
destination.write_text(source, encoding='utf-8')
print(f'Bundled {len(manifest)} public resource files into {destination.name} ({destination.stat().st_size} bytes).')
