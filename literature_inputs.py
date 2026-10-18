"""DOI lookup through Europe PMC and private, local PDF text extraction."""
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pandas as pd
import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from literature import API, FIELDS, MISSING, TABLE_FIELDS, extract_evidence, literature_table, plain_text, record_from_item

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 40
MAX_PAGE_STREAM_BYTES = 8 * 1024 * 1024
MAX_TOTAL_STREAM_BYTES = 64 * 1024 * 1024
MAX_TEXT_CHARS = 500_000
DOI_PATTERN = re.compile(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', re.I)


def _failure(message):
    return None, pd.DataFrame(columns=TABLE_FIELDS), message


def normalize_doi(value):
    """Accept a DOI or an exact doi.org resolver URL, never an arbitrary URL."""
    value = str(value or '').strip()
    if len(value) > 300:
        raise ValueError('DOI过长，请只填写一个DOI编号。')
    value = re.sub(r'^doi\s*:\s*', '', value, flags=re.I)
    if re.match(r'^https?://', value, re.I):
        parsed = urlsplit(value)
        if (parsed.scheme.lower() not in ('http', 'https')
                or parsed.netloc.lower() not in ('doi.org', 'dx.doi.org', 'www.doi.org')
                or parsed.query or parsed.fragment):
            raise ValueError('请填写DOI编号或doi.org链接；不接受其他网站网址。')
        value = unquote(parsed.path.lstrip('/'))
    if not DOI_PATTERN.fullmatch(value):
        raise ValueError('DOI格式不正确，例如：10.1038/s41596-020-00471-4。')
    return value.lower()


def doi_for_ui(doi, fulltext=False):
    """Return (state, table, status); input cannot control the network destination."""
    try:
        normalized = normalize_doi(doi)
    except ValueError as exc:
        return _failure(str(exc))
    try:
        # DOI is a supported Europe PMC search field; keep the phrase quoted.
        response = requests.get(
            f'{API}/search',
            params={'query': f'DOI:"{normalized}"', 'resultType': 'core',
                    'format': 'json', 'pageSize': 25},
            timeout=(8, 25), allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        matched = []
        for item in payload.get('resultList', {}).get('result', []):
            try:
                candidate = normalize_doi(item.get('doi', ''))
            except ValueError:
                continue
            if candidate == normalized:
                matched.append(record_from_item(item, bool(fulltext)))
        if not matched:
            return _failure('Europe PMC未返回完全匹配该DOI的记录。请核对DOI，或上传已取得的PDF；这不表示论文不存在。')
        state = {'query': f'DOI:{normalized}', 'input_type': 'doi', 'total_hits': len(matched), 'records': matched}
        scopes = '、'.join(dict.fromkeys(record['text_scope'] for record in matched))
        notes = ' '.join(dict.fromkeys(record['retrieval_note'] for record in matched if record['retrieval_note']))
        status = f'已核对DOI完全匹配，取得{len(matched)}条记录。读取范围：{scopes}。所有条件字段均待人工核对。'
        return state, pd.DataFrame(literature_table(state)), status + (' '+notes if notes else '')
    except requests.RequestException:
        return _failure('Europe PMC暂时无法连接。请稍后重试，或使用PDF与本地缓存入口。')
    except (ValueError, TypeError, KeyError, AttributeError):
        return _failure('Europe PMC返回的数据未能解析，请稍后重试或上传PDF。')


def _read_pdf(path):
    if not path:
        raise ValueError('请先上传一份PDF文件。')
    file_path = Path(getattr(path, 'name', path))
    if file_path.suffix.lower() != '.pdf':
        raise ValueError('请上传PDF文件。')
    if not file_path.is_file():
        raise ValueError('未找到上传的PDF，请重新选择文件。')
    if file_path.stat().st_size > MAX_PDF_BYTES:
        raise ValueError('PDF不能超过15MB，请拆分后上传。')
    data = file_path.read_bytes()
    if not data.lstrip()[:8].startswith(b'%PDF-'):
        raise ValueError('文件内容不是可读取的PDF，请重新导出后上传。')
    reader = PdfReader(BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError('PDF已加密，请先使用有权访问的未加密副本。')
    count = len(reader.pages)
    if not count or count > MAX_PDF_PAGES:
        raise ValueError('支持1至40页PDF，请按需要拆分后上传。')
    pages, total_stream, text_chars = [], 0, 0
    for number, page in enumerate(reader.pages, start=1):
        contents = page.get_contents()
        stream_size = len(contents.get_data()) if contents is not None else 0
        total_stream += stream_size
        if stream_size > MAX_PAGE_STREAM_BYTES or total_stream > MAX_TOTAL_STREAM_BYTES:
            raise ValueError('这份PDF的页面内容过于复杂，请导出较小的文本版PDF再试。')
        text = plain_text(page.extract_text() or '')
        text_chars += len(text)
        if text_chars > MAX_TEXT_CHARS:
            raise ValueError('PDF文字量超过本次读取上限，请拆分后上传。')
        pages.append((number, text))
    return file_path, data, reader.metadata or {}, pages


def pdf_for_ui(path):
    """Extract the uploaded PDF locally; neither its text nor bytes go to a service."""
    try:
        file_path, data, metadata, pages = _read_pdf(path)
        nonempty = [(number, text) for number, text in pages if text.strip()]
        if not nonempty:
            return _failure('PDF没有可提取的文字，可能是扫描件。当前不含OCR；请上传可选择文字的PDF。')
        text = '\n'.join(page_text for _, page_text in pages)
        fields, evidence = extract_evidence(text)
        for values in evidence['field_matches'].values():
            for match in values:
                match['candidate_pages'] = [number for number, page_text in nonempty
                                            if match['value'].lower() in page_text.lower()][:3]
        title = plain_text(str(metadata.get('/Title', '') or '')).strip()
        if not title or title.lower() in ('untitled', 'anonymous'):
            title = file_path.name
        doi_candidates = list(dict.fromkeys(match.group().rstrip('.,;').lower()
                                             for match in DOI_PATTERN.finditer('\n'.join(t for _, t in pages[:3]))))[:5]
        record = {
            'id': 'pdf:'+hashlib.sha256(data).hexdigest()[:16], 'title': title[:300],
            'authors': plain_text(str(metadata.get('/Author', '') or ''))[:200], 'year': '',
            'doi': (doi_candidates[0]+'（PDF候选，待核对）') if doi_candidates else '',
            'doi_candidates': doi_candidates, 'pmcid': '', 'url': '',
            'document_source': '用户上传PDF：'+file_path.name,
            'text_scope': f'用户PDF第1–{len(pages)}页的可提取文字；{len(nonempty)}页有文字；未做OCR',
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'extraction_status': '规则抽取，待人工核对',
            'retrieval_note': '仅在本部署实例处理上传文件，未将PDF或正文发送给第三方检索服务；标题/作者来自PDF元数据。',
            'evidence': evidence, 'evidence_excerpt': evidence['excerpt'],
            'orbit_note': '保留原文单位；轨道半径/直径、设备及培养组对应关系待核对。',
            'missing_interpretation': '未抽取到仅针对PDF可提取文字；图表、扫描页与复杂排版可能遗漏，不能推断原文未报告。',
            'pdf_sha256': hashlib.sha256(data).hexdigest(), 'pdf_pages': len(pages),
            'text_pages': [number for number, _ in nonempty],
        }
        record.update({field: fields[field] or MISSING for field in FIELDS})
        state = {'query': file_path.name, 'input_type': 'pdf', 'total_hits': 1, 'records': [record]}
        status = f'已读取PDF的{len(nonempty)}/{len(pages)}页文字，候选条件已列出，需核对页码与适用培养组。当前未做OCR。'
        if len(nonempty) < len(pages):
            status += ' 部分页面没有文字层，可能遗漏图表或扫描内容。'
        return state, pd.DataFrame(literature_table(state)), status
    except ValueError as exc:
        return _failure(str(exc))
    except (PdfReadError, OSError, TypeError, KeyError, RecursionError):
        return _failure('PDF无法解析，可能已损坏或采用不支持的编码，请重新导出文本版PDF。')

