"""OrgaCal cultivation scenarios and morphology consistency workbench."""
import os
from functools import partial
from pathlib import Path
from deployment_resources import ensure_resources

# Some browser uploaders omit nested folders. Restore the checked public assets
# before importing modules that read CSS or construct example File components.
_restored_resources = ensure_resources()
if _restored_resources:
    print(f'[OrgaCal] Restored {len(_restored_resources)} bundled public resource files.', flush=True)

import gradio as gr
import pandas as pd
from physics import SUPPORTED_GEOMETRY
from single_ui import (build_single, analyze_for_ui, reset_result, reset_image,
                       apply_calibration, review_result, clear_calibration)
from ui_logic import (calculate_shear, calculate_interval, convert_for_ui, batch_for_ui,
                      batch_example_for_ui, review_for_ui, stats_for_ui, paper_for_ui,
                      literature_for_ui, cached_for_ui, export_for_ui)
from visual_design import (CSS, HEAD, HEADER, make_theme, page_heading, panel_heading,
                           notice, shear_visual, batch_overview, interval_context)
from presentation import run_info, overview, workflow, validation_panel
from screening import scan_for_ui
from literature_inputs import doi_for_ui, pdf_for_ui
from reliability import reliability_for_ui, TEMPLATE_CSV

ROOT = Path(__file__).resolve().parent
NAV = [('shear','剪切预算'),('conversion','转速换算'),('morphology','形态量化'),
       ('literature','文献条件'),('screening','条件筛选'),('report','综合报告')]

def navigate(selected):
    return [gr.update(selected=selected), *[gr.update(variant='primary' if key == selected else 'secondary') for key, _ in NAV]]

with gr.Blocks(title='OrgaCal · 境算师') as demo:
    gr.HTML(HEADER)
    physics_state=gr.State(None)
    interval_state=gr.State(None)
    conversion_state=gr.State(None)
    batch_state=gr.State(None,time_to_live=3600)
    stats_state=gr.State(None,time_to_live=3600)
    literature_state=gr.State(None)
    screening_state=gr.State(None)
    reliability_state=gr.State(None)
    with gr.Row(elem_classes='oc-shell'):
        with gr.Column(scale=1,min_width=0,elem_id='oc-sidebar'):
            gr.HTML('<div class="oc-nav-caption">微环境分析工作区</div>',elem_classes='oc-nav-context')
            nav_buttons=[gr.Button(label,variant='primary' if key=='shear' else 'secondary',elem_id=f'nav-{key}',elem_classes='oc-nav-button') for key,label in NAV]
            gr.HTML('<div class="oc-sidebar-note"><strong>当前支持轨道摇床</strong>剪切为物理情景估算<br>候选轮廓需人工核对<br>图像在运行端处理</div>',elem_classes='oc-nav-context')
        with gr.Column(scale=7,min_width=0,elem_id='oc-workspace'):
            with gr.Tabs(selected='shear',elem_id='workspace-tabs') as workspace_tabs:
                with gr.Tab('剪切预算',id='shear'):
                    gr.HTML(page_heading('把设备参数，变成可核对的剪切预算','输入摇摆直径、转速、容器与液量，查看剪切量级及其计算依据。初始参数仅供演示。'))
                    with gr.Row(elem_classes='oc-two-column'):
                        with gr.Column(scale=11,min_width=280,elem_classes='oc-panel'):
                            gr.HTML(panel_heading('设备与培养条件','晃幅填写轨道直径；容器尺寸和液量均以单孔 / 单皿计。'))
                            geometry=gr.Dropdown([SUPPORTED_GEOMETRY,'其他几何（暂不支持）'],value=SUPPORTED_GEOMETRY,label='容器形状')
                            with gr.Row():
                                orbit=gr.Dropdown(['10','19','25','50'],value='25',allow_custom_value=True,label='轨道直径（mm）',info='即摇摆直径，来自设备手册或实测，不是半径。',min_width=140)
                                rpm=gr.Number(value=80,label='转速（rpm）',min_width=120)
                            with gr.Row():
                                vessel=gr.Number(value=35,label='容器内径（mm）',min_width=130)
                                volume=gr.Number(value=3,label='单孔液量（mL）',min_width=130)
                            with gr.Accordion('培养液黏度与温度',open=False,elem_classes='oc-technical'):
                                with gr.Row():
                                    mu_low=gr.Number(value=.7,label='黏度下限（mPa·s）',min_width=130)
                                    mu_high=gr.Number(value=1,label='黏度上限（mPa·s）',min_width=130)
                                temperature=gr.Number(value=37,label='黏度对应温度（°C，仅记录）')
                                gr.Markdown('黏度应对应培养基与温度；只有一个值时上下限相同。温度改变不会自动修正黏度。',elem_classes='oc-help')
                            gr.Markdown('**参数来源核对**　设备参数查手册或实测；黏度查匹配温度的文献或实测。',elem_classes='oc-help')
                            common=[geometry,orbit,rpm,vessel,volume,mu_low,mu_high,temperature]
                            shear_button=gr.Button('计算剪切预算',variant='primary',elem_classes='oc-primary-action')
                        with gr.Column(scale=12,min_width=280,elem_classes=['oc-panel','oc-result-panel']):
                            gr.HTML(panel_heading('剪切应力量级','液深梯度尺度模型，单位 mPa'))
                            shear_value=gr.Textbox(label='本次计算范围',interactive=False,elem_classes='oc-result-value')
                            shear_visual_box=gr.HTML(shear_visual(None))
                            shear_note=gr.Textbox(label='结果含义与适用范围',interactive=False,lines=3,elem_classes='oc-note-text',value='模型尚未针对实际装置校准；计算结果不代表组织表面剪切或安全保证。')
                            shear_run=gr.HTML(run_info(None,'shear'))
                            screen_shortcut=gr.Button('继续筛选条件区间')
                    with gr.Accordion('查看本次参数、公式与文献依据',open=False,elem_classes='oc-technical'):
                        shear_table=gr.Dataframe(label='参数与中间量',headers=['参数','数值','单位'],interactive=False,elem_classes='oc-table')
                        shear_assumptions=gr.Markdown('完成计算后，这里会保留全部中间量、公式和适用条件。')
                    gr.Markdown('**文献背景**　[Driessen 等（2020）](https://pmc.ncbi.nlm.nih.gov/articles/PMC7345652/)：牛顿流体剪切应力与速度梯度的关系。[脑类器官轨道摇床 CFD（2019）](https://pmc.ncbi.nlm.nih.gov/articles/PMC6404276/)：六孔板内的流场与剪切。[轨道摇床孔板壁面剪切 CFD（Annals of Biomedical Engineering）](https://link.springer.com/article/10.1007/s10439-011-0444-9)：流动随空间和时间变化。这些文献给出剪切的定义和分布特征，没有验证本页的 U/h 尺度。',elem_classes='oc-help')
                    shear_outputs=[shear_value,shear_note,shear_table,shear_assumptions,physics_state]
                    shear_event=shear_button.click(calculate_shear,common,shear_outputs)
                    for component in common:
                        component.change(lambda:('','参数已改变，请重新计算。',pd.DataFrame(),'',None),None,shear_outputs,cancels=[shear_event],queue=False)
                    physics_state.change(shear_visual,physics_state,shear_visual_box,queue=False,api_name=False)
                    physics_state.change(partial(run_info,kind='shear'),physics_state,shear_run,queue=False,api_name=False)

                with gr.Tab('转速换算',id='conversion'):
                    gr.HTML(page_heading('把文献条件，换到自己的摇床','先选定要保持的物理量，再比较两台设备。不同换算准则可能得到不同转速。'))
                    criterion=gr.Radio(['等模型剪切（液深尺度）','等轨道线速度','等轨道加速度'],value='等模型剪切（液深尺度）',label='换算准则')
                    with gr.Row(elem_classes='oc-two-column'):
                        with gr.Column(min_width=260,elem_classes='oc-panel'):
                            gr.HTML(panel_heading('文献中的设备','以论文原文、补充材料或设备手册为准。'))
                            with gr.Row():
                                source_rpm=gr.Number(80,label='文献转速（rpm）',min_width=120)
                                source_orbit=gr.Number(25,label='轨道直径（mm）',min_width=120)
                            source_vessel=gr.Number(35,label='容器内径（mm）')
                            source_volume=gr.Number(3,label='单孔液量（mL）')
                            source_mu=gr.Number(.7,label='动力黏度（mPa·s）')
                        with gr.Column(min_width=260,elem_classes='oc-panel'):
                            gr.HTML(panel_heading('自己的设备','填写目标设备的实际培养条件。'))
                            target_orbit=gr.Number(19,label='目标轨道直径（mm）')
                            target_vessel=gr.Number(35,label='目标容器内径（mm）')
                            target_volume=gr.Number(3,label='目标单孔液量（mL）')
                            target_mu=gr.Number(.7,label='目标动力黏度（mPa·s）')
                    conversion_inputs=[criterion,source_rpm,source_orbit,target_orbit,source_vessel,source_volume,source_mu,target_vessel,target_volume,target_mu]
                    conversion_button=gr.Button('计算目标转速',variant='primary',elem_classes='oc-primary-action')
                    with gr.Column(elem_classes=['oc-panel','oc-result-panel']):
                        conversion_value=gr.Textbox(label='目标转速',interactive=False,elem_classes='oc-result-value')
                        conversion_details=gr.Textbox(label='换算依据与条件记录',value='填写双方条件，点击“计算目标转速”。',interactive=False,lines=6)
                        conversion_run=gr.HTML(run_info(None,'conversion'))
                        conversion_state.change(partial(run_info,kind='conversion'),conversion_state,conversion_run,queue=False,api_name=False)
                    conversion_event=conversion_button.click(convert_for_ui,conversion_inputs,[conversion_value,conversion_details,conversion_state])
                    for component in conversion_inputs:
                        component.change(lambda:('','条件已改变，请重新换算。',None),None,[conversion_value,conversion_details,conversion_state],cancels=[conversion_event],queue=False)
                    with gr.Accordion('公式与换算边界',open=False,elem_classes='oc-technical'):
                        gr.Markdown('等线速度：n₂=n₁D₁/D₂；等加速度：n₂=n₁√(D₁/D₂)。等模型剪切按双方液深与黏度反解尺度模型，不证明真实流场或生物学效果等价。')

                with gr.Tab('形态量化',id='morphology'):
                    gr.HTML(page_heading('从显微照片，到可复核的形态报告','先核对候选轮廓和比例尺，再查看分层统计。原始测量、排除状态与失败记录都会保留。'))
                    with gr.Tabs(elem_id='morphology-tabs'):
                        with gr.Tab('单图核对与标定'):
                            single=build_single(demo)
                        with gr.Tab('批量与一致性报告'):
                            with gr.Column(elem_classes='oc-panel'):
                                gr.HTML(panel_heading('上传一批显微照片','最多 20 张，每张不超过 25 MB；比例尺未知时保留像素单位。'))
                                images=gr.File(label='选择或拖入图片',file_count='multiple',file_types=['image'],type='filepath')
                                with gr.Accordion('批次信息、识别设置与比例尺',open=False,elem_classes='oc-technical'):
                                    with gr.Row():
                                        metadata=gr.File(label='逐图元数据 CSV（可选）',file_types=['.csv'],type='filepath')
                                        gr.File(value=str(ROOT/'examples/batch_metadata.csv'),label='下载元数据示例模板',interactive=False)
                                    with gr.Row():
                                        default_batch=gr.Textbox('批次1',label='缺省批次',min_width=130)
                                        condition=gr.Textbox('未提供',label='培养条件',min_width=130)
                                    with gr.Row():
                                        day=gr.Textbox('',label='培养天数 / 时间点',min_width=130)
                                        imaging=gr.Textbox('未提供',label='成像批次',min_width=130)
                                    with gr.Row():
                                        min_area=gr.Number(5000,label='最小候选面积（原图 px²）',min_width=160)
                                        offset=gr.Slider(-50,50,value=0,step=1,label='阈值偏移',min_width=160)
                                    shared_scale=gr.Number(value=None,label='共用比例尺（µm/px，未知留空）')
                                    shared_confirm=gr.Checkbox(False,label='确认这批图片可共用同一比例尺；逐图 CSV 值优先')
                                batch_button=gr.Button('批量分析图片',variant='primary',elem_classes='oc-primary-action')
                                with gr.Row(elem_classes='oc-action-row'):
                                    batch_example=gr.Button('体验 4 张论文原图')
                                    paper_button=gr.Button('载入作者 EV1 统计示例')
                            batch_summary=gr.HTML(batch_overview(None))
                            batch_run=gr.HTML(run_info(None,'batch'))
                            batch_status=gr.Textbox(label='处理与失败记录',interactive=False,lines=3)
                            gallery=gr.Gallery(label='逐图编号与轮廓',columns=2,height=420,object_fit='contain')
                            with gr.Accordion('全部测量记录与逐目标排除',open=True,elem_classes='oc-technical'):
                                exclusions=gr.Dropdown(choices=[],multiselect=True,label='搜索并选择要排除的目标（文件名 / 编号）')
                                review_button=gr.Button('应用排除并更新表格')
                                batch_table=gr.Dataframe(label='全部目标、像素值、比例尺与元数据',interactive=False,elem_classes='oc-table')
                            with gr.Column(elem_classes='oc-panel'):
                                gr.HTML(panel_heading('比较批次一致性','样本 CV、相对 MAD 与分层 PCA；仅使用未排除的目标。'))
                                mad_factor=gr.Radio(['1.0','1.4826'],value='1.0',label='MAD 比例因子（论文复现需匹配口径）')
                                stats_button=gr.Button('生成分层一致性统计',variant='primary',elem_classes='oc-primary-action')
                                stats_run=gr.HTML(run_info(None,'statistics'))
                                stats_table=gr.Dataframe(label='各批次中位数、均值、CV 与相对 MAD',interactive=False,elem_classes='oc-table')
                                pca_gallery=gr.Gallery(label='分层 PCA 与 95% 数据分布椭圆',columns=2,object_fit='contain')
                                stats_notes=gr.Markdown()
                            batch_outputs=[batch_state,gallery,batch_table,exclusions,batch_status,stats_state,stats_table,pca_gallery,stats_notes]
                            settings=[min_area,offset,default_batch,condition,day,imaging,shared_scale,shared_confirm]
                            batch_event=batch_button.click(batch_for_ui,[images,metadata,*settings],batch_outputs)
                            example_event=batch_example.click(batch_example_for_ui,settings,batch_outputs)
                            paper_event=paper_button.click(paper_for_ui,None,batch_outputs)
                            review_event=review_button.click(review_for_ui,[batch_state,exclusions],[batch_state,gallery,batch_table,batch_status,stats_state,stats_table,pca_gallery,stats_notes])
                            stats_event=stats_button.click(stats_for_ui,[batch_state,mad_factor],[stats_state,stats_table,pca_gallery,stats_notes])
                            batch_events=[batch_event,example_event,paper_event,review_event,stats_event]
                            for component in [images,metadata,*settings]:
                                component.change(lambda:(None,[],pd.DataFrame(),gr.update(choices=[],value=[]),'输入已改变，请重新分析。',None,pd.DataFrame(),[],''),None,batch_outputs,cancels=batch_events,queue=False)
                            mad_factor.change(lambda:(None,pd.DataFrame(),[],'设置已改变，请重新生成统计。'),None,[stats_state,stats_table,pca_gallery,stats_notes],cancels=[stats_event],queue=False)
                            batch_state.change(batch_overview,batch_state,batch_summary,queue=False,api_name=False)
                            batch_state.change(partial(run_info,kind='batch'),batch_state,batch_run,queue=False,api_name=False)
                            stats_state.change(partial(run_info,kind='statistics'),stats_state,stats_run,queue=False,api_name=False)
                            gr.HTML(notice('不同时间、成像批次和像素 / 微米单位分层统计。PCA 椭圆表示数据分布，不直接判定培养优劣。作者 EV1 示例不用于验证本程序分割精度。'))
                        with gr.Tab('配对重复测量 ICC'):
                            gr.HTML(panel_heading('测量一致性 ICC(2,1)','需要同一目标被多名测量者或多轮重复测量；独立照片的批次 CV 不能代替 ICC。'))
                            with gr.Column(elem_classes='oc-panel'):
                                with gr.Row():
                                    icc_file=gr.File(label='配对重复测量 CSV（target_id, rater_id, value）',file_types=['.csv'],type='filepath')
                                    icc_template=gr.File(value=str(ROOT/'examples/icc_template.csv'),label='下载 CSV 模板（演示数值，无生物学含义）',interactive=False)
                                icc_button=gr.Button('计算 ICC',variant='primary',elem_classes='oc-primary-action')
                                icc_text=gr.Markdown('上传完整、平衡的配对重复测量表后计算。仅给出点估计，不含 95% 置信区间或合格评级。')
                                icc_table=gr.Dataframe(label='方差分解',interactive=False,elem_classes='oc-table')
                            icc_event=icc_button.click(reliability_for_ui,icc_file,[icc_text,icc_table,reliability_state])
                            icc_file.change(lambda:('文件已改变，请重新计算。',pd.DataFrame(),None),None,[icc_text,icc_table,reliability_state],cancels=[icc_event],queue=False)

                with gr.Tab('文献条件',id='literature'):
                    gr.HTML(page_heading('让每条培养条件，都能追到原文','检索开放文献，查看设备条件、证据片段与出处。自动提取的数值需要逐条人工核对。'))
                    with gr.Column(elem_classes='oc-panel'):
                        gr.HTML(panel_heading('检索培养条件','在线检索使用 Europe PMC；本地参考示例可离线载入。'))
                        query=gr.Textbox('brain organoid orbital shaker',label='检索式',placeholder='例如 brain organoid orbital shaker')
                        with gr.Row():
                            count=gr.Slider(1,50,value=20,step=1,label='本次最多读取条数',min_width=180)
                            fulltext=gr.Checkbox(True,label='可用时读取 PMC 开放全文（较慢）',min_width=200)
                        with gr.Row(elem_classes='oc-action-row'):
                            search_button=gr.Button('检索并提取证据',variant='primary',elem_classes='oc-primary-action')
                            cache_button=gr.Button('载入本地公开文献示例')
                    literature_status=gr.Textbox(label='检索状态',value='输入检索式，或先载入本地公开文献示例。',interactive=False)
                    with gr.Column(elem_classes='oc-panel'):
                        gr.HTML(panel_heading('按 DOI 或 PDF 录入','DOI 经 Europe PMC 精确匹配；PDF 仅在本部署实例内提取文字层，不做 OCR。'))
                        with gr.Row():
                            doi_input=gr.Textbox(label='DOI 或 doi.org 链接',placeholder='例如 10.1038/s41596-020-00471-4',min_width=260)
                            pdf_input=gr.File(label='上传可选择文字的 PDF（≤15 MB，≤40 页）',file_types=['.pdf'],type='filepath',min_width=260)
                        with gr.Row(elem_classes='oc-action-row'):
                            doi_button=gr.Button('按 DOI 录入',variant='primary')
                            pdf_button=gr.Button('提取 PDF 条件')
                    literature_frame=gr.Dataframe(label='论文、字段证据与出处',interactive=False,wrap=True,elem_classes='oc-table')
                    literature_run=gr.HTML(run_info(None,'literature'))
                    search_button.click(literature_for_ui,[query,count,fulltext],[literature_state,literature_frame,literature_status])
                    cache_button.click(cached_for_ui,None,[literature_state,literature_frame,literature_status])
                    doi_button.click(doi_for_ui,[doi_input,fulltext],[literature_state,literature_frame,literature_status])
                    pdf_button.click(pdf_for_ui,pdf_input,[literature_state,literature_frame,literature_status])
                    literature_state.change(partial(run_info,kind='literature'),literature_state,literature_run,queue=False,api_name=False)
                    gr.HTML(notice('“未报告”仅指获取的文本中未抽取到，不能说明全文或补充材料不存在。设备背景、转速用途及结局仍需核对；导出保留文本范围、检索时间与逐条状态。'))
                    with gr.Accordion('当前入口与后续功能',open=False,elem_classes='oc-technical'):
                        gr.Markdown('当前支持检索式、DOI 定向录入、本地 PDF 文字提取和公开文献缓存。PDF 无 OCR，扫描件与图表内容不会被读取；字段级人工修订尚未接入。所有自动抽取字段均待人工核对。')

                with gr.Tab('条件筛选',id='screening'):
                    gr.HTML(page_heading('在剪切与传质约束之间，寻找条件交集','沿用设备条件，补充有依据的阈值、耗氧率和速度系数。缺少必要参数时不生成区间。'))
                    context_box=gr.HTML(interval_context(SUPPORTED_GEOMETRY,'25',80,35,3,.7,1,37))
                    for component in common:
                        component.change(interval_context,common,context_box,queue=False,api_name=False)
                    with gr.Row(elem_classes='oc-two-column'):
                        with gr.Column(scale=1,min_width=280,elem_classes='oc-panel'):
                            gr.HTML(panel_heading('约束与组织参数','请填写与实际培养体系匹配的参数。'))
                            with gr.Row():
                                shear_limit=gr.Number(value=None,label='剪切上限（mPa，需依据）',min_width=140)
                                diameter=gr.Number(value=500,label='类器官直径（µm）',min_width=120)
                            with gr.Row():
                                density_difference=gr.Number(value=40,label='组织与液体密度差（kg/m³）',min_width=140)
                                density=gr.Number(value=1000,label='培养液密度（kg/m³）',min_width=120)
                            q=gr.Number(value=None,label='体积耗氧率 Q（mol/m³/s）')
                            with gr.Accordion('氧浓度与扩散系数',open=False,elem_classes='oc-technical'):
                                oxygen_bulk=gr.Number(value=.2,label='体相氧浓度（mol/m³）')
                                oxygen_critical=gr.Number(value=.02,label='设定中心氧浓度下限（mol/m³）')
                                diffusivity=gr.Number(value=3e-9,label='液相氧扩散系数（m²/s）')
                                tissue_diffusivity=gr.Number(value=2e-9,label='组织氧扩散系数（m²/s）')
                            with gr.Accordion('速度比例、设备范围与依据',open=True,elem_classes='oc-technical'):
                                beta_suspend=gr.Number(value=None,label='悬浮有效速度 / 轨道速度（0–1）')
                                beta_transfer=gr.Number(value=None,label='表面相对速度 / 轨道速度（0–1）')
                                max_rpm=gr.Number(value=300,label='设备最高转速（rpm，自行确认）')
                                basis=gr.Textbox(label='参数依据 / 算例说明',placeholder='记录阈值、耗氧率及速度系数的来源与适用条件。',lines=3)
                            safe_fields=[shear_limit,diameter,density_difference,density,q,oxygen_bulk,oxygen_critical,diffusivity,tissue_diffusivity,beta_suspend,beta_transfer,max_rpm,basis]
                            safe_button=gr.Button('计算双边界条件区间',variant='primary',elem_classes='oc-primary-action')
                            demo_scenario=gr.Button('载入假设算例（仅演示）')
                            demo_scenario.click(lambda:(45,500,40,1000,.02,.2,.02,3e-9,2e-9,.05,.01,300,'假设演示：阈值和速度系数均未经本装置/类器官验证；45mPa不是通用安全阈值。'),None,safe_fields)
                        with gr.Column(scale=1,min_width=280,elem_classes=['oc-panel','oc-result-panel']):
                            gr.HTML(panel_heading('条件交集与敏感性','剪切上界 × 悬浮下界 × 氧供给下界'))
                            safe_text=gr.Markdown('补充左侧必要参数，再计算条件区间。假设算例用于演示流程，不能作为实验安全建议。')
                            safe_plot=gr.Plot(label='各约束交集与敏感性图',show_label=False)
                    with gr.Accordion('逐项约束、敏感性数据与模型边界',open=False,elem_classes='oc-technical'):
                        safe_table=gr.Dataframe(label='每项约束与依据',interactive=False,elem_classes='oc-table')
                        safe_sensitivity=gr.Dataframe(label='Δρ × Q 敏感性（0.5、1、2 倍）',interactive=False,elem_classes='oc-table')
                        gr.Markdown('球体阻力用 Schiller–Naumann（Re<1000）；外部传质用 Ranz–Marshall 形式并限制 Re≤200；内部氧为稳态、均匀恒定耗氧。高 Schmidt 数传质及速度系数尚未在本体系验证，结果仅为情景分析。内部扩散受限时，提高转速也不一定有解。')
                    safe_run=gr.HTML(run_info(None,'interval'))
                    safe_outputs=[safe_text,safe_table,safe_plot,safe_sensitivity,interval_state]
                    safe_event=safe_button.click(calculate_interval,[*common,*safe_fields],safe_outputs)
                    for component in common+safe_fields:
                        component.change(lambda:('参数已改变，请重新计算区间。',pd.DataFrame(),None,pd.DataFrame(),None),None,safe_outputs,cancels=[safe_event],queue=False)
                    interval_state.change(partial(run_info,kind='interval'),interval_state,safe_run,queue=False,api_name=False)

                    with gr.Column(elem_classes='oc-panel'):
                        gr.HTML(panel_heading('候选条件扫描','在上方双边界区间的输入下，按轨道直径与转速网格逐点判定是否满足物理约束。需先计算双边界区间。'))
                        with gr.Row():
                            scan_orbits=gr.Textbox('10,19,25,50',label='轨道直径列表（mm，逗号分隔）',min_width=200)
                            scan_min=gr.Number(40,label='转速下限（rpm）',min_width=120)
                            scan_max=gr.Number(160,label='转速上限（rpm）',min_width=120)
                            scan_step=gr.Number(10,label='步长（rpm）',min_width=100)
                        with gr.Row():
                            target_diameter=gr.Number(500,label='目标等效直径（µm，仅记录）',min_width=160)
                            target_circularity=gr.Number(.8,label='目标圆形度（0–1，仅记录）',min_width=160)
                        scan_button=gr.Button('扫描候选条件',variant='primary',elem_classes='oc-primary-action')
                        scan_text=gr.Markdown('先计算双边界区间，再运行扫描。扫描只应用物理约束，不预测形态是否达标，也不给候选排序。')
                        scan_plot=gr.Plot(label='物理约束扫描图',show_label=False)
                        scan_table=gr.Dataframe(label='候选条件与约束判定',interactive=False,wrap=True,elem_classes='oc-table')
                        scan_run=gr.HTML(run_info(None,'screening'))
                    scan_inputs=[interval_state,scan_orbits,scan_min,scan_max,scan_step,target_diameter,target_circularity]
                    scan_outputs=[scan_text,scan_table,scan_plot,screening_state]
                    scan_event=scan_button.click(scan_for_ui,scan_inputs,scan_outputs)
                    for component in [interval_state,scan_orbits,scan_min,scan_max,scan_step,target_diameter,target_circularity]:
                        component.change(lambda:('参数已改变，请重新扫描。',pd.DataFrame(),None,None),None,scan_outputs,cancels=[scan_event],queue=False)
                    screening_state.change(lambda s:(f"<div class=\"oc-run-info\"><strong>后端耗时 {s['runtime_ms']:.1f} ms</strong><span>{s['scan_count']} 组网格</span><span>条件—形态配对训练样本 0 组</span><span>预测误差：尚未评估</span></div>" if s else run_info(None,'screening')),screening_state,scan_run,queue=False,api_name=False)

                with gr.Tab('综合报告',id='report'):
                    gr.HTML(page_heading('把本次依据、计算与测量，一起带走','汇总当前会话已运行的模块；未运行部分会明确注明。修改参数后，请重新生成报告。'))
                    gr.HTML('<div class="oc-report-intro"><div><strong>计算记录</strong><span>输入条件、假设、约束与换算准则</span></div><div><strong>形态与一致性</strong><span>逐目标测量、排除状态、MAD / PCA</span></div><div><strong>可追溯证据</strong><span>文献出处、元数据与完整数据包</span></div></div>')
                    gr.HTML(workflow())
                    overview_box=gr.HTML(overview())
                    overview_states=[physics_state,interval_state,conversion_state,batch_state,stats_state,literature_state,screening_state,reliability_state]
                    gr.on([state.change for state in overview_states],
                          lambda p,i,c,b,s,l,sc,r:overview(physics=p,interval=i,conversion=c,batch=b,stats=s,literature=l,screening=sc,reliability=r),
                          overview_states,overview_box,queue=False,api_name=False)
                    gr.HTML(validation_panel())
                    gr.HTML(notice('单图入口用于核对。需要纳入综合报告的照片，请在「形态量化 → 批量与一致性报告」中运行。'))
                    export_button=gr.Button('生成综合报告与数据包',variant='primary',elem_classes='oc-primary-action')
                    report_status=gr.Textbox(label='报告状态',value='运行需要的模块后，点击上方按钮生成本次会话快照。',interactive=False,lines=3)
                    with gr.Row(elem_classes='oc-downloads'):
                        report_pdf=gr.File(label='PDF 报告',interactive=False,min_width=200)
                        measurements_csv=gr.File(label='全部目标 CSV',interactive=False,min_width=200)
                    with gr.Row(elem_classes='oc-downloads'):
                        report_zip=gr.File(label='完整 ZIP 数据包',interactive=False,min_width=200)
                        report_md=gr.File(label='Markdown 报告',interactive=False,min_width=200)
                    export_button.click(export_for_ui,[physics_state,interval_state,conversion_state,batch_state,stats_state,literature_state,screening_state,reliability_state],[report_zip,report_pdf,measurements_csv,report_md,report_status])
                    with gr.Accordion('数据处理、证据边界与项目说明',open=False,elem_classes='oc-technical'):
                        gr.Markdown('下载文件是生成时的快照。图像在运行应用的服务器临时处理；本地运行时该服务器就是本机，公开部署后则是部署服务器。报告含文件名与成像元数据，请使用获授权数据。在线文献检索需要联网。')
                        gr.Markdown('当前支持轨道摇床尺度计算、形态候选测量、样本 CV、相对 MAD / PCA、配对重复测量的 ICC(2,1) 点估计（无置信区间）、DOI 与 PDF 文字提取（无 OCR）以及物理约束扫描与敏感性分析。')
                        gr.Markdown('### 主要依据\n[主论文与数据](https://pmc.ncbi.nlm.nih.gov/articles/PMC12715241/) · [轨道摇床 CFD](https://pmc.ncbi.nlm.nih.gov/articles/PMC6404276/) · [剪切定义及几何影响](https://pmc.ncbi.nlm.nih.gov/articles/PMC7345652/) · [球体氧扩散模型](https://pmc.ncbi.nlm.nih.gov/articles/PMC5029285/)')
            with gr.Row(elem_classes='oc-action-row'):
                gr.Markdown('结果随附计算假设、来源与适用范围。',elem_classes='oc-help')
                report_shortcut=gr.Button('查看与导出本次结果',size='sm',min_width=190)
    navigation_outputs=[workspace_tabs,*nav_buttons]
    for (key,_),button in zip(NAV,nav_buttons):
        button.click(partial(navigate,key),None,navigation_outputs,queue=False,api_name=False)
    screen_shortcut.click(partial(navigate,'screening'),None,navigation_outputs,queue=False,api_name=False)
    report_shortcut.click(partial(navigate,'report'),None,navigation_outputs,queue=False,api_name=False)
    gr.HTML('<footer class="oc-footer"><span>OrgaCal 境算师：参数计算与形态一致性</span><span>公开数据演示，物理结果为情景估算，来源可追溯</span></footer>')
    demo.load(lambda:(None,None,None,None,None),None,[shear_limit,q,beta_suspend,beta_transfer,shared_scale],queue=False)
    demo.queue(default_concurrency_limit=1,max_size=20)

if __name__=='__main__':
    demo.launch(server_name=os.environ.get('GRADIO_SERVER_NAME','127.0.0.1'),
                server_port=int(os.environ.get('GRADIO_SERVER_PORT','7860')),
                theme=make_theme(),head=HEAD+'<style id="orgacal-workbench">'+CSS+'</style>',footer_links=['settings'],
                max_file_size='25mb',show_error=True)
