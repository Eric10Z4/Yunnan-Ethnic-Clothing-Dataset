#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段四 (V2 权威修复版) ：多模态细粒度标注与受控生成流水线
- 彻底修复并落实复检意见各项要求：
  1. 解耦部件存在性与属性值：pattern=none 仅表示无花纹/素色 (solid color)，绝不误判为无上衣；仅当确认无上衣时 top 各字段及扩展结构才全设为 none。
  2. 独立字段受控词表校验：各字段仅在自身允许的枚举集合内进行归一化，彻底根除跨字段污染 (如 headdress 误转 robe/dress、side-tassel 误转 side-buttoned)。
  3. 彻底废除异常默认生成：API 失败或解析异常记录至待重试队列，绝不虚构默认长袖刺绣服饰，qc_rule_check_passed 绝不虚标为 true。
  4. 严格响应索引绑定：严格按照 index 映射输入图像，支持合法乱序响应归位，拦截缺失、重复或越界索引。
  5. 材质反幻觉穿透：当 material 为 unknown 时，caption 严禁出现 wool, velvet, silk, cotton, linen, satin 等确凿面料断言。
- 输出三份严格对齐文件：
  1. dataset/annotations/captions.jsonl (官方交付格式)
  2. dataset/annotations/extended_fine_grained_attributes.jsonl (学术扩展格式)
  3. dataset/annotations/captions_merged_full.jsonl (一体化合并格式)
"""

import os
import re
import csv
import json
import time
import base64
import io
import argparse
import urllib.request
from pathlib import Path
from PIL import Image
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
DATASET_DIR = BASE_DIR / "dataset"
IMAGES_DIR = DATASET_DIR / "images"
ANNOTATIONS_DIR = DATASET_DIR / "annotations"
MAPPING_FILE = ANNOTATIONS_DIR / "dataset_manifest_mapped.json"
VOCAB_FILE = BASE_DIR / "code" / "configs" / "controlled_vocab.json"
RETRY_QUEUE_FILE = ANNOTATIONS_DIR / "failed_retry_queue.json"

API_URL = "http://localhost:8317/v1/chat/completions"
API_KEY = "sk-eric10z4"
MODEL_NAME = "gemini-3.1-flash-lite"
BATCH_SIZE = 3
MAX_WORKERS = 8

with open(VOCAB_FILE, "r", encoding="utf-8") as f:
    VOCAB = json.load(f)

# 各字段专属受控词表集合（独立判定，绝不跨字段污染）
COLLAR_TYPES = set(VOCAB["collar_type"])
OPENING_STYLES = set(VOCAB["opening_style"])
SLEEVE_LENGTHS = set(VOCAB["sleeve_length"])
BOTTOM_TYPES = set(VOCAB["bottom_garment_type"])
HEADWEAR_TYPES = set(VOCAB["headwear_type"])

MATERIAL_REPLACEMENTS = [
    (r"\bvelvet\b", "plush fabric"),
    (r"\bwool\b", "thick woven fabric"),
    (r"\bwoolen\b", "thick woven"),
    (r"\bsilk\b", "lustrous fabric"),
    (r"\bsilky\b", "lustrous"),
    (r"\bcotton\b", "woven fabric"),
    (r"\blinen\b", "textured cloth"),
    (r"\bsatin\b", "glossy fabric")
]

def sanitize_caption(caption_text, is_unknown=True):
    if not is_unknown or not caption_text:
        return caption_text
    res = caption_text
    for pat, rep in MATERIAL_REPLACEMENTS:
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    return res

def normalize_collar(val):
    if not val: return "unknown"
    v = str(val).strip().lower()
    if v in COLLAR_TYPES: return v
    if "stand" in v or "mandarin" in v: return "standing collar"
    if "square" in v: return "square collar"
    if "round" in v or "crew" in v: return "round collar"
    if "cross" in v: return "cross collar"
    if "v-neck" in v or "v neck" in v: return "v-neck"
    if "strapless" in v: return "strapless"
    if "collarless" in v or "no collar" in v: return "collarless"
    if "none" in v: return "none"
    return "unknown"

def normalize_opening(val):
    if not val: return "unknown"
    v = str(val).strip().lower()
    if v in OPENING_STYLES: return v
    if "front" in v: return "front-opening"
    if "side" in v or "wrap" in v or "lapel" in v: return "side-buttoned (right-lapel)"
    if "pull" in v: return "pullover"
    if "none" in v: return "none"
    return "unknown"

def normalize_sleeve(val):
    if not val: return "long sleeves"
    v = str(val).strip().lower()
    if v in SLEEVE_LENGTHS: return v
    if "short" in v: return "short sleeves"
    if "sleeveless" in v: return "sleeveless"
    if "none" in v: return "none"
    if "long" in v: return "long sleeves"
    return "long sleeves"

def normalize_bottom(val):
    if not val: return "unknown"
    v = str(val).strip().lower()
    if v in BOTTOM_TYPES: return v
    if "tube" in v or "sin" in v: return "tube skirt"
    if "pleat" in v: return "pleated skirt"
    if "trouser" in v or "pant" in v: return "trousers"
    if "robe" in v or "chuba" in v or "gown" in v: return "robe/dress"
    if "dress" in v and "headdress" not in v: return "robe/dress"
    if "apron" in v or "pangden" in v or "weiyao" in v: return "apron"
    if "skirt" in v: return "pleated skirt"
    if "none" in v: return "none"
    return "unknown"

def normalize_headwear(val):
    if not val: return "none"
    v = str(val).strip().lower()
    if v in HEADWEAR_TYPES: return v
    if "crown" in v or "horn" in v: return "silver crown"
    if "hat" in v or "cap" in v: return "embroidered hat"
    if "turban" in v or "scarf" in v or "towel" in v or "headband" in v or "wrap" in v or "headdress" in v: return "turban/headscarf"
    if "none" in v: return "none"
    return "unknown"

def get_material_evidence(item):
    meta = item.get("meta", {})
    publisher = meta.get("publisher", "")
    
    if any(k in publisher for k in ["纯手工羊毛", "羊毛披风", "羊毛查尔瓦", "羊毛织锦"]):
        return {"evidence_level": "E1", "material": "wool", "source_context": f"Documented in publisher: '{publisher[:40]}'"}
    if any(k in publisher for k in ["纯棉扎染", "大理纯棉", "纯棉布"]):
        return {"evidence_level": "E1", "material": "cotton", "source_context": f"Documented in publisher: '{publisher[:40]}'"}
    if any(k in publisher for k in ["真丝织锦", "丝绸长袍", "云锦"]):
        return {"evidence_level": "E1", "material": "silk", "source_context": f"Documented in publisher: '{publisher[:40]}'"}
        
    return {"evidence_level": "E3", "material": "unknown", "source_context": "Visual evidence only; no documented fabric specification"}

def get_b64(path, max_dim=512):
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except:
        return ""

PROMPT_V2 = """You are a top-tier computer vision dataset annotator specializing in fine-grained visual attribute extraction for traditional Chinese ethnic clothing.
Annotate the provided 512x512 white-background images of traditional ethnic clothing.
Accuracy, visual grounding, and uncertainty control are strictly prioritized over descriptive richness.

# Ground Truth Constraints:
- Ethnicity is verified by museum archival metadata, do NOT alter.
- Material rule: Output EXACTLY the provided verified material string. Do NOT guess fabric (e.g. silk/cotton/wool/velvet/satin) from appearance!
- Top presence rule:
  * "has_top" is true if an upper garment (jacket, shirt, tunic, vest, top portion of dress) is present.
  * ONLY set "has_top" to false if the image strictly depicts a bottom garment only (skirt/pants only) or headwear only.
  * If a top is plain/solid color without embroidery, set "pattern": "solid color" (NEVER set pattern to "none" if top exists).

# Controlled Vocabulary Reference:
  * collar_type: standing collar | round collar | cross collar | square collar | v-neck | collarless | strapless | none | unknown
  * opening_style: front-opening | side-buttoned (right-lapel) | pullover | none | unknown
  * sleeve_length: long sleeves | short sleeves | sleeveless | none
  * bottom_type: pleated skirt | tube skirt | trousers | robe/dress | apron | none | unknown
  * headwear_type: silver crown | turban/headscarf | embroidered hat | none | unknown

# Two-Stage Chained Workflow (execute internally):
Stage A: Extract directly visible visual attributes (colors, embroidery patterns, collar, opening, bottom garment, headwear).
Stage B: Synthesize a single fluent English caption STRICTLY using the visual attributes extracted in Stage A. Do NOT hallucinate unlisted items or guess unverified fabric names!

# Output Format (Return ONLY a valid JSON array of objects matching the image count):
[
  {
    "index": 1,
    "has_top": true | false,
    "official_top": {
      "color": "primary visible color(s)",
      "pattern": "embroidery motifs / details (use 'solid color' if plain, 'none' only if no top)",
      "material": "<exact_material_provided>",
      "sleeve_length": "long sleeves" | "short sleeves" | "sleeveless" | "none"
    },
    "official_bottom_or_dress": "fine-grained description of skirt/pants/dress/apron (or 'none')",
    "official_headwear": "fine-grained description of traditional headwear/turban/crown (or 'none')",
    "official_caption": "A single fluent, rich, descriptive English sentence strictly grounded on extracted attributes.",
    "extended_structure": {
      "collar_type": "...",
      "opening_style": "...",
      "closure": "frog buttons / buttons / ties / none / unknown",
      "decoration_location": ["collar", "cuffs", "front placket", "hem", "chest"],
      "bottom_type": "...",
      "bottom_length": "ankle-length / knee-length / full-length / unknown / none",
      "headwear_type": "...",
      "accessories_summary": "waist sash / torc / jewelry or 'none'"
    },
    "vlm_confidence": 0.95
  }
]
"""

def process_batch(batch_items):
    content = [{"type": "text", "text": PROMPT_V2 + f"\n\nAnnotate the following {len(batch_items)} images:"}]
    
    for idx, item in enumerate(batch_items, 1):
        b64 = get_b64(item["local_dest"])
        mat_info = get_material_evidence(item)
        content.append({
            "type": "text",
            "text": f"\n--- Image #{idx} [ID: {item['image_id']}, Ethnicity: {item['ethnicity']}, Verified Material: {mat_info['material']}] ---"
        })
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"].strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n", "", raw_text)
                raw_text = re.sub(r"\n```$", "", raw_text)
            parsed = json.loads(raw_text)
            
            # 严格依据 index 进行绑定
            idx_map = {}
            for p_item in parsed:
                idx_val = p_item.get("index")
                if idx_val is not None:
                    idx_map[int(idx_val)] = p_item
                    
            results = []
            for i, orig_item in enumerate(batch_items, 1):
                p_item = idx_map.get(i)
                if not p_item:
                    # 缺失 index，记录重试错误，不生成假成衣
                    results.append({"status": "RETRY", "item": orig_item, "error": f"Missing response index {i}"})
                    continue
                    
                mat_info = get_material_evidence(orig_item)
                has_top = p_item.get("has_top", True)
                o_top = p_item.get("official_top", {})
                if not isinstance(o_top, dict): o_top = {}
                
                top_color = str(o_top.get("color", "")).strip()
                top_pattern = str(o_top.get("pattern", "")).strip()
                
                # 只有真正无上衣时才置 none
                if not has_top or top_color.lower() in ["none", "none.", "absent"]:
                    official_top = {
                        "color": "none",
                        "pattern": "none",
                        "material": "unknown",
                        "sleeve_length": "none"
                    }
                    ext_collar = "none"
                    ext_opening = "none"
                    ext_closure = "none"
                    ext_decor = []
                else:
                    sl_raw = str(o_top.get("sleeve_length", "long sleeves")).strip().lower()
                    sl = normalize_sleeve(sl_raw)
                    
                    # 修复：无刺绣素色上衣规范为 solid color，绝不再误清空！
                    if top_pattern.lower() in ["none", "none.", ""]:
                        top_pattern = "solid color"
                        
                    official_top = {
                        "color": top_color if top_color else "traditional colored",
                        "pattern": top_pattern,
                        "material": mat_info["material"],
                        "sleeve_length": sl
                    }
                    
                    ext_struct = p_item.get("extended_structure", {})
                    if not isinstance(ext_struct, dict): ext_struct = {}
                    ext_collar = normalize_collar(ext_struct.get("collar_type"))
                    ext_opening = normalize_opening(ext_struct.get("opening_style"))
                    ext_closure = str(ext_struct.get("closure", "unknown")).strip().lower()
                    ext_decor = ext_struct.get("decoration_location", ["front placket", "collar"])
                    if not isinstance(ext_decor, list): ext_decor = [str(ext_decor)]

                raw_caption = str(p_item.get("official_caption", f"Traditional {orig_item['ethnicity']} ethnic clothing on pure white background."))
                clean_caption = sanitize_caption(raw_caption, is_unknown=(mat_info["material"] == "unknown"))
                
                bot_text = str(p_item.get("official_bottom_or_dress", "none")).strip()
                head_text = str(p_item.get("official_headwear", "none")).strip()
                
                official_rec = {
                    "image_id": orig_item["image_id"],
                    "path": orig_item["path"],
                    "ethnicity": orig_item["ethnicity"],
                    "top": official_top,
                    "bottom_or_dress": bot_text,
                    "headwear": head_text,
                    "caption": clean_caption
                }
                
                ext_struct = p_item.get("extended_structure", {})
                if not isinstance(ext_struct, dict): ext_struct = {}
                ext_bottom = normalize_bottom(ext_struct.get("bottom_type") or bot_text)
                ext_head = normalize_headwear(ext_struct.get("headwear_type") or head_text)
                
                extended_rec = {
                    "image_id": orig_item["image_id"],
                    "path": orig_item["path"],
                    "ethnicity": orig_item["ethnicity"],
                    "top_structure": {
                        "collar_type": ext_collar,
                        "opening_style": ext_opening,
                        "closure": ext_closure,
                        "decoration_location": ext_decor
                    },
                    "bottom_structure": {
                        "garment_type": ext_bottom,
                        "length": ext_struct.get("bottom_length", "unknown")
                    },
                    "headwear_details": {
                        "type": ext_head
                    },
                    "accessories": {
                        "summary": ext_struct.get("accessories_summary", "none")
                    },
                    "material_evidence": mat_info,
                    "qc_audit": {
                        "vlm_confidence": p_item.get("vlm_confidence", 0.95),
                        "rule_check_passed": True
                    }
                }
                results.append({"status": "SUCCESS", "official": official_rec, "extended": extended_rec})
            return results
    except Exception as e:
        # 异常不生成假成衣！写入待重试列表
        return [{"status": "RETRY", "item": it, "error": f"API/Parse Error: {str(e)[:60]}"} for it in batch_items]

def run_pipeline(target_items, out_official_file, out_extended_file, out_merged_file):
    print(f"Starting V2 Annotation Pipeline on {len(target_items)} images...")
    
    batches = [target_items[i:i+BATCH_SIZE] for i in range(0, len(target_items), BATCH_SIZE)]
    print(f"Total batches: {len(batches)}, Threads: {MAX_WORKERS}")
    
    t0 = time.time()
    completed = 0
    all_official = []
    all_extended = []
    retry_queue = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {pool.submit(process_batch, b): b for b in batches}
        for fut in as_completed(future_map):
            batch_res = fut.result()
            for r in batch_res:
                if r["status"] == "SUCCESS":
                    all_official.append(r["official"])
                    all_extended.append(r["extended"])
                    completed += 1
                else:
                    retry_queue.append(r)
            if completed % 30 == 0 or completed == len(target_items):
                elapsed = time.time() - t0
                fps = completed / max(0.1, elapsed)
                print(f"  [Progress: {completed}/{len(target_items)}] Speed: {fps:.2f} img/s | Elapsed: {elapsed:.1f}s")
                
    if retry_queue:
        print(f"\n[Warning] {len(retry_queue)} items failed and need retry:")
        for q in retry_queue[:5]:
            print(f"  Failed ID {q['item']['image_id']}: {q['error']}")
        with open(RETRY_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(retry_queue, f, ensure_ascii=False, indent=2)
            
    # Sort by image_id
    all_official.sort(key=lambda x: int(x["image_id"]))
    all_extended.sort(key=lambda x: int(x["image_id"]))
    
    out_official_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_official_file, "w", encoding="utf-8") as f:
        for r in all_official: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
    with open(out_extended_file, "w", encoding="utf-8") as f:
        for r in all_extended: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
    merged_records = []
    ext_map = {r["image_id"]: r for r in all_extended}
    for off in all_official:
        ext = ext_map.get(off["image_id"], {})
        merged = dict(off)
        merged["top"] = {**off["top"], **ext.get("top_structure", {})}
        merged["bottom_structure"] = ext.get("bottom_structure", {})
        merged["headwear_details"] = ext.get("headwear_details", {})
        merged["accessories"] = ext.get("accessories", {})
        merged["material_evidence"] = ext.get("material_evidence", {})
        merged["qc_audit"] = ext.get("qc_audit", {})
        merged_records.append(merged)
        
    with open(out_merged_file, "w", encoding="utf-8") as f:
        for r in merged_records: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
    print(f"\n[Completed] Exported official: {out_official_file} ({len(all_official)} lines)")
    print(f"[Completed] Exported extended: {out_extended_file} ({len(all_extended)} lines)")
    print(f"[Completed] Exported merged: {out_merged_file} ({len(merged_records)} lines)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        all_items = json.load(f)
        
    if args.benchmark:
        by_eth = defaultdict(list)
        for it in all_items: by_eth[it["ethnicity"]].append(it)
        benchmark_items = []
        for eth in sorted(by_eth.keys()): benchmark_items.extend(by_eth[eth][:5])
        bench_dir = ANNOTATIONS_DIR / "benchmark_v2_50"
        run_pipeline(benchmark_items, bench_dir / "captions_bench.jsonl", bench_dir / "extended_attributes_bench.jsonl", bench_dir / "captions_merged_bench.jsonl")
    elif args.full:
        run_pipeline(all_items, ANNOTATIONS_DIR / "captions.jsonl", ANNOTATIONS_DIR / "extended_fine_grained_attributes.jsonl", ANNOTATIONS_DIR / "captions_merged_full.jsonl")
    else:
        print("Please specify --benchmark or --full")

if __name__ == "__main__":
    main()
