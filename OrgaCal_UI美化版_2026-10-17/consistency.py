"""Batch statistics with explicit MAD and per-stratum PCA definitions."""
import math

import numpy as np
import pandas as pd

DEFAULT_FEATURES = ['area', 'perimeter', 'equivalent_diameter', 'circularity', 'max_feret', 'min_feret', 'solidity']
STRATA = ['condition', 'day', 'imaging_batch', 'unit_basis']


def feature_unit(feature,basis):
    if feature=='area':return basis+'^2'
    if feature in ('perimeter','equivalent_diameter','mean_radius','max_feret','min_feret','paper_radius'):return basis
    if feature=='paper_roundness_pct':return '%'
    if feature in ('mean_curvature','std_curvature'):return '1/'+basis
    return 'dimensionless'


def relative_mad(values, factor=1.0):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return {'n':0, 'median':None, 'mad':None, 'relative_mad_pct':None}
    median = float(np.median(x))
    mad = float(np.median(np.abs(x - median))) * factor
    return {'n':len(x), 'median':median, 'mad':mad,
            'relative_mad_pct': None if abs(median) <= 1e-12 else mad/abs(median)*100}


def pca_fit(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] < 3 or matrix.shape[1] < 2:
        raise ValueError('PCA至少需要3个目标和2个特征。')
    if not np.isfinite(matrix).all():
        raise ValueError('PCA输入包含缺失或非有限数值。')
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0, ddof=1)
    keep = std > 1e-12
    if keep.sum() < 2:
        raise ValueError('不足2个有变异的特征，不能作二维PCA。')
    z = (matrix[:, keep] - mean[keep]) / std[keep]
    u, singular, vt = np.linalg.svd(z, full_matrices=False)
    if singular[1] <= singular[0] * 1e-12:
        raise ValueError('数据有效秩不足2，不能绘制二维PCA及椭圆。')
    scores = u[:, :2] * singular[:2]
    explained = singular**2 / np.sum(singular**2)
    return {'scores':scores, 'loadings':vt[:2], 'explained':explained[:2],
            'mean':mean, 'std':std, 'kept':keep}


def summarize(records, features=None, mad_factor=1.0):
    if not records:
        return {'summary':[], 'pca':[], 'notes':['没有保留的目标，未生成一致性统计。']}
    frame = pd.DataFrame([r for r in records if not r.get('excluded', False)])
    if frame.empty:
        return {'summary':[], 'pca':[], 'notes':['全部目标已排除。']}
    features = features or DEFAULT_FEATURES
    features = [f for f in features if f in frame.columns]
    if not features:
        raise ValueError('没有可用于统计的特征。')
    for field in STRATA + ['batch']:
        if field not in frame:
            frame[field] = '未提供'
        frame[field] = frame[field].fillna('未提供').astype(str)
    summary, pca, notes = [], [], []
    for keys, strata_frame in frame.groupby(STRATA, dropna=False, sort=True):
        strata = dict(zip(STRATA, keys))
        for batch, group in strata_frame.groupby('batch', sort=True):
            for feature in features:
                values = pd.to_numeric(group[feature], errors='coerce').to_numpy()
                summary.append({**strata, 'batch':batch, 'feature':feature,'unit':feature_unit(feature,strata['unit_basis']), **relative_mad(values, mad_factor)})
        matrix = strata_frame[features].apply(pd.to_numeric, errors='coerce')
        finite = np.isfinite(matrix.to_numpy()).all(axis=1)
        if not finite.all():
            notes.append(f'{keys}: PCA删除{int((~finite).sum())}条存在缺失值的目标；MAD按各特征有效值计算。')
        try:
            fitted = pca_fit(matrix[finite].to_numpy())
            kept_names = np.asarray(features)[fitted['kept']].tolist()
            pca.append({**strata, 'fit':fitted, 'features':kept_names,
                        'batches':strata_frame.loc[finite, 'batch'].tolist(),
                        'object_ids':strata_frame.loc[finite, 'object_key'].tolist()})
        except ValueError as error:
            notes.append(f'{keys}: {error}')
    notes.append(f'MAD定义：{mad_factor:g}×median(|x−median(x)|) / |median(x)| ×100%；中位数接近0时不计算比例。')
    notes.append('按条件、时间、成像批次和单位分层；每层内各批次单独算MAD，共同拟合标准化PCA。')
    notes.append('95%椭圆为二维正态近似的数据分布椭圆，不是均值置信区间或生物学合格判据。每组至少3点且协方差满秩才绘制。')
    notes.append('逐目标统计未处理同图/同实验重复的嵌套相关；组间生物学推断需以独立实验批次为重复单位。')
    return {'summary':summary, 'pca':pca, 'notes':notes, 'features':features, 'mad_factor':mad_factor}


def plot_pca(item):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse
    fig, ax = plt.subplots(figsize=(6.7, 4.5), constrained_layout=True)
    scores = item['fit']['scores']
    batches = np.array(item['batches'])
    for index, batch in enumerate(sorted(set(batches))):
        points = scores[batches == batch]
        color = plt.get_cmap('tab10')(index % 10)
        ax.scatter(points[:,0], points[:,1], s=30, alpha=.8, color=color, label=f'B{index+1}')
        if len(points) >= 3:
            covariance = np.cov(points, rowvar=False)
            eigen, vectors = np.linalg.eigh(covariance)
            if eigen[0] > max(1e-12, eigen[-1]*1e-12):
                order = np.argsort(eigen)[::-1]
                eigen, vectors = eigen[order], vectors[:,order]
                angle = math.degrees(math.atan2(vectors[1,0], vectors[0,0]))
                widths = 2*np.sqrt(5.991464547*eigen)
                ax.add_patch(Ellipse(points.mean(axis=0), widths[0], widths[1], angle=angle,
                                     fill=False, color=color, alpha=.7))
    explained = item['fit']['explained'] * 100
    ax.set(xlabel=f'PC1 ({explained[0]:.1f}%)', ylabel=f'PC2 ({explained[1]:.1f}%)',
           title='PCA | 95% normal data ellipses')
    ax.legend(title='Batch', loc='best', fontsize=8)
    ax.grid(alpha=.18)
    return fig
