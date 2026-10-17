"""Europe PMC retrieval with evidence snippets; absent text never becomes an invented value."""
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import requests

API = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
ROOT = Path(__file__).resolve().parent
FIELDS = ['equipment','rpm','orbit','culture','outcome']


def plain_text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', value or ''))).strip()


def extract_evidence(text):
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    equipment = [s for s in sentences if re.search(r'orbital.shak|spinner.flask|Spin.?[Ωω]|rotat.{0,12}bioreactor|rotating.chamber', s, re.I)]
    rpm = [s for s in sentences if re.search(r'\b\d+(?:\.\d+)?\s*(?:rpm|r\.p\.m\.|rev.?/min)\b', s, re.I)
           and re.search(r'shak|orbit|spinner|bioreactor|rotat', s, re.I)
           and not re.search(r'centrifug|pellet|torque|rheomet|viscomet', s, re.I)]
    orbit = [s for s in sentences if re.search(r'\b\d+(?:\.\d+)?\s*mm\b', s, re.I)
             and re.search(r'orbit|gyrat|shaking.diameter', s, re.I)]
    culture = [s for s in sentences if re.search(r'(?:brain|cerebral|cortical|intestinal|kidney|retinal|liver).{0,30}organoid', s, re.I)]
    # Outcome is an evidence passage, never an automatic causal conclusion.
    outcome = [s for s in sentences if re.search(r'organoid', s, re.I)
               and re.search(r'reproduc|viabil|growth|matur|differenti|shear', s, re.I)]
    values = dict(zip(FIELDS,(equipment,rpm,orbit,culture,outcome)))
    evidence = {}
    # One short excerpt per paper; remaining provenance is a source URL + text scope.
    passage = (rpm or equipment or culture or outcome or [''])[0]
    evidence['excerpt'] = ' '.join(passage.split()[:18])
    evidence['scope_note'] = '短摘录用于定位；其他字段由规则提取，需回到原文核对。'
    equipment_names = ['orbital shaker','spinner flask','rotating chamber','SpinΩ','bioreactor']
    equipment_value = ', '.join(name for name in equipment_names if any(name.lower() in s.lower() for s in equipment))
    rpm_values = sorted(set(m.group(0) for s in rpm for m in re.finditer(r'\d+(?:\.\d+)?(?:\s*(?:[-–]|to)\s*\d+(?:\.\d+)?)?\s*(?:RPM|rpm|rev/min)',s)))
    orbit_values = sorted(set(m.group(0) for s in orbit for m in re.finditer(r'\d+(?:\.\d+)?\s*mm',s)))
    culture_names = ['brain','cerebral','cortical','intestinal','kidney','retinal','liver']
    culture_value = ', '.join(name+' organoid' for name in culture_names if any(name in s.lower() for s in culture))
    fields = {'equipment':equipment_value,'rpm':', '.join(rpm_values), 'orbit':', '.join(orbit_values),
              'culture':culture_value, 'outcome':'需回原文核对，自动提取不判定培养效果' if outcome else ''}
    return fields,evidence


def search_papers(query='brain organoid orbital shaker', limit=20, fulltext=False):
    query = str(query).strip()
    if not query or len(query) > 500:
        raise ValueError('检索词需要1到500个字符。')
    limit = min(50, max(1, int(limit)))
    response = requests.get(f'{API}/search', params={'query':query,'resultType':'core','format':'json','pageSize':limit}, timeout=(10,45))
    response.raise_for_status()
    payload = response.json()
    records = []
    for item in payload.get('resultList',{}).get('result',[]):
        abstract = plain_text(item.get('abstractText',''))
        pmcid, doi = item.get('pmcid',''), item.get('doi','')
        text, scope, error = abstract, '摘要', ''
        if fulltext and pmcid:
            try:
                r = requests.get(f'{API}/{pmcid}/fullTextXML',timeout=(10,30))
                r.raise_for_status()
                root = ET.fromstring(r.content)
                body = root.find('body')
                if body is not None:
                    text = ' '.join(' '.join(p.itertext()) for p in body.iter('p'))
                    text = plain_text(text)
                    scope = 'PMC开放全文正文（不含补充材料）'
            except (requests.RequestException, ET.ParseError) as e:
                error = f'全文未取得：{type(e).__name__}'
        fields,snippets = extract_evidence(text)
        record = {'id':item.get('id'), 'title':item.get('title',''), 'authors':item.get('authorString',''),
                  'year':item.get('pubYear',''), 'doi':doi, 'pmcid':pmcid,
                  'url':f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/' if pmcid else (f'https://doi.org/{doi}' if doi else f'https://europepmc.org/article/{item.get("source","MED")}/{item.get("id")}'),
                  'text_scope':scope, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
                  'extraction_status':'规则抽取，待人工核对', 'retrieval_note':error,
                  'evidence':snippets}
        for field in FIELDS:
            record[field] = fields[field] or '未报告'
        record['evidence_excerpt']=snippets['excerpt']
        record['orbit_note'] = '提及同句的mm值，可能是容器尺寸；轨道半径/直径及具体设备均需核对。'
        record['missing_interpretation'] = '“未报告”仅指已获取文本中未抽取到；不代表全文或补充材料不存在该信息。'
        records.append(record)
    return {'query':query,'total_hits':payload.get('hitCount',0),'records':records}


def cached_papers():
    path = ROOT/'data/reference/literature_cache.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'records':[],'query':'','total_hits':0}


def literature_table(result):
    return [{k:r.get(k,'') for k in ['title','year','pmcid','doi','equipment','rpm','orbit','orbit_note','culture','outcome','evidence_excerpt','text_scope','extraction_status','url']} for r in result.get('records',[])]
