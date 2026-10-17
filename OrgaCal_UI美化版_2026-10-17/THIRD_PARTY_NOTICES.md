# 第三方资料与署名

1. **Aiello等，2025，Increased reproducibility of brain organoids through controlled fluid dynamics**，DOI 10.1038/s44319-025-00619-x，[论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC12715241/)。4张示例图逐字节复制自用户下载的Source data Fig. 3，原始内部路径与SHA256见 `examples/source_manifest.json`；原图未修改，网页轮廓为本软件另行生成。作者EV1参数及关联索引保留来源。Europe PMC全文许可声明为CC BY 4.0，关联研究数据声明CC0（除另有标注的内容）；许可抓取记录见 `data/reference/paper_license.json`。本项目未将作者代码复制进计算模块。
2. **SLiMIA / The Spheroid Light Microscopy Image Atlas**，Scientific Data (2025)，[论文](https://www.nature.com/articles/s41597-025-04441-x)。OperaPhenix子集DOI [10.6084/m9.figshare.27390402.v1](https://doi.org/10.6084/m9.figshare.27390402.v1)，Figshare标注CC BY 4.0。原始24MB压缩包未纳入发布包；发布逐图验证数值、路径、哈希和统计结果。使用时请引用原论文及数据DOI。
3. **公开文献题录与证据定位**由Europe PMC API获取。缓存包含21条题录、规则提取的事实候选、短摘录、出处及核对状态，不包含整篇全文。转速和轨道尺寸需与设备及具体实验用途对应核查。
4. **依赖软件**独立安装，适用各自许可；本项目不将依赖包重新打包进代码仓库。主要依赖为Gradio、NumPy、Pillow、OpenCV、pandas、Matplotlib、ReportLab和requests。

研究论文中的生物学结论、文献CFD、软件单元测试、作者数据统计复算以及外部分割验证是不同证据类型，不能互相替代。
