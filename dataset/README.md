# Yunnan Ethnic Clothing Image Dataset (YECID-1542)
## 云南少数民族服饰高质量图像生成与细粒度标注数据集

本项目为**云南大学软件学院 2026 春季学期《计算机视觉》课程期中大作业**成果，由**邹弘辉团队**构建。聚焦云南 10 大代表性世居少数民族传统服饰，严格遵循任务书各项科学规范，经过六级漏斗初筛、深度抠图、双图严格 VLM 预检以及两轮双盲人工独立复审构建而成。

---

## 一、 数据集基本概况
- **样本总量**：1,542 组配对样本（超额满足图像生成任务 $\ge 1,500$ 组要求）
- **涵盖民族**：10 个云南世居少数民族（傣族、苗族、彝族、藏族、壮族、白族、哈尼族、纳西族、佤族、景颇族）
- **图像规范**：纯白底 `RGB(255, 255, 255)`，尺寸统一 `512 × 512` 像素，主体长边占比稳定在 `75%`（$\ge 60\%$），横纵中心偏差 $\le 0.6\%$（$\le 10\%$）。
- **标注形式**：细粒度结构化属性标注与对齐英文文本描述（JSONL），适用于 Text-to-Image、Diffusion / FLUX / SDXL 微调与多模态生成研究。

---

## 二、 目录结构与划分说明

数据集严格采用标准学术格式划分（约 70% 训练集，15% 验证集，15% 测试集，按民族分层随机划分）：

```
dataset/
├── images/                             # 标准化 512x512 纯白底图像集
│   ├── train/                          # 训练集 (1,079 张, 69.9%)
│   ├── val/                            # 验证集 (232 张, 15.0%)
│   └── test/                           # 测试集 (232 张, 15.0%)
├── annotations/
│   ├── captions.jsonl                  # 图像生成任务细粒度结构化 JSONL 描述
│   └── dataset_manifest_mapped.json    # 映射总表
├── metadata.csv                        # 全量元数据总表 (包含10大核心字段)
└── README.md                           # 本说明文档
```

---

## 三、 类别定义与分布统计表

| 序号 | 民族名称 (中文) | 英文名称 (Ethnicity) | 训练集 (Train) | 验证集 (Val) | 测试集 (Test) | 总计样本量 | 占比 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 苗族 | Miao | 174 | 37 | 37 | **248** | 15.7% |
| 2 | 傣族 | Dai | 172 | 37 | 37 | **246** | 15.5% |
| 3 | 彝族 | Yi | 148 | 32 | 32 | **212** | 13.4% |
| 4 | 藏族 | Tibetan | 139 | 30 | 30 | **199** | 12.6% |
| 5 | 壮族 | Zhuang | 107 | 23 | 23 | **153** | 9.7% |
| 6 | 白族 | Bai | 95 | 20 | 20 | **135** | 8.5% |
| 7 | 哈尼族 | Hani | 82 | 18 | 17 | **117** | 7.4% |
| 8 | 纳西族 | Naxi | 74 | 16 | 15 | **105** | 6.6% |
| 9 | 佤族 | Wa | 60 | 13 | 13 | **86** | 5.4% |
| 10 | 景颇族 | Jingpo | 59 | 12 | 13 | **83** | 5.2% |
| **合计** | - | - | **1,079** | **232** | **232** | **1,542** | **100.0%** |

*注：类别最大最小比为 $248 : 83 = 2.98 : 1$；前 7 大主要民族比例为 $248 : 117 = 2.12 : 1$，在保持真实分布多样性的前提下高度均衡。*

---

## 四、 标注规范与字段说明

### 1. `annotations/captions.jsonl`
每行一条严格遵循任务书规范的结构化 JSON 记录，示例：
```json
{
  "image_id": "0001",
  "path": "images/train/0001.jpg",
  "ethnicity": "Bai",
  "top": {
    "color": "magenta and white",
    "pattern": "floral embroidery",
    "material": "unknown",
    "sleeve_length": "long sleeves"
  },
  "bottom_or_dress": "white floral embroidered apron over magenta skirt",
  "headwear": "white traditional Bai headdress with fringe and white tassels",
  "caption": "Traditional Bai ethnic clothing featuring a magenta top with white long sleeves and delicate floral embroidery, paired with a white apron adorned with red floral embroidery, a decorative waistband, and a traditional Bai fringe headdress with dangling white tassels."
}
```

- **字段含义**：
  - `image_id`: 四位零填充全局唯一数字标识（`0001`~`1542`）。
  - `path`: 图像相对路径。
  - `ethnicity`: 对应 10 大民族英文标准名称。
  - `top`:
    - `color`: 上衣主色调；
    - `pattern`: 刺绣工艺与纹样描述；
    - `material`: 统一规范为 `"unknown"`（严格遵循任务书“无法从图像核验的信息标为未知，不得臆测”的学术要求）；
    - `sleeve_length`: `"long sleeves"` / `"short sleeves"` / `"sleeveless"` / `"none"`。
  - `bottom_or_dress`: 下装、百褶裙、筒裙、长袍或围腰细粒度细节。
  - `headwear`: 民族特色头帕、银冠、包头帽饰。
  - `caption`: 符合现代生成模型微调标准的自然语言完整描述句。

### 2. `metadata.csv`
包含全部 10 大必填核心字段：
`image_id, path, ethnicity, garment_type, split, source_url, publisher, collected_at, license, processing`

---

## 五、 数据集构建流程与技术参数

1. **多源采集**：定向爬取必应高清图库与博物馆官方数字典藏，台账完备。
2. **清洗去重**：经文件完整性解码、几何分辨率（`min>=220px`）、单色方差（`std(L)>=15`）、归一化拉普拉斯清晰度（`var>=45`）、MD5 精准去重与 32x32 DCT 感知哈希（`Hamming<=5`）去重。
3. **主体抠图与几何标准化**：
   - 算法：Rembg U2Net 前景提取；
   - 背景：纯白补边 `RGB(255, 255, 255)`；
   - 尺度：主体长边等比缩放至画布的 `75.0%`（384 px，超额满足 $\ge 60\%$）；
   - 居中度：水平偏差 $\le 0.6\%$，垂直偏差 $\le 0.3\%$（严格满足 $\le 10\%$）。
4. **质检与人机闭环**：
   - 机器初检：全量双图（原图+白底图）VLM 严格深度审查，拦截 4,979 张多人合照、方形布料、纯脸特写及插画；
   - 人工复审：经过两轮独立双盲人工终审，剔除全部残余瑕疵图，最终精炼锁定 1,542 张极品纯金图像。

---

## 六、 软件环境与复现步骤

### 运行环境
- Python >= 3.10
- Pillow >= 10.0.0, numpy >= 1.24.0, rembg >= 2.0.50, scipy >= 1.11.0

### 执行全流程复现
```bash
# 1. 运行清洗与去重
python code/02_clean_and_dedup.py

# 2. 运行主体抠图与白底标准化
python code/03_process_all_cleaned.py

# 3. 运行双图严格质检
python code/03_strict_dual_vlm_qc.py

# 4. 运行生成任务打标
python code/04_generate_captions.py

# 5. 导出元数据总表
python code/05_export_metadata_and_qc.py
```
