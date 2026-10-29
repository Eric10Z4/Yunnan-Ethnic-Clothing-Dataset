#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三 · 步骤二：扩展处理至 2,540 张规模 (2500张左右，不超过3000张)
- 精选 10 大云南世居民族，各类 220~270 张，配比极佳 (1.23:1)
- 自动断点续跑：检测已有的 1,730 张，只处理新增的 810 张样本
- 执行 Rembg U2Net 抠图、75% 等比缩放与 512x512 纯白底合成
- 实时校验：中心偏差 <= 10%, 主体比例 >= 60%
"""

import os
import csv
import time
import json
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import numpy as np
from rembg import remove, new_session

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
CLEANED_DIR = BASE_DIR / "dataset" / "cleaned"
CLEANED_META_FILE = CLEANED_DIR / "cleaned_metadata.csv"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
MANIFEST_FILE = PROCESSED_DIR / "processing_manifest.csv"

TARGET_SIZE = 512
MAX_CENTER_DEV_RATIO = 0.10
MIN_BBOX_RATIO = 0.60
TARGET_BBOX_RATIO = 0.75

# 扩充目标配额总计 2,540 张 (严格控制在 2500 左右且不超过 3000)
QUOTAS = {
    "Dai": 270,
    "Zhuang": 270,
    "Miao": 260,
    "Yi": 260,
    "Tibetan": 260,
    "Bai": 260,
    "Wa": 250,
    "Naxi": 250,
    "Hani": 240,
    "Jingpo": 220
}

def load_selected_candidates():
    by_eth = defaultdict(list)
    with open(CLEANED_META_FILE, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_eth[r["ethnicity_en"]].append(r)
            
    selected = []
    for eth, quota in QUOTAS.items():
        candidates = by_eth.get(eth, [])
        candidates.sort(
            key=lambda x: (
                float(x.get("sharpness", 0)),
                int(x.get("width", 0)) * int(x.get("height", 0))
            ),
            reverse=True
        )
        picked = candidates[:quota]
        selected.extend(picked)
        print(f"  {eth}: 目标 {len(picked)} 张 (候选库总量: {len(candidates)})")
        
    return selected

def process_image(item, session):
    fname = item["filename"]
    eth = item["ethnicity_en"]
    cleaned_rel = item["cleaned_path"]
    src_path = BASE_DIR / cleaned_rel
    
    try:
        with Image.open(src_path) as orig:
            orig_rgb = orig.convert("RGB")
            
            rgba = remove(orig_rgb, session=session)
            alpha = np.array(rgba)[:, :, 3]
            
            coords = np.argwhere(alpha > 10)
            if len(coords) == 0:
                return {
                    "sample_id": item["sample_id"], "filename": fname, "ethnicity": eth,
                    "status": "FAIL", "reason": "NO_FOREGROUND_FOUND",
                    "bbox_ratio": 0, "center_dev_x": 0, "center_dev_y": 0
                }
                
            ymin, xmin = coords.min(axis=0)
            ymax, xmax = coords.max(axis=0)
            w_box = max(1, xmax - xmin)
            h_box = max(1, ymax - ymin)
            
            subject_crop = rgba.crop((xmin, ymin, xmax, ymax))
            
            target_len = int(TARGET_SIZE * TARGET_BBOX_RATIO)
            scale = target_len / max(w_box, h_box)
            new_w = max(1, int(w_box * scale))
            new_h = max(1, int(h_box * scale))
            resized_subject = subject_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            canvas = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), (255, 255, 255))
            paste_x = (TARGET_SIZE - new_w) // 2
            paste_y = (TARGET_SIZE - new_h) // 2
            canvas.paste(resized_subject, (paste_x, paste_y), mask=resized_subject.split()[3])
            
            cx = paste_x + new_w / 2.0
            cy = paste_y + new_h / 2.0
            dev_x = abs(cx - TARGET_SIZE / 2.0)
            dev_y = abs(cy - TARGET_SIZE / 2.0)
            bbox_ratio = max(new_w, new_h) / TARGET_SIZE
            
            center_valid = (dev_x / TARGET_SIZE <= MAX_CENTER_DEV_RATIO) and (dev_y / TARGET_SIZE <= MAX_CENTER_DEV_RATIO)
            bbox_valid = bbox_ratio >= MIN_BBOX_RATIO
            
            if not (center_valid and bbox_valid):
                return {
                    "sample_id": item["sample_id"], "filename": fname, "ethnicity": eth,
                    "status": "FAIL", "reason": "GEOMETRY_MISMATCH",
                    "bbox_ratio": round(bbox_ratio, 3), "center_dev_x": round(dev_x, 1), "center_dev_y": round(dev_y, 1)
                }
                
            out_dir = PROCESSED_DIR / eth
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / fname
            canvas.save(out_path, "JPEG", quality=95)
            
            return {
                "sample_id": item["sample_id"], "filename": fname, "ethnicity": eth,
                "status": "SUCCESS", "reason": "OK",
                "processed_path": str(out_path.relative_to(BASE_DIR)),
                "bbox_ratio": round(bbox_ratio, 3), "center_dev_x": round(dev_x, 1), "center_dev_y": round(dev_y, 1)
            }
    except Exception as e:
        return {
            "sample_id": item["sample_id"], "filename": fname, "ethnicity": eth,
            "status": "FAIL", "reason": f"EXCEPTION_{str(e)[:40]}",
            "bbox_ratio": 0, "center_dev_x": 0, "center_dev_y": 0
        }

def run_batch():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print("==================================================")
    print("启动扩增处理至 2,540 张规模 (2500张区间)")
    print("==================================================")
    
    candidates = load_selected_candidates()
    
    existing_processed = set()
    for f in PROCESSED_DIR.glob("*/*"):
        if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            existing_processed.add((f.parent.name, f.name))
        
    remaining = [c for c in candidates if (c["ethnicity_en"], c["filename"]) not in existing_processed]
    print(f"\n已就绪: {len(existing_processed)} 张 | 新增待处理: {len(remaining)} 张 | 目标总量: {len(candidates)} 张")
    
    if len(remaining) == 0:
        print("所有样本均已处理完成！")
        return
        
    print("初始化 Rembg 深度分割引擎，开启 3 线程并发处理...")
    session = new_session("u2net")
    t0 = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_map = {pool.submit(process_image, item, session): item for item in remaining}
        completed = 0
        success_cnt = 0
        for fut in as_completed(future_map):
            res = fut.result()
            completed += 1
            if res["status"] == "SUCCESS":
                success_cnt += 1
            if completed % 100 == 0 or completed == len(remaining):
                elapsed = time.time() - t0
                fps = completed / max(0.1, elapsed)
                print(f"  [新增进度: {completed}/{len(remaining)}] 成功: {success_cnt} | 速度: {fps:.2f} 图/秒 | 耗时: {elapsed:.1f}s")
                
    total_time = time.time() - t0
    print("\n==================================================")
    print(f"增量处理全部完成！本次耗时: {total_time:.1f} 秒，新增成功: {success_cnt} 张")
    print("==================================================")

if __name__ == "__main__":
    run_batch()
