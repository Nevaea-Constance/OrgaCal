"""Readable, traceable summaries of real workbench results."""
from functools import lru_cache
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def metric(label, value, note=''):
    return f'<div class="oc-evidence-metric"><span>{escape(str(label))}</span><strong>{escape(str(value))}</strong><small>{escape(str(note))}</small></div>'


def duration(state):
    value = (state or {}).get('runtime_ms')
    if value is None:
        return '待运行'
    return f'{value / 1000:.2f} s' if value >= 1000 else f'{value:.1f} ms'


@lru_cache(maxsize=1)
def validation_data():
    def read(name):
        return json.loads((ROOT / 'data' / 'reference' / name).read_text(encoding='utf-8'))
    segmentation = read('segmentation_validation.json')
    mad = read('mad_validation.json')
    errors = [abs(r['computed']['relative_mad_ratio'] - r['reference']) for r in mad['rows']]
    return {'segmentation': segmentation, 'mad': mad, 'mad_max_error': max(errors, default=0)}


def validation_panel():
    data = validation_data()
    s, m = data['segmentation'], data['mad']
    cells = metric('外部分割验证', f"{s['n_images']} 张", 'SLiMIA OperaPhenix 细胞球')
    cells += metric('平均前景 Dice', f"{s['mean_dice']:.4f}", f"平均 IoU {s['mean_iou']:.4f}；非实例准确率")
    cells += metric('作者相对 MAD 复算', f"{m['match_counts']['relative_mad_ratio']} / {m['rows_checked']}", f"最大绝对误差 {data['mad_max_error']:.2e}")
    cells += metric('条件—形态训练样本', '0 组', '未训练代理模型；预测误差未评估')
    return f'<section class="oc-validation"><h3>公开验证记录</h3><div class="oc-evidence-grid">{cells}</div><p>分割指标来自已保存的外部细胞球验证；MAD 核验统计口径。两者均不等于摇床流场标定或生物学效果验证。</p></section>'


def run_info(state, kind):
    if not state:
        return '<div class="oc-run-info"><span>待运行</span><span>完成操作后显示本次输入、样本规模和后端耗时。</span></div>'
    details = []
    if kind == 'shear':
        details = [f"轨道 {state['orbit_diameter_mm']:g} mm", f"{state['rpm']:g} rpm", f"内径 {state['vessel_diameter_mm']:g} mm", f"液量 {state['volume_ml']:g} mL", '解析计算 / 无训练样本']
    elif kind == 'interval':
        p = state.get('inputs', {})
        details = [f"阈值 {p.get('shear_limit_mpa', '未提供')} mPa", f"直径 {p.get('diameter_um', '未提供')} µm", f"Q {p.get('oxygen_q', '未提供')} mol/m³/s", f"{len(state.get('sensitivity', []))} 组敏感性情景", '装置标定误差：未评估']
    elif kind == 'batch':
        details = [f"{state.get('image_count', 0)} 张图像", f"{len(state.get('records', []))} 条目标记录", f"{len(state.get('failures', []))} 张失败或未检出", '作者 EV1 参数表' if state.get('origin') == 'paper_ev1' else '本程序轮廓测量 / 待复核']
    elif kind == 'statistics':
        details = [f"{len(state.get('summary', []))} 行批次指标", f"{len(state.get('pca', []))} 个 PCA 分层", 'CV + 相对 MAD / 不混合条件与单位']
    elif kind == 'literature':
        details = [f"{len(state.get('records', []))} 篇记录", '自动提取 / 待人工核对', '准确率：尚未人工评估']
    elif kind == 'conversion':
        details = [state.get('criterion', ''), f"{state.get('source_rpm', '')} → {state.get('target_rpm', 0):.3g} rpm", '保持选定物理量']
    items = ''.join(f'<span>{escape(str(item))}</span>' for item in details)
    return f'<div class="oc-run-info"><strong>后端耗时 {duration(state)}</strong>{items}</div>'


def overview(physics=None, interval=None, conversion=None, batch=None, stats=None, literature=None, screening=None, reliability=None):
    rows = [
        ('剪切预算', f"{physics['shear_low_mpa']:.2f}–{physics['shear_high_mpa']:.2f} mPa" if physics else '等待参数计算', '液深尺度模型；结果随输入黏度变化', physics),
        ('双边界条件区间', f"{interval['lower']:.2f}–{interval['upper']:.2f} rpm" if interval and interval.get('status') == 'feasible' else ('当前约束无交集' if interval else '等待约束输入'), '剪切上界与悬浮、氧供给下界求交', interval),
        ('形态与一致性', f"{len((batch or {}).get('records', []))} 条记录 / {len((stats or {}).get('pca', []))} 个 PCA 分层" if batch else '等待图片或作者统计示例', '作者 EV1 统计示例' if (batch or {}).get('origin') == 'paper_ev1' else '候选轮廓、CV、相对 MAD 与 PCA', stats or batch),
        ('文献条件', f"{len(literature.get('records', []))} 篇可追溯记录" if literature else '等待检索、DOI 或 PDF', '出处、文本范围与逐条核对状态', literature),
        ('候选条件筛选', f"{screening['feasible_count']} / {screening['scan_count']} 组满足物理约束" if screening and screening.get('scan_count') else '等待参数网格扫描', '训练样本不足时显示敏感性与条件交集', screening),
        ('转速换算', f"{conversion['target_rpm']:.2f} rpm" if conversion else '等待两台设备参数', '等模型剪切、等线速度或等加速度', conversion),
    ]
    cards = ''.join(f'<article class="oc-overview-card"><div><h3>{escape(title)}</h3><span class="oc-state-chip">{"已运行" if state else "待运行"}</span></div><strong>{escape(value)}</strong><p>{escape(note)}</p><small>后端耗时 {duration(state)}</small></article>' for title, value, note, state in rows)
    return '<div class="oc-overview-grid">' + cards + '</div>'


def workflow():
    return '<div class="oc-workflow"><span>设备与培养条件</span><b>→</b><span>解析计算与参数扫描</span><b>→</b><span>照片测量与一致性</span><b>→</b><span>文献核对与报告导出</span></div>'


def statistics_table(stats):
    import pandas as pd
    columns = {'condition': '条件', 'day': '天数', 'batch': '批次', 'feature': '形态特征', 'unit': '单位', 'n': '目标数', 'median': '中位数', 'mean': '均值', 'cv_pct': 'CV (%)', 'relative_mad_pct': '相对 MAD (%)'}
    frame = pd.DataFrame((stats or {}).get('summary', []))
    if frame.empty:
        return frame
    return frame[[c for c in columns if c in frame]].rename(columns=columns).round(4)
