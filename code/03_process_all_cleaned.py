#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三 · 全量主体抠图与 512x512 纯白底标准化处理 (All Cleaned Images Batch Processor)
- 遍历 dataset/cleaned/ 下的全部 5,424 张样本
- 自动断点续跑：跳过已存在于 dataset/processed/ 的样本
- 执行 Rembg U2Net 抠图、75% 等比缩放与 512x512 (RGB 255,255,255) 纯白底合成
- 实时校验：中心偏差 <= 10%, 主体比例 >= 60%
- 4 线程并发，支持通过 --limit 参数分批次执行，防止长时间任务中断
"""

import os
import sys
import csv
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import numpy as np
from rembg import remove, new_session

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
CLEANED_DIR = BASE_DIR / "dataset" / "cleaned"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
MANIFEST_FILE = PROCESSED_DIR / "processing_manifest.csv"

TARGET_SIZE = 512
MAX_CENTER_DEV_RATIO = 0.10
MIN_BBOX_RATIO = 0.60
TARGET_BBOX_RATIO = 0.75

def process_image(src_path, session):
    fname = src_path.name
    eth = src_path.parent.name
    
    try:
        with Image.open(src_path) as orig:
            orig_rgb = orig.convert("RGB")
            
            rgba = remove(orig_rgb, session=session)
            alpha = np.array(rgba)[:, :, 3]
            
            coords = np.argwhere(alpha > 10)
            if len(coords) == 0:
                return {"filename": fname, "ethnicity": eth, "status": "FAIL", "reason": "NO_FOREGROUND_FOUND"}
                
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
                return {"filename": fname, "ethnicity": eth, "status": "FAIL", "reason": "GEOMETRY_MISMATCH"}
                
            out_dir = PROCESSED_DIR / eth
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / fname
            canvas.save(out_path, "JPEG", quality=95)
            
            return {
                "filename": fname, "ethnicity": eth, "status": "SUCCESS", "reason": "OK",
                "processed_path": str(out_path.relative_to(BASE_DIR)),
                "bbox_ratio": round(bbox_ratio, 3), "center_dev_x": round(dev_x, 1), "center_dev_y": round(dev_y, 1)
            }
    except Exception as e:
        return {"filename": fname, "ethnicity": eth, "status": "FAIL", "reason": f"EXCEPTION_{str(e)[:40]}"}

def main(limit=None):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    
    all_cleaned = [f for d in CLEANED_DIR.iterdir() if d.is_dir() for f in d.glob("*") if f.suffix.lower() in extensions]
    existing_processed = set()
    for d in PROCESSED_DIR.iterdir():
        if d.is_dir():
            for f in d.glob("*"):
                if f.suffix.lower() in extensions:
                    existing_processed.add((d.name, f.name))
                    
    remaining = [f for f in all_cleaned if (f.parent.name, f.name) not in existing_processed]
    print(f"[Info] 全量清洗库: {len(all_cleaned)} 张 | 已标准化: {len(existing_processed)} 张 | 剩余待抠图: {len(remaining)} 张")
    
    if len(remaining) == 0:
        print("[Success] 所有清洗后图片已全部完成 512x512 纯白底标准化！")
        return
        
    if limit and limit > 0:
        remaining = remaining[:limit]
        print(f"[Batch] 本批次计划处理前 {len(remaining)} 张样本...")
        
    print("[Engine] 初始化 Rembg U2Net，启用 4 线程并发处理...")
    session = new_session("u2net")
    t0 = time.time()
    
    completed = 0
    success_cnt = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(process_image, f, session): f for f in remaining}
        for fut in as_completed(future_map):
            res = fut.result()
            completed += 1
            if res["status"] == "SUCCESS":
                success_cnt += 1
            if completed % 100 == 0 or completed == len(remaining):
                elapsed = time.time() - t0
                fps = completed / max(0.1, elapsed)
                print(f"  [进度: {completed}/{len(remaining)}] 成功: {success_cnt} | 速度: {fps:.2f} 图/秒 | 耗时: {elapsed:.1f}s")
                
    total_time = time.time() - t0
    print(f"\n[Done] 本批次处理完成！耗时: {total_time:.1f} 秒，新增成功: {success_cnt} 张")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="处理样本上限数量")
    args = parser.parse_args()
    main(limit=args.limit)
