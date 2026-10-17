"""Gradio adapters; calculations and reports remain usable without the web UI."""
import json
from pathlib import Path

import gradio as gr
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from physics import SUPPORTED_GEOMETRY, estimate_shear, shear_for_ui
from constraints import conditional_interval, convert_rpm, sensitivity
from batch import analyze_batch, review_batch, reference_records
from consistency import summarize, plot_pca
from literature import search_papers, cached_papers, literature_table
from reports import build_bundle

SAFE_KEYS = ['shear_limit_mpa','diameter_um','delta_rho','rho','oxygen_q','bulk_oxygen',
             'critical_oxygen','diffusivity','tissue_diffusivity','beta_suspend','beta_transfer','max_rpm','basis']


def calculate_shear(*args):
    value,note,rows,assumptions = shear_for_ui(*args)
    if not value:
        return value,note,rows,assumptions,None
    result = estimate_shear(*args)
    return value,note,rows,assumptions,{**result,'assumptions':assumptions}


def calculate_interval(geometry,orbit,rpm,vessel,volume,mu_low,mu_high,temp,*args):
    if geometry != SUPPORTED_GEOMETRY:
        return '当前仅支持圆形平底容器。',pd.DataFrame(),None,pd.DataFrame(),None
    p = {'orbit_mm':orbit,'vessel_mm':vessel,'volume_ml':volume,'mu_low':mu_low,'mu_high':mu_high,'temperature_c':temp,
         **dict(zip(SAFE_KEYS,args))}
    try:
        result = conditional_interval(p)
        if result['status'] == 'missing':
            return result['message']+' 缺少：'+', '.join(result['missing']),pd.DataFrame(),None,pd.DataFrame(),result
        text = result['message']
        if result['status'] == 'feasible':
            text = f"**条件可行区间：{result['lower']:.2f}–{result['upper']:.2f} rpm**\n\n"+text
        text += '\n\n'+result['evidence_status']
        rows = [{'约束':'剪切上界','转速rpm':result['shear_upper'],'依据':'输入剪切阈值 / 液深尺度模型（尚未校准）'},
                {'约束':'悬浮下界','转速rpm':result['suspension_lower'],'依据':'球体沉降速度 / 用户输入的有效速度系数'},
                {'约束':'氧供给下界','转速rpm':result.get('oxygen_lower'),'依据':'外部传质 + 球内稳态扩散/恒定耗氧'}]
        fig,(ax,heat_ax) = plt.subplots(2,1,figsize=(6.6,6.7),height_ratios=[.85,1.15],constrained_layout=True)
        upper=float(p['max_rpm'])
        for y,(key,label,color) in enumerate([('suspension_lower','Suspension lower','#437B9A'),('oxygen_lower','Oxygen lower','#0E7C86'),('shear_upper','Shear upper','#D9772B')]):
            bound=result.get(key)
            if bound is not None:
                start,end=(bound,upper) if 'lower' in key else (0,bound)
                ax.plot([max(0,start),min(upper,end)],[y,y],lw=9,color=color,solid_capstyle='butt')
        if result['status']=='feasible':
            ax.axvspan(result['lower'],result['upper'],color='#B8D5BE',alpha=.35)
        ax.set(xlim=(0,upper),yticks=[0,1,2],yticklabels=['Suspension','Oxygen','Shear'],xlabel='rpm',title='Conditional constraint intersection')
        for chart in (ax,heat_ax):
            chart.tick_params(colors='#526674',labelsize=9)
            for spine in chart.spines.values():
                spine.set_color('#C9D2D8')
        ax.grid(axis='x',alpha=.2)
        sensitivity_rows=sensitivity(result['inputs'])
        widths=np.array([max(0,r['upper_rpm']-r['lower_rpm']) if r['status']=='feasible' else np.nan for r in sensitivity_rows]).reshape(3,3)
        image=heat_ax.imshow(np.ma.masked_invalid(widths),cmap='YlGn',vmin=0,vmax=max(1,float(np.nanmax(widths))) if np.isfinite(widths).any() else 1,aspect='auto')
        heat_ax.set_facecolor('#eeeeee')
        normalized=result['inputs']
        heat_ax.set(xticks=[0,1,2],yticks=[0,1,2],xticklabels=[f"{normalized['oxygen_q']*f:.3g}" for f in (.5,1,2)],
                    yticklabels=[f"{normalized['delta_rho']*f:.3g}" for f in (.5,1,2)],xlabel='Q (mol/m3/s)',ylabel='Density difference (kg/m3)',title='Conditional sensitivity')
        for index,row in enumerate(sensitivity_rows):
            label=f"{row['lower_rpm']:.0f}-{row['upper_rpm']:.0f}" if row['status']=='feasible' else 'No fit'
            heat_ax.text(index%3,index//3,label,ha='center',va='center',fontsize=8,color='#162D21')
        fig.colorbar(image,ax=heat_ax,label='Feasible width (rpm)',shrink=.8)
        result['sensitivity']=sensitivity_rows
        return text,pd.DataFrame(rows),fig,pd.DataFrame(sensitivity_rows),result
    except (ValueError,ArithmeticError,TypeError) as error:
        return '未生成区间：'+str(error),pd.DataFrame(),None,pd.DataFrame(),None


def convert_for_ui(*args):
    try:
        value=convert_rpm(*args)
        if not np.isfinite(value):
            raise ValueError('结果超出可计算范围。')
        result={'criterion':args[0],'source_rpm':args[1],'source_orbit_mm':args[2], 'target_orbit_mm':args[3],
                'source_vessel_mm':args[4],'source_volume_ml':args[5],'source_mu_mpas':args[6],
                'target_vessel_mm':args[7],'target_volume_ml':args[8],'target_mu_mpas':args[9],
                'target_rpm':value,'note':'匹配选定模型或运动学量，不证明生物学效果等价。'}
        shown = ['未提供' if x is None or x == '' else str(x) for x in args]
        details=(f'换算准则：{args[0]}\n'
                 f'文献设备：{shown[1]} rpm，轨道直径 {shown[2]} mm\n'
                 f'目标设备：轨道直径 {shown[3]} mm → {value:.4g} rpm\n'
                 f'文献条件：内径 {shown[4]} mm，液量 {shown[5]} mL，黏度 {shown[6]} mPa·s\n'
                 f'目标条件：内径 {shown[7]} mm，液量 {shown[8]} mL，黏度 {shown[9]} mPa·s\n'
                 +result['note'])
        return f'{value:.4g} rpm',details,result
    except (ValueError,ArithmeticError,TypeError) as error:
        return '',str(error),None


def _batch_output(state):
    updated,gallery,frame=review_batch(state,[])
    choices=[(f"{r['image']} / #{r['object_id']}",r['object_key']) for r in state['records']]
    text=f"处理{state['image_count']}张；候选{len(state['records'])}个；失败或未检出{len(state['failures'])}张。全部候选仍需核对。"
    if state['failures']:
        text+='\n'+'\n'.join(f"{r['image']}：{r['reason']}" for r in state['failures'])
    return updated,gallery,frame,gr.update(choices=choices,value=[]),text,None,pd.DataFrame(),[],''


def batch_for_ui(*args):
    try:
        return _batch_output(analyze_batch(*args))
    except (ValueError,TypeError,ArithmeticError,OSError) as error:
        return None,[],pd.DataFrame(),gr.update(choices=[],value=[]),str(error),None,pd.DataFrame(),[],''


def batch_example_for_ui(*settings):
    root=Path(__file__).resolve().parent
    paths=[str(root/'examples'/name) for name in ['pa_day6.jpg','rc_day6.jpg','os_day90.jpg','rc_day90.jpg']]
    return batch_for_ui(paths,str(root/'examples/batch_metadata.csv'),*settings)


def review_for_ui(state,excluded):
    if state is None:
        return None,[],pd.DataFrame(),'请先运行批量分析。',None,pd.DataFrame(),[],''
    updated,gallery,frame=review_batch(state,excluded)
    return updated,gallery,frame,f'已排除{sum(r["excluded"] for r in updated["records"])}个；其余仍待核对。',None,pd.DataFrame(),[],''


def stats_for_ui(state,factor):
    if state is None:
        return None,pd.DataFrame(),[],'请先分析图片或载入论文参数。'
    try:
        features=None if state.get('origin')!='paper_ev1' else ['area','perimeter','paper_radius','paper_roundness_pct','max_feret','min_feret','mean_curvature','std_curvature','std_curvature_times_radius','paper_dne']
        stats=summarize(state['records'],features=features,mad_factor=float(factor))
        gallery=[]
        for item in stats['pca']:
            fig=plot_pca(item)
            caption=f"{item['condition']} / day {item['day']} / {item['unit_basis']} | "+', '.join(f'B{i+1}={b}' for i,b in enumerate(sorted(set(item['batches']))))
            from PIL import Image
            import io
            stream=io.BytesIO()
            fig.savefig(stream,format='png',dpi=140)
            stream.seek(0)
            gallery.append((Image.open(stream).copy(),caption))
            plt.close(fig)
        return stats,pd.DataFrame(stats['summary']),gallery,'\n\n'.join(stats['notes'])
    except (ValueError,TypeError) as error:
        return None,pd.DataFrame(),[],str(error)


def paper_for_ui():
    records=reference_records()
    state={'origin':'paper_ev1','records':records,'results':[],'failures':[],'image_count':0,
           'notes':['作者EV1表，不是本项目从图像测得的结果；不能用此演示宣称分割精度。']}
    return state,[],pd.DataFrame(records),gr.update(choices=[],value=[]),f'已载入作者EV1的{len(records)}条记录，供统计演示；与本项目图像测量结果分开。',None,pd.DataFrame(),[],''


def literature_for_ui(query,limit,fulltext):
    try:
        data=search_papers(query,limit,fulltext)
        return data,pd.DataFrame(literature_table(data)),f'命中{data["total_hits"]}条，本次读取{len(data["records"])}条。字段带原文证据，仍需核对。'
    except Exception as error:
        return None,pd.DataFrame(),f'检索未完成：{type(error).__name__}。可先载入本地公开文献示例。'


def cached_for_ui():
    data=cached_papers()
    return data,pd.DataFrame(literature_table(data)),f'已载入{len(data["records"])}条缓存文献；检索日期及逐条状态见导出。'


def export_for_ui(physics,interval,conversion,batch,stats,literature):
    figures=[plot_pca(item) for item in (stats or {}).get('pca',[])]
    try:
        files=build_bundle(physics,interval,conversion,batch,stats,literature,figures)
        return *files,'报告已生成。CSV包含全部目标与排除状态；统计仅使用保留目标；未运行模块在报告中注明。'
    except Exception as error:
        return None,None,None,None,f'报告生成失败：{type(error).__name__}：{error}'
    finally:
        for fig in figures:
            plt.close(fig)
