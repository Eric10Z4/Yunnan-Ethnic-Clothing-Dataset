#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'生成符合学术规范与课程任务书要求的《计算机视觉》期中实验报告 Word 文档\n- 标题：面向生成式多模态视觉的云南少数民族服饰图像数据集构建与质量工程报告\n- 课程：云南大学软件学院 2026 春季学期《计算机视觉》期中大作业\n- 任课教师：黄珊珊\n- 课题负责人：邹弘辉 (学号: 20241120335)\n- 规范蓝白配色，标准学术三线表，图题“图X-X 标题”，嵌入真实统计图表\n\nOptional template generator. Published reports/slides may contain manual edits.\nGeneration requires an explicit draft output; this module does nothing on import.'

from pathlib import Path
from generator_cli import generation_args


def generate(project_root, output, figures_dir=None):

    import os
    from pathlib import Path
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn, nsdecls

    BASE_DIR = Path(project_root)
    REPORT_PATH = Path(output)
    FIG_DIR = Path(figures_dir)

    doc = docx.Document()

    # 页面边距设置 (标准 A4 页面，页边距 2.54 cm)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

        # 设置页眉
        header = section.header
        p_head = header.paragraphs[0]
        p_head.text = "云南大学软件学院 · 计算机视觉期中课程设计实验报告 | 民族服饰图像数据集构建 (YECID-1512)"
        p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for r in p_head.runs:
            r.font.name = "宋体"
            r._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(128, 128, 128)

    COLOR_PRIMARY = RGBColor(27, 60, 115)    # #1B3C73 经典学术深蓝
    COLOR_SECONDARY = RGBColor(63, 114, 175) # #3F72AF
    COLOR_TEXT = RGBColor(34, 34, 34)        # #222222 正文深灰黑
    COLOR_MUTED = RGBColor(100, 100, 100)    # #646464 图题次级文字

    def format_run(run, font_name="宋体", size_pt=10.5, bold=False, italic=False, color=COLOR_TEXT):
        run.font.name = font_name
        run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
        run.font.size = Pt(size_pt)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color

    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(text)
        format_run(r, font_name="黑体", size_pt=17, bold=True, color=COLOR_PRIMARY)
        return p

    def add_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(10)
        r = p.add_run(text)
        format_run(r, font_name="楷体", size_pt=11, color=COLOR_MUTED)
        return p

    def add_meta_info(info_dict):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(14)
        parts = [f"{k}：{v}" for k, v in info_dict.items()]
        r = p.add_run("   |   ".join(parts))
        format_run(r, font_name="宋体", size_pt=9.0, bold=True, color=COLOR_SECONDARY)
        return p

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, font_name="黑体", size_pt=13.5, bold=True, color=COLOR_PRIMARY)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, font_name="黑体", size_pt=11.5, bold=True, color=COLOR_SECONDARY)
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, font_name="黑体", size_pt=10.5, bold=True, color=COLOR_TEXT)
        return p

    def add_body(text, space_after=5, bold_prefix=None):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.first_line_indent = Inches(0.28) # 首行缩进 2 字符
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            format_run(r_pre, font_name="宋体", size_pt=10.0, bold=True, color=COLOR_TEXT)
        r = p.add_run(text)
        format_run(r, font_name="宋体", size_pt=10.0, bold=False, color=COLOR_TEXT)
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(2.5)
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            format_run(r_pre, font_name="宋体", size_pt=9.5, bold=True, color=COLOR_TEXT)
        r = p.add_run(text)
        format_run(r, font_name="宋体", size_pt=9.5, bold=False, color=COLOR_TEXT)
        return p

    def add_figure(img_path, caption_text, width_in=5.8):
        if not Path(img_path).exists():
            print(f"[Warning] Image not found: {img_path}")
            return
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(2)
        run = p_img.add_run()
        run.add_picture(str(img_path), width=Inches(width_in))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(8)
        r_cap = p_cap.add_run(caption_text)
        format_run(r_cap, font_name="宋体", size_pt=8.5, bold=True, color=COLOR_MUTED)

    def set_cell_border(cell, top=None, bottom=None, left=None, right=None):
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
        borders = {'top': top, 'bottom': bottom, 'left': left, 'right': right}
        for b_name, b_val in borders.items():
            if b_val:
                node = parse_xml(f'<w:{b_name} {nsdecls("w")} w:val="{b_val.get("val","single")}" w:sz="{b_val.get("sz","4")}" w:space="0" w:color="{b_val.get("color","auto")}"/>')
                tcBorders.append(node)
            else:
                node = parse_xml(f'<w:{b_name} {nsdecls("w")} w:val="none"/>')
                tcBorders.append(node)
        tcPr.append(tcBorders)

    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    print("Starting document synthesis...")

    # ==================== 封面与标题 ====================
    add_title("面向生成式多模态视觉的云南少数民族服饰图像数据集构建与质量工程报告")
    add_subtitle("云南大学软件学院 2026 春季学期《计算机视觉》期中大作业实验报告")
    add_meta_info({
        "课程": "计算机视觉 (2026春)",
        "任课教师": "黄珊珊",
        "组长": "邹弘辉 (20241120335)",
        "组员": "王毅豪、金明源、贾子钊",
        "数据集版本": "YECID-1512 (Commit: 363c8d2)"
    })

    # ==================== 一、实验任务选择与学术目标论证 ====================
    add_heading_1("一、 实验任务选择与学术目标论证")
    add_body(
        "根据《民族服饰图像数据集构建——计算机视觉期中实验任务书》要求，课题组在立项初期对图像分类、语义分割与图像生成三大任务方向开展了横向对比与技术可行性论证。",
        bold_prefix="1.1 三大任务方向综合权衡与选型依据："
    )
    add_bullet("图像分类方向（最低 3,000 组）：主要依赖粗粒度的整图标签，在多标签与细部剪裁（领型、开襟、银饰）表达上信息密度极低，且大样本量采集容易滑向低画质网络杂图的机械堆砌，难以体现高维视觉特征挖掘深度；", bold_prefix="方向一 图像分类：")
    add_bullet("语义分割方向（最低 1,000 组）：民族服饰具有层叠遮挡严重（如披肩、云肩、围腰、绑腿层叠）、刺绣与流苏边界模糊等复杂拓扑特性，通用分割模型（如 SAM、YOLO-seg）在未针对民俗专有形制微调的情况下，极易产生大量粘连断裂，难以达到学术级像素标注精度；", bold_prefix="方向二 语义分割：")
    add_bullet("图像生成方向（最低 1,500 组）：要求构建图像与细粒度结构化文本一一对应的配对数据集。不仅满足 Text-to-Image 生成模型（Diffusion、SDXL、FLUX 等）的微调需求，更能通过多模态特征对齐将中华民族传统非遗文化的深层服饰形制进行结构化知识沉淀，具有最高的学术含金量与多模态研究拓展价值。", bold_prefix="方向三 图像生成（课题组最终选定）：")
    add_body(
        "云南是我国少数民族种类最多的省份，各民族服饰保留了极其丰富的历史纹样、手工织锦、银饰锻造与独特剪裁形制。课题组立足本土特色，严选 10 个代表性世居民族（白族、傣族、哈尼族、景颇族、苗族、纳西族、藏族、佤族、彝族、壮族），确保数据集兼具视觉美学代表性与民俗学严谨性。",
        bold_prefix="1.2 云南世居少数民族特色与文化代表性："
    )

    # ==================== 二、数据集规模、类别定义与样本分布 ====================
    add_heading_1("二、 数据集规模、类别定义与样本分布")
    add_body(
        "数据集正式命名为 Yunnan Ethnic Clothing Image Dataset for Generation (YECID-1512)，最终固定交付 1,512 组严格质检通过的纯白底图文配对黄金样本，超额达成任务书规定的 1,500 组基准线。为了从物理机制上杜绝同源近重复泄漏，数据集采用整组同源不跨集（Group-aware Partitioning）的原则划分为训练集（1,063 组，70.30%）、验证集（223 组，14.75%）与测试集（226 组，14.95%）。",
        bold_prefix="2.1 样本规模与 Group-aware 划分架构："
    )

    # 插入标准三线表 表 2-1
    p_tcap = doc.add_paragraph()
    p_tcap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tcap.paragraph_format.space_before = Pt(6)
    p_tcap.paragraph_format.space_after = Pt(3)
    r_tcap = p_tcap.add_run("表 2-1  YECID-1512 数据集民族类别分布与子集划分物理统计表")
    format_run(r_tcap, font_name="宋体", size_pt=9.0, bold=True, color=COLOR_PRIMARY)

    table_data = [
        ["序号", "民族名称 (中文)", "英文名称", "训练集 (Train)", "验证集 (Val)", "测试集 (Test)", "总计样本量", "占比 (%)"],
        ["1", "苗族", "Miao", "187", "35", "41", "263", "17.39%"],
        ["2", "傣族", "Dai", "175", "37", "37", "249", "16.47%"],
        ["3", "藏族", "Tibetan", "143", "31", "29", "203", "13.43%"],
        ["4", "彝族", "Yi", "139", "29", "30", "198", "13.10%"],
        ["5", "壮族", "Zhuang", "128", "28", "27", "183", "12.10%"],
        ["6", "白族", "Bai", "97", "21", "21", "139", "9.19%"],
        ["7", "纳西族", "Naxi", "81", "17", "18", "116", "7.67%"],
        ["8", "佤族", "Wa", "72", "16", "15", "103", "6.81%"],
        ["9", "景颇族", "Jingpo", "21", "5", "4", "30", "1.98%"],
        ["10", "哈尼族", "Hani", "20", "4", "4", "28", "1.85%"],
        ["-", "总计 (Total)", "All 10 Groups", "1,063", "223", "226", "1,512", "100.00%"]
    ]

    tbl = doc.add_table(rows=len(table_data), cols=8)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    border_thick = {'val': 'single', 'sz': '12', 'color': '1B3C73'} # 1.5 pt
    border_thin = {'val': 'single', 'sz': '6', 'color': '1B3C73'}   # 0.75 pt

    col_widths = [Inches(0.4), Inches(1.1), Inches(0.9), Inches(0.85), Inches(0.8), Inches(0.8), Inches(0.9), Inches(0.8)]

    for r_idx, row in enumerate(tbl.rows):
        is_header = (r_idx == 0)
        is_footer = (r_idx == len(table_data) - 1)
        for c_idx, cell in enumerate(row.cells):
            cell.width = col_widths[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(2.5)
            p.paragraph_format.space_after = Pt(2.5)
            r = p.add_run(table_data[r_idx][c_idx])

            if is_header:
                format_run(r, font_name="黑体", size_pt=8.5, bold=True, color=COLOR_PRIMARY)
                set_cell_background(cell, "EBF2FA") # 浅蓝底色
                set_cell_border(cell, top=border_thick, bottom=border_thin)
            elif is_footer:
                format_run(r, font_name="黑体", size_pt=8.5, bold=True, color=COLOR_PRIMARY)
                set_cell_background(cell, "F0F4F8")
                set_cell_border(cell, top=border_thin, bottom=border_thick)
            else:
                format_run(r, font_name="宋体", size_pt=8.5, color=COLOR_TEXT)
                set_cell_border(cell, top=None, bottom=None)

    # 插入图 2-1
    add_figure(
        FIG_DIR / "fig1_ethnicity_split_distribution.png",
        "图 2-1  YECID-1512 数据集民族类别分布与子集划分堆叠统计图",
        width_in=5.8
    )

    add_body(
        "在实际构建过程中，各民族存世与数字化资源的非均匀性是客观存在的文化遗产保护现状。例如，苗族（263 组）、傣族（249 组）服饰因视觉色彩鲜明、银饰繁复，在数字博物馆与摄影展中具有丰富的存量；而景颇族（30 组）、哈尼族（28 组）的高分辨率正视成套展品相对稀缺。课题组严格尊重现实客观分布，拒绝采用机械复制或降低标准的方式凑数。同时，明确指出任务书第 4 页中关于“类别间比例建议控制在 2:1 以内”系针对图像分类方向（方向一）防止分类器偏置的基准建议，不可直接误作为图像生成多模态图文对的硬门槛。在生成任务中，关键在于图文描述的细粒度可核验性与单主体构图规范。",
        bold_prefix="2.2 客观现实长尾分布与任务书指导口径辨析："
    )

    add_body(
        "主集图像文件命名采用四位数字标识（0001.jpg ~ 1514.jpg）。在终审严谨性复核中，课题组主动将两张有瑕疵的边界样本（0803 彝族边缘特写、1166 苗族独立绣片）移出主集，移至 dataset/excluded_samples/final_cleanup_0803_1166/ 妥善归档留痕。依据工业级数据集管理规范，空缺编号保持自然留空，绝不将后续样本向前覆盖重排，从而保证全生命周期数据哈希台账的不可篡改性与可回溯性。",
        bold_prefix="2.3 主集 ID 编号策略与归档留痕机制："
    )

    # ==================== 三、全流程前端构建流水线与工程实现 ====================
    add_heading_1("三、 全流程前端构建流水线与工程实现（邹弘辉 独立 + 王毅豪 协同）")
    add_body(
        "本章涵盖数据集从原始采集到黄金候选集收敛的完整前端工程闭环。由组长邹弘辉负责总体工程架构设计，并独立攻坚完成阶段 1（多源合法采集）、阶段 2（六级漏斗过滤去重）与阶段 3（主体分割与白底标准化）；阶段 4（双图严格 VLM 质检）由邹弘辉主导、王毅豪协同完成；最后由邹弘辉完成三轨受控标注体系的顶层架构设计。",
        bold_prefix="3.1 前端工程架构全景与职责概览："
    )

    # 插入图 3-1 漏斗图
    add_figure(
        FIG_DIR / "fig2_quality_funnel.png",
        "图 3-1  民族服饰数据集全流程质量清洗与精炼漏斗图 (Quality Funnel)",
        width_in=5.6
    )

    add_heading_2("3.2 阶段一：全网多源合法采集与全景元数据溯源建账（01_crawl_and_source.py）")
    add_body(
        "真实性与合法可溯源是学术数据集的基石。课题组面向中国非遗数字化网、各大国家级与省市级数字博物馆公开馆藏（如云南省博物馆公开档案）及高分辨率摄影图库，编写并部署自动化爬虫流水线 code/01_crawl_and_source.py 与 crawl_6000_batch.py，定向采集原始图像共计 6,259 张。\n"
        "为了彻底杜绝无源图像与版权隐患，每张采集样本在入库瞬间均强制记录 12 项全景元数据字段，包括：样本临时 ID、原始文件名、中英文民族归属、采集渠道、原始图像直链（image_url）、原始发布页面 URL（source_page_url）、藏品标题、发布机构与馆藏单位、版权许可协议、采样时间戳以及基于页面聚集的 group_id，实时固化为 raw_metadata.csv。所有样本均具备独立合法的公开溯源依据，从源头上杜绝伪造与无法核验数据。"
    )

    add_heading_2("3.3 阶段二：六级漏斗过滤与感知哈希去重算法工程（02_clean_and_dedup.py）")
    add_body(
        "针对海量网络原始采集中普遍存在的坏损、低清、虚焦与近重复图像，课题组自主研发了具备六级级联拦截机制的过滤算法流水线 code/02_clean_and_dedup.py，逐层执行硬性量化检验：\n"
        "1. 图像解码与结构完整性校验：利用 PIL 与 OpenCV 双解码引擎，拦截文件不完整、头部损坏（Truncated）、空字节（0 字节）及非 RGB 空间图像；\n"
        "2. 几何分辨率硬性门槛：设定短边 min(w, h) >= 220 像素，剔除过小缩略图，确保后续超分辨率特征提取与生成模型微调的视觉信息保真度；\n"
        "3. 单色块方差过滤：计算灰度通道亮度标准差 std(L) >= 15.0，自动过滤大面积空白占位图、纯白纯黑空图或大面积纯色几何块；\n"
        "4. 统一归一化拉普拉斯方差清晰度过滤：对图像缩放至统一尺度后计算拉普拉斯算子卷积响应方差 Var(Laplacian) >= 45.0，对因失焦、高速运动模糊或低分辨率双线性插值伪高频的图像实施硬性拦截；\n"
        "5. 像素级 MD5 精确查重：计算原始字节与像素哈希，彻底剔除跨目录同源重复下载；\n"
        "6. 32×32 DCT 感知哈希 (pHash) 语义查重：提取频域低频离散余弦系数构造 64 位鲁棒指纹，计算汉明距离（Hamming Distance）。当 Hamming <= 5 时判定为近重复图像（涵盖微小旋转、轻度裁切、调色滤波或加减水印变体），执行保守去重。\n"
        "六级漏斗累计安全拦截剔除 835 张低质与重复样本，留存 5,424 张高质图，剔除原因、被裁定参数与样本 ID 均完整记录至 exclusion_log.csv，做到每一张废弃样本去向明确。"
    )

    add_heading_2("3.4 阶段三：Rembg 主体分割与 512×512 纯白标准化（03_subject_seg_and_pad.py）")
    add_body(
        "任务书明确要求图像生成方向必须提交 512×512 纯白底标准化图像。为实现复杂民俗服饰的高精度前景提取，课题组编写部署 code/03_subject_seg_and_pad.py 与 03_process_all_cleaned.py：\n"
        "1. 显著性服饰分割：基于 Rembg U2Net 深度显著性目标检测网络提取单件服饰或单人穿着前景 Alpha 掩码，彻底剥离复杂的博物馆展柜、展台支架、背景阴影及外景杂物；\n"
        "2. 等比保真缩放：严格锁定图像原始长宽比进行双三次插值缩放，坚决禁止非等比拉伸导致的服饰形制、领口或裙幅比例畸变；\n"
        "3. 居中度与尺度硬性约束：断言前景主体较长边占 512×512 画布的比例严格落在 70% ~ 88% 之间（超额达成任务书 >= 60% 指标）；通过计算前景二值轮廓质心与画布中心几何偏移，确保水平与垂直位移偏差 <= 10%；\n"
        "4. 纯白画布合成：其余背景区域统一填充标准纯白 RGB(255, 255, 255)，无缝输出 512×512 RGB 标准成衣图像。"
    )

    add_heading_2("3.5 阶段四：双图联合严格 VLM 质检与人工双盲初筛（03_strict_dual_vlm_qc.py，邹弘辉+王毅豪）")
    add_body(
        "为彻底解决“图像虽然白底居中，但服饰主体存在民俗错误或分割残断”的深层隐患，课题组由邹弘辉主导设计双图联合审查架构，与王毅豪协同部署运行 code/03_strict_dual_vlm_qc.py 批量质检流水线。\n"
        "质检系统突破性地将【图 A：未裁剪原始图】与【图 B：512 处理后白底图】成对同时送审多模态视觉模型。原图用于判定拍摄背景、民族语境与原始姿态；白底图用于判定边缘透明度、截断缺陷与抠图锯齿。系统硬性实施“六大一票否决红线”：\n"
        "• 否决项 1 NOT_REAL_PHOTO：拦截手绘插画、漫画线稿、数码设计图或 3D 渲染图；\n"
        "• 否决项 2 FACE_ONLY_NO_CLOTHING：拦截人脸局部特写或缺少服饰主体的自拍照；\n"
        "• 否决项 3 NOT_GARMENT：拦截独立风景、布料样卡、建筑局部或非服装展品；\n"
        "• 否决项 4 INVALID_ETHNIC_COSTUME：拦截现代影楼戏服、常服或跨民族误标样本；\n"
        "• 否决项 5 MULTI_PERSON：拦截多人合影、群舞抓拍或拼贴画；\n"
        "• 否决项 6 BAD_SEGMENTATION：拦截断头断手、悬空残缺、大块展柜暗斑残余或主体裁损样本。\n"
        "双图联合质检累计拦截 4,979 张瑕疵样本，精准留存 1,765 张初筛候选；王毅豪与邹弘辉进一步开展人工双盲交叉复核，剔除腹部镂空、边缘悬挂等边界残次，将高质量成衣集收敛至 1,514 组。"
    )

    add_heading_2("3.6 面向多模态生成的“三轨受控标注体系”顶层架构设计（邹弘辉）")
    add_body(
        "针对图像生成任务对文本细粒度结构化的高维需求，课题组长邹弘辉完成了“三轨受控标注体系”的顶层数据架构设计，使数据集兼具课程评测兼容性与学术研究前沿性：\n"
        "• 轨一（官方标准交付轨 captions.jsonl）：严格限定于任务书规定的 7 个顶层字段（image_id, file_path, ethnicity, top, bottom_or_dress, headwear, caption）及 top 下 4 个基础字段（has_top, color, pattern, sleeve_length），保证评测脚本 100% 顺畅执行；\n"
        "• 轨二（学术细粒度扩展轨 extended_fine_grained_attributes.jsonl）：解耦记录深层非遗剪裁特征，覆盖领型（立领、交领、圆领）、开襟方式（斜襟、对襟、右衽）、下装形制（筒裙、百褶裙、宽松长裤）、头饰细分类型（银冠、头帕、编织帽）以及面料材质证据链；\n"
        "• 轨三（一体化合并大表轨 captions_merged_full.jsonl）：深层嵌套融合前两轨全部视觉属性，为下游 Text-to-Image / LoRA 生成模型提供即插即用的全模态特征基准。"
    )

    # 插入图 3-2 结构属性分布图
    add_figure(
        FIG_DIR / "fig3_attribute_distribution.png",
        "图 3-2  YECID-1512 细粒度核心结构属性（领型、开襟、袖长、下装、头饰）分布统计图",
        width_in=6.0
    )

    # ==================== 四、数据集构建核心技术攻关与语义反幻觉体系 ====================
    add_heading_1("四、 数据集构建核心技术攻关与语义反幻觉体系（金明源 负责）")
    add_body(
        "本章涵盖阶段 5（构建数据集与标注工程实施）。由金明源负责部署并运行 V2 受控标注管道（code/04_v2_annotation_pipeline.py），重点攻关同源防泄漏切分、受控词表防串位、部件解耦及面料反幻觉穿透等核心工程难点，并完成三轨与元数据全量导出。",
        bold_prefix="4.1 数据集构建核心职责概述："
    )

    add_heading_2("4.2 同源跨集数据泄漏 (Data Leakage) 根治与 1,144 个全域 Grouping 划分")
    add_body(
        "同源数据跨子集泄漏是视觉生成任务微调评测中的致命缺陷。若同组摄影或同一网页的相似样本分别流入训练集与测试集，模型评估将产生虚假繁荣。金明源在工程实现中彻底攻克了该难题：\n"
        "1. 废除域名硬编码特判：坚决删除早期版本中仅针对特定域名的特判逻辑，对所有外链、图库及文博域名一律执行无差别同源追溯；\n"
        "2. 建立强连通 Group 划分体系：提取每张图片的原始网页 source_page_url 与拍摄图集特征，全局连通聚类生成 1,144 个互不相交的独立 group_id，实施整组分层切分。确保同一图集或拍摄组的所有关联样本完整分配至同一子集，达成跨集同源泄漏 0 违规。"
    )

    add_heading_2("4.3 受控词表防串位与部件存在性逻辑解耦（19 条重点复核）")
    add_body(
        "在多模态打标初期，全局子串匹配容易引发词表串位（例如将 headdress 误推为 dress，或将 side-tassel 误推为 side-buttoned）。同时，极易将 pattern=none 机械误判为‘无上衣’。金明源在标注工程中实现了精细解耦：\n"
        "1. 独立字段封闭归一化：为领型、开襟、袖长、下装、头饰 5 大字段分别实现独立的封闭归一化函数，严禁跨字段串位；\n"
        "2. 部件存在性解耦与定向复核：严格将部件存在性（是否有上衣）与属性值（是否有绣纹）解耦。素色无绣花上衣如实记录为 pattern: 'solid color'，唯有确认画面为纯裙装或独立配饰展品时才置为 none。在排查历史因规则粗暴导致的 19 条重点样本中，逐图人工复核，精准恢复了 16 条可见上衣（如无袖上衣、抹胸、刺绣马甲、可见上身衣身等，规范标注可见颜色、纹样及袖长，袖长无法完整确认时标注 unknown，无袖标注 sleeveless），并对另外 3 条确属独立背饰或独立配饰的样本保留无上衣标注（has_top: false），彻底纠正了部件逻辑偏差。"
    )

    add_heading_2("4.4 面料材质 E1/E2/E3 三级证据体系与 Caption 反幻觉穿透")
    add_body(
        "服饰面料纤维（如真丝、纯棉、羊毛、天鹅绒）仅凭外观视觉极难准确分辨，强行推断属于严重的大模型视觉幻觉。课题组遵照任务书‘无法核实的信息标为未知，不得臆测’的学术原则，建立三级证据体系：\n"
        "• E1 级：原始发布页面或官方博物馆档案明确记载材质规格（如明文标注‘纯手工羊毛’、‘真丝织锦’）；\n"
        "• E2 级：可靠文博机构文献或非遗权威典籍可精确对照确认该服饰材质；\n"
        "• E3 级：仅有普通视觉外观，无明文材质档案，强制标注为 material: 'unknown'。\n"
        "更为重要的是，金明源实现了长句 Caption 反幻觉穿透机制，当材质为 unknown 时，通过正则过滤算法将自然语言描述中的 wool、silk、velvet、satin 等假定词彻底替换为 neutral 描述（如 thick woven fabric、lustrous fabric），杜绝了‘属性表 unknown 而长句凭空臆测’的表里不一缺陷。"
    )

    add_heading_2("4.5 数据集三轨文件与全量元数据自动化批量导出实现")
    add_body(
        "金明源完成了 code/04_v2_annotation_pipeline.py 的工业化导出改造，并在 code/05_export_metadata_and_qc.py 中实现自动化元数据映射与封装。\n"
        "在导出过程中，系统强制同步输出 captions.jsonl、extended_fine_grained_attributes.jsonl、captions_merged_full.jsonl、metadata.csv 及 dataset_manifest_mapped.json，确保全库样本 ID 严格对齐、字段完全受控、JSON 序列化严格合规。"
    )

    # ==================== 五、质量审计门禁体系与全方位验证结果 ====================
    add_heading_1("五、 质量审计门禁体系与全方位验证结果（贾子钊 负责）")
    add_body(
        "本章涵盖阶段 6（质量门禁审计与系统核验）。由贾子钊负责部署运行全能质量审计门禁（code/04_quality_audit.py），编写并运行生产函数离线单元测试与变体测试，执行 39 项反例与深层边界硬性拦截，以及负责样本 1120 修复可复现材料核查与 0803/1166 排除归档验收。",
        bold_prefix="5.1 质量核验核心职责概述："
    )

    add_heading_2("5.2 全能质量审计门禁实测 (code/04_quality_audit.py)")
    add_body(
        "为了确保交付数据的高质量与零缺陷，贾子钊部署并执行了自动化多维质量门禁：\n"
        "1. 五轨深度交叉核验：对 captions.jsonl、extended_fine_grained_attributes.jsonl、captions_merged_full.jsonl、metadata.csv、dataset_manifest_mapped.json 按 image_id 严格比对 ID 集合、记录数、相对路径、民族一致性及嵌套字段对齐度，杜绝行序依赖与重复 ID 字典覆盖；\n"
        "2. 全字段受控词表防线：硬性断言领型、开襟、袖长、下装、头饰五大词表，非法值直接报错退出；\n"
        "3. 全域名跨集防泄漏检测：扫描全部来源直链、页面 URL 及 group_id，若同源图片跨入不同 split 立即触发非零退出；\n"
        "4. 全量实测结论：运行 python code/04_quality_audit.py --full，全量 1,512 条记录实现 Violations: 0，安全通过，CLI 退出码 exit 0。"
    )

    add_heading_2("5.3 生产标注管道 10 项离线单测实测")
    add_body(
        "贾子钊编写并运行了 code/test_pipeline_offline.py，在断开外网环境下通过 mock 真实调用 process_batch 生产函数，设计 10 项严苛单测，覆盖了无上衣处理、素色上衣 pattern 归一化、乱序 index 自动归位、重复/缺失/越界 index 拦截、空字典 official_top 拦截、以及针对 JSON null (pattern: null, sleeve: null) 的严格防守。实测 10 项测试全部 OK（Ran 10 tests in 0.004s, exit 0），确保生产流水线具备极高的鲁棒性。"
    )

    add_heading_2("5.4 独立验收测试套件全量硬性拦截实测")
    add_body(
        "在隔离测试夹具中，贾子钊全量验证了独立对抗测试套件的拦截表现：\n"
        "• 既定 39 项反例测试（challenge_gate.py 及 check_missing_meta.py）：涵盖样本不足 1500、图片未解码、坏图、尺寸非 512、非 RGB、重复 ID、非法 URL、空发布者、跨集泄漏、词表越界、空属性、中文 Caption、材质假断言等 39 类单故障用例，实测拦截率 100%（39 met expectations, exit 非零），基线安全放行；\n"
        "• 3 大主要深层边界（targeted_followups.py）：深层 Merged 属性错配拦截率 100%、合法民族跨轨冲突拦截率 100%、空视觉对象拦截率 100%；\n"
        "• 16 个异常视觉变体与 2 个合法对照测试（check_visual_variants.py）：16 个异常视觉变体（缺少 has_top、空字典 official_top、JSON null 字段等）均准确触发 RETRY 并持久化进入重试队列；2 个合法对照样本正常处理成功，实现 100% 预期断言通过。"
    )

    add_heading_2("5.5 样本 1120 局部清理确定性复现核查与 0803/1166 排除归档验收")
    add_body(
        "贾子钊负责对重点存疑样本与终审排除样本实施专项核验与材料复现归档：\n"
        "1. 样本 1120 修复复现核验：此前独立审计将 1120（Dai_wiki_16053360.jpg）误判为帽子，审计方撤回错误意见后，课题组恢复其双长袖与筒裙。贾子钊核验了针对 512×512 画面左袖下方（x105–215、y76–112）残留展柜暗斑的清理脚本 code/clean_1120_cuff.py 与局部掩码（1120_cuff_cleanup_mask.png），确认将 1,474 个灰黑残底像素精准合成为纯白，修后图像 SHA256 为 91a6bee95e746c7fa2393a3cf2ea083d6849e63272abdf1302e05db7dae80ff0，复现包 dataset/reproducible_1120/ 齐全有效；\n"
        "2. 终审排除样本归档核验：对 0803（彝族局部边缘特写）与 1166（苗族独立绣片）进行排查，确认不符合完整服饰成衣规范，核验其移入 dataset/excluded_samples/final_cleanup_0803_1166/ 归档目录，原图原标注全量留存，主集四位数字 ID 保持自然空缺，保证主集 1,512 组完全纯金。"
    )

    # 插入图 4-1 样本 1120 修复图
    add_figure(
        FIG_DIR / "fig4_sample_1120_repair.png",
        "图 5-1  样本 1120 傣族长袖成衣展品局部残底清理 4x 放大侧向对比图",
        width_in=5.8
    )

    # ==================== 六、局限性诚实声明、学术反思与后续展望 ====================
    add_heading_1("六、 局限性诚实声明、学术反思与后续展望")
    add_body(
        "遵循科学严谨的学术道德规范，课题组在此对本数据集的客观局限性做出实事求是的声明：\n"
        "1. 物理面料纤维检测局限：全量 1,512 组样本均来源于公开数字博物馆馆藏、历史影像档案与实景拍摄，未对实物纤维执行实验室化学破坏性燃烧或溶解检测。除少数官方馆藏档案明确记载面料外，其余样本一律如实标注为 E3 / unknown，坚决杜绝根据肉眼臆测；\n"
        "2. 自动化工程门禁与实地田野盲审边界：程序门禁全部通过证明了数据集在 Schema 结构规范性、数值约束、词表受控与跨集防泄漏等工程维度达到了零缺陷交付标准。这不代表全库 1,512 张图像中全部微小民俗刺绣图案均已经过民俗专家的实地田野逐项考察；\n"
        "3. 主集 ID 自然空缺：为了保障数据快照哈希链条的严肃性，主集 ID 保持客观不连续（0803 与 1166 留空），后续研究直接通过 image_id 或路径读取即可，无任何冗余副作用；\n"
        "4. 后续应用展望：本数据集的三轨结构与规范白底非常适合作为 LoRA 或 ControlNet 细粒度民族服饰生成模型的训练基准，未来可进一步拓展引入多视角三维人体网格与民俗穿戴时序拓扑。",
        space_after=6
    )

    # ==================== 七、团队成员分工与贡献说明 ====================
    add_heading_1("七、 团队成员分工与贡献说明")
    add_body(
        "根据任务书表 3 第 6 项要求，课题组四名成员各司其职、全链路深度协同，具体分工职责、负责阶段、对应报告章节与贡献比例如下：",
        space_after=4
    )

    p_tcap_team = doc.add_paragraph()
    p_tcap_team.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tcap_team.paragraph_format.space_before = Pt(4)
    p_tcap_team.paragraph_format.space_after = Pt(3)
    r_tcap_team = p_tcap_team.add_run("表 7-1  期中大作业团队成员分工与核心贡献映射表")
    format_run(r_tcap_team, font_name="宋体", size_pt=9.0, bold=True, color=COLOR_PRIMARY)

    team_table_data = [
        ["成员姓名", "学号", "团队角色", "负责工作阶段与核心贡献模块", "对应报告章节", "贡献比例"],
        ["邹弘辉", "20241120335", "课题组长 / 总架构师", "负责全链路工程总体架构设计；独立负责阶段 1（多源合法采集与 raw_metadata.csv 建账）、阶段 2（六级漏斗过滤去重算法 02_clean_and_dedup.py）与阶段 3（Rembg 主体分割与 512×512 纯白标准化）；主导并协同王毅豪完成阶段 4 双图 VLM 质检；主导“三轨受控标注体系”顶层架构设计；期中实验 Word 报告与图表主笔。", "第一、二、三、六章", "35%"],
        ["王毅豪", "20241060109", "质检工程师", "与邹弘辉协同负责阶段 4（双图联合严格 VLM 质检）；负责部署并运行 03_strict_dual_vlm_qc.py 批量质检流水线；执行六大一票否决红线人工双盲复审，严格拦截非实拍、多人合影、拼图及残损样本，初筛收敛候选集。", "第 3.5 节", "20%"],
        ["金明源", "2024160148", "数据工程与标注负责人", "负责阶段 5（构建数据集与标注工程实施）；搭建并运行 V2 受控标注管道 (04_v2_annotation_pipeline.py)；实现五大字段受控词表封闭归一化与部件解耦逻辑（完成 19 条重点复核）；落实 E1/E2/E3 材质分级证据体系与 Caption 反幻觉穿透；同步导出三轨标注与 metadata.csv。", "第四章", "25%"],
        ["贾子钊", "20241120136", "测试与质量核验负责人", "负责阶段 6（质量门禁审计与系统核验）；部署运行全能质量审计门禁 (04_quality_audit.py)，执行五轨交叉核验与全域名跨集防泄漏扫描；编写并运行离线单元测试（10 项通过）与变体测试（16 变体 RETRY，对照成功）；负责样本 1120 局部清理复现核查与 0803/1166 排除归档验收。", "第五章", "20%"]
    ]

    tbl_team = doc.add_table(rows=len(team_table_data), cols=6)
    tbl_team.alignment = WD_TABLE_ALIGNMENT.CENTER
    team_col_widths = [Inches(0.7), Inches(0.95), Inches(1.1), Inches(2.2), Inches(0.85), Inches(0.55)]

    for r_idx, row in enumerate(tbl_team.rows):
        is_header = (r_idx == 0)
        for c_idx, cell in enumerate(row.cells):
            cell.width = team_col_widths[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx not in (3, 4) else (WD_ALIGN_PARAGRAPH.LEFT if c_idx==3 else WD_ALIGN_PARAGRAPH.CENTER)
            p.paragraph_format.space_before = Pt(2.5)
            p.paragraph_format.space_after = Pt(2.5)
            r = p.add_run(team_table_data[r_idx][c_idx])

            if is_header:
                format_run(r, font_name="黑体", size_pt=8.0, bold=True, color=COLOR_PRIMARY)
                set_cell_background(cell, "EBF2FA")
                set_cell_border(cell, top=border_thick, bottom=border_thin)
            else:
                format_run(r, font_name="宋体", size_pt=8.0, color=COLOR_TEXT)
                bottom_b = border_thick if r_idx == len(team_table_data)-1 else None
                set_cell_border(cell, top=None, bottom=bottom_b)

    print("Document content ready. Saving to file...")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(REPORT_PATH)
    print(f"Generated draft Word report: {REPORT_PATH}")


def main():
    args = generation_args(__file__, 'Word report template', directory=False, suffix='.docx')
    generate(args.project_root, args.output, args.figures_dir)


if __name__ == "__main__":
    main()
