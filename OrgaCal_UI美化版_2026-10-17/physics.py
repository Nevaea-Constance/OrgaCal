"""Explicit depth-gradient scaling hypothesis; not a calibrated flow simulation."""
import math

MODEL_ID = 'depth-gradient-scale-v0.1'
SUPPORTED_GEOMETRY = '圆形平底孔 / 培养皿'


def _number(value, label, allow_zero=False):
    if isinstance(value, bool) or value is None or value == '':
        raise ValueError(f'请填写{label}。')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{label}需要填写数字。') from None
    if not math.isfinite(result) or (result < 0 if allow_zero else result <= 0):
        rule = '大于或等于0' if allow_zero else '大于0'
        raise ValueError(f'{label}必须是{rule}的有限数字。')
    return result


def estimate_shear(geometry, orbit_diameter_mm, rpm, vessel_diameter_mm, volume_ml,
                   viscosity_low_mpas, viscosity_high_mpas, temperature_c):
    if geometry != SUPPORTED_GEOMETRY:
        raise ValueError('当前模型仅支持圆形平底孔或培养皿；其他几何需要另外建模。')
    orbit = _number(orbit_diameter_mm, '轨道直径')
    speed = _number(rpm, '转速', allow_zero=True)
    diameter = _number(vessel_diameter_mm, '容器内径')
    volume = _number(volume_ml, '液量')
    mu_low = _number(viscosity_low_mpas, '黏度下限')
    mu_high = _number(viscosity_high_mpas, '黏度上限')
    temp = _number(temperature_c, '黏度对应温度', allow_zero=True)
    if mu_low > mu_high:
        raise ValueError('黏度下限不能大于上限，请检查两个输入。')
    try:
        radius_m = orbit / 2000
        area_m2 = math.pi * (diameter / 2000)**2
        depth_m = volume * 1e-6 / area_m2
        omega = 2 * math.pi * speed / 60
        velocity = omega * radius_m
        gradient = velocity / depth_m
        # (mPa s) * (1/s) yields mPa directly, with no second factor of 1000.
        low, high = mu_low * gradient, mu_high * gradient
        depth_ratio = depth_m / (diameter / 1000)
        positive_values = (radius_m, area_m2, depth_m, depth_ratio)
        derived_values = (*positive_values, depth_m * 1000, omega, velocity, gradient, low, high)
        if any(not math.isfinite(v) for v in derived_values) or any(v <= 0 for v in positive_values):
            raise ArithmeticError
        if speed > 0 and any(v <= 0 for v in (omega, velocity, gradient, low, high)):
            raise ArithmeticError
    except (ArithmeticError, OverflowError):
        raise ValueError('输入量级超出可计算范围，请检查单位及数值。') from None
    return {
        'model_id': MODEL_ID, 'geometry': geometry,
        'orbit_diameter_mm': orbit, 'rpm': speed, 'vessel_diameter_mm': diameter,
        'volume_ml': volume, 'viscosity_low_mpas': mu_low, 'viscosity_high_mpas': mu_high,
        'temperature_c': temp, 'depth_mm': depth_m * 1000,
        'omega_rad_s': omega, 'orbital_speed_m_s': velocity,
        'gradient_scale_s_inv': gradient, 'shear_low_mpa': low, 'shear_high_mpa': high,
        'depth_to_diameter': depth_ratio,
    }


def shear_for_ui(*inputs):
    try:
        result = estimate_shear(*inputs)
    except ValueError as error:
        return '', f'未生成结果：{error}', [], ''
    lo, hi = result['shear_low_mpa'], result['shear_high_mpa']
    value = f'{lo:.4g} – {hi:.4g} mPa' if lo != hi else f'{lo:.4g} mPa（输入范围重合）'
    note = ('当前为液深梯度尺度估算，尚未针对实际摇床校准。范围仅来自输入的黏度范围，'
            '不包含模型误差，也不是生物安全范围。')
    if result['rpm'] == 0:
        note += ' 当前转速为0：本模型的轨道运动剪切贡献为0，其他流动未计入。'
    rows = [
        ['轨道直径', f"{result['orbit_diameter_mm']:.6g}", 'mm'],
        ['转速', f"{result['rpm']:.6g}", 'rpm'],
        ['容器内径', f"{result['vessel_diameter_mm']:.6g}", 'mm'],
        ['单孔 / 单皿液量', f"{result['volume_ml']:.6g}", 'mL'],
        ['计算得到的平均液深', f"{result['depth_mm']:.6g}", 'mm'],
        ['轨道线速度尺度', f"{result['orbital_speed_m_s']:.6g}", 'm/s'],
        ['速度梯度尺度 U/h', f"{result['gradient_scale_s_inv']:.6g}", 's⁻¹'],
        ['输入黏度范围', f"{result['viscosity_low_mpas']:.6g} – {result['viscosity_high_mpas']:.6g}", 'mPa·s'],
        ['黏度对应温度（记录）', f"{result['temperature_c']:.6g}", '°C'],
        ['液深 / 容器内径', f"{result['depth_to_diameter']:.6g}", '无单位'],
    ]
    assumptions = f'''**本次计算假设与公式**（{MODEL_ID}）

1. 容器为圆形、平底、直壁，内径{result['vessel_diameter_mm']:g} mm；单孔/单皿液量{result['volume_ml']:g} mL，平均液深按体积除以底面积计算。
2. 轨道直径{result['orbit_diameter_mm']:g} mm，半径为它的一半；转速{result['rpm']:g} rpm先除以60，再换算角速度。
3. 假设牛顿流体，动力黏度{result['viscosity_low_mpas']:g}–{result['viscosity_high_mpas']:g} mPa·s。{result['temperature_c']:g} °C只记录黏度对应条件，程序不自动修正黏度。
4. 用轨道线速度作为流速尺度，用平均液深作为速度变化长度：U=π×轨道直径×rpm/60，h=液量/[π×(容器内径/2)²]，τ尺度=μU/h；计算时长度和体积换成SI单位。
5. 上述U和h是本版选取的尺度，尚未通过流场测量校准。输出不代表组织表面或壁面某位置的剪切峰值或平均值。
6. 未解析液面波动、共振、湍流、局部边界层、组织运动和组织间碰撞；未计算悬浮与氧供给，因此本步不生成安全转速区间。

**依据及区别**：牛顿流体剪切应力与速度梯度的关系见[Driessen等（2020），式4](https://pmc.ncbi.nlm.nih.gov/articles/PMC7345652/)。U取轨道速度、梯度长度取液深，是本项目按策划书采用的简化假设，不是该文验证过的解析模型。类器官六孔板的[CFD研究（2019）](https://pmc.ncbi.nlm.nih.gov/articles/PMC6404276/)在其90 rpm条件下报告约45 mPa局部最大值；该数值仅作独立文献背景，不用于拟合本公式或判断安全。'''
    return value, note, rows, assumptions


def reset_shear():
    return '', '参数已改变，请重新计算。', [], ''
