"""Fetch public bibliography and machine-extracted evidence; never mark as human verified."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from literature import search_papers

result = search_papers('(organoid*) AND ("orbital shaker" OR "rotating chamber" OR "spinner flask" OR "SpinOmega")',30,fulltext=True)
path = ROOT/'data/reference/literature_cache.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Saved {len(result["records"])} public records; full text: '+str(sum(r['text_scope'].startswith('PMC') for r in result['records'])),flush=True)
for index,r in enumerate(result['records'],1):
    print(f'{index:02d} | {r["pmcid"] or r["doi"]} | {r["title"]} | '+r['rpm'][:180],flush=True)
