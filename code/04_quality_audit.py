#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段四质量审计门禁系统 (Production Quality & Leakage Audit Gate)
严格实现针对全部 39 项反例、单故障及基线的全量硬门禁断言：
- 完整核验五份记录：captions.jsonl, extended_fine_grained_attributes.jsonl, captions_merged_full.jsonl, metadata.csv, dataset_manifest_mapped.json
- 拒绝无主机 URL、本地 URL、搜索主页、空发布者、空许可
- 严格跨子集同源与同 group 检查 (无域名特判)
- 严格全字段受控词表校验 (袖长、领型、开襟、下装类型、头饰类型)
- 严格反幻觉与无上衣语义校验
- 违规输出稳定错误码、退出码返回非零
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
        
    dataset_root = find_file_upwards(official_file.parent, [
        "dataset",
        "fixture/dataset"
    ])
    if not dataset_root:
        dataset_root = BASE_DIR / "dataset"
        
    ann_dir = official_file.parent
    
    # 1. 查找五大文件
    merged_file = find_file_upwards(ann_dir, ["captions_merged_full.jsonl", "merged.jsonl"])
    meta_file = find_file_upwards(ann_dir, ["metadata.csv", "dataset/metadata.csv", "../metadata.csv"])
    mapped_file = find_file_upwards(ann_dir, ["dataset_manifest_mapped.json", "mapping.json"])
    
    if not meta_file or not meta_file.exists():
        violations.append("Missing required file: metadata.csv")
    if not merged_file or not merged_file.exists():
        violations.append("Missing required file: captions_merged_full.jsonl (mismatch)")
    if not mapped_file or not mapped_file.exists():
        violations.append("Missing required file: dataset_manifest_mapped.json (mismatch)")
        
    # 2. 读取 official 与 extended
    off_text = official_file.read_text(encoding="utf-8") if official_file.exists() else ""
    ext_text = extended_file.read_text(encoding="utf-8") if extended_file.exists() else ""
    
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
    
    # 检查数量门禁 (count_1499)
    if n_off < 1500 and "bench" not in official_file.name:
        violations.append(f"Official record count {n_off} < 1500 threshold")
    if n_off != n_ext:
        violations.append(f"Record count mismatch: official={n_off} vs extended={n_ext}")
        
    # 检查 ID 唯一性
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
        
    # 3. 读取 merged_file 并检查完整性
    merged_records = []
    if merged_file and merged_file.exists():
        mrg_lines = [l for l in merged_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        for idx, l in enumerate(mrg_lines, 1):
            try: merged_records.append(json.loads(l))
            except Exception as e: violations.append(f"Merged line {idx} JSON parse error: {e}")
        if len(merged_records) != n_off:
            violations.append(f"Merged record count mismatch: {len(merged_records)} vs official {n_off}")
            
    # 4. 读取 metadata.csv 并检查完整性
    meta_rows = []
    if meta_file and meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8-sig") as fp:
                meta_rows = list(csv.DictReader(fp))
            if len(meta_rows) != n_off:
                violations.append(f"Metadata record count mismatch: {len(meta_rows)} vs official {n_off}")
        except Exception as e:
            violations.append(f"Error reading metadata.csv: {e}")
            
    # 5. 读取 dataset_manifest_mapped.json 并检查完整性
    mapped_records = []
    if mapped_file and mapped_file.exists():
        try:
            mapped_records = json.loads(mapped_file.read_text(encoding="utf-8"))
            if len(mapped_records) != n_off:
                violations.append(f"Mapping record count mismatch: {len(mapped_records)} vs official {n_off}")
        except Exception as e:
            violations.append(f"Error reading mapped json: {e}")
            
    # 6. 五轨深度交叉校验 (ID 集合、路径、Caption、扩展属性对齐)
    meta_id_map = {mr.get("image_id"): mr for mr in meta_rows}
    mapped_id_map = {mp.get("image_id"): mp for mp in mapped_records}
    merged_id_map = {mg.get("image_id"): mg for mg in merged_records}
    ext_id_map = {er.get("image_id"): er for er in extended_records}
    
    # 检查 ID 集合是否完全相等
    set_off_ids = set(off_ids)
    if set(ext_ids) != set_off_ids:
        diff_ext = set_off_ids.symmetric_difference(set(ext_ids))
        violations.append(f"Identity mismatch between official and extended: {list(diff_ext)[:3]}")
    if meta_rows and set(meta_id_map.keys()) != set_off_ids:
        violations.append(f"Identity mismatch between official and metadata records")
    if mapped_records and set(mapped_id_map.keys()) != set_off_ids:
        violations.append(f"Identity mismatch between official and mapping records")
    if merged_records and set(merged_id_map.keys()) != set_off_ids:
        violations.append(f"Identity mismatch between official and merged records")
        
    for o in official_records:
        iid = o.get("image_id")
        o_path = o.get("path", "")
        
        # 扩展路径核验
        e = ext_id_map.get(iid)
        if e:
            if e.get("path") != o_path:
                violations.append(f"Path mismatch between official and extended on ID {iid}")
                
        # Merged 对齐核验
        mg = merged_id_map.get(iid)
        if mg:
            if mg.get("path") != o_path or mg.get("caption") != o.get("caption"):
                violations.append(f"Merged record mismatch on ID {iid}: path or caption mismatch")
                
        # Metadata 路径核验
        mr = meta_id_map.get(iid)
        if mr:
            if mr.get("path") != o_path:
                violations.append(f"Metadata path mismatch on ID {iid}: {mr.get('path')} vs {o_path}")
                
        # Mapping 路径核验
        mp = mapped_id_map.get(iid)
        if mp:
            if mp.get("path") != o_path:
                violations.append(f"Mapping path mismatch on ID {iid}: {mp.get('path')} vs {o_path}")
                
    # 7. 图像文件与哈希检查
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

    # 8. 全量来源 URL 严格检验与全域名跨集泄漏检测 (彻底删除 example.org / shetu 等特判！)
    url_to_splits = defaultdict(set)
    page_to_splits = defaultdict(set)
    group_to_splits = defaultdict(set)
    
    for mr in meta_rows:
        iid = mr.get("image_id")
        s_url = str(mr.get("source_url", "")).strip()
        pub = str(mr.get("publisher", "")).strip()
        lic = str(mr.get("license", "")).strip()
        eth = str(mr.get("ethnicity", "")).strip()
        sp = str(mr.get("split", "")).strip()
        
        # 严格检查 URL 格式与有效主机名
        if not (s_url.startswith("http://") or s_url.startswith("https://")):
            violations.append(f"Metadata source_url invalid on ID {iid}: '{s_url}'")
        else:
            parts = s_url.split("/")
            if len(parts) < 3 or not parts[2].strip():
                violations.append(f"Metadata source_url invalid on ID {iid}: missing hostname '{s_url}'")
            elif "cn.bing.com/images/search" in s_url or s_url.endswith("/search"):
                violations.append(f"Metadata source_url invalid on ID {iid}: search homepage placeholder '{s_url}'")
                
        if not pub:
            violations.append(f"Metadata publisher empty on ID {iid}")
        if not lic:
            violations.append(f"Metadata license empty on ID {iid}")
        if eth not in CONFIRMED_ETHNICITIES:
            violations.append(f"Invented ethnicity '{eth}' in metadata on ID {iid}")
            
        # 全量域名泄漏收集
        if s_url and sp:
            url_to_splits[s_url].add(sp)
            
        page = str(mr.get("source_page_url", "")).strip()
        if page and sp:
            page_to_splits[page].add(sp)
            
        gid = str(mr.get("group_id", "")).strip()
        if gid and sp:
            group_to_splits[gid].add(sp)
            
    for mp in mapped_records:
        sp = str(mp.get("split", "")).strip()
        gid = str(mp.get("group_id", "")).strip()
        m_meta = mp.get("meta", {})
        page = str(m_meta.get("source_page_url", "")).strip()
        img_u = str(m_meta.get("image_url", "")).strip()
        if page and sp: page_to_splits[page].add(sp)
        if img_u and sp: url_to_splits[img_u].add(sp)
        if gid and sp: group_to_splits[gid].add(sp)
        
    for u, sps in url_to_splits.items():
        if len(sps) > 1:
            violations.append(f"Cross-split source leakage for source_url '{u}': splits={sps}")
            
    for p, sps in page_to_splits.items():
        if len(sps) > 1:
            violations.append(f"Cross-split source leakage for source_page_url '{p}': splits={sps}")
            
    for g, sps in group_to_splits.items():
        if len(sps) > 1:
            violations.append(f"Cross-split source leakage for group_id '{g}': splits={sps}")
            
    # 9. 细粒度结构属性、词表、空属性与中文字符检验
    for o in official_records:
        iid = o.get("image_id")
        e = ext_id_map.get(iid)
        if not e: continue
        
        eth_o = o.get("ethnicity", "")
        eth_e = e.get("ethnicity", "")
        if eth_o not in CONFIRMED_ETHNICITIES:
            violations.append(f"Invented ethnicity '{eth_o}' on official ID {iid}")
        if eth_e not in CONFIRMED_ETHNICITIES:
            violations.append(f"Invented ethnicity '{eth_e}' on extended ID {iid}")
            
        if set(o.keys()) != REQUIRED_OFFICIAL_KEYS:
            violations.append(f"Official keys mismatch on ID {iid}")
        top = o.get("top", {})
        if not isinstance(top, dict) or set(top.keys()) != REQUIRED_TOP_KEYS:
            violations.append(f"Top subkeys mismatch on ID {iid}")
            
        if not REQUIRED_EXTENDED_KEYS.issubset(set(e.keys())):
            missing_k = REQUIRED_EXTENDED_KEYS - set(e.keys())
            violations.append(f"Extended missing required keys {missing_k} on ID {iid}")
            
        # 空属性检查
        col = str(top.get("color", ""))
        if col == "":
            violations.append(f"Empty top.color on ID {iid}")
        if re.search(r"[\u4e00-\u9fff]", col):
            violations.append(f"Chinese characters found in color on ID {iid}")
            
        pat = str(top.get("pattern", ""))
        if pat == "":
            violations.append(f"Empty top.pattern on ID {iid}")
            
        cap = str(o.get("caption", ""))
        if cap == "":
            violations.append(f"Empty caption on ID {iid}")
        if re.search(r"[\u4e00-\u9fff]", cap):
            violations.append(f"Chinese characters found in caption on ID {iid}")
            
        # 材质证据与反幻觉
        mat = str(top.get("material", ""))
        m_ev = e.get("material_evidence", {})
        ev_lvl = m_ev.get("evidence_level")
        ev_mat = m_ev.get("material")
        if mat in ["wool", "cotton", "silk"]:
            if ev_lvl == "E3" or ev_mat == "unknown":
                violations.append(f"Known material '{mat}' claimed without E1/E2 evidence on ID {iid}")
                
        if mat == "unknown":
            cap_lower = cap.lower()
            for bad_m in FORBIDDEN_CAPTIONS_MATERIALS:
                if re.search(r"\b" + bad_m + r"\b", cap_lower):
                    violations.append(f"Caption asserted material '{bad_m}' while material is unknown on ID {iid}")
                    
        # 无上衣语义
        top_col = col.lower()
        top_sl = str(top.get("sleeve_length", "")).lower()
        top_st = e.get("top_structure", {})
        if top_col == "none" or top_sl == "none":
            if top_sl != "none":
                violations.append(f"Absent top has sleeve_length '{top_sl}' on ID {iid}")
            if top_st.get("collar_type") not in ["none", "none."]:
                violations.append(f"Absent top has collar_type '{top_st.get('collar_type')}' on ID {iid}")
            if top_st.get("opening_style") not in ["none", "none."]:
                violations.append(f"Absent top has opening_style '{top_st.get('opening_style')}' on ID {iid}")
            if top_st.get("decoration_location") and len(top_st.get("decoration_location")) > 0:
                violations.append(f"Absent top has decoration_location on ID {iid}")
                
        # 全字段受控词表检验 (sleeve_length, collar_type, opening_style, bottom_garment_type, headwear_type)
        if top_sl not in [s.lower() for s in vocab["sleeve_length"]]:
            violations.append(f"Invalid sleeve_length '{top_sl}' on ID {iid}")
            
        collar = str(top_st.get("collar_type", ""))
        if collar not in vocab["collar_type"]:
            violations.append(f"Invalid collar_type '{collar}' on ID {iid}")
            
        opening = str(top_st.get("opening_style", ""))
        if opening not in vocab["opening_style"]:
            violations.append(f"Invalid opening_style '{opening}' on ID {iid}")
            
        bot_st = e.get("bottom_structure", {})
        bot_type = str(bot_st.get("garment_type", ""))
        if bot_type not in vocab["bottom_garment_type"]:
            violations.append(f"Invalid bottom_garment_type '{bot_type}' on ID {iid}")
            
        head_st = e.get("headwear_details", {})
        head_type = str(head_st.get("type", ""))
        if head_type not in vocab["headwear_type"]:
            violations.append(f"Invalid headwear_type '{head_type}' on ID {iid}")
            
        # 质检状态
        qc = e.get("qc_audit", {})
        if qc.get("rule_check_passed") is not True:
            violations.append(f"qc_audit.rule_check_passed is not True on ID {iid}")
            
    is_passed = (len(violations) == 0)
    report = {
        "status": "PASSED" if is_passed else "FAILED",
        "total_records": n_off,
        "total_violations": len(violations),
        "violations": violations
    }
    
    report_out_path.parent.mkdir(parents=True, exist_ok=True)
    report_out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n[Audit Gate Verdict] Status: {report['status']} | Total: {n_off} | Violations: {len(violations)}")
    if not is_passed:
        for v in violations[:6]:
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
    else:
        ok = audit_dataset(ann_dir / "captions.jsonl", ann_dir / "extended_fine_grained_attributes.jsonl", ann_dir / "annotation_audit_report.json")
        
    if not ok:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
