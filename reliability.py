"""Auditable ICC(2,1) for complete, balanced repeated measurements.

The point-estimate equation follows the absolute-agreement ANOVA formulation:
https://pmc.ncbi.nlm.nih.gov/articles/PMC6645485/
https://pingouin-stats.org/generated/pingouin.intraclass_corr.html
https://github.com/raphaelvallat/pingouin/blob/main/src/pingouin/reliability.py

No ICC is inferred from unpaired organoid images. No confidence interval or
reliability grade is produced by this module.
"""
from pathlib import Path
import time

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ['target_id', 'rater_id', 'value']
ICC_FORMULA = '(MSR − MSE) / [MSR + (k − 1) × MSE + k × (MSC − MSE) / n]'
MEAN_SQUARE_FORMULAS = {
    'MSR':'k × Σ(目标均值 − 总均值)² / (n − 1)',
    'MSC':'n × Σ(测量者均值 − 总均值)² / (k − 1)',
    'MSE':'Σ(测量值 − 对应目标均值 − 对应测量者均值 + 总均值)² / [(n − 1) × (k − 1)]',
}
SOURCES = [
    {'title':'Liljequist et al. (2019), PLOS ONE',
     'url':'https://doi.org/10.1371/journal.pone.0219854'},
    {'title':'Pingouin: intraclass_corr',
     'url':'https://pingouin-stats.org/generated/pingouin.intraclass_corr.html'},
]
LIMITATIONS = [
    '只分析一个形态指标及同一种单位；每个target_id必须代表同一实际目标，各rater_id必须对所有目标完成测量。',
    '两向随机效应、单次测量、绝对一致性模型；将测量者视为可推广测量者总体的样本。固定测量者的结果不宜直接外推。',
    '假定不同目标相互独立；重复测量期间目标未发生真实变化。时间变化、混合单位或不同器官的独立照片不能视为配对重复。',
    '本实现仅给出ICC点估计，未计算95%置信区间，也不作合格/不合格评级；3个目标是计算门槛，不代表足够的验证样本量。',
    '每个目标×测量者组合只允许一个数值；交互作用与测量误差合并进入残差，不支持缺测、非平衡或嵌套设计。',
    '负ICC按原值保留，提示误差可超过目标间变异，不能截断为0或表述为生物学一致性结论。',
]
# A copyable template only. These values deliberately carry no biological claim.
TEMPLATE_CSV = '''target_id,rater_id,value
demo_target_01,rater_A,100
demo_target_01,rater_B,102
demo_target_02,rater_A,120
demo_target_02,rater_B,119
demo_target_03,rater_A,140
demo_target_03,rater_B,142
demo_target_04,rater_A,160
demo_target_04,rater_B,158
'''


def icc_two_way_absolute(data):
    """Return JSON-serializable ICC(2,1), ANOVA terms, design and limitations.

    ``data`` is a DataFrame or records with target_id, rater_id, value. Missing
    values and duplicate target/rater pairs raise an informative ValueError.
    A fully balanced design with n>=3 targets and k>=2 raters is required.
    """
    frame = pd.DataFrame(data).copy()
    missing_columns = [name for name in REQUIRED_COLUMNS if name not in frame]
    if missing_columns:
        raise ValueError('CSV缺少必需列：' + '、'.join(missing_columns) + '。')
    if frame.empty:
        raise ValueError('CSV没有测量记录。请填写同一目标的配对重复测量。')
    frame = frame[REQUIRED_COLUMNS]
    for name in ('target_id', 'rater_id'):
        if frame[name].isna().any():
            raise ValueError(f'{name}含缺失编号，请为每条记录填写编号。')
        frame[name] = frame[name].astype(str).str.strip()
        if frame[name].eq('').any():
            raise ValueError(f'{name}含空白编号。')
    if frame.duplicated(['target_id', 'rater_id']).any():
        raise ValueError('存在重复的target_id与rater_id组合；每个目标×测量者只能有一个数值，请先整理重复记录。')
    values = pd.to_numeric(frame['value'], errors='coerce').to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('value含缺失、非数字或无穷值；本算法不自动填补或删除测量。')
    frame['value'] = values
    targets = sorted(frame['target_id'].unique().tolist())
    raters = sorted(frame['rater_id'].unique().tolist())
    n, k = len(targets), len(raters)
    if n < 3 or k < 2:
        raise ValueError(f'至少需要3个目标和2名测量者/测量轮次；当前为{n}个目标、{k}组测量。')
    if len(frame) != n * k:
        raise ValueError(f'测量表不完整或不平衡：{n}个目标×{k}组测量应有{n*k}条记录，当前只有{len(frame)}条。每个目标须由同一组测量者测量。')
    matrix = frame.pivot(index='target_id', columns='rater_id', values='value').loc[targets, raters].to_numpy()
    # Normalization makes the ratio stable for differing measurement units.
    scale = float(np.max(np.abs(matrix)))
    if scale == 0:
        raise ValueError('所有测量值相同，数据没有变异，ICC无法定义。')
    normalized = matrix / scale
    grand = normalized.mean()
    row = normalized.mean(axis=1)
    column = normalized.mean(axis=0)
    ssr = float(k * np.sum((row - grand) ** 2))
    ssc = float(n * np.sum((column - grand) ** 2))
    sse = float(np.sum((normalized - row[:,None] - column[None,:] + grand) ** 2))
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), sse / ((n - 1) * (k - 1))
    denominator = msr + (k - 1) * mse + k * (msc - mse) / n
    if denominator <= 0 or not np.isfinite(denominator):
        raise ValueError('测量缺乏可估计的变异，ICC分母为0或无效；请检查是否全部为同一数值。')
    icc = float((msr - mse) / denominator)
    with np.errstate(over='ignore', invalid='ignore'):
        rescaled = np.asarray([ssr, ssc, sse, msr, msc, mse]) * np.float64(scale) ** 2
    if not np.isfinite(rescaled).all():
        raise ValueError('测量数值过大，无法稳定呈现方差分解；请统一换用更合适的单位后重试。')
    ssr, ssc, sse, msr, msc, mse = map(float, rescaled)
    return {
        'status':'ok', 'type':'ICC(2,1)', 'alias':'ICC(A,1)', 'icc':icc,
        'n_targets':n, 'n_raters':k, 'n_measurements':n*k,
        'n':n, 'k':k, 'MSR':msr, 'MSC':msc, 'MSE':mse,
        'confidence_interval':None, 'ci_note':'未计算95%置信区间',
        'formula':ICC_FORMULA, 'mean_square_formulas':dict(MEAN_SQUARE_FORMULAS),
        'anova':[
            {'source':'目标（rows）', 'sum_squares':ssr, 'df':n-1, 'mean_square':msr, 'symbol':'MSR'},
            {'source':'测量者（columns）', 'sum_squares':ssc, 'df':k-1, 'mean_square':msc, 'symbol':'MSC'},
            {'source':'残差', 'sum_squares':sse, 'df':(n-1)*(k-1), 'mean_square':mse, 'symbol':'MSE'},
        ],
        'targets':targets, 'raters':raters,
        'matrix':matrix.tolist(), 'limitations':list(LIMITATIONS), 'sources':list(SOURCES),
    }


def reliability_for_ui(file):
    """Gradio callback: uploaded CSV -> (Markdown, ANOVA DataFrame, state).

    The file can be a path, pathlib.Path or Gradio file object with ``name``.
    An empty/error state is None; no exception or previous result is retained.
    """
    columns = ['来源', '平方和', '自由度', '均方', '符号']
    empty = pd.DataFrame(columns=columns)
    if file is None:
        return '请上传含target_id、rater_id、value三列的配对重复测量CSV。独立照片不能直接计算ICC。', empty, None
    start = time.perf_counter()
    try:
        path = Path(file if isinstance(file, (str, Path)) else file.name)
        frame = pd.read_csv(path, encoding='utf-8-sig', dtype={'target_id':str, 'rater_id':str})
        result = icc_two_way_absolute(frame)
    except (ValueError, OSError, UnicodeError, AttributeError, TypeError) as error:
        return '无法计算ICC：' + str(error), empty, None
    result['elapsed_seconds'] = round(time.perf_counter() - start, 6)
    rows = [{
        '来源':r['source'], '平方和':r['sum_squares'], '自由度':r['df'],
        '均方':r['mean_square'], '符号':r['symbol'],
    } for r in result['anova']]
    markdown = (
        f'**ICC(2,1) = {result["icc"]:.4f}** · 单次测量的绝对一致性\n\n'
        f'已配对{result["n"]}个目标 × {result["k"]}组测量，共{result["n_measurements"]}条记录。'
        f'计算耗时{result["elapsed_seconds"]:.3f}秒。\n\n'
        f'**计算式**：{ICC_FORMULA}\n\n'
        'MSR为目标间均方，MSC为测量者间均方，MSE为残差均方；下表保留方差分解供复核。\n\n'
        + '\n\n'.join(f'{term} = {formula}' for term, formula in MEAN_SQUARE_FORMULAS.items()) + '\n\n'
        '**解释范围**：' + '\n\n'.join(LIMITATIONS) + '\n\n'
        '计算依据：[Liljequist等（2019）](https://doi.org/10.1371/journal.pone.0219854)；'
        '[Pingouin统计文档](https://pingouin-stats.org/generated/pingouin.intraclass_corr.html)。'
    )
    return markdown, pd.DataFrame(rows, columns=columns), result
