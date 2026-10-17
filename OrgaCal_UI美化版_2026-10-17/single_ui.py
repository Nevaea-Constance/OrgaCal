from pathlib import Path

import gradio as gr

from morphology import detect_candidates, render_result
from calibration import make_calibration, calibrated_rows

ROOT = Path(__file__).resolve().parent
READY_MESSAGE = '请上传图片或选择论文示例，然后点击“开始分析”。'
HEADERS = ['编号', '核对状态', '面积（原图 px²）', '周长（原图 px）', '等效直径（原图 px）', '圆形度 Circularity']
PHYSICAL_HEADERS = ['编号', '核对状态', '面积（µm²）', '周长（µm）', '等效直径（µm）', '圆形度 Circularity']
UNCALIBRATED = '未标定：目前仅显示像素结果。'


def invalidate_calibration():
    return None, UNCALIBRATED + ' 如需换算，请核对两个长度后点击“应用比例尺”。', gr.update(value=[], visible=False)


def clear_calibration():
    return None, None, *invalidate_calibration()


def analyze_for_ui(image, min_area, threshold_offset):
    try:
        result = detect_candidates(image, min_area, threshold_offset)
        preview, message, rows = render_result(result)
    except ValueError as error:
        return None, str(error), [], gr.update(choices=[], value=[]), None, *invalidate_calibration()
    choices = [str(item['id']) for item in result['objects']]
    return preview, message, rows, gr.update(choices=choices, value=[]), result, *invalidate_calibration()


def reset_result():
    return None, READY_MESSAGE, [], gr.update(choices=[], value=[]), None, *invalidate_calibration()


def reset_image():
    return *reset_result(), None, None


def apply_calibration(real_length_um, pixel_length, result, excluded_ids):
    if result is None:
        return None, '请先选择图片并点击“开始分析”，再应用比例尺。', gr.update(value=[], visible=False)
    try:
        calibration = make_calibration(real_length_um, pixel_length, result['original_size'])
        rows = calibrated_rows(result, excluded_ids, calibration)
    except ValueError as error:
        return None, f'未标定：{error}', gr.update(value=[], visible=False)
    message = (f"按输入比例尺换算：{real_length_um:g} µm ÷ {pixel_length:g} px = "
               f"{calibration['um_per_pixel']:.8g} µm/px。仅用于当前图片；比例尺来源和轮廓仍需人工核对。")
    return calibration, message, gr.update(value=rows, visible=True)


def review_result(excluded_ids, result, calibration):
    if result is None:
        return None, READY_MESSAGE, [], gr.update(value=[], visible=False)
    preview, message, rows = render_result(result, excluded_ids)
    return preview, message, rows, gr.update(value=calibrated_rows(result, excluded_ids, calibration), visible=calibration is not None)



def build_single(demo):
    gr.Markdown('上传明场图片 → 核对候选轮廓 → 按可靠比例尺换算。适用于浅色背景、较深目标。', elem_classes='oc-help')
    analysis_state = gr.State(value=None, time_to_live=3600)
    calibration_state = gr.State(value=None, time_to_live=3600)
    with gr.Column(elem_classes='oc-panel'):
        gr.Markdown('### 01 / 图片与候选轮廓', elem_classes='oc-panel-heading')
        with gr.Row(elem_classes='oc-media-row'):
            with gr.Column(min_width=280):
                input_image = gr.Image(label='上传明场图片', type='pil', image_mode='RGBA', sources=['upload'], height=400)
            with gr.Column(min_width=280):
                output_image = gr.Image(label='候选轮廓与编号：绿色待核对，灰色已排除', type='pil', interactive=False, height=400)
        with gr.Accordion('识别设置｜漏掉小目标或轮廓不合适时调整', open=False, elem_classes='oc-technical'):
            min_area = gr.Number(label='最小目标面积（原图 px²）', value=5000, minimum=1, precision=0)
            threshold_offset = gr.Slider(label='识别范围微调：向右更容易纳入浅色区域', minimum=-50, maximum=50, step=1, value=0)
            gr.Markdown('调整设置后需要重新分析。漏掉小目标时减小最小面积；浅色区域误连时，可向左调整识别范围。不同图片可能需要不同设置。', elem_classes='oc-help')
        with gr.Row(elem_classes='oc-action-row'):
            analyze_button = gr.Button('开始分析', variant='primary', elem_classes='oc-primary-action')
        status = gr.Textbox(label='分析提示', value=READY_MESSAGE, interactive=False, lines=3, elem_classes='oc-notice')

    with gr.Column(elem_classes='oc-panel'):
        gr.Markdown('### 02 / 逐个核对与测量', elem_classes='oc-panel-heading')
        gr.Markdown('照片编号与表格逐行对应。排除气泡、碎屑或不完整轮廓后，记录仍会保留并标注状态。', elem_classes='oc-help')
        exclusions = gr.CheckboxGroup(label='勾选需要排除的编号（例如气泡、碎屑或不完整轮廓）', choices=[], value=[])
        results_table = gr.Dataframe(label='逐目标测量结果', headers=HEADERS,
                                     datatype=['number', 'str', 'number', 'number', 'number', 'number'],
                                     type='array', value=[], interactive=False, elem_classes='oc-table')
        with gr.Accordion('核对方法与指标定义', open=False, elem_classes='oc-technical'):
            gr.Markdown('**核对方法：** 图片编号与表格逐行对应。勾选编号后，该轮廓变灰，表格仍保留它并标记“已排除”。编号仅属于本次分析，与论文原编号不同。', elem_classes='oc-help')
            gr.Markdown('**指标说明：** 面积为外轮廓包围的面积（含内部孔洞）；等效直径为等面积圆的直径；Circularity＝4πA/P²，通常越接近1越圆。它与论文的Roundness不是同一指标。', elem_classes='oc-help')
            gr.Markdown('上表保留原图像素结果；大图先缩小识别后换算回原图坐标。粘连区域可能作为一个目标，需要人工复核。', elem_classes='oc-notice')

    with gr.Column(elem_classes='oc-panel'):
        gr.Markdown('### 03 / 比例尺标定', elem_classes='oc-panel-heading')
        gr.Markdown('先分析图片，再填写标尺的真实长度和原图像素长度。没有可靠标尺时留空，结果保留为像素。', elem_classes='oc-help')
        with gr.Row():
            scale_um = gr.Number(label='比例尺真实长度（µm）', value=None)
            scale_px = gr.Number(label='比例尺在原图中的长度（px）', value=None)
        with gr.Row(elem_classes='oc-action-row'):
            apply_scale_button = gr.Button('应用比例尺')
            clear_scale_button = gr.Button('清除比例尺')
        scale_status = gr.Textbox(label='标定状态', value=UNCALIBRATED, interactive=False, lines=2, elem_classes='oc-notice')
        physical_table = gr.Dataframe(label='按输入比例尺换算的测量结果', headers=PHYSICAL_HEADERS,
                                      datatype=['number', 'str', 'number', 'number', 'number', 'number'],
                                      type='array', value=[], interactive=False, visible=False, elem_classes='oc-table')
        with gr.Accordion('标定方法、换算依据与适用条件', open=False, elem_classes='oc-technical'):
            gr.Markdown('先分析图片，再填写两个长度并点击“应用比例尺”。例如：标尺上写着100 µm，在**原始图片**中长200 px，则每个像素代表0.5 µm。这个例子仅用于说明，不能直接套用到论文示例。', elem_classes='oc-help')
            gr.Markdown('像素长度需在图像软件中测量标尺两端的距离；不要使用网页缩略图或屏幕截图的长度。只有2x/4x倍率不能确定比例尺。没有可靠标尺时留空。此换算要求横纵方向比例一致，图片未被不等比例拉伸；图上的标尺或文字若被圈中，请按编号排除。', elem_classes='oc-notice')
            gr.Markdown('长度乘以 µm/px；面积乘以它的平方；圆形度不变。更换图片会清除标定和输入值；重新分析或修改长度后需重新应用。', elem_classes='oc-help')

    example_paths = [ROOT / 'examples' / name for name in ['pa_day6.jpg', 'rc_day6.jpg', 'os_day90.jpg', 'rc_day90.jpg']]
    if all(p.exists() for p in example_paths):
        with gr.Accordion('论文原图示例与来源', open=False, elem_classes='oc-technical'):
            gr.Examples(examples=[[str(p)] for p in example_paths], inputs=[input_image],
                        label='论文原图示例：依次为PA第6天、RC第6天、OS第90天、RC第90天', cache_examples=False)
            gr.Markdown('示例来源：[Aiello等，EMBO Reports（2025）](https://pmc.ncbi.nlm.nih.gov/articles/PMC12715241/)，Source data Fig. 3。', elem_classes='oc-help')
            gr.Markdown('第4张示例存在与边缘目标误连的情况：可展开识别设置，把范围微调设为−35再分析，随后检查轮廓。该设置只供此图演示。', elem_classes='oc-notice')

    calibration_outputs = [calibration_state, scale_status, physical_table]
    outputs = [output_image, status, results_table, exclusions, analysis_state, *calibration_outputs]
    analysis_event = analyze_button.click(analyze_for_ui, inputs=[input_image, min_area, threshold_offset],
                                           outputs=outputs, concurrency_limit=1, concurrency_id='image-analysis')
    review_event = exclusions.input(review_result, inputs=[exclusions, analysis_state, calibration_state],
                                    outputs=[output_image, status, results_table, physical_table],
                                    concurrency_limit=1, concurrency_id='image-analysis')
    apply_event = apply_scale_button.click(apply_calibration, inputs=[scale_um, scale_px, analysis_state, exclusions],
                                            outputs=calibration_outputs, concurrency_limit=1, concurrency_id='image-analysis')
    events = [analysis_event, review_event, apply_event]
    clear_scale_button.click(clear_calibration, inputs=[], outputs=[scale_um, scale_px, *calibration_outputs],
                             cancels=events, queue=False)
    # Gradio's number input may initially display 0 for None; explicitly clear on load.
    demo.load(clear_calibration, inputs=[], outputs=[scale_um, scale_px, *calibration_outputs], queue=False)
    for component in (scale_um, scale_px):
        component.change(invalidate_calibration, inputs=[], outputs=calibration_outputs,
                         cancels=[review_event, apply_event], queue=False)
    input_image.change(reset_image, inputs=[], outputs=[*outputs, scale_um, scale_px],
                       cancels=events, queue=False)
    for component in (min_area, threshold_offset):
        component.change(reset_result, inputs=[], outputs=outputs,
                         cancels=events, queue=False)


    return {"analysis":analysis_state, "calibration":calibration_state, "exclusions":exclusions}
