"""Evidence-first literature retrieval; missing text is never an invented value."""
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import requests

API = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
ROOT = Path(__file__).resolve().parent
FIELDS = ['equipment', 'rpm', 'orbit', 'container', 'shear', 'culture', 'timepoint', 'outcome']
NEW_FIELDS = ('container', 'shear', 'timepoint')
TABLE_FIELDS = ['title', 'year', 'pmcid', 'doi', 'equipment', 'rpm', 'orbit', 'orbit_note',
                'container', 'shear', 'culture', 'timepoint', 'outcome', 'evidence_excerpt',
                'text_scope', 'document_source', 'extraction_status', 'url']
MISSING = '未在已读取文本中抽取到'
NUMBER = r'\d+(?:\.\d+)?(?:\s*(?:[-–−]|to)\s*\d+(?:\.\d+)?)?'
SIZE = rf'{NUMBER}\s*[-–]?\s*(?:mm|cm)\b'
VESSEL = r'(?:dish(?:es)?|well(?:s)?|flask(?:s)?|vessel(?:s)?|chamber(?:s)?|培养皿|培养孔|培养瓶|容器)'
MECHANICAL = r'centrifug|pellet|torque|rheomet|viscomet|tensile|elastic.modul|杨氏模量|离心|流变仪|黏度计'


def plain_text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', value or ''))).strip()


def _short_context(sentence, value, words=18):
    """Keep enough surrounding words to check a candidate, without copying a passage."""
    tokens = sentence.split()
    if len(tokens) <= words:
        return sentence[:180]
    start = sentence.lower().find(value.lower())
    index = len(sentence[:max(0, start)].split())
    low = max(0, min(index - 5, len(tokens) - words))
    return ('… ' if low else '') + ' '.join(tokens[low:low+words]) + (' …' if low+words < len(tokens) else '')


def extract_evidence(text):
    """Return candidate values with units and local context, always requiring review.

    These conservative English/Chinese rules do not establish that a condition was
    used for a particular culture group, or that a reported shear value is safe.
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+|[\r\n]+', str(text or '')) if s.strip()]
    matches = {field: [] for field in FIELDS}

    def add(field, value, sentence):
        value = re.sub(r'\s+', ' ', value).strip()
        if value and not any(m['value'].lower() == value.lower() for m in matches[field]):
            matches[field].append({'value': value, 'context': _short_context(sentence, value),
                                   'needs_review': True})

    equipment_patterns = [
        ('orbital shaker', r'orbital[ -]shak\w*|轨道摇床|圆周摇床'),
        ('spinner flask', r'spinner[ -]flask\w*'),
        ('rotating chamber', r'rotat\w*[ -]chamber\w*'),
        ('SpinΩ', r'Spin\s*[Ωω]'),
        ('bioreactor', r'bioreactor\w*'),
    ]
    for sentence in sentences:
        mechanical = bool(re.search(MECHANICAL, sentence, re.I))
        culture_context = bool(re.search(r'organoid|cultur|类器官|培养', sentence, re.I))
        for name, pattern in equipment_patterns:
            if re.search(pattern, sentence, re.I):
                add('equipment', name, sentence)
        if not mechanical and re.search(r'shak|orbit|spinner|bioreactor|rotat|摇床|振荡', sentence, re.I):
            for match in re.finditer(rf'\b{NUMBER}\s*(?:rpm\b|r\.p\.m\.?|rev(?:olutions)?\s*/\s*min\b|转/分)', sentence, re.I):
                add('rpm', match.group(), sentence)
        if not mechanical:
            orbit_patterns = [
                rf'(?:orbit(?:al)?(?:\s+(?:diameter|radius|throw))?|gyration|shaking\s+diameter|轨道直径|轨道半径|晃幅)[\s:=(),-]*(?:of\s+)?(?P<value>{SIZE})',
                rf'(?P<value>{SIZE})\s*(?:orbit(?:al)?(?:\s+(?:diameter|radius|throw))?|shaking\s+diameter)',
            ]
            for pattern in orbit_patterns:
                for match in re.finditer(pattern, sentence, re.I):
                    add('orbit', match.group('value'), sentence)
            container_patterns = [
                rf'(?P<value>{SIZE})\s*(?:diameter\s+|wide\s+)?(?:(?:culture|petri|round|circular|flat.bottom)\s+)*{VESSEL}',
                rf'{VESSEL}\s*(?:with\s+)?(?:an?\s+)?(?:inner\s+)?(?:diameter|width|size|内径|直径)[\s:=(),-]*(?:of\s+)?(?P<value>{SIZE})',
                rf'{VESSEL}\s*\(\s*(?P<value>{SIZE})',
            ]
            for pattern in container_patterns:
                for match in re.finditer(pattern, sentence, re.I):
                    add('container', match.group('value'), sentence)
            if re.search(r'shear\s+stress|fluid\s+shear|剪切应力', sentence, re.I):
                for match in re.finditer(rf'\b{NUMBER}\s*(?:mPa|kPa|Pa|dyn(?:e)?s?\s*/\s*cm\s*(?:\^?2|²))\b', sentence, re.I):
                    add('shear', match.group(), sentence)
        for name in ['brain', 'cerebral', 'cortical', 'intestinal', 'kidney', 'retinal', 'liver']:
            if re.search(rf'\b{name}\b.{{0,30}}organoid', sentence, re.I):
                add('culture', name+' organoid', sentence)
        if culture_context and not mechanical:
            for pattern in [rf'\b(?:day|days|week|weeks)\s+{NUMBER}(?:\s*(?:,|and|&)\s*\d+(?:\.\d+)?)*',
                            rf'\b{NUMBER}\s*(?:days?|weeks?|hours?)\b',
                            rf'第?\s*{NUMBER}\s*(?:天|周|小时)']:
                for match in re.finditer(pattern, sentence, re.I):
                    add('timepoint', match.group(), sentence)
        if re.search(r'organoid|类器官', sentence, re.I) and re.search(r'reproduc|viabil|growth|matur|differenti|shear|一致|存活|生长', sentence, re.I):
            add('outcome', '需回原文核对，自动提取不判定培养效果', sentence)
    fields = {field: ', '.join(m['value'] for m in matches[field][:6]) for field in FIELDS}
    best = next((matches[f][0]['context'] for f in ['rpm', 'equipment', 'culture', 'outcome'] if matches[f]), '')
    evidence = {
        'excerpt': ' '.join(best.split()[:18]),
        'scope_note': '数值与单位为候选字段；匹配语境、适用培养组及半径/直径等定义均待人工核对。',
        'field_matches': {field: values[:3] for field, values in matches.items()},
    }
    return fields, evidence


def record_from_item(item, fulltext=False):
    """Build a record from Europe PMC metadata; only official PMC IDs are fetched."""
    abstract = plain_text(item.get('abstractText', ''))
    raw_pmcid = str(item.get('pmcid', ''))
    pmcid = raw_pmcid if re.fullmatch(r'PMC\d+', raw_pmcid, re.I) else ''
    doi = str(item.get('doi', ''))
    text, scope, error = abstract, '摘要' if abstract else '仅书目信息，未取得摘要正文', ''
    if fulltext and pmcid:
        try:
            response = requests.get(f'{API}/{pmcid}/fullTextXML', timeout=(10, 30), allow_redirects=False)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            body = root.find('body')
            if body is not None:
                body_text = plain_text(' '.join(' '.join(p.itertext()) for p in body.iter('p')))
                if body_text:
                    text, scope = body_text, 'PMC开放全文正文（不含补充材料）'
                else:
                    error = '开放全文正文为空，保留摘要范围。'
            else:
                error = '未找到开放全文正文，保留摘要范围。'
        except (requests.RequestException, ET.ParseError) as exc:
            error = f'全文未取得：{type(exc).__name__}；仅保留实际取得的文本。'
    elif fulltext:
        error = '无PMC全文标识；仅保留实际取得的摘要。'
    fields, evidence = extract_evidence(text)
    record = {
        'id': item.get('id'), 'title': item.get('title', ''), 'authors': item.get('authorString', ''),
        'year': item.get('pubYear', ''), 'doi': doi, 'pmcid': pmcid,
        'url': f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/' if pmcid else (f'https://doi.org/{doi}' if doi else f'https://europepmc.org/article/{item.get("source", "MED")}/{item.get("id")}'),
        'document_source': 'Europe PMC', 'text_scope': scope,
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'extraction_status': '规则抽取，待人工核对', 'retrieval_note': error, 'evidence': evidence,
        'evidence_excerpt': evidence['excerpt'],
        'orbit_note': '保留原文单位；轨道半径/直径与设备及培养组的对应关系待核对。',
        'missing_interpretation': '未抽取到仅针对本次实际读取的文本；不代表全文或补充材料未报告。',
    }
    record.update({field: fields[field] or MISSING for field in FIELDS})
    return record


def search_papers(query='brain organoid orbital shaker', limit=20, fulltext=False):
    query = str(query).strip()
    if not query or len(query) > 500:
        raise ValueError('检索词需要1到500个字符。')
    limit = min(50, max(1, int(limit)))
    response = requests.get(f'{API}/search', params={'query': query, 'resultType': 'core', 'format': 'json', 'pageSize': limit}, timeout=(10, 45), allow_redirects=False)
    response.raise_for_status()
    payload = response.json()
    records = [record_from_item(item, fulltext) for item in payload.get('resultList', {}).get('result', [])]
    return {'query': query, 'total_hits': payload.get('hitCount', 0), 'records': records}


def cached_papers():
    path = ROOT/'data/reference/literature_cache.json'
    result = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'records': [], 'query': '', 'total_hits': 0}
    for record in result.get('records', []):
        for field in NEW_FIELDS:
            record.setdefault(field, '未在缓存中抽取')
        record.setdefault('document_source', 'Europe PMC本地缓存')
        for field in FIELDS:
            if record.get(field) == '未报告':
                record[field] = '缓存读取范围内未抽取到'
        record['missing_interpretation'] = '新字段未在旧缓存中抽取；其他空缺仅针对当时读取的文本范围，不能推断全文未报告。'
    return result


def literature_table(result):
    return [{key: record.get(key, '未在缓存中抽取' if key in NEW_FIELDS else '') for key in TABLE_FIELDS}
            for record in result.get('records', [])]
