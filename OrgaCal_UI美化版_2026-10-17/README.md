# OrgaCal · 境算师

**算剪切 · 找安全区 · 量形状**

面向类器官轨道摇床培养的“参数计算 + 形态一致性”网页工作台。培养前比较参数及假设，培养后核对图像与批次分布。

## 最新界面

按最新版申报书及附图册图3整合科研工作台：海军蓝顶栏、青绿主色，桌面左侧导航、输入与结果分栏；手机为两行导航和单列内容。

五类功能为“剪切预算、转速换算、形态量化、文献条件、条件筛选”，综合报告另有独立入口。公式、识别设置、元数据和长篇说明可展开查看。结果仅在计算后显示，演示数据与作者原始数据保留明确标签。

最新方案中的旋转腔、机械扰动分项、CV/ICC、PDF导入及目标形态代理模型尚未完整实现；本次界面升级不代表这些模型已获验证。界面设计与核对记录见 `docs/界面升级说明.md`。

## 已接入的功能

| 功能 | 内容 |
| --- | --- |
| 算剪切 | 输入轨道直径、转速、容器、液量、动力黏度，输出液深尺度剪切估算、完整参数和假设 |
| 找区间 | 剪切上界与悬浮、氧供给下界取交集；处理无交集、内部扩散受限和缺参，提供Δρ×Q敏感性 |
| 转速换算 | 等模型剪切、等轨道线速度、等轨道加速度；界面明示准则 |
| 量形状 | 单图与多图候选分割、人工排除、比例尺、面积/周长/等效直径/平均轮廓半径/Feret/实心度、分层MAD与PCA |
| 查文献 | Europe PMC检索及开放全文证据提取，21条本地参考记录，保留出处、文本范围及核对状态 |
| 报告 | CSV、JSON、Markdown、PDF与ZIP；保留失败记录、参数、比例尺及PCA拟合参数 |

**证据边界：** 物理部分为未校准情景模型；条件可行区间不是实验安全保证。图像为传统CV候选轮廓，需人工核对。论文EV1参数用于统计演示，不能作为本项目从图像复现了所有论文指标的证明。

## 本地运行

已测试环境：Windows、Python 3.13。锁定依赖要求Python至少3.12。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

打开 `http://127.0.0.1:7860`。已有虚拟环境时，可双击 `启动OrgaCal.bat`。

Linux或macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

不需要GPU、商业API或大模型密钥。在线文献检索需要可访问Europe PMC；本地缓存与其他功能可离线运行。

## 三分钟演示

1. “剪切预算”：用演示参数计算，展开读完假设；输入自己的条件时重新计算。
2. “条件筛选”：点“载入假设算例”，再计算条件区间。此页沿用剪切预算的设备条件；演示阈值和速度系数并非实验推荐。
3. “转速换算”：选择明确准则，比较25 mm与19 mm轨道直径的换算结果。
4. “形态量化/批量与一致性报告”：载入4张论文图，查看失败与候选；第二张图中的气泡可按编号排除。未知比例尺保留为空。
5. 载入论文EV1参数并生成统计，展示分层MAD/PCA；它与本程序的图像测量结果分开。
6. 载入公开文献示例，最后生成综合报告。未运行模块会注明，下载文件为生成时的快照。

## 批量元数据

模板见 `examples/batch_metadata.csv`。image列必须与原始图片文件名一致，同批同名文件会拒绝。支持batch、condition、day、imaging_batch、microscope、magnification、um_per_pixel。

逐图比例尺优先；否则仅在用户确认同成像条件时使用共用比例尺；都未提供则保留px。面积单位为px²或um²，长度为px或um，Circularity及Solidity无单位。不同单位、时间和成像批次分层统计；成像信息未提供会保留该状态。

## 已完成的验证

- 自动检查覆盖数值单位、条件约束、换算、几何、MAD、PCA、校验与原有功能。
- 论文EV3/EV4的**180条**MAD记录与 `median(abs(x−median(x)))/abs(median(x))` 一致，不乘1.4826。网页以百分数显示，即表中比例×100。
- SLiMIA OperaPhenix全部**59张**非标尺图，固定阈值设置，无人工排除、无标签调参：前景平均IoU **0.8633**，平均Dice **0.9228**。这是一个显微镜、4种细胞系的球体图像结果；不是逐实例准确率，也不代表脑类器官培养验证。
- 剪切→区间→换算→论文统计→文献→报告的服务接口已联调。物理流场、自有培养实验及真实平台部署还需分别核验。

逐条结果：`data/reference/mad_validation.json`、`segmentation_validation.json`。计算定义、限制和验证记录见 `docs/`。

```bash
python -m unittest discover -s tests -v
```

额外复算论文Excel时：`pip install -r requirements-dev.txt`，再运行 `python scripts/validate_paper_mad.py --source-dir <原始资料目录>`。运行外部分割验证：`python scripts/validate_slimia.py <OperaPhenix.zip> --output-dir <输出目录>`。

## 魔搭与GitHub

`app.py`暴露全局`demo`对象；提供Dockerfile和完整依赖。推荐Python3.13的CPU容器，端口7860。魔搭Gradio模式应选择支持Python≥3.12及当前Gradio版本的基础环境；若基础环境不匹配，使用Docker模式。具体操作和账号前提见 `docs/部署与提交.md`。

本仓库不含个人认证文件、访问令牌或虚拟环境。报告不通过Git提交。代码许可证由团队决定；第三方数据许可与出处单独列在 `THIRD_PARTY_NOTICES.md`。

主要数据：[Aiello等（2025）](https://pmc.ncbi.nlm.nih.gov/articles/PMC12715241/)；外部分割基准：[SLiMIA论文](https://www.nature.com/articles/s41597-025-04441-x)、[OperaPhenix子集](https://doi.org/10.6084/m9.figshare.27390402.v1)。
