"""Presentation only: OrgaCal's supplied logo and research-workbench identity."""
import base64
from html import escape
from pathlib import Path

import gradio as gr
from gradio.themes.utils.fonts import Font

ROOT = Path(__file__).resolve().parent
CSS = (ROOT / 'assets' / 'workbench.css').read_text(encoding='utf-8')


def make_theme():
    teal = gr.themes.colors.Color(
        name='orgacal', c50='#F2F9F6', c100='#E5F2ED', c200='#C3E1D7',
        c300='#98CDBE', c400='#65AE9E', c500='#2E8B7F', c600='#246E65',
        c700='#205B54', c800='#194A43', c900='#123B36', c950='#0D2A26',
    )
    return gr.themes.Base(
        primary_hue=teal, secondary_hue=teal, neutral_hue='gray',
        font=[Font(name) for name in ['Aptos', 'Microsoft YaHei', 'PingFang SC', 'sans-serif']],
        font_mono=[Font(name) for name in ['Cascadia Code', 'Consolas', 'monospace']],
        radius_size='md', text_size='md',
    ).set(
        body_background_fill='#F3F7F4', body_background_fill_dark='#171B1A',
        body_text_color='#123B36', body_text_color_dark='#EAEFEC',
        block_background_fill='#FFFFFF', block_background_fill_dark='#1F2524',
        block_border_color='#D2E1D9', block_border_color_dark='#38433F',
        block_label_text_color='#36584F', block_label_text_color_dark='#C4D0CA',
        block_title_text_color='#123B36', block_title_text_color_dark='#EAEFEC',
        input_background_fill='#F9FBF9', input_background_fill_dark='#161B1A',
        input_border_color='#829D92', input_border_color_dark='#7C8E87',
        input_border_color_focus='#246E65', input_border_color_focus_dark='#7FC4B2',
        button_primary_background_fill='#246E65', button_primary_background_fill_dark='#8CCDBB',
        button_primary_background_fill_hover='#205B54', button_primary_background_fill_hover_dark='#A9DCCD',
        button_primary_text_color='#FFFFFF', button_primary_text_color_dark='#14201D',
        button_primary_border_color='#246E65', button_primary_border_color_dark='#8CCDBB',
        button_secondary_background_fill='#FFFFFF', button_secondary_background_fill_dark='#2A3532',
        button_secondary_background_fill_hover='#E5F2ED', button_secondary_background_fill_hover_dark='#34423E',
        button_secondary_text_color='#123B36', button_secondary_text_color_dark='#EAEFEC',
        button_secondary_border_color='#829D92', button_secondary_border_color_dark='#7C8E87',
        border_color_primary='#D2E1D9', border_color_primary_dark='#38433F',
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


_LOGO_DATA = base64.b64encode((ROOT / 'assets' / 'logo.png').read_bytes()).decode('ascii')
HEADER = f'''<header class="oc-topbar">
  <div class="oc-brand"><img class="oc-brand-logo" src="data:image/png;base64,{_LOGO_DATA}" alt="OrgaCal 境算师" width="477" height="169">
    <div class="oc-brand-copy"><h1>类器官微环境计算与形态评价软件</h1><p>面向轨道摇床培养：剪切估算、条件筛选、形态量化与文献证据整理</p></div></div>
  <div class="oc-header-meta"><span class="oc-header-tag">科研工作台</span><span class="oc-header-motto">算剪切，查条件交集，量形状</span></div>
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


HEAD = '<meta name="theme-color" content="#123B36"><meta name="color-scheme" content="light dark">'
