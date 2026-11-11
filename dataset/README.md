# Yunnan Ethnic Clothing Image Dataset (YECID-1512)
## 面向图像生成的云南少数民族服饰细粒度标注数据集

本项目为**云南大学软件学院 2026 春季学期《计算机视觉》课程期中大作业**成果，由**邹弘辉、王毅豪、金明源、贾子钊**共同构建。聚焦云南 10 大代表性世居少数民族传统服饰，按任务书开展来源登记、清洗、主体处理、标注与质量检查。

团队贡献比例依次为 **35%、20%、25%、20%**。1120 的重分割、袖缘局部清理及复现由贾子钊负责；完整分工见[项目说明](../README.md)。[实验报告](../report/民族服饰图像数据集构建_期中实验报告.docx)说明构建过程与核验结果。

本仓库上传代码、标注、metadata、来源映射和报告，正式主集 `images/` 沿用 metadata-only 约定，不上传全量图像二进制；少量排除与 1120 复现材料单独保留。图像获取和使用遵守原始来源许可。

---

## 一、 数据集基本概况
- **样本总量**：1,512 组正式主集配对样本（达到课程任务书图像生成方向不少于 1,500 组的数量要求）。
- **涵盖民族**：10 个云南代表性世居少数民族（白族、傣族、哈尼族、景颇族、苗族、纳西族、藏族、佤族、彝族、壮族）。
- **图像规范**：统一为 `512 × 512` RGB 图像，采用白底、等比例居中补边处理；任务要求主体长边占比不少于 60%，横纵中心偏差不超过 10%。
- **标注形式**：细粒度结构化属性标注与对齐英文自然语言文本描述（JSONL），可供后续 Text-to-Image 与多模态图文对齐实验使用。

---

## 二、 目录结构与划分说明

数据集按整组同源不跨集（Group-aware Partitioning）的原则进行子集划分，训练集、验证集、测试集比例约为 `70% : 15% : 15%`：

```
dataset/
├── images/                                 # 正式主集 512x512 纯白底图像 (1,512 张)
│   ├── train/                              # 训练集 (1,063 张, 70.30%)
│   ├── val/                                # 验证集 (223 张, 14.75%)
│   └── test/                               # 测试集 (226 张, 14.95%)
├── annotations/
│   ├── captions.jsonl                      # 官方交付格式细粒度结构化标注 (1,512 行)
│   ├── extended_fine_grained_attributes.jsonl # 学术扩展细粒度属性与证据链标注 (1,512 行)
│   ├── captions_merged_full.jsonl          # 全字段一体化合并标注 (1,512 行)
│   ├── dataset_manifest_mapped.json        # 主集物理路径与元数据映射清单 (1,512 条)
│   └── annotation_audit_report.json        # 质量门禁全量检测报告 (PASSED, 0 违规)
├── excluded_samples/                       # 归档排除样本目录 (非主集，不纳入训练及统计)
│   └── final_cleanup_0803_1166/            # 终审排除归档 (0803 局部特写、1166 独立绣片)
├── reproducible_1120/                      # 样本 1120 左袖下缘确定性清理材料与对比图
├── metadata.csv                            # 主集全量元数据总表 (1,512 行，包含 12 大字段)
└── README.md                               # 本说明文档
```

### 主集 ID 编号与连续性说明
- 主集样本图像文件采用四位数字标识（如 `0001.jpg` 至 `1514.jpg`）。
- **主集 ID 不连续**：在最终复核中，`0803`（彝族服饰边缘机绣特写，无法呈现成衣主体）与 `1166`（苗族刺绣独立绣片，非完整服饰样本）被正式移出主集，移至 `dataset/excluded_samples/final_cleanup_0803_1166/` 归档留痕。
- 遵循数据管理规范，未将后续样本前移覆盖已定编号，空缺 ID 保持留空，正式主集实际样本量为 **1,512 组**。

---

## 三、 类别定义与分布统计表

下表为修后主集实际数据与元数据物理统计结果：

| 序号 | 民族名称 (中文) | 英文名称 (Ethnicity) | 训练集 (Train) | 验证集 (Val) | 测试集 (Test) | 总计样本量 | 占比 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 苗族 | Miao | 187 | 35 | 41 | **263** | 17.39% |
| 2 | 傣族 | Dai | 175 | 37 | 37 | **249** | 16.47% |
| 3 | 藏族 | Tibetan | 143 | 31 | 29 | **203** | 13.43% |
| 4 | 彝族 | Yi | 139 | 29 | 30 | **198** | 13.10% |
| 5 | 壮族 | Zhuang | 128 | 28 | 27 | **183** | 12.10% |
| 6 | 白族 | Bai | 97 | 21 | 21 | **139** | 9.19% |
| 7 | 纳西族 | Naxi | 81 | 17 | 18 | **116** | 7.67% |
| 8 | 佤族 | Wa | 72 | 16 | 15 | **103** | 6.81% |
| 9 | 景颇族 | Jingpo | 21 | 5 | 4 | **30** | 1.98% |
| 10 | 哈尼族 | Hani | 20 | 4 | 4 | **28** | 1.85% |
| **合计** | - | - | **1,063** | **223** | **226** | **1,512** | **100.00%** |

### 类别分布与任务书口径

任务书要求至少选择 5 个经来源核验的民族类别。图像生成方向不少于 1,500 组，并建议每类不少于 150 组。

当前主集选择 10 类，最大类 263 组、最小类 28 组，存在明显不均衡；白族、纳西族、佤族、景颇族和哈尼族未达到每类 150 组的建议。总量达标不代表每类建议均已实现。任务书的 2:1 类别比例建议列于图像分类方向，不能将其改写为生成方向的硬性门槛。

---

## 四、 标注体系与文件规范

数据集采用“三轨对齐”的标注架构，确保向下兼容课程评测，向上支撑学术拓展：

### 1. `annotations/captions.jsonl`（官方交付格式）
沿用任务书英文示例的 7 个顶层字段与 top 内 4 个基础字段：
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
  "caption": "Traditional Bai ethnic clothing featuring a magenta top with white long sleeves and delicate floral embroidery, paired with a white apron adorned with red floral embroidery, a decorative waistband, and a traditional Bai fringe headdress with dangling white tassels on a pure white background."
}
```

### 2. `annotations/extended_fine_grained_attributes.jsonl`（结构属性扩展）
记录服装可见的结构属性，并保留面料证据等级字段：
- `top_structure`: `collar_type`（立领/圆领/交领/方领/V领/无领/抹胸等）、`opening_style`（对襟/大襟/右衽/套头等）、`closure`（盘扣/纽扣/系带等）、`decoration_location`（领口/门襟/袖口/衣摆等）。
- `bottom_structure`: `garment_type`（百褶裙/筒裙/裤装/长袍/围裙/无等）、`length`。
- `headwear_details`: `type`（银冠/头帕/刺绣帽/编织帽/结构帽等）。
- `material_evidence`: `evidence_level`（E1 网页明文确证、E2 可靠典籍对照、E3 仅外观视觉证据）、`material`。
- `qc_audit`: `vlm_confidence`, `rule_check_passed`。

### 3. `annotations/captions_merged_full.jsonl`（合并格式）
以官方字段为底座，合并对应的结构属性、证据和质检字段，便于后续图文实验读取。

### 4. `metadata.csv`（全量元数据总表）
包含完整 12 项字段：
`image_id, path, ethnicity, garment_type, split, source_url, publisher, collected_at, license, processing, source_page_url, group_id`。

---

## 五、 质量审计门禁与学术诚信说明

### 1. 自动化质量门禁 (`code/04_quality_audit.py`)
系统内置了全自动质量门禁脚本，支持 `--full` 模式对全库进行硬性校验：
- **数量与唯一性**：核验主集样本 $\ge 1,500$ 组；检查 5 份文件之间的 `image_id` 集合严格完全对齐，杜绝行序依赖与重复覆盖。
- **图像与物理规格**：逐张解码核验 512×512 分辨率、RGB 通道模式，计算文件字节 SHA256，检查完全相同的图像文件。
- **全字段受控词表**：严格校验领型、开襟、袖长、下装、头饰 5 大词表，杜绝跨字段串位与未定义值。
- **防同源数据泄漏**：对图像 URL、原始页面 URL (`source_page_url`) 和分组标识 (`group_id`) 检查跨子集归属。
- **反幻觉一致性**：检查材质证据字段与 Caption 中的具体面料词是否一致；未知材质记录为 `unknown`。无上衣部件时，领型、开襟与袖长同步为 `none`。

### 2. 阶段台账与定向复核

- 初始清洗批次：6,259 张候选图像，排除 835 张，保留 5,424 张。
- 独立双图质检候选池：6,744 个候选文件，其中 1,765 条 PASS、4,979 条 FAIL。该候选池与初始清洗批次口径不同，分别记录。
- 上衣属性定向复核：复核 19 条记录，恢复 16 条的可见上衣属性，3 条保留 `none`。
- 1120：由贾子钊完成重分割、袖缘局部清理及复现，材料见 `reproducible_1120/`，脚本见 `../code/clean_1120_cuff.py`。

### 3. 客观局限性声明
- **程序通过的边界**：代码运行 `04_quality_audit.py` 得到 `PASSED`（0 违规），表明数据集在 Schema 结构、引用完整性、词表合法性及跨集防泄漏方面达到了工程规范。这**不等于全库 1,512 张图像中的所有民俗细微特征均已经过人类民俗专家的逐项实地确认**。
- **材质证据边界**：绝大多数样本按不臆测原则记录为 `E3 / unknown`；来源明示的材质按相应证据记录。证据等级不等同于实物纤维检测结果。来源记录中的通用许可文字也不替代各来源的具体授权条款。

---

## 六、 运行环境与常用验证命令

### 依赖环境
- Python >= 3.10
- Pillow, numpy, requests

### 常用核验命令

完整门禁与默认 1120 核验需要本地完整主集图像；metadata-only 仓库不含全量 `images/`。以下命令用于核验，不重新导出定稿元数据。

```bash
# 1. 运行主集全量数据质量与防泄漏审计门禁 (预期 PASSED, exit 0)
python code/04_quality_audit.py --full

# 2. 运行生产标注管道真实离线单元测试套件 (包含 10 项测试, 预期全部 OK)
python code/test_pipeline_offline.py

# 3. 验证样本 1120 左袖下缘确定性修复成果哈希
python code/clean_1120_cuff.py --verify

```
