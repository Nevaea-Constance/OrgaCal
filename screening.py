"""Scan explicit physical constraints without inventing a morphology predictor."""
import math
import re
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from constraints import conditional_interval
from physics import estimate_shear, SUPPORTED_GEOMETRY


def scan_conditions(interval, orbit_text='10,19,25,50', rpm_min=40, rpm_max=160, rpm_step=10, target_diameter=500, target_circularity=.8):
    start = perf_counter()
    if not interval or not interval.get('inputs'):
        raise ValueError('请先在上方填写完整约束，并计算双边界条件区间。')
    try:
        orbits = sorted(set(float(x) for x in re.split(r'[,，;；\s]+', str(orbit_text).strip()) if x))
        lower, upper, step = map(float, (rpm_min, rpm_max, rpm_step))
        diameter, circularity = float(target_diameter), float(target_circularity)
    except (ValueError, TypeError):
        raise ValueError('轨道直径、转速范围和目标形态需要填写有效数字。')
    values = [*orbits, lower, upper, step, diameter, circularity]
    if not all(math.isfinite(v) for v in values) or not orbits or any(v <= 0 for v in orbits) or lower < 0 or upper < lower or step <= 0:
        raise ValueError('轨道直径和步长需大于0；转速下限不能大于上限。')
    if diameter <= 0 or not 0 < circularity <= 1:
        raise ValueError('目标直径需大于0，目标圆形度需在0到1之间。')
    count = math.floor((upper - lower) / step + 1e-9) + 1
    if len(orbits) * count > 300:
        raise ValueError('最多扫描300组组合，请减少轨道规格或增大转速步长。')
    rpms = [lower + i * step for i in range(count)]
    rows = []
    for orbit in orbits:
        p = {**interval['inputs'], 'orbit_mm': orbit}
        bounds = conditional_interval(p)
        for rpm in rpms:
            shear = estimate_shear(SUPPORTED_GEOMETRY, orbit, rpm, p['vessel_mm'], p['volume_ml'], p['mu_low'], p['mu_high'], p['temperature_c'])
            passed = bounds.get('status') == 'feasible' and bounds['lower'] - 1e-9 <= rpm <= bounds['upper'] + 1e-9
            reasons = []
            if rpm > p['max_rpm']: reasons.append('超过设备上限')
            if shear['shear_high_mpa'] > p['shear_limit_mpa'] + 1e-9: reasons.append('超过剪切上限')
            if rpm < bounds.get('suspension_lower', 0): reasons.append('未达悬浮下界')
            if bounds.get('oxygen_lower') is not None and rpm < bounds['oxygen_lower']: reasons.append('未达氧供给下界')
            if bounds.get('transfer_re_upper_rpm') is not None and rpm > bounds['transfer_re_upper_rpm']: reasons.append('超出传质模型Re范围')
            if bounds.get('status') == 'empty' and not reasons: reasons.append(bounds['message'])
            rows.append({'orbit_mm': orbit, 'rpm': rpm, 'shear_low_mpa': shear['shear_low_mpa'], 'shear_high_mpa': shear['shear_high_mpa'],
                         'physical_feasible': passed, 'reason': '满足当前物理约束' if passed else '；'.join(reasons), 'morphology_prediction': '未预测：缺少条件—形态配对训练数据'})
    return {'records': rows, 'scan_count': len(rows), 'feasible_count': sum(r['physical_feasible'] for r in rows),
            'inputs': {'orbit_mm': orbits, 'rpm_min': lower, 'rpm_max': upper, 'rpm_step': step, 'constraints': interval['inputs']},
            'target': {'diameter_um': diameter, 'circularity': circularity, 'role': '待实验验证的目标；未参与生物学预测'},
            'paired_training_samples': 0, 'prediction_error': None, 'runtime_ms': round((perf_counter() - start) * 1000, 3),
            'status': 'physical_scan', 'note': '离散物理约束扫描；不预测形态达标，不对候选作生物学优劣排序。'}


def scan_for_ui(*args):
    try:
        result = scan_conditions(*args)
        records = result['records']
        fig, ax = plt.subplots(figsize=(7.2, 3.1), constrained_layout=True)
        for passed, color, marker, label in [(False, '#B46A56', 'x', 'Outside constraints'), (True, '#2E8B7F', 'o', 'Within constraints')]:
            selected = [r for r in records if r['physical_feasible'] == passed]
            if selected:
                ax.scatter([r['rpm'] for r in selected], [r['orbit_mm'] for r in selected], color=color, marker=marker, label=label, s=45)
        ax.set(xlabel='Rotation speed (rpm)', ylabel='Orbit diameter (mm)', title='Physical constraint scan | morphology not predicted')
        ax.set_yticks(result['inputs']['orbit_mm'])
        ax.grid(alpha=.16, color='#123B36')
        ax.legend(loc='best', fontsize=8)
        columns = {'orbit_mm': '轨道直径 (mm)', 'rpm': '转速 (rpm)', 'shear_low_mpa': '剪切下限 (mPa)', 'shear_high_mpa': '剪切上限 (mPa)', 'reason': '约束判定'}
        frame = pd.DataFrame(records).sort_values(['physical_feasible', 'orbit_mm', 'rpm'], ascending=[False, True, True])
        frame = frame[list(columns)].rename(columns=columns).round(3)
        text = f"### {result['feasible_count']} / {result['scan_count']} 组满足当前物理约束\n\n后端计算耗时 **{result['runtime_ms']:.1f} ms**；条件—形态配对训练样本 **0 组**；预测误差 **尚未评估**。\n\n目标：等效直径 {result['target']['diameter_um']:g} µm，圆形度 ≥ {result['target']['circularity']:g}。这些目标仅作实验记录；当前数据不足，展示物理筛选与敏感性，不声称候选达到目标形态。"
        return text, frame, fig, result
    except (ValueError, TypeError, ArithmeticError) as error:
        return '未完成扫描：' + str(error), pd.DataFrame(), None, None
