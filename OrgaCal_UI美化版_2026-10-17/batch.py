"""Multi-image measurements with stable keys, per-image calibration and failure accounting."""
import hashlib
import json
from pathlib import Path

import pandas as pd
from PIL import Image

from morphology import detect_candidates, render_result

ROOT = Path(__file__).resolve().parent
LENGTH_METRICS = {'perimeter':'perimeter_px', 'equivalent_diameter':'equivalent_diameter_px',
                  'mean_radius':'mean_radius_px', 'max_feret':'max_feret_px', 'min_feret':'min_feret_px'}
FEATURES = ['area', *LENGTH_METRICS, 'circularity', 'solidity']
META_COLUMNS = ['image','batch','condition','day','imaging_batch','microscope','magnification','um_per_pixel']


def image_records(result, image_name, digest, metadata, scale=None):
    records = []
    for item in result['objects']:
        m = item['metrics']
        record = {'object_key': f'{digest[:10]}:{item["id"]}', 'image':image_name, 'image_sha256':digest,
                  'object_id':item['id'], 'excluded':False, 'review_status':'待核对', **metadata,
                  'um_per_pixel':scale, 'unit_basis':'um' if scale is not None else 'px',
                  'area_px2':m['area_px2'], **{v:m[v] for v in LENGTH_METRICS.values()},
                  'circularity':m['circularity'], 'solidity':m['solidity']}
        record['area'] = m['area_px2'] * (scale**2 if scale is not None else 1)
        for name, original in LENGTH_METRICS.items():
            record[name] = m[original] * (scale if scale is not None else 1)
        records.append(record)
    return records


def load_metadata(path):
    if not path:
        return {}
    frame = pd.read_csv(str(path), encoding='utf-8-sig', dtype=str).fillna('')
    if 'image' not in frame:
        raise ValueError('元数据CSV必须包含image列，值为图片完整文件名。')
    if frame['image'].duplicated().any():
        raise ValueError('元数据中image文件名重复，请先消除歧义。')
    return {r['image']:r for r in frame.to_dict('records')}


def analyze_batch(paths, metadata_path=None, min_area=5000, offset=0,
                  default_batch='批次1', condition='未提供', day='', imaging_batch='未提供',
                  shared_scale=None, shared_scale_confirmed=False):
    if not paths:
        raise ValueError('请先上传一批图片。')
    if len(paths) > 20:
        raise ValueError('每次最多20张图片，请分批处理。')
    names = [Path(str(p)).name for p in paths]
    if len(set(names)) != len(names):
        raise ValueError('本批图片存在同名文件，请改成不同文件名后上传，以便准确关联元数据。')
    meta = load_metadata(metadata_path)
    scale_default = None
    if shared_scale_confirmed:
        if shared_scale is None or not 0 < float(shared_scale) < float('inf'):
            raise ValueError('确认共用比例尺后，请填写大于0的um/px数值。')
        scale_default = float(shared_scale)
    results, records, failures, digests = [], [], [], set()
    for path, name in zip(paths, names):
        try:
            path = Path(str(path))
            if path.stat().st_size > 25 * 1024 * 1024:
                raise ValueError('单图超过25 MB。')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in digests:
                raise ValueError('与本批其他图片内容相同，避免重复计数。')
            digests.add(digest)
            info = {k: meta.get(name, {}).get(k) or v for k, v in {
                'batch':default_batch or '未提供', 'condition':condition or '未提供',
                'day':day or '未提供', 'imaging_batch':imaging_batch or '未提供',
                'microscope':'未提供', 'magnification':'未提供'}.items()}
            raw_scale = meta.get(name, {}).get('um_per_pixel', '')
            scale = float(raw_scale) if raw_scale else scale_default
            if scale is not None and not (0 < scale < float('inf')):
                raise ValueError('比例尺必须是正的有限um/px数值。')
            with Image.open(path) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError('单图超过4000万像素，请先等比例缩小并同步修改比例尺。')
                result = detect_candidates(image, min_area, offset)
            result['image_name'], result['digest'] = name, digest
            results.append(result)
            records.extend(image_records(result, name, digest, info, scale))
            if not result['objects']:
                failures.append({'image':name,'reason':'未检出完整候选目标；仍保留此图运行记录。'})
        except (ValueError, OSError, Image.DecompressionBombError) as error:
            failures.append({'image':name, 'reason':str(error)})
    if len(records) > 3000:
        raise ValueError('本次候选超过3000个，请减小批量或提高最小面积。')
    return {'records':records,'results':results,'failures':failures,'image_count':len(paths),
            'parameters':{'min_area_px2':min_area,'threshold_offset':offset},
            'scale_policy':'per-image metadata, else user-confirmed shared scale, else pixels',
            'notes':['候选尚未经过人工核对；排除操作不能补画漏检或拆开粘连。',
                     '未提供微米比例尺的图片保留像素单位，不与微米数据混合。',
                     '成像批次未提供时无法控制该协变量；同显微镜倍率不代表比例尺相同。']}


def review_batch(state, excluded):
    excluded = set(excluded or [])
    records = [{**r, 'excluded':r['object_key'] in excluded,
                'review_status':'已排除' if r['object_key'] in excluded else '待核对'} for r in state['records']]
    gallery = []
    for result in state['results']:
        ids = [str(r['object_id']) for r in records if r['image_sha256'] == result['digest'] and r['excluded']]
        gallery.append((render_result(result, ids)[0], result['image_name']))
    return {**state, 'records':records}, gallery, pd.DataFrame(records)


def reference_records():
    index = json.loads((ROOT/'data/reference/paper_data_index.json').read_text(encoding='utf-8'))
    records = []
    for r in index['reference_samples']:
        m = r['metrics']
        record = {'object_key':r['reference_id'], 'batch':r['batch'], 'condition':r['group'].split('_')[0],
                  'day':str(r['day']), 'imaging_batch':'论文EV1（具体成像协变量未充分提供）',
                  'unit_basis':'um', 'excluded':False, 'source':'author EV1',
                  'area':m['area_um2'], 'perimeter':m['perimeter_um'],
                  'paper_radius':m['paper_radius_um'], 'paper_roundness_pct':m['paper_roundness_pct'],
                  'max_feret':m['max_feret_um'], 'min_feret':m['min_feret_um'],
                  'mean_curvature':m['mean_curvature_per_um'], 'std_curvature':m['std_curvature_per_um'],
                  'std_curvature_times_radius':m['std_curvature_times_radius'], 'paper_dne':m['paper_dne'],
                  'source_row':r['source_row'], 'match_status':r['match_status']}
        records.append(record)
    return records
