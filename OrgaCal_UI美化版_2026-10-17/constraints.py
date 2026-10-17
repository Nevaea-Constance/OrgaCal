"""Conditional sphere-model constraints. No biological safety threshold is hardcoded."""
import math

from physics import SUPPORTED_GEOMETRY, _number, estimate_shear

G = 9.80665
SOURCES = {
    'shear': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7345652/',
    'oxygen': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5029285/',
    'mass_transfer': 'https://www.nist.gov/system/files/documents/el/fire_research/Sivathanu-Droplet-Interaction-with-Hot-Surfaces-Final-Report-to-the-Strategic-Environmental-Research-and-Development-Program.pdf',
    'drag': 'https://cpp.openfoam.org/v13/SchillerNaumann_8C_source.html',
}


def settling_velocity(diameter_m, delta_rho, rho, mu_pas):
    """Rigid sphere drag balance, Schiller-Naumann for Re<1000; no Stokes-only shortcut."""
    if delta_rho == 0:
        return 0.0, 0.0
    stokes = delta_rho * G * diameter_m**2 / (18 * mu_pas)
    lower, upper = 0.0, stokes
    for _ in range(100):
        speed = (lower + upper) / 2
        re = rho * speed * diameter_m / mu_pas
        if speed * (1 + 0.15 * re**0.687) < stokes:
            lower = speed
        else:
            upper = speed
    speed = (lower + upper) / 2
    re = rho * speed * diameter_m / mu_pas
    if re >= 1000:
        raise ValueError('沉降Re≥1000，超出本版球体阻力关系范围。')
    return speed, re


def oxygen_minimum(d, q, bulk, critical, diffusivity, tissue_diffusivity, rho, mu, beta, orbit_m):
    """Steady uniform volumetric uptake + external film; q in mol/m3/s, C in mol/m3."""
    drop_internal = q * d**2 / (24 * tissue_diffusivity)
    allowance = bulk - critical - drop_internal
    if allowance <= 0:
        return {'rpm': None, 'reason': '内部扩散限制：即使表面达到培养液氧浓度，中心仍不能达到设定阈值。',
                'internal_drop': drop_internal}
    required_k = q * d / (6 * allowance)
    required_sh = required_k * d / diffusivity
    sc = mu / (rho * diffusivity)
    re = 0.0 if required_sh <= 2 else ((required_sh - 2) / (0.6 * sc**(1/3)))**2
    if re > 200:
        return {'rpm': None, 'reason': '达到设定供氧条件需要的Re>200，超出本版传质关联式的计算范围。',
                'internal_drop': drop_internal}
    relative_speed = re * mu / (rho * d)
    rpm = relative_speed * 60 / (math.pi * orbit_m * beta)
    return {'rpm': rpm, 'required_k_m_s': required_k, 're': re, 'sc': sc,
            'internal_drop': drop_internal, 'reason': ''}


def conditional_interval(p):
    """Return explicit missing/empty/feasible state; all outputs remain uncalibrated scenarios."""
    needed = ['orbit_mm','vessel_mm','volume_ml','mu_low','mu_high','temperature_c',
              'shear_limit_mpa','diameter_um','delta_rho','rho','oxygen_q','bulk_oxygen',
              'critical_oxygen','diffusivity','tissue_diffusivity','beta_suspend','beta_transfer',
              'max_rpm','basis']
    missing = [key for key in needed if p.get(key) is None or p.get(key) == '']
    if missing:
        return {'status': 'missing', 'missing': missing, 'message': '参数或依据不足，暂不能确定双边界区间。'}
    values = {}
    for key in needed:
        if key == 'basis':
            continue
        values[key] = _number(p[key], key, allow_zero=key in ('delta_rho','oxygen_q','critical_oxygen','temperature_c'))
    if values['mu_low'] > values['mu_high']:
        raise ValueError('黏度下限不能大于上限。')
    if values['critical_oxygen'] >= values['bulk_oxygen']:
        raise ValueError('中心氧阈值必须小于培养液体相氧浓度。')
    if any(values[key] > 1 for key in ('beta_suspend','beta_transfer')):
        raise ValueError('速度比例系数必须在0到1之间。该系数需要校准，不是已知通用常数。')
    p = {**p, **values}
    one = estimate_shear(SUPPORTED_GEOMETRY, p['orbit_mm'], 1, p['vessel_mm'], p['volume_ml'],
                         p['mu_low'], p['mu_high'], p['temperature_c'])
    shear_upper = p['shear_limit_mpa'] / one['shear_high_mpa']
    diameter = p['diameter_um'] * 1e-6
    orbit = p['orbit_mm'] * 1e-3
    settling = [settling_velocity(diameter, p['delta_rho'], p['rho'], mu * 1e-3)
                for mu in (p['mu_low'], p['mu_high'])]
    suspend_lower = max(x[0] for x in settling) * 60 / (math.pi * orbit * p['beta_suspend'])
    oxygen = [oxygen_minimum(diameter, p['oxygen_q'], p['bulk_oxygen'], p['critical_oxygen'],
                            p['diffusivity'], p['tissue_diffusivity'], p['rho'], mu * 1e-3,
                            p['beta_transfer'], orbit) for mu in (p['mu_low'], p['mu_high'])]
    base = {'inputs': p, 'shear_upper': shear_upper, 'suspension_lower': suspend_lower,
            'settling_re_max': max(x[1] for x in settling), 'oxygen_scenarios': oxygen,
            'model': 'conditional-sphere-v0.1', 'sources': SOURCES,
            'evidence_status': '未校准情景；输入依据由用户提供，未独立验证平台匹配性。'}
    if any(x['rpm'] is None for x in oxygen):
        return {**base, 'status':'empty', 'message': next(x['reason'] for x in oxygen if x['rpm'] is None)}
    oxygen_lower = max(x['rpm'] for x in oxygen)
    lower = max(suspend_lower, oxygen_lower)
    upper = min(shear_upper, p['max_rpm'])
    # Restrict the computed interval to Re<=200 for both viscosity endpoint scenarios.
    transfer_limit = 200 * p['mu_low'] * 1e-3 / (p['rho'] * diameter) * 60 / (math.pi * orbit * p['beta_transfer'])
    upper = min(upper, transfer_limit)
    return {**base, 'oxygen_lower': oxygen_lower, 'lower': lower, 'upper': upper,
            'transfer_re_upper_rpm': transfer_limit,
            'status': 'feasible' if lower <= upper else 'empty',
            'message': '给定模型与输入下的条件可行区间；不是经实验验证的安全转速。' if lower <= upper else '各约束无可行交集。'}


def sensitivity(p):
    rows = []
    for density_factor in (0.5, 1, 2):
        for uptake_factor in (0.5, 1, 2):
            scenario = {**p, 'delta_rho': float(p['delta_rho']) * density_factor,
                        'oxygen_q': float(p['oxygen_q']) * uptake_factor}
            r = conditional_interval(scenario)
            rows.append({'density_difference_kg_m3':scenario['delta_rho'], 'uptake_mol_m3_s':scenario['oxygen_q'],
                         'lower_rpm':r.get('lower'), 'upper_rpm':r.get('upper'), 'status':r['status']})
    return rows


def convert_rpm(criterion, source_rpm, source_orbit, target_orbit, source_vessel=35, source_volume=3,
                source_mu=0.7, target_vessel=35, target_volume=3, target_mu=0.7):
    n = _number(source_rpm, '文献转速', allow_zero=True)
    d1 = _number(source_orbit, '文献轨道直径')
    d2 = _number(target_orbit, '目标轨道直径')
    if criterion == '等轨道线速度':
        return n * d1 / d2
    if criterion == '等轨道加速度':
        return n * math.sqrt(d1 / d2)
    if criterion != '等模型剪切（液深尺度）':
        raise ValueError('请选择明确的换算准则。')
    a = estimate_shear(SUPPORTED_GEOMETRY, d1, n, source_vessel, source_volume, source_mu, source_mu, 37)
    b = estimate_shear(SUPPORTED_GEOMETRY, d2, 1, target_vessel, target_volume, target_mu, target_mu, 37)
    return a['shear_high_mpa'] / b['shear_high_mpa']
