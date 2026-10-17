"""Convert original-image pixel measurements using a user-supplied scale bar."""
import math


def make_calibration(real_length_um, pixel_length, original_size):
    if real_length_um is None or pixel_length is None:
        raise ValueError('请同时填写比例尺的真实长度和原图像素长度。')
    for value in (real_length_um, pixel_length):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('两个长度都必须是大于0的有限数字。')
    if pixel_length < 1:
        raise ValueError('比例尺像素长度至少为1 px，请在原图中测量。')
    if pixel_length > math.hypot(original_size[0] - 1, original_size[1] - 1):
        raise ValueError('比例尺像素长度超过原图对角线，请检查是否填错单位。')
    scale = real_length_um / pixel_length
    area_scale = scale * scale
    if not math.isfinite(scale) or not math.isfinite(area_scale) or area_scale <= 0:
        raise ValueError('比例尺数值超出可计算范围，请检查输入。')
    return {'real_length_um': float(real_length_um), 'pixel_length': float(pixel_length),
            'um_per_pixel': scale, 'original_size': tuple(original_size)}


def calibrated_rows(result, excluded_ids, calibration):
    if result is None or calibration is None:
        return []
    if tuple(result['original_size']) != tuple(calibration['original_size']):
        raise ValueError('标定与当前原图尺寸不一致，请重新标定。')
    scale = calibration['um_per_pixel']
    excluded = {str(number) for number in (excluded_ids or [])}
    rows = []
    for item in result['objects']:
        metrics = item['metrics']
        values = [metrics['area_px2'] * scale * scale,
                  metrics['perimeter_px'] * scale,
                  metrics['equivalent_diameter_px'] * scale]
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError('换算结果超出可计算范围，请检查比例尺。')
        # Use full-precision pixel measurements for conversion, then format for display.
        rows.append([item['id'], '已排除' if str(item['id']) in excluded else '待核对',
                     *(float(f'{value:.6g}') for value in values),
                     round(metrics['circularity'], 3)])
    return rows
