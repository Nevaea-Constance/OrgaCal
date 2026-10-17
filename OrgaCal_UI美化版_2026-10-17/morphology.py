"""Candidate outlines for bright-field images. No biological classification is performed."""
import math

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_PREVIEW_SIDE = 1600
MAX_CANDIDATES = 500


def measure_contour(contour, original_size, preview_size):
    """Measure a closed outer contour in original-image pixel coordinates."""
    scale = np.array([original_size[0] / preview_size[0], original_size[1] / preview_size[1]], dtype=np.float32)
    original_contour = contour.astype(np.float32) * scale
    area = float(cv2.contourArea(original_contour))
    perimeter = float(cv2.arcLength(original_contour, True))
    if not math.isfinite(area + perimeter) or area <= 0 or perimeter <= 0:
        raise ValueError('轮廓面积或周长无效。')
    hull = cv2.convexHull(original_contour).reshape(-1, 2).astype(float)
    hull_area = float(cv2.contourArea(hull.astype(np.float32)))
    if len(hull) >= 3:
        max_feret = float(np.sqrt(np.max(np.sum((hull[:, None, :] - hull[None, :, :])**2, axis=2))))
        edges = np.roll(hull, -1, axis=0) - hull
        norms = np.linalg.norm(edges, axis=1)
        normals = np.column_stack([-edges[:, 1], edges[:, 0]])[norms > 0] / norms[norms > 0, None]
        projected = hull @ normals.T
        min_feret = float(np.min(projected.max(axis=0) - projected.min(axis=0)))
    else:
        max_feret = min_feret = 0.0
    points = original_contour.reshape(-1, 2).astype(float)
    closed = np.vstack([points, points[0]])
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cumulative = np.r_[0, np.cumsum(lengths)]
    positions = np.linspace(0, cumulative[-1], 256, endpoint=False)
    samples = np.column_stack([np.interp(positions, cumulative, closed[:, i]) for i in (0, 1)])
    moments = cv2.moments(original_contour)
    centre = np.array([moments['m10']/moments['m00'], moments['m01']/moments['m00']])
    mean_radius = float(np.mean(np.linalg.norm(samples - centre, axis=1)))
    return {'area_px2': area, 'perimeter_px': perimeter,
            'equivalent_diameter_px': math.sqrt(4 * area / math.pi),
            'circularity': 4 * math.pi * area / perimeter**2,
            'mean_radius_px': mean_radius, 'max_feret_px': max_feret, 'min_feret_px': min_feret,
            'solidity': area / hull_area if hull_area > 0 else None}


def find_field_of_view(gray):
    """Ignore connected black exterior around a bright microscope field, when present."""
    height, width = gray.shape
    full = np.full(gray.shape, 255, dtype=np.uint8)
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    if float(np.mean(border < 16)) < 0.55:
        return full, False
    light = np.uint8(gray > 16) * 255
    contours, _ = cv2.findContours(light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return full, False
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 0.2 * height * width:
        return full, False
    field = np.zeros_like(gray)
    # Filling only the external outline restores dark objects wholly inside the field.
    cv2.drawContours(field, [largest], -1, 255, cv2.FILLED)
    return field, True


def detect_candidates(image, min_area_px2=5000, threshold_offset=0):
    if image is None:
        raise ValueError('请先上传图片，或点击下方论文示例。')
    if min(image.size) < 32:
        raise ValueError('图片太小，宽和高都需要至少32像素。')
    if not isinstance(min_area_px2, (int, float)) or not math.isfinite(min_area_px2) or min_area_px2 < 1:
        raise ValueError('最小目标面积需要是大于或等于1的数字。')
    if not isinstance(threshold_offset, (int, float)) or not math.isfinite(threshold_offset) or not -50 <= threshold_offset <= 50:
        raise ValueError('识别范围微调需要在-50到50之间。')
    rgba = ImageOps.exif_transpose(image).convert('RGBA')
    original_size = rgba.size
    rgba.thumbnail((MAX_PREVIEW_SIDE, MAX_PREVIEW_SIDE), Image.Resampling.LANCZOS)
    preview = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
    rgb = np.array(preview)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    field, field_found = find_field_of_view(gray)
    # Remove the transition rim before RETR_EXTERNAL; otherwise a dark rim can
    # enclose and hide every interior object. A second margin detects clipped objects.
    rim_size = 11 if field_found else 3
    analysis_field = cv2.erode(field, np.ones((rim_size, rim_size), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    safe_field = cv2.erode(analysis_field, np.ones((3, 3), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    pixels = gray[safe_field > 0]
    if pixels.size < 32 or float(pixels.std()) < 2:
        raise ValueError('有效视野中的明暗差异太小，暂时无法识别轮廓。')
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    threshold, _ = cv2.threshold(blurred[safe_field > 0].reshape(-1, 1), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    threshold = float(np.clip(threshold + threshold_offset, 1, 254))
    mask = np.uint8((blurred <= threshold) & (analysis_field > 0)) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask[analysis_field == 0] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    scale_area = original_size[0] * original_size[1] / (gray.shape[0] * gray.shape[1])
    field_area = int(np.count_nonzero(field))
    accepted, border_count, small_count = [], 0, 0
    for contour in contours:
        if cv2.contourArea(contour) * scale_area < min_area_px2:
            small_count += 1
            continue
        xy = contour[:, 0, :]
        if np.any(safe_field[xy[:, 1], xy[:, 0]] == 0):
            border_count += 1
            continue
        if cv2.contourArea(contour) > 0.95 * field_area:
            continue
        try:
            metrics = measure_contour(contour, original_size, preview.size)
        except ValueError:
            continue
        accepted.append({'contour': contour, 'metrics': metrics})
    if len(accepted) > MAX_CANDIDATES:
        raise ValueError('候选目标超过500个。请提高最小目标面积或裁剪图片后重新分析。')
    accepted.sort(key=lambda o: (cv2.boundingRect(o['contour'])[1], cv2.boundingRect(o['contour'])[0]))
    for number, item in enumerate(accepted, 1):
        item['id'] = number
    return {'rgb': rgb, 'original_size': original_size, 'objects': accepted,
            'field_found': field_found, 'threshold': threshold,
            'border_count': border_count, 'small_count': small_count,
            'min_area_px2': min_area_px2}


def render_result(result, excluded_ids=()):
    """Re-render review choices without re-segmenting or changing object IDs."""
    excluded = {str(n) for n in (excluded_ids or [])}
    rgb = result['rgb'].copy()
    rows = []
    font_scale = max(0.5, min(rgb.shape[:2]) / 1250)
    for item in result['objects']:
        number, contour, metrics = item['id'], item['contour'], item['metrics']
        is_excluded = str(number) in excluded
        color = (150, 150, 150) if is_excluded else (0, 190, 80)
        cv2.drawContours(rgb, [contour], -1, color, 2)
        moments = cv2.moments(contour)
        x = int(moments['m10'] / moments['m00'])
        y = int(moments['m01'] / moments['m00'])
        label = str(number)
        # Dark backing stroke keeps IDs readable on both bright and dark objects.
        cv2.putText(rgb, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(rgb, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 2, cv2.LINE_AA)
        rows.append([number, '已排除' if is_excluded else '待核对',
                     round(metrics['area_px2'], 2), round(metrics['perimeter_px'], 2),
                     round(metrics['equivalent_diameter_px'], 2), round(metrics['circularity'], 3)])
    total = len(rows)
    excluded_count = sum(row[1] == '已排除' for row in rows)
    message = f'找到{total}个候选区域；保留{total - excluded_count}个待核对，已排除{excluded_count}个。'
    if result['field_found']:
        message += ' 已忽略显微视野外的黑色背景。'
    if result['border_count']:
        message += f" 有{result['border_count']}个触及视野边缘的区域未纳入。"
    if not total:
        message += ' 可降低最小目标面积或调整识别范围后重试。'
    else:
        message += ' 请检查绿色轮廓；碎屑、气泡和粘连区域可能被当作候选。'
    return Image.fromarray(rgb), message, rows
