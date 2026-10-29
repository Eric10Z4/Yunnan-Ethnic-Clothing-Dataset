#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三：主体分割与图像规范化处理 (Subject Segmentation & Standardization)
严格遵循任务书第 4 节规范：
1. 抠出主体并替换为纯白背景 (RGB 255, 255, 255)
2. 保持宽高比居中缩放，确保主体较长边占 512 的 60% 以上 (>= 307.2 px)
3. 纯白填充补边至 512 × 512 像素
4. 严格校验中心偏差：横向与纵向中心偏差均不超过 512 * 10% = 51.2 像素
"""

import os
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CLEANED_DIR = BASE_DIR / "dataset" / "cleaned"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"

TARGET_SIZE = 512
MAX_CENTER_DEV_RATIO = 0.10  # 偏差 <= 10%
MIN_BBOX_RATIO = 0.60        # 较长边 >= 60%

def segment_subject_rembg(pil_img):
    """
    使用 rembg 抠取前景主体，返回带有透明通道的 RGBA 图像。
    若未安装 rembg，则自动降级为颜色/边缘检测估计。
    """
    try:
        from rembg import remove
        return remove(pil_img)
    except ImportError:
        # Fallback: 基于自适应阈值与形态学的简易前景提取
        np_img = np.array(pil_img)
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, mask = cv2.threshold(blur, 240, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
        rgba = cv2.cvtColor(np_img, cv2.COLOR_RGB2RGBA)
        rgba[:, :, 3] = mask
        return Image.fromarray(rgba)

def process_and_standardize(input_path: Path, output_path: Path) -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as orig:
        orig_rgb = orig.convert("RGB")

    # 1. 抠图获取透明通道
    rgba = segment_subject_rembg(orig_rgb)
    alpha = np.array(rgba)[:, :, 3]

    # 2. 计算主体外接矩形 (Bounding Box)
    coords = cv2.findNonZero(alpha)
    if coords is None:
        return {"status": "FAIL", "reason": "NO_SUBJECT_DETECTED"}

    x, y, w, h = cv2.boundingRect(coords)
    subject_crop = rgba.crop((x, y, x + w, y + h))

    # 3. 缩放主体使较长边占 512 的 75% (确保满足 >= 60% 且不超过画布)
    target_subject_len = int(TARGET_SIZE * 0.75)
    scale = target_subject_len / max(w, h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized_subject = subject_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 4. 创建纯白 512x512 画布
    canvas = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), (255, 255, 255))
    paste_x = (TARGET_SIZE - new_w) // 2
    paste_y = (TARGET_SIZE - new_h) // 2

    # 将 RGBA 主体贴入纯白画布
    canvas.paste(resized_subject, (paste_x, paste_y), mask=resized_subject.split()[3])

    # 5. 校验规范硬指标
    # 中心点校验
    cx = paste_x + new_w / 2.0
    cy = paste_y + new_h / 2.0
    dev_x = abs(cx - TARGET_SIZE / 2.0)
    dev_y = abs(cy - TARGET_SIZE / 2.0)

    center_valid = (dev_x <= TARGET_SIZE * MAX_CENTER_DEV_RATIO) and (dev_y <= TARGET_SIZE * MAX_CENTER_DEV_RATIO)
    bbox_ratio = max(new_w, new_h) / float(TARGET_SIZE)
    bbox_valid = bbox_ratio >= MIN_BBOX_RATIO

    if not (center_valid and bbox_valid):
        return {
            "status": "FAIL",
            "reason": f"OUT_OF_SPEC: center_dev=({dev_x:.1f},{dev_y:.1f}), bbox_ratio={bbox_ratio:.2f}"
        }

    canvas.save(output_path, "JPEG", quality=95)
    return {
        "status": "SUCCESS",
        "bbox_ratio": bbox_ratio,
        "center_dev": (dev_x, dev_y)
    }

def batch_process():
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    img_files = [f for f in CLEANED_DIR.glob("*") if f.suffix.lower() in valid_exts]
    print(f"[Process] 待处理样本: {len(img_files)} 张...")
    
    success_cnt = 0
    fail_cnt = 0
    for f in img_files:
        out_file = PROCESSED_DIR / f"{f.stem}.jpg"
        res = process_and_standardize(f, out_file)
        if res["status"] == "SUCCESS":
            success_cnt += 1
        else:
            fail_cnt += 1
            print(f"[Warn] 图像不合规跳过: {f.name} -> {res.get('reason')}")
            
    print(f"[Process] 处理完成！成功生成合规 512x512 纯白底图像: {success_cnt} 张，不合规: {fail_cnt} 张。")

if __name__ == "__main__":
    batch_process()
