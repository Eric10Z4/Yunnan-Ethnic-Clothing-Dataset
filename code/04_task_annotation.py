#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段四：任务专属标注导出 (Task-Specific Annotation & Export)
支持任务书要求的三大任务方向格式：
1. 图像分类：annotations/classification_labels.csv (image_id, path, ethnicity, garment_type, split)
2. 语义分割：annotations/masks/{split}/{image_id}.png + classes.json
3. 图像生成：annotations/captions.jsonl (结构化英文属性 + 配对描述)
"""

import json
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ANNOTATIONS_DIR = BASE_DIR / "dataset" / "annotations"

def export_classification_labels(records: list):
    """
    导出分类任务标签
    records: list of dict(image_id, path, ethnicity, garment_type, split)
    """
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = ANNOTATIONS_DIR / "classification_labels.csv"
    fields = ["image_id", "path", "ethnicity", "garment_type", "split"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(f"[Annotation] 成功导出图像分类标签: {out_csv} (共 {len(records)} 条)")

def export_generation_captions(records: list):
    """
    导出图像生成任务细粒度结构化 JSONL
    每个 record 格式严格匹配任务书示例：
    {
      "image_id": "001",
      "path": "images/001.jpg",
      "ethnicity": "Miao",
      "top": {"color": "blue", "pattern": "floral embroidery", "material": "unknown", "sleeve_length": "long sleeves"},
      "bottom_or_dress": "pleated skirt with embroidered trim",
      "headwear": "silver headdress",
      "caption": "Miao ethnic clothing with a blue long-sleeved top featuring floral embroidery, a pleated skirt with embroidered trim, and a silver headdress."
    }
    """
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_jsonl = ANNOTATIONS_DIR / "captions.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for rec in records:
            # 校验必填字段
            assert "image_id" in rec and "path" in rec and "ethnicity" in rec
            assert "top" in rec and "bottom_or_dress" in rec and "caption" in rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[Annotation] 成功导出图像生成结构化描述: {out_jsonl} (共 {len(records)} 条)")

def export_segmentation_classes():
    """
    导出语义分割类别映射 classes.json
    0=background, 1=top, 2=bottom, 3=dress, 4=headwear, 5=accessories
    """
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    classes_file = ANNOTATIONS_DIR / "classes.json"
    mapping = {
        "0": "background",
        "1": "top",
        "2": "bottom",
        "3": "dress",
        "4": "headwear",
        "5": "accessories"
    }
    with open(classes_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    print(f"[Annotation] 成功导出分割类别映射: {classes_file}")

if __name__ == "__main__":
    export_segmentation_classes()
    print("阶段四标注工具库已就绪。")
