"""Presentation only: the research-workbench identity from the latest UI brief."""
from html import escape
from pathlib import Path

import gradio as gr
from gradio.themes.utils.fonts import Font

ROOT = Path(__file__).resolve().parent
CSS = (ROOT / 'assets' / 'workbench.css').read_text(encoding='utf-8')


def make_theme():
    teal = gr.themes.colors.Color(
        name='orgacal', c50='#F0F8F8', c100='#E6F2F3', c200='#BFDEE1',
        c300='#88C3CA', c400='#4BA3AF', c500='#208996', c600='#0E7C86',
        c700='#096570', c800='#10515B', c900='#163F49', c950='#102D35',
    )
    return gr.themes.Base(
        primary_hue=teal, secondary_hue='slate', neutral_hue='slate',
        font=[Font(name) for name in ['Aptos', 'Microsoft YaHei', 'PingFang SC', 'sans-serif']],
        font_mono=[Font(name) for name in ['Cascadia Code', 'Consolas', 'monospace']],
        radius_size='md', text_size='md',
    ).set(
        body_background_fill='#F7F9FA', body_background_fill_dark='#0C1C2A',
        body_text_color='#1E2A33', body_text_color_dark='#E7F0F4',
        block_background_fill='#FFFFFF', block_background_fill_dark='#122638',
        block_border_color='#D8E1E6', block_border_color_dark='#3C5366',
        block_label_text_color='#334957', block_label_text_color_dark='#C6D5DF',
        block_title_text_color='#16324F', block_title_text_color_dark='#E7F0F4',
        input_background_fill='#F9FBFC', input_background_fill_dark='#102131',
        input_border_color='#A7B8C4', input_border_color_dark='#647F93',
        input_border_color_focus='#0E7C86', input_border_color_focus_dark='#75CDD4',
        button_primary_background_fill='#0E7C86', button_primary_background_fill_dark='#91D7DE',
        button_primary_background_fill_hover='#096570', button_primary_background_fill_hover_dark='#AFE4E8',
        button_primary_text_color='#FFFFFF', button_primary_text_color_dark='#102D35',
        button_primary_border_color='#0E7C86', button_primary_border_color_dark='#91D7DE',
        button_secondary_background_fill='#FFFFFF', button_secondary_background_fill_dark='#193245',
        button_secondary_background_fill_hover='#E6F2F3', button_secondary_background_fill_hover_dark='#25465B',
        button_secondary_text_color='#16324F', button_secondary_text_color_dark='#E7F0F4',
        button_secondary_border_color='#A7B8C4', button_secondary_border_color_dark='#647F93',
        border_color_primary='#D8E1E6', border_color_primary_dark='#3C5366',
        shadow_drop='none', shadow_drop_lg='none',
    )


def icon(name, size=24):
    paths = {
        'orbit': '<ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-30 12 12)"/><circle cx="12" cy="12" r="3"/><path d="M6 4.5 5 8l3.5.5"/>',
        'swap': '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
        'shape': '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m3 17 5-5 4 4 4-6 5 7"/><circle cx="9" cy="8" r="1"/>',
        'paper': '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/>',
        'target': '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 9v6m-3-3h6"/>',
        'report': '<path d="M6 3h9l4 4v7M14 3v5h5M9 12h4M9 16h3M16 15v7m-3-3 3 3 3-3M6 21H4V3h2"/>',
        'check': '<path d="m5 12 4 4L19 6"/>',
    }
    return f'<svg aria-hidden="true" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


HEADER = f'''<header class="oc-topbar">
  <div class="oc-brand"><span class="oc-brand-mark">{icon('orbit', 32)}</span>
    <div><h1>OrgaCal <span>境算师</span></h1><p>类器官微环境设计与预测软件</p></div></div>
  <div class="oc-header-meta"><span class="oc-local-dot"></span><span>科研工作台</span><span class="oc-header-rule"></span><span>算剪切 · 找安全区 · 量形状</span></div>
</header>'''


def page_heading(title, description):
    return f'<div class="oc-page-heading"><h2>{escape(title)}</h2><p>{escape(description)}</p></div>'


def panel_heading(title, description=''):
    detail = f'<p>{escape(description)}</p>' if description else ''
    return f'<div class="oc-panel-heading"><h3>{escape(title)}</h3>{detail}</div>'


def notice(text, kind='info'):
    return f'<div class="oc-notice oc-notice-{kind}">{escape(text)}</div>'


def shear_visual(result):
    if not result:
        return '''<div class="oc-empty-result">
<svg aria-hidden="true" viewBox="0 0 260 130" fill="none"><ellipse cx="130" cy="83" rx="86" ry="22" stroke="currentColor" stroke-dasharray="4 5"/><path d="M74 45v39c0 14 112 14 112 0V45" stroke="currentColor" stroke-width="2"/><ellipse cx="130" cy="45" rx="56" ry="16" stroke="currentColor" stroke-width="2"/><path d="M79 67c24 13 78 13 102 0" stroke="currentColor" stroke-width="2"/><circle cx="111" cy="66" r="5" stroke="currentColor"/><circle cx="144" cy="73" r="7" stroke="currentColor"/><path d="m208 79 7 8-11 2" stroke="currentColor" stroke-width="2"/></svg>
<strong>等待计算剪切预算</strong><p>填写左侧参数后，查看剪切量级、平均液深和计算依据。</p></div>'''
    low, high = result['shear_low_mpa'], result['shear_high_mpa']
    ceiling = max(1, high * 1.25)
    left, width = low / ceiling * 100, max(.6, (high - low) / ceiling * 100)
    metrics = [
        ('平均液深', f"{result['depth_mm']:.3g}", 'mm'),
        ('轨道线速度', f"{result['orbital_speed_m_s']:.3g}", 'm/s'),
        ('速度梯度尺度', f"{result['gradient_scale_s_inv']:.3g}", 's⁻¹'),
    ]
    cells = ''.join(f'<div><span>{label}</span><strong>{value}<small>{unit}</small></strong></div>' for label, value, unit in metrics)
    return f'''<div class="oc-shear-visual"><div class="oc-meter-heading"><span>输入黏度对应的计算范围</span><span>mPa</span></div>
<div class="oc-range-track"><span style="left:{left:.4f}%;width:{width:.4f}%"></span></div>
<div class="oc-meter-axis"><span>0</span><span>{ceiling:.3g}</span></div>
<div class="oc-metric-strip">{cells}</div>
<p class="oc-caption">范围来自输入黏度，不表示安全阈值或模型置信区间。</p></div>'''


def batch_overview(state):
    if not state:
        return '<div class="oc-summary-strip"><span>尚未分析图片</span><span>上传原图或载入公开示例，开始核对。</span></div>'
    if state.get('origin') == 'paper_ev1':
        return '<div class="oc-summary-strip"><strong>作者 EV1 数据</strong><span>统计演示；不是本程序从图片测得的结果。</span></div>'
    records = state.get('records', [])
    excluded = sum(bool(r.get('excluded')) for r in records)
    return f'<div class="oc-summary-strip"><strong>{state.get("image_count", 0)} 张图片</strong><span>{len(records)} 个候选</span><span>{excluded} 个已排除</span><span>{len(state.get("failures", []))} 张失败或未检出</span></div>'


def interval_context(geometry, orbit, rpm, vessel, volume, mu_low, mu_high, temp):
    values = [('轨道直径', orbit, 'mm'), ('容器内径', vessel, 'mm'), ('单孔液量', volume, 'mL'), ('黏度', f'{mu_low}–{mu_high}', 'mPa·s')]
    items = ''.join(f'<span>{escape(label)} <strong>{escape(str(value))}</strong> {unit}</span>' for label, value, unit in values)
    return f'<div class="oc-shared-context"><strong>沿用「剪切预算」中的设备条件</strong><div>{items}</div></div>'


HEAD = '<meta name="theme-color" content="#16324F"><meta name="color-scheme" content="light dark">'
