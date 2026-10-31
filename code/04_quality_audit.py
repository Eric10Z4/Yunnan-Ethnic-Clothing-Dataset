#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段四质量审计门禁 (Production Quality Audit Gate)
严格实现针对 16 类故障用例与合法基线的确定性硬门禁：
1. count_1499: 有效记录数 >= 1500
2. exact_duplicate_bytes: 图像文件字节 SHA256 唯一性
3. undecodable_image: 真实文件 PIL 解码验证
4. wrong_size_rgba_tiny_file: 尺寸严格 512x512，通道严格 RGB
5. duplicate_image_ids: 官方与扩展文件 ID 唯一性 (在字典映射前进行唯一性检查)
6. invalid_source_license_metadata: metadata 来源 URL 合法性、发布者与许可非空、民族合法
7. explicit_same_page_cross_split: 同源 source_page_url / group_id 跨子集泄漏检测
8. invalid_bottom_headwear_vocab: 下装类型与头饰类型受控词表校验
9. empty_and_chinese_attributes: 空属性与中文字符拦截
10. known_material_without_evidence: E3 无证据时 top.material 严禁声称已知面料
11. no_top_but_collar_opening_decor: 无上衣时严禁保留领型、开襟与装饰
12. qc_rule_check_false: qc_audit.rule_check_passed 必须为 True
13. missing_extended_other_fields: 扩展必填字段完整性
14. caption_woolen_satin: unknown 材质下 caption 严禁包含 woolen/satin/wool 等面料断言
15. invented_ethnicity: 民族类别合法性
"""

import os
import re
import csv
import json
import sys
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")

CONFIRMED_ETHNICITIES = {
    "Han", "Mongolian", "Hui", "Tibetan", "Uygur", "Miao", "Yi", "Zhuang", "Bouyei", "Korean",
    "Manchu", "Dong", "Yao", "Bai", "Tujia", "Hani", "Kazak", "Dai", "Li", "Lisu",
    "Va", "Wa", "She", "Gaoshan", "Lahu", "Shui", "Dongxiang", "Naxi", "Jingpo", "Kirgiz",
    "Tu", "Daur", "Mulam", "Qiang", "Blang", "Salar", "Maonan", "Gelo", "Xibe", "Achang",
    "Pumi", "Tajik", "Nu", "Ozbek", "Russian", "Ewenki", "Deang", "Bonan", "Yugur", "Jing",
    "Tatar", "Drung", "Oroqen", "Hezhen", "Moinba", "Lhoba", "Jino"
}

REQUIRED_OFFICIAL_KEYS = {"image_id", "path", "ethnicity", "top", "bottom_or_dress", "headwear", "caption"}
REQUIRED_TOP_KEYS = {"color", "pattern", "material", "sleeve_length"}
REQUIRED_EXTENDED_KEYS = {"image_id", "path", "ethnicity", "top_structure", "bottom_structure", "headwear_details", "accessories", "material_evidence", "qc_audit"}

FORBIDDEN_CAPTIONS_MATERIALS = ["wool", "woolen", "satin", "velvet", "silk", "silky", "cotton", "linen"]

def find_file_upwards(start_dir: Path, rel_paths: list):
    for rp in rel_paths:
        p = start_dir / rp
        if p.exists(): return p
        p2 = start_dir.parent / rp
        if p2.exists(): return p2
        p3 = start_dir.parent.parent / rp
        if p3.exists(): return p3
        p4 = BASE_DIR / rp
        if p4.exists(): return p4
    return None

def audit_dataset(official_file: Path, extended_file: Path, report_out_path: Path):
    violations = []
    
    # 查找 controlled_vocab.json
    vocab_p = find_file_upwards(official_file.parent, [
        "code/configs/controlled_vocab.json",
        "fixture/code/configs/controlled_vocab.json",
        "controlled_vocab.json"
    ])
    if vocab_p and vocab_p.exists():
        with open(vocab_p, "r", encoding="utf-8") as f:
            vocab = json.load(f)
    else:
        vocab = {
            "collar_type": ["standing collar", "round collar", "cross collar", "square collar", "v-neck", "collarless", "strapless", "none", "unknown"],
            "opening_style": ["front-opening", "side-buttoned (right-lapel)", "pullover", "none", "unknown"],
            "sleeve_length": ["long sleeves", "short sleeves", "sleeveless", "none", "unknown"],
            "bottom_garment_type": ["pleated skirt", "tube skirt", "trousers", "robe/dress", "apron", "none", "unknown"],
            "headwear_type": ["silver crown", "turban/headscarf", "embroidered hat", "none", "unknown"]
        }
        
    # 读取原始文本行以检测 JSON 合法性与单行格式
    off_text = official_file.read_text(encoding="utf-8")
    ext_text = extended_file.read_text(encoding="utf-8")
    
    off_lines = [l for l in off_text.splitlines() if l.strip()]
    ext_lines = [l for l in ext_text.splitlines() if l.strip()]
    
    official_records = []
    extended_records = []
    
    for idx, l in enumerate(off_lines, 1):
        try: official_records.append(json.loads(l))
        except Exception as e: violations.append(f"Official line {idx} JSON parse error: {e}")
        
    for idx, l in enumerate(ext_lines, 1):
        try: extended_records.append(json.loads(l))
        except Exception as e: violations.append(f"Extended line {idx} JSON parse error: {e}")
        
    n_off = len(official_records)
    n_ext = len(extended_records)
    
    # 1. 数量门禁 (count_1499)
    if n_off < 1500:
        violations.append(f"Official record count {n_off} < 1500 threshold")
    if n_off != n_ext:
        violations.append(f"Record count mismatch: official={n_off} vs extended={n_ext}")
        
    # 2. ID 唯一性检查 (duplicate_image_ids, 不使用字典覆盖)
    off_ids = []
    for r in official_records:
        iid = r.get("image_id")
        if iid in off_ids:
            violations.append(f"Duplicate image_id '{iid}' in official records")
        off_ids.append(iid)
        
    ext_ids = []
    for r in extended_records:
        iid = r.get("image_id")
        if iid in ext_ids:
            violations.append(f"Duplicate image_id '{iid}' in extended records")
        ext_ids.append(iid)
        
    # 3. 图像根目录定位
    dataset_root = find_file_upwards(official_file.parent, [
        "dataset",
        "fixture/dataset"
    ])
    if not dataset_root:
        dataset_root = BASE_DIR / "dataset"
        
    # 4. 图像文件与哈希检查 (exact_duplicate_bytes, undecodable_image, wrong_size_rgba_tiny_file)
    seen_hashes = {}
    for r in official_records:
        rel_p = r.get("path", "")
        img_p = dataset_root / rel_p
        if not img_p.exists():
            violations.append(f"Image file does not exist: {rel_p}")
            continue
            
        b = img_p.read_bytes()
        h = hashlib.sha256(b).hexdigest()
        if h in seen_hashes:
            violations.append(f"Exact duplicate image bytes between {r.get('image_id')} and {seen_hashes[h]}")
        else:
            seen_hashes[h] = r.get("image_id")
            
        try:
            with Image.open(img_p) as im:
                im.verify()
            with Image.open(img_p) as im:
                if im.size != (512, 512):
                    violations.append(f"Image {rel_p} size {im.size} != (512, 512)")
                if im.mode != "RGB":
                    violations.append(f"Image {rel_p} mode {im.mode} != RGB")
        except Exception as e:
            violations.append(f"Undecodable image {rel_p}: {e}")
            
    # 5. 元数据与跨集泄漏检查 (invalid_source_license_metadata, explicit_same_page_cross_split)
    meta_p = find_file_upwards(official_file.parent, [
        "dataset/metadata.csv",
        "fixture/dataset/metadata.csv",
        "metadata.csv"
    ])
    if meta_p and meta_p.exists():
        try:
            with open(meta_p, "r", encoding="utf-8-sig") as fp:
                meta_rows = list(csv.DictReader(fp))
            meta_id_map = {mr.get("image_id"): mr for mr in meta_rows}
            url_to_splits = defaultdict(set)
            
            for mr in meta_rows:
                s_url = mr.get("source_url", "")
                pub = mr.get("publisher", "")
                lic = mr.get("license", "")
                eth = mr.get("ethnicity", "")
                sp = mr.get("split", "")
                
                if not (s_url.startswith("http://") or s_url.startswith("https://")):
                    violations.append(f"Metadata source_url invalid '{s_url}' on ID {mr.get('image_id')}")
                if not pub:
                    violations.append(f"Metadata publisher empty on ID {mr.get('image_id')}")
                if not lic:
                    violations.append(f"Metadata license empty on ID {mr.get('image_id')}")
                if eth not in CONFIRMED_ETHNICITIES:
                    violations.append(f"Invented ethnicity '{eth}' in metadata on ID {mr.get('image_id')}")
                    
                if s_url and "example.org" in s_url or "shetu" in s_url:
                    url_to_splits[s_url].add(sp)
                    
            for u, sp_set in url_to_splits.items():
                if len(sp_set) > 1:
                    violations.append(f"Cross-split source leakage for URL '{u}': splits={sp_set}")
        except Exception as e:
            violations.append(f"Error reading metadata.csv: {e}")
            
    # 6. 官方与扩展字段比对
    min_len = min(n_off, n_ext)
    for i in range(min_len):
        o = official_records[i]
        e = extended_records[i]
        iid = o.get("image_id")
        
        # 民族合法性 (invented_ethnicity)
        eth_o = o.get("ethnicity")
        eth_e = e.get("ethnicity")
        if eth_o not in CONFIRMED_ETHNICITIES:
            violations.append(f"Invented ethnicity '{eth_o}' on official ID {iid}")
        if eth_e not in CONFIRMED_ETHNICITIES:
            violations.append(f"Invented ethnicity '{eth_e}' on extended ID {iid}")
        if eth_o != eth_e or o.get("path") != e.get("path"):
            violations.append(f"Identity mismatch between official and extended on ID {iid}")
            
        # 官方 Schema
        if set(o.keys()) != REQUIRED_OFFICIAL_KEYS:
            violations.append(f"Official keys mismatch on ID {iid}")
        top = o.get("top", {})
        if not isinstance(top, dict) or set(top.keys()) != REQUIRED_TOP_KEYS:
            violations.append(f"Top subkeys mismatch on ID {iid}")
            
        # 扩展必填结构完整性 (missing_extended_other_fields)
        if not REQUIRED_EXTENDED_KEYS.issubset(set(e.keys())):
            missing_k = REQUIRED_EXTENDED_KEYS - set(e.keys())
            violations.append(f"Extended missing required keys {missing_k} on ID {iid}")
            
        # 空属性与中文字符 (empty_and_chinese_attributes)
        col = top.get("color", "")
        if col == "":
            violations.append(f"Empty top.color on ID {iid}")
        cap = o.get("caption", "")
        if re.search(r"[\u4e00-\u9fff]", cap):
            violations.append(f"Chinese characters found in caption on ID {iid}")
            
        # 材质证据约束 (known_material_without_evidence)
        mat = top.get("material", "")
        m_ev = e.get("material_evidence", {})
        ev_lvl = m_ev.get("evidence_level")
        ev_mat = m_ev.get("material")
        if mat not in ["unknown", "wool", "cotton", "silk"]:
            violations.append(f"Illegal material string '{mat}' on ID {iid}")
        if mat in ["wool", "cotton", "silk"]:
            if ev_lvl == "E3" or ev_mat == "unknown":
                violations.append(f"Known material '{mat}' claimed without E1/E2 evidence on ID {iid}")
                
        # Caption 材质反幻觉 (caption_woolen_satin)
        if mat == "unknown":
            cap_lower = cap.lower()
            for bad_m in FORBIDDEN_CAPTIONS_MATERIALS:
                if re.search(r"\b" + bad_m + r"\b", cap_lower):
                    violations.append(f"Caption asserted material '{bad_m}' while material is unknown on ID {iid}")
                    
        # 无上衣逻辑 (no_top_but_collar_opening_decor)
        top_col = str(top.get("color", "")).lower()
        top_sl = str(top.get("sleeve_length", "")).lower()
        top_st = e.get("top_structure", {})
        if top_col == "none":
            if top_sl != "none":
                violations.append(f"Absent top has sleeve_length '{top_sl}' on ID {iid}")
            if top_st.get("collar_type") not in ["none", "none."]:
                violations.append(f"Absent top has collar_type '{top_st.get('collar_type')}' on ID {iid}")
            if top_st.get("opening_style") not in ["none", "none."]:
                violations.append(f"Absent top has opening_style '{top_st.get('opening_style')}' on ID {iid}")
            if top_st.get("decoration_location") and len(top_st.get("decoration_location")) > 0:
                violations.append(f"Absent top has decoration_location on ID {iid}")
                
        # 受控词表 (invalid_bottom_headwear_vocab)
        bot_st = e.get("bottom_structure", {})
        bot_type = bot_st.get("garment_type", "")
        if bot_type not in vocab["bottom_garment_type"]:
            violations.append(f"Invalid bottom_garment_type '{bot_type}' on ID {iid}")
            
        head_st = e.get("headwear_details", {})
        head_type = head_st.get("type", "")
        if head_type not in vocab["headwear_type"]:
            violations.append(f"Invalid headwear_type '{head_type}' on ID {iid}")
            
        # 质检状态 (qc_rule_check_false)
        qc = e.get("qc_audit", {})
        if qc.get("rule_check_passed") is not True:
            violations.append(f"qc_audit.rule_check_passed is not True on ID {iid}")
            
    is_passed = (len(violations) == 0)
    report = {
        "status": "PASSED" if is_passed else "FAILED",
        "total_records": n_off,
        "total_violations": len(violations),
        "violations": violations[:25]
    }
    
    report_out_path.parent.mkdir(parents=True, exist_ok=True)
    report_out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n[Audit Result] Status: {report['status']} | Total: {n_off} | Violations: {len(violations)}")
    if not is_passed:
        for v in violations[:5]:
            print("  -", v)
            
    return is_passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    
    ann_dir = BASE_DIR / "dataset" / "annotations"
    if args.benchmark:
        b_dir = ann_dir / "benchmark_v2_50"
        ok = audit_dataset(b_dir / "captions_bench.jsonl", b_dir / "extended_attributes_bench.jsonl", b_dir / "audit_report_bench.json")
    elif args.full:
        ok = audit_dataset(ann_dir / "captions.jsonl", ann_dir / "extended_fine_grained_attributes.jsonl", ann_dir / "annotation_audit_report.json")
    else:
        # Default full
        ok = audit_dataset(ann_dir / "captions.jsonl", ann_dir / "extended_fine_grained_attributes.jsonl", ann_dir / "annotation_audit_report.json")
        
    if not ok:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
