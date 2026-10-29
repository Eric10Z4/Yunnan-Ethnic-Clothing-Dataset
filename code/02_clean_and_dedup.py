#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段二：工业级自动化图像清洗与感知去重引擎 (Automated Cleaning & Perceptual Deduplication)
遵循 CV 数据集构建最高规范，六级级联漏斗过滤：
1. 完整性校验 (Integrity Check): 损坏文件、0字节、伪装图片、无法解码的截断文件
2. 几何与分辨率过滤 (Geometry Check): 最小分辨率约束 (min(w,h) >= 220px), 异常长宽比 (aspect_ratio <= 3.0)
3. 信息熵与单色过滤 (Low-Information Filter): 纯色占位图、全白/全灰/全黑图 (std(L) >= 15.0)
4. 标准化清晰度过滤 (Normalized Sharpness Filter): 统一长边至512后计算拉普拉斯算子方差 (variance >= 45.0)
5. 像素级精准去重 (Exact Deduplication): 原始像素 MD5 散列匹配
6. 感知哈希去重 (Perceptual Deduplication): 32x32 DCT 变换 64位 pHash，海明距离 <= 5 判为近重复

输出产物：
- dataset/cleaned/{ethnicity}/ : 清洗后高质图像库
- dataset/cleaned/exclusion_log.csv : 逐样本剔除原因台账
- dataset/cleaned/cleaned_metadata.csv : 继承阶段一溯源信息的清洗后元数据
- dataset/cleaned/cleaning_report.json : 全流程统计指标与留存率分析报告
"""

import os
import csv
import json
import time
import hashlib
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import scipy.fftpack as fft
import scipy.ndimage as ndi
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = False

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
RAW_DIR = BASE_DIR / "dataset" / "raw"
RAW_METADATA_FILE = RAW_DIR / "raw_metadata.csv"

CLEANED_DIR = BASE_DIR / "dataset" / "cleaned"
EXCLUSION_LOG_FILE = CLEANED_DIR / "exclusion_log.csv"
CLEANED_METADATA_FILE = CLEANED_DIR / "cleaned_metadata.csv"
REPORT_FILE = CLEANED_DIR / "cleaning_report.json"

# 超参数阈值定义
MIN_DIM_PX = 220
MAX_ASPECT_RATIO = 3.0
MIN_LUM_STD = 15.0
MIN_SHARPNESS_VAR = 45.0
PHASH_HAMMING_THRESHOLD = 5

def compute_phash(pil_img):
    img = pil_img.convert("L").resize((32, 32), Image.Resampling.BILINEAR)
    pixels = np.array(img, dtype=np.float32)
    dct = fft.dct(fft.dct(pixels, axis=0, norm="ortho"), axis=1, norm="ortho")
    dct_low = dct[:8, :8]
    med = np.median(dct_low.flatten()[1:])
    return (dct_low > med).flatten()

def compute_normalized_sharpness(pil_img, ref_size=512):
    w, h = pil_img.size
    scale = ref_size / max(w, h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    img_resized = pil_img.convert("L").resize((new_w, new_h), Image.Resampling.BILINEAR)
    arr = np.array(img_resized, dtype=np.float32)
    lap = ndi.laplace(arr)
    return float(np.var(lap))

def inspect_single_image(fpath: Path):
    fname = fpath.name
    eth = fpath.parent.name
    
    try:
        size_bytes = fpath.stat().st_size
        if size_bytes < 5120:
            return {"status": "REJECT", "file": fpath, "stage": "INTEGRITY", "reason": "FILE_TOO_SMALL", "metric": f"{size_bytes} bytes", "thresh": ">= 5120"}
        
        with Image.open(fpath) as img:
            img.verify()
        
        pil_img = Image.open(fpath)
        pil_img = pil_img.convert("RGB")
        w, h = pil_img.size
    except Exception as e:
        return {"status": "REJECT", "file": fpath, "stage": "INTEGRITY", "reason": "CORRUPTED_OR_UNREADABLE", "metric": str(e)[:60], "thresh": "valid_image"}

    min_dim = min(w, h)
    if min_dim < MIN_DIM_PX:
        return {"status": "REJECT", "file": fpath, "stage": "GEOMETRY", "reason": "RESOLUTION_TOO_LOW", "metric": f"{w}x{h} (min={min_dim})", "thresh": f">={MIN_DIM_PX}"}
    
    ar = max(w / h, h / w)
    if ar > MAX_ASPECT_RATIO:
        return {"status": "REJECT", "file": fpath, "stage": "GEOMETRY", "reason": "EXTREME_ASPECT_RATIO", "metric": f"{ar:.2f}", "thresh": f"<={MAX_ASPECT_RATIO}"}

    gray_arr = np.array(pil_img.convert("L"))
    std_val = float(np.std(gray_arr))
    if std_val < MIN_LUM_STD:
        return {"status": "REJECT", "file": fpath, "stage": "LOW_INFO", "reason": "MONOCHROMATIC_OR_BLANK", "metric": f"std={std_val:.2f}", "thresh": f">={MIN_LUM_STD}"}

    sharpness = compute_normalized_sharpness(pil_img)
    if sharpness < MIN_SHARPNESS_VAR:
        return {"status": "REJECT", "file": fpath, "stage": "SHARPNESS", "reason": "BLURRY_OR_OOF", "metric": f"var={sharpness:.1f}", "thresh": f">={MIN_SHARPNESS_VAR}"}

    exact_hash = hashlib.md5(pil_img.tobytes()).hexdigest()
    phash = compute_phash(pil_img)

    return {
        "status": "PASS",
        "file": fpath,
        "filename": fname,
        "ethnicity": eth,
        "width": w,
        "height": h,
        "sharpness": sharpness,
        "exact_hash": exact_hash,
        "phash": phash
    }

def run_cleaning_and_deduplication():
    start_time = time.time()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    
    raw_meta = {}
    if RAW_METADATA_FILE.exists():
        with open(RAW_METADATA_FILE, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                raw_meta[r["filename"]] = r

    all_raw_files = [p for p in RAW_DIR.glob("*/*") if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
    print(f"[Start] 启动图像质量清洗漏斗，待处理文件总数: {len(all_raw_files)} 张...")

    exclusions = []
    candidates = []

    print("[Stage 1-4] 正在并发执行：完整性解码、几何分辨率、单色过滤与标准化清晰度计算...")
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(inspect_single_image, f): f for f in all_raw_files}
        for fut in as_completed(futures):
            res = fut.result()
            if res["status"] == "REJECT":
                exclusions.append({
                    "sample_id": res["file"].stem,
                    "filename": res["file"].name,
                    "ethnicity": res["file"].parent.name,
                    "stage": res["stage"],
                    "reason": res["reason"],
                    "metric_value": res["metric"],
                    "threshold": res["thresh"]
                })
            else:
                candidates.append(res)

    print(f"[Stage 1-4 完成] 通过单图基础体检: {len(candidates)} 张，拦截不合规样本: {len(exclusions)} 张。")

    print("[Stage 5-6] 正在执行全库精确 MD5 去重与感知哈希 (pHash) 邻域去重...")
    seen_exact_hashes = set()
    accepted_records = []
    accepted_phashes = []

    candidates.sort(key=lambda x: str(x["file"]))

    for cand in candidates:
        fname = cand["filename"]
        eth = cand["ethnicity"]
        eh = cand["exact_hash"]
        ph = cand["phash"]

        if eh in seen_exact_hashes:
            exclusions.append({
                "sample_id": cand["file"].stem,
                "filename": fname,
                "ethnicity": eth,
                "stage": "EXACT_DEDUP",
                "reason": "DUPLICATE_IDENTICAL_PIXELS",
                "metric_value": eh[:12],
                "threshold": "unique"
            })
            continue

        if len(accepted_phashes) > 0:
            accepted_matrix = np.array(accepted_phashes, dtype=bool)
            hamming_dists = np.count_nonzero(accepted_matrix != ph, axis=1)
            min_dist = int(np.min(hamming_dists))
            if min_dist <= PHASH_HAMMING_THRESHOLD:
                exclusions.append({
                    "sample_id": cand["file"].stem,
                    "filename": fname,
                    "ethnicity": eth,
                    "stage": "PERCEPTUAL_DEDUP",
                    "reason": "NEAR_DUPLICATE_PHASH",
                    "metric_value": f"Hamming_dist={min_dist}",
                    "threshold": f">{PHASH_HAMMING_THRESHOLD}"
                })
                continue

        seen_exact_hashes.add(eh)
        accepted_phashes.append(ph)
        accepted_records.append(cand)

    print(f"[Stage 5-6 完成] 全量去重结束，最终合格保留样本: {len(accepted_records)} 张！")

    print("[Persist] 正在将清洗后高质图像分发至 dataset/cleaned/ 目录...")
    cleaned_meta_rows = []
    
    with open(EXCLUSION_LOG_FILE, "w", newline="", encoding="utf-8") as f:
        fields = ["sample_id", "filename", "ethnicity", "stage", "reason", "metric_value", "threshold"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(exclusions)

    for cand in accepted_records:
        src_path = cand["file"]
        eth = cand["ethnicity"]
        fname = cand["filename"]
        dest_dir = CLEANED_DIR / eth
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / fname
        
        shutil.copy2(src_path, dest_path)

        m = raw_meta.get(fname, {})
        row = {
            "sample_id": cand["file"].stem,
            "ethnicity_zh": m.get("ethnicity_zh", eth),
            "ethnicity_en": eth,
            "filename": fname,
            "cleaned_path": str(dest_path.relative_to(BASE_DIR)),
            "width": cand["width"],
            "height": cand["height"],
            "sharpness": round(cand["sharpness"], 1),
            "source_type": m.get("source_type", "Web_Search_Verified"),
            "image_url": m.get("image_url", ""),
            "source_page_url": m.get("source_page_url", ""),
            "publisher": m.get("publisher", ""),
            "license": m.get("license", "Web Published / Editorial Use"),
            "collected_at": m.get("collected_at", "")
        }
        cleaned_meta_rows.append(row)

    if cleaned_meta_rows:
        with open(CLEANED_METADATA_FILE, "w", newline="", encoding="utf-8") as f:
            fields = list(cleaned_meta_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(cleaned_meta_rows)

    elapsed = time.time() - start_time
    eth_counts = {}
    for r in accepted_records:
        eth_counts[r["ethnicity"]] = eth_counts.get(r["ethnicity"], 0) + 1

    stage_rejections = {}
    for ex in exclusions:
        s = ex["stage"]
        stage_rejections[s] = stage_rejections.get(s, 0) + 1

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_raw_processed": len(all_raw_files),
        "total_cleaned_accepted": len(accepted_records),
        "total_excluded": len(exclusions),
        "retention_rate": f"{len(accepted_records) / len(all_raw_files) * 100:.2f}%",
        "elapsed_seconds": round(elapsed, 2),
        "exclusions_by_stage": stage_rejections,
        "distribution_by_ethnicity": eth_counts,
        "thresholds_used": {
            "min_dim_px": MIN_DIM_PX,
            "max_aspect_ratio": MAX_ASPECT_RATIO,
            "min_luminance_std": MIN_LUM_STD,
            "min_sharpness_laplacian_variance": MIN_SHARPNESS_VAR,
            "phash_hamming_threshold": PHASH_HAMMING_THRESHOLD
        }
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n==================================================")
    print("自动化清洗与去重完成！核心成果指标如下：")
    print(f"  原始输入样本: {len(all_raw_files)} 张")
    print(f"  合格保留样本: {len(accepted_records)} 张 (留存率: {report['retention_rate']})")
    print(f"  剔除异常样本: {len(exclusions)} 张")
    print(f"  各过滤阶段剔除数: {stage_rejections}")
    print(f"  清洗后各民族分布: {eth_counts}")
    print(f"  总耗时: {elapsed:.2f} 秒")
    print(f"  剔除原因日志: {EXCLUSION_LOG_FILE}")
    print(f"  清洗元数据表: {CLEANED_METADATA_FILE}")
    print(f"  分析统计报告: {REPORT_FILE}")
    print("==================================================")

if __name__ == "__main__":
    run_cleaning_and_deduplication()
