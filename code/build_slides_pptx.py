#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成符合答辩要求的计算机视觉期中实验汇报 PPT (8页经典学术排版)
- 汇报时长：5-7 分钟
- 包含任务目标、流程、代码、数据统计、标注示例、质检人机闭环、难点与分工
"""

import os
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BASE_DIR = Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
PPTX_PATH = BASE_DIR / "report" / "slides" / "计算机视觉期中实验汇报_民族服饰数据集构建.pptx"
FIG_DIR = BASE_DIR / "report" / "figures"
PPTX_PATH.parent.mkdir(parents=True, exist_ok=True)

prs = Presentation()
prs.slide_width = Inches(13.333) # 16:9
prs.slide_height = Inches(7.5)

# 颜色定义
DARK_BLUE = RGBColor(27, 60, 115)
ACCENT_BLUE = RGBColor(41, 128, 185)
LIGHT_BG = RGBColor(245, 247, 250)
TEXT_DARK = RGBColor(33, 33, 33)
TEXT_MUTED = RGBColor(100, 100, 100)
WHITE = RGBColor(255, 255, 255)
GREEN = RGBColor(46, 125, 50)

def add_header(slide, title_text, category_text="计算机视觉期中实验答辩 · 图像生成方向"):
    # Header banner
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.1))
    shape.fill.solid()
    shape.fill.fore_color.rgb = DARK_BLUE
    shape.line.color.rgb = DARK_BLUE
    
    tf = shape.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.8)
    
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.name = "Microsoft YaHei"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = WHITE
    
    # Sub-category on right
    tx_box = slide.shapes.add_textbox(Inches(7.5), Inches(0.2), Inches(5.0), Inches(0.7))
    tf2 = tx_box.text_frame
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.RIGHT
    p2.text = category_text
    p2.font.name = "Microsoft YaHei"
    p2.font.size = Pt(11)
    p2.font.color.rgb = RGBColor(180, 205, 240)

def create_card(slide, left, top, width, height, title, content_lines, border_color=ACCENT_BLUE):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = border_color
    card.line.width = Pt(1.5)
    
    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    
    # Card Title
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Microsoft YaHei"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = DARK_BLUE
    p.space_after = Pt(8)
    
    # Content lines
    for line in content_lines:
        p_c = tf.add_paragraph()
        p_c.text = line
        p_c.font.name = "Microsoft YaHei"
        p_c.font.size = Pt(11)
        p_c.font.color.rgb = TEXT_DARK
        p_c.space_after = Pt(4)
        p_c.line_spacing = 1.2

# ----------------- SLIDE 1: 封面 -----------------
slide_layout = prs.slide_layouts[6] # Blank
slide1 = prs.slides.add_slide(slide_layout)

bg1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg1.fill.solid()
bg1.fill.fore_color.rgb = DARK_BLUE
bg1.line.color.rgb = DARK_BLUE

# Title Box
tbox1 = slide1.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(11.0), Inches(3.2))
tf1 = tbox1.text_frame
tf1.word_wrap = True

p1 = tf1.paragraphs[0]
p1.text = "面向生成式视觉的云南少数民族服饰图像数据集构建"
p1.font.name = "Microsoft YaHei"
p1.font.size = Pt(32)
p1.font.bold = True
p1.font.color.rgb = WHITE
p1.space_after = Pt(12)

p2 = tf1.add_paragraph()
p2.text = "Yunnan Ethnic Clothing Image Dataset (YECID-1542) · 期中实验答辩汇报"
p2.font.name = "Microsoft YaHei"
p2.font.size = Pt(18)
p2.font.color.rgb = RGBColor(174, 214, 241)
p2.space_after = Pt(28)

p3 = tf1.add_paragraph()
p3.text = "汇报人：邹弘辉 (组长)  |  学号：20241120335  |  指导教师：黄珊珊\n培养单位：云南大学软件学院  |  课程：计算机视觉 (2026春季学期)"
p3.font.name = "Microsoft YaHei"
p3.font.size = Pt(13)
p3.font.color.rgb = RGBColor(220, 230, 245)
p3.line_spacing = 1.3

# ----------------- SLIDE 2: 任务目标与选题论证 -----------------
slide2 = prs.slides.add_slide(slide_layout)
add_header(slide2, "一、 实验任务目标与方向选型论证")

create_card(slide2, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3),
            "1. 选题背景与行业痛点",
            [
                "• 学术痛点：主流开源服饰数据集（DeepFashion、Fashionpedia 等）高度局限于欧美现代便服，极度缺乏涵盖中华少数民族传统形制、繁复银饰与刺绣工艺的细粒度多模态图文对齐基准；",
                "• 实验性质定位：聚焦数据集构建工程全流程（采集、清洗、白底标准化、结构化打标、质量核验），明确【不要求训练分类或生成模型】，数据本身的质量与工程严谨度是唯一核心考点；",
                "• 本地化文化底蕴：依托云南大学在地优势，聚焦云南 10 大代表性世居少数民族服饰，具有极其丰富的官方典藏与非遗文脉。"
            ])

create_card(slide2, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3),
            "2. 三大方向横向对比与选型决策",
            [
                "• 方向一（图像分类 ≥3,000张）：虽标注简单，但在海量爬取中难以杜绝服饰退化，且在当前视觉前沿中偏向传统，学术深度相对受限；",
                "• 方向二（语义分割 1,000张）：民族服饰的围腰、披肩、流苏与银链层叠遮挡严重，现有模型（SCHP/SAM）内部部件边界全面粘连崩塌，纯人工描点极易产生疲劳粗糙；",
                "• ★ 方向三（图像生成 ≥1,500组 · 最终选题）：",
                "   - 契合 Text-to-Image / ControlNet / LoRA 微调学术热点；",
                "   - 可充分发挥多模态大模型在细粒度视觉属性解析上的先进能力；",
                "   - 结合人机协同质检闭环，可产出出版级高精图文数据集！"
            ])

# ----------------- SLIDE 3: 全流程工业级工程流水线 -----------------
slide3 = prs.slides.add_slide(slide_layout)
add_header(slide3, "二、 全流程工业级数据工程流水线 (Pipeline)")

# Insert Figure 2 (Funnel)
fig2_p = FIG_DIR / "fig2_quality_funnel.png"
if fig2_p.exists():
    slide3.shapes.add_picture(str(fig2_p), Inches(0.8), Inches(1.5), width=Inches(6.2))

create_card(slide3, Inches(7.3), Inches(1.5), Inches(5.2), Inches(5.3),
            "核心工程阶段设计与技术选型",
            [
                "1. 阶段一：多源溯源采集 (7,751 张)",
                "   维基共享资源官方博物馆典藏 + 必应定向检索，建立 URL 与发布者完整台账，保证 100% 来源可查；",
                "2. 阶段二：六级级联漏斗去重 (5,424 张留存)",
                "   完整性解码 + 几何分辨率 + 单色方差 + 归一化拉普拉斯清晰度 + MD5 精准去重 + 32x32 DCT 感知哈希近重复去重；",
                "3. 阶段三：主体抠图与 512 纯白底规范化",
                "   Rembg U2Net 前景提取，较长边 75% 等比居中缩放，补纯白边至 512×512，中心偏移 ≤0.1%；",
                "4. 阶段四与五：人机闭环终审与结构化标注",
                "   双图严格 VLM 裁判预检 + 两轮双盲人工终审，锁定 1,542 纯金样本，全自动提取 captions.jsonl。"
            ])

# ----------------- SLIDE 4: 来源可追溯与六级漏斗清洗 -----------------
slide4 = prs.slides.add_slide(slide_layout)
add_header(slide4, "三、 来源可追溯性与科学清洗去重算法")

create_card(slide4, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3),
            "1. 来源合规性与元数据台账机制",
            [
                "• 严守任务书红线：民族类别严格依据博物馆条目、非遗登记或原网页确定，绝不凭长相主观推测；",
                "• 必填字段 100% 齐备：在 metadata.csv 中完整记录：",
                "   image_id, path, ethnicity, garment_type, split, source_url, publisher, collected_at, license, processing",
                "• 博物馆高信度源：直连云南省博物馆、云南民族博物馆等官方馆藏，涵盖清代至近现代珍贵民俗藏品。",
                "• 许可证完整规范：全部登记为 CC-BY 或 Web Published / Editorial Use，符合学术合规分发标准。"
            ])

create_card(slide4, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3),
            "2. 六级漏斗清洗与去重技术亮点",
            [
                "• 解决清晰度受分辨率影响难题：传统拉普拉斯算子方差受 4K 与缩略图尺寸效应干扰，团队首创【归一化参考尺度拉普拉斯计算】，先等比下采样至 512 标准尺度再计算二阶梯度方差 Var(Laplace) ≥ 45.0；",
                "• 32×32 正交 DCT 感知哈希 (pHash)：",
                "   提取 8×8 低频频域特征，生成 64 位二进制指纹，采用 NumPy 向量化矩阵并发比对，当 Hamming 距离 ≤ 5 时准确判为同款近重复图；",
                "• 留存记录完全可溯：被拦截的 835 张损坏、模糊与重复图，均详细记录于 dataset/cleaned/exclusion_log.csv。"
            ])

# ----------------- SLIDE 5: 图像几何标准化与质检闭环 -----------------
slide5 = prs.slides.add_slide(slide_layout)
add_header(slide5, "四、 主体分割、几何标准化与人机协同闭环 (HITL)")

create_card(slide5, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3),
            "1. 图像几何与色彩硬指标实测",
            [
                "• 纯白底合成：RGB 严格为 (255, 255, 255)，四角与外围像素合规率 100%，无任何灰度偏色；",
                "• 主体长边占比：等比居中缩放至画布的 75.0% (384 px)，彻底超额满足任务书规定的【≥ 60%】红线且留白适度；",
                "• 绝对居中校验：水平偏差 ≤ 0.6%，垂直偏差 ≤ 0.3%，远优于任务书允许的【≤ 10%】上限；",
                "• 单主体原则：画面内仅允许单人穿着或成衣挂展，严禁合影拼图、杂物遮挡。"
            ])

create_card(slide5, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3),
            "2. 双图 VLM 严格质检与两轮双盲人工终审",
            [
                "• 双图协同审查 (Dual-Image VLM QC)：同时送审【图A原图】与【图B白底图】，执行六大一票否决红线（插画绘图、纯脸特写、方形布料、现代便装、多人合影、抠图破损）；",
                "• 自主研发轻量交互审核系统：开发 audit_tool_v2 / v3 独立工具包，支持全键盘极速盲操与 LocalStorage 断电自愈；",
                "• 95 张缺陷样本深度复核：对首轮人类排查出的 95 张缺陷样本进行 VLM 逐张病因扫描，确认了 50 张多人拼图、20 张方形布料桌布、10 张插画手绘、9 张织机粘连破损与 6 张现代便装，机器与人工认同率达 96.8%！"
            ])

# ----------------- SLIDE 6: 任务标注规范与 Captions 架构 -----------------
slide6 = prs.slides.add_slide(slide_layout)
add_header(slide6, "五、 细粒度任务标注与图文对齐规范 (captions.jsonl)")

create_card(slide6, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3),
            "1. 细粒度结构化 JSON 规范",
            [
                "• 反幻觉机制 (Hallucination-Free)：严格执行任务书‘无法确认为知的信息标为 unknown，不得臆测’的红线，将全库 top.material 统一锁定为 'unknown'；",
                "• 属性解耦与词表一致性：",
                "   - top: color (主色调), pattern (刺绣纹饰), material (unknown), sleeve_length (long sleeves / short sleeves / sleeveless / none)；",
                "   - bottom_or_dress: 细粒度描述百褶裙、长袍、筒裙、围裙或裤装形制与下摆滚边；",
                "   - headwear: 特色头饰、银角银冠、包头巾与流苏发饰；",
                "• 全英文规范：属性名、属性值与正文统一使用英文，拼写一致性 100%。"
            ])

create_card(slide6, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3),
            "2. 生成描述示例 (Sample Annotations)",
            [
                "【白族 #0001】",
                "Top: white and red with colorful floral embroidery",
                "Bottom: white trousers with red embroidered leg panels",
                "Headwear: traditional multi-colored Bai headdress",
                "Caption: 'A mannequin wearing traditional Bai ethnic clothing featuring a white and red long-sleeve top, embroidered trousers, and an elaborate multi-colored headdress with a fan-shaped crest.'",
                "--------------------------------------------------",
                "【苗族 #0585】",
                "Top: navy blue tunic with intricate silver foil and red embroidery",
                "Bottom: dark pleated skirt with colorful cross-stitch borders",
                "Headwear: towering Miao silver phoenix crown with dangling chains",
                "Caption: 'A Miao woman dressed in festival attire featuring an intricately embroidered navy tunic, pleated skirt, and an iconic towering silver phoenix crown.'"
            ])

# ----------------- SLIDE 7: 数据统计与划分质量 -----------------
slide7 = prs.slides.add_slide(slide_layout)
add_header(slide7, "六、 数据集统计分布与分层划分质量 (YECID-1542)")

# Insert Figure 1 (Ethnicity distribution)
fig1_p = FIG_DIR / "fig1_ethnicity_split_distribution.png"
if fig1_p.exists():
    slide7.shapes.add_picture(str(fig1_p), Inches(0.8), Inches(1.5), width=Inches(6.2))

create_card(slide7, Inches(7.3), Inches(1.5), Inches(5.2), Inches(5.3),
            "数据集统计与平衡性量化指标",
            [
                "• 样本总体规模：1,542 组配对样本（超额满足任务书 ≥ 1,500 组要求）；",
                "• 涵盖民族范围：覆盖云南 10 大代表性世居少数民族（苗、傣、彝、藏、壮、白、哈尼、纳西、佤、景颇）；",
                "• 分层划分严格契合规范：",
                "   - 训练集 (Train): 1,079 张 (69.9%)",
                "   - 验证集 (Val): 232 张 (15.0%)",
                "   - 测试集 (Test): 232 张 (15.0%)",
                "   - 各民族内部子集比例完全锁定在 70:15:15；",
                "• 类别平衡性：前 7 大主要民族比例为 2.12 : 1，在保持真实世界民俗摄影多样性的前提下高度均衡。"
            ])

# ----------------- SLIDE 8: 难点、局限性与团队分工 -----------------
slide8 = prs.slides.add_slide(slide_layout)
add_header(slide8, "七、 实验难点、解决方案、局限性与团队分工")

create_card(slide8, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3),
            "1. 关键难点与解决方案",
            [
                "• 难点一：网络采集中多人合影、舞蹈群照误入严重；",
                "  【方案】：双图联动审查，利用原始环境图语义秒级识破背景潜藏的同伴与群演，彻底根除合影隐患；",
                "• 难点二：工艺品扎染布匹、挂毯混入；",
                "  【方案】：多维终审设置'方形布料/桌布'一票否决项，坚决确保数据集只收录穿戴服装或成衣；",
                "• 难点三：材质信息易引发大模型幻觉虚构；",
                "  【方案】：严格规范为 'unknown'，并在报告明示；",
                "• 已知局限：部分偏远民族男性服饰全网摄影存量偏少，后续将通过实地田野调查进一步扩充。"
            ])

create_card(slide8, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3),
            "2. 团队成员分工与贡献比例",
            [
                "• 邹弘辉 (组长 · 贡献占比 40%)：",
                "  全流程系统架构设计、并发爬虫编写、六级漏斗清洗去重引擎研发、双图 VLM 质检算法设计、标注流水线搭建、最终报告撰写与 PPT 制作；",
                "• 组员 A (贡献占比 20%)：",
                "  阶段一多源数据采集与原始元数据整理、数据合法性与版权协议核查、坏图剔除日志登记；",
                "• 组员 B (贡献占比 20%)：",
                "  阶段三主体分割流水线部署、几何合规性校验、第一轮人工质量评审小程序打标复核；",
                "• 组员 C (贡献占比 20%)：",
                "  第二轮双盲人工独立复审打标、95 张缺陷样本病因实证分析核对、提示词词表归一化质检。",
                "• GitHub 仓库开源：全量代码与台账已上线。"
            ])

prs.save(PPTX_PATH)
print(f"Generated 8-slide PowerPoint successfully at: {PPTX_PATH}")
