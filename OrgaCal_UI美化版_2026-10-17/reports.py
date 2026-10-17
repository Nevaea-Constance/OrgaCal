"""Portable CSV/JSON/Markdown/PDF report bundle, using only current session results."""
import csv
from datetime import datetime, timezone
from html import escape
import io
import json
import math
from pathlib import Path
import tempfile
import zipfile

import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as PDFImage, KeepTogether


def clean_json(value):
    if isinstance(value, dict):
        return {str(k):clean_json(v) for k,v in value.items() if k not in ('rgb','contour','results','fit')}
    if isinstance(value,(list,tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value,np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value,np.generic):
        return clean_json(value.item())
    if isinstance(value,float) and not math.isfinite(value):
        return None
    return value


def csv_bytes(records):
    buffer = io.StringIO(newline='')
    headers = list(dict.fromkeys(key for row in records for key in row))
    if not headers:
        headers = ['status']
    writer = csv.DictWriter(buffer,fieldnames=headers,extrasaction='ignore')
    writer.writeheader()
    for row in records:
        safe = {}
        for key,value in row.items():
            if isinstance(value,(dict,list,tuple)):
                value = json.dumps(clean_json(value),ensure_ascii=False)
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return b'\xef\xbb\xbf'+buffer.getvalue().encode('utf-8')


def build_bundle(physics=None, interval=None, conversion=None, batch=None, stats=None, literature=None, figures=None):
    folder = Path(tempfile.mkdtemp(prefix='orgacal-report-'))
    timestamp = datetime.now(timezone.utc).isoformat()
    data = {'created_at_utc':timestamp, 'product':'OrgaCal · 摇床境算师', 'version':'0.2.0',
            'physics':physics, 'conditional_interval':interval,'conversion':conversion,
            'batch':batch,'statistics':stats,'literature':literature,
            'limitations':['解析模型和速度系数未做本设备实验校准；条件可行区间不能视为实验安全保证。',
                           '分割候选需人工复核；像素与微米不混合；逐目标统计不等于独立生物学重复。',
                           '文献规则抽取保留原文证据，未经人工确认的字段不能作为已核实参数。']}
    cleaned = clean_json(data)
    # Retain PCA fit parameters, scores and feature order in the reproducibility record.
    if stats:
        cleaned['statistics']['pca'] = []
        for item in stats.get('pca',[]):
            cleaned['statistics']['pca'].append({**clean_json(item),'fit':clean_json(item['fit'])})
    (folder/'results.json').write_text(json.dumps(cleaned,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    measurements = batch.get('records',[]) if batch else []
    (folder/'measurements.csv').write_bytes(csv_bytes(measurements))
    (folder/'batch_summary.csv').write_bytes(csv_bytes(stats.get('summary',[]) if stats else []))
    (folder/'literature.csv').write_bytes(csv_bytes(literature.get('records',[]) if literature else []))
    lines = ['# OrgaCal · 摇床境算师',f'生成时间（UTC）：{timestamp}',
             '本报告仅包含当前会话已运行的模块；未运行模块明确留空。',
             '## 剪切量级',json.dumps(clean_json(physics),ensure_ascii=False,indent=2) if physics else '尚未运行。',
             '## 双边界区间',json.dumps(clean_json(interval),ensure_ascii=False,indent=2) if interval else '尚未运行。',
             '## 转速换算',json.dumps(clean_json(conversion),ensure_ascii=False,indent=2) if conversion else '尚未运行。',
             '## 形态一致性',('数据来源：作者EV1参数表，不是本软件从图片测得的结果。' if (batch or {}).get('origin')=='paper_ev1' else '数据来源：用户图片的候选轮廓测量，核对状态见逐目标记录。'),
             f'目标记录：{len(measurements)}；排除：{sum(bool(r.get("excluded")) for r in measurements)}。',
             '\n'.join(stats.get('notes',[])) if stats else '尚未运行。',
             '## 文献',f'记录：{len(literature.get("records",[])) if literature else 0}；核对状态见literature.csv及results.json。',
             '## 局限','\n'.join(data['limitations']),
             '## 重现','原始像素指标、比例尺、批次/成像信息、模型输入和PCA参数见results.json；每个图像文件的SHA256随测量记录保存。']
    (folder/'report.md').write_text('\n\n'.join(lines),encoding='utf-8')
    _write_pdf(folder/'report.pdf',data,measurements,stats,figures or [])
    archive = folder/'Orgacal_report.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.iterdir():
            if path != archive:
                z.write(path,path.name)
    return str(archive),str(folder/'report.pdf'),str(folder/'measurements.csv'),str(folder/'report.md')


def _write_pdf(path,data,measurements,stats,figures):
    if 'STSong-Light' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    styles = getSampleStyleSheet()
    for name in ('Normal','BodyText','Heading1','Heading2','Title'):
        styles[name].fontName = 'STSong-Light'
        styles[name].wordWrap = 'CJK'
        styles[name].leading = max(styles[name].fontSize*1.5,15)
    styles.add(ParagraphStyle(name='SmallCN',fontName='STSong-Light',fontSize=8,leading=12,wordWrap='CJK',alignment=TA_LEFT))
    def para(text,style='BodyText'):
        text=str(text).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-')
        return Paragraph(escape(text).replace('\n','<br/>'),styles[style])
    story = [para('OrgaCal · 摇床境算师','Title'),para('参数计算 + 形态一致性报告','Heading1'),
             para(f"生成时间（UTC）：{data['created_at_utc']}"),Spacer(1,5*mm)]
    for title,key in [('剪切应力量级','physics'),('双边界条件可行区间','conditional_interval'),('转速换算','conversion')]:
        story.append(para(title,'Heading2'))
        result = data.get(key)
        if not result:
            story.append(para('尚未运行。'))
            continue
        if key=='physics':
            story.append(para(f"剪切应力尺度：{result.get('shear_low_mpa',0):.4g} - {result.get('shear_high_mpa',0):.4g} mPa；范围仅来自输入黏度。"))
            story.append(para(f"轨道直径{result.get('orbit_diameter_mm')} mm；转速{result.get('rpm')} rpm；容器内径{result.get('vessel_diameter_mm')} mm；液量{result.get('volume_ml')} mL。"))
            story.append(para(f"平均液深{result.get('depth_mm',0):.5g} mm；轨道速度尺度{result.get('orbital_speed_m_s',0):.5g} m/s；动力黏度{result.get('viscosity_low_mpas')} - {result.get('viscosity_high_mpas')} mPa s；记录温度{result.get('temperature_c')} C。"))
            story.append(para('假设圆形平底直壁容器、牛顿流体；以轨道速度/平均液深近似速度梯度。未解析液面波动、局部边界层或组织运动；未做流场校准。'))
            story.append(para('剪切定义依据：https://pmc.ncbi.nlm.nih.gov/articles/PMC7345652/；完整假设随results.json保存。','SmallCN'))
        elif key=='conditional_interval':
            story.append(para(result.get('message','尚无区间。')))
            if result.get('status')=='feasible':
                story.append(para(f"条件交集：{result['lower']:.3g} - {result['upper']:.3g} rpm。"))
            for name,label in [('shear_upper','剪切上界'),('suspension_lower','悬浮下界'),('oxygen_lower','氧供给下界')]:
                value=result.get(name)
                story.append(para(label+'：'+('未能确定' if value is None else f'{value:.4g} rpm')))
            story.append(para('参数依据：'+str(result.get('inputs',{}).get('basis','未提供'))))
            inputs=result.get('inputs',{})
            if inputs:
                story.append(para(f"几何：轨道直径{inputs.get('orbit_mm')} mm，容器内径{inputs.get('vessel_mm')} mm，单孔液量{inputs.get('volume_ml')} mL；动力黏度{inputs.get('mu_low')} - {inputs.get('mu_high')} mPa s。"))
                story.append(para(f"组织直径{inputs.get('diameter_um')} um；密度差{inputs.get('delta_rho')} kg/m3；液体密度{inputs.get('rho')} kg/m3；体积耗氧率Q={inputs.get('oxygen_q')} mol/m3/s。"))
                story.append(para(f"体相氧{inputs.get('bulk_oxygen')}、中心阈值{inputs.get('critical_oxygen')} mol/m3；液相/组织扩散系数分别为{inputs.get('diffusivity')}、{inputs.get('tissue_diffusivity')} m2/s；悬浮/传质速度比例分别为{inputs.get('beta_suspend')}、{inputs.get('beta_transfer')}；设备上限{inputs.get('max_rpm')} rpm。"))
            story.append(para('球体阻力、外部传质和内部恒定耗氧扩散组成的条件模型；速度比例系数与高Schmidt数传质尚未在本体系校准。完整输入和敏感性可复算记录见results.json。'))
            if result.get('sensitivity'):
                grid=[['密度差 kg/m3','Q mol/m3/s','下界 rpm','上界 rpm','状态']]
                for r in result['sensitivity']:
                    grid.append([f"{r['density_difference_kg_m3']:.4g}",f"{r['uptake_mol_m3_s']:.4g}",
                                 'n.a.' if r['lower_rpm'] is None else f"{r['lower_rpm']:.4g}",
                                 'n.a.' if r['upper_rpm'] is None else f"{r['upper_rpm']:.4g}",{'feasible':'有交集','empty':'无交集','missing':'缺参数'}.get(r['status'],r['status'])])
                grid_heading=para('密度差(kg/m3)与耗氧率(mol/m3/s)的敏感性','Heading2')
                grid=Table([[para(c,'SmallCN') for c in row] for row in grid],colWidths=[38*mm,25*mm,30*mm,30*mm,35*mm],repeatRows=1)
                grid.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8F2EE')),('GRID',(0,0),(-1,-1),.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
                story.append(KeepTogether([grid_heading,grid]))
            for label,url in result.get('sources',{}).items():
                story.append(para(f'{label}: {url}','SmallCN'))
        else:
            story.append(para(f"准则：{result.get('criterion')}；文献{result.get('source_rpm')} rpm、{result.get('source_orbit_mm')} mm轨道直径；目标{result.get('target_orbit_mm')} mm轨道直径，换算{result.get('target_rpm',0):.4g} rpm。"))
            story.append(para(result.get('note','')))
    story.extend([para('形态与批次一致性','Heading2'),
                  para(f'目标记录{len(measurements)}；保留{sum(not r.get("excluded",False) for r in measurements)}；排除{sum(bool(r.get("excluded")) for r in measurements)}。')])
    if (data.get('batch') or {}).get('origin')=='paper_ev1':
        story.append(para('数据来源：作者EV1参数表，用于统计复算演示，不是本软件从图片测得的结果。'))
    elif measurements:
        story.append(para('数据来源：用户图片的候选轮廓测量；未经过逐目标人工确认的记录仍需核对。'))
    if data.get('batch'):
        story.append(para('图像失败/未检出记录：'+json.dumps(data['batch'].get('failures',[]),ensure_ascii=False)))
    for note in (stats or {}).get('notes',[]):
        story.append(para(note))
    summary = (stats or {}).get('summary',[])
    if summary:
        headers = ['条件/天数','批次','特征/单位','n','中位数','相对MAD%']
        rows = [[para(h,'SmallCN') for h in headers]]
        for r in summary:
            rows.append([para(f"{r['condition']}/{r['day']}",'SmallCN'),para(r['batch'],'SmallCN'),
                         para(f"{r['feature']} ({r.get('unit',r['unit_basis'])})",'SmallCN'),para(r['n'],'SmallCN'),
                         para('n.a.' if r['median'] is None else f"{r['median']:.5g}",'SmallCN'),
                         para('n.a.' if r['relative_mad_pct'] is None else f"{r['relative_mad_pct']:.4g}",'SmallCN')])
        table = Table(rows,colWidths=[29*mm,18*mm,58*mm,10*mm,25*mm,25*mm],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8F2EE')),
                                   ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#C4CDC8')),
                                   ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(table)
    for index,fig in enumerate(figures):
        image_path = path.parent/f'figure_{index+1}.png'
        fig.savefig(image_path,dpi=160,bbox_inches='tight')
        item=(stats or {}).get('pca',[])[index]
        caption=f"PCA：{item['condition']} / 第{item['day']}天 / 长度基准{item['unit_basis']}。"
        legend='图例：'+', '.join(f'B{i+1}={b}' for i,b in enumerate(sorted(set(item['batches']))))
        story.append(KeepTogether([Spacer(1,4*mm),para(caption,'Heading2'),para(legend,'SmallCN'),PDFImage(str(image_path),width=165*mm,height=110*mm,kind='proportional')]))
    story.append(para('文献与依据','Heading2'))
    for paper in (data.get('literature') or {}).get('records',[]):
        story.append(para(f"{paper.get('title','')} ({paper.get('year','')}) | {paper.get('doi') or paper.get('pmcid','')} | {paper.get('extraction_status','')}",'SmallCN'))
        story.append(para(paper.get('url',''),'SmallCN'))
    story.append(para('适用范围与局限','Heading2'))
    story.extend(para(note) for note in data['limitations'])
    def footer(canvas,doc):
        canvas.setFont('STSong-Light',9)
        canvas.drawString(18*mm,11*mm,'OrgaCal | '+str(doc.page))
    SimpleDocTemplate(str(path),pagesize=(210*mm,297*mm),rightMargin=18*mm,leftMargin=18*mm,
                      topMargin=17*mm,bottomMargin=18*mm).build(story,onFirstPage=footer,onLaterPages=footer)
