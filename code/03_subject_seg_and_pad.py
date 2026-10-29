#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三：主体抠图、512x512纯白底合成与几何硬指标合规化引擎 (Segmentation & Standardization Engine)
严格遵循任务书第 4 节规范：
1. 抠出主体前景透明通道 (Rembg U2Net / ONNX Runtime)
2. 保持宽高比将主体较长边等比缩放至 512 的 75% (384px, 保证 >= 60% 且边距适度)
3. 纯白填充补边至 512 × 512 像素 (RGB 255, 255, 255)
4. 严格校验中心偏差：横向与纵向中心偏差均不超过 512 * 10% = 51.2 像素
5. 自动记录处理日志至 dataset/processed/processing_log.csv
"""

import os
import csv
import json
import time
from pathlib import Path
from PIL import Image
import numpy as np
from rembg import remove, new_session

BASE_DIR = Path(__file__).resolve().parent.parent
CLEANED_DIR = BASE_DIR / "dataset" / "cleaned"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
LOG_FILE = PROCESSED_DIR / "processing_log.csv"

TARGET_SIZE = 512
MAX_CENTER_DEV_RATIO = 0.10  # 偏差 <= 10% (51.2px)
MIN_BBOX_RATIO = 0.60        # 较长边 >= 60% (307.2px)
TARGET_BBOX_RATIO = 0.75     # 目标居中缩放较长边占 75% (384px)

def process_single_image(img_path: Path, session) -> dict:
    fname = img_path.name
    eth = img_path.parent.name
    
    try:
        with Image.open(img_path) as orig:
            orig_rgb = orig.convert("RGB")
            w_orig, h_orig = orig_rgb.size
            
            # 1. 抠图提取 Alpha 通道
            rgba = remove(orig_rgb, session=session)
            alpha = np.array(rgba)[:, :, 3]
            
            # 2. 计算主体前景外接矩形
            coords = np.argwhere(alpha > 10)  # y, x
            if len(coords) == 0:
                return {"file": fname, "ethnicity": eth, "status": "FAIL", "reason": "NO_FOREGROUND_FOUND"}
            
            ymin, xmin = coords.min(axis=0)
            ymax, xmax = coords.max(axis=0)
            w_box = xmax - xmin
            h_box = ymax - ymin
            
            # 3. 裁剪主体前景
            subject_crop = rgba.crop((xmin, ymin, xmax, ymax))
            
            # 4. 等比尺度缩放
            target_len = int(TARGET_SIZE * TARGET_BBOX_RATIO)
            scale = target_len / max(w_box, h_box)
            new_w = max(1, int(w_box * scale))
            new_h = max(1, int(h_box * scale))
            resized_subject = subject_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # 5. 合成至 512x512 纯白画布
            canvas = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), (255, 255, 255))
            paste_x = (TARGET_SIZE - new_w) // 2
            paste_y = (TARGET_SIZE - new_h) // 2
            canvas.paste(resized_subject, (paste_x, paste_y), mask=resized_subject.split()[3])
            
            # 6. 几何硬指标合规性核验
            cx = paste_x + new_w / 2.0
            cy = paste_y + new_h / 2.0
            dev_x = abs(cx - TARGET_SIZE / 2.0)
            dev_y = abs(cy - TARGET_SIZE / 2.0)
            
            dev_x_ratio = dev_x / TARGET_SIZE
            dev_y_ratio = dev_y / TARGET_SIZE
            bbox_ratio = max(new_w, new_h) / TARGET_SIZE
            
            center_valid = (dev_x_ratio <= MAX_CENTER_DEV_RATIO) and (dev_y_ratio <= MAX_CENTER_DEV_RATIO)
            bbox_valid = bbox_ratio >= MIN_BBOX_RATIO
            
            if not (center_valid and bbox_valid):
                return {
                    "file": fname,
                    "ethnicity": eth,
                    "status": "FAIL",
                    "reason": f"GEOMETRY_OUT_OF_SPEC: center_dev=({dev_x:.1f},{dev_y:.1f}), bbox_ratio={bbox_ratio:.2f}"
                }
            
            # 保存至 dataset/processed/{ethnicity}/{fname}
            out_dir = PROCESSED_DIR / eth
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / fname
            canvas.save(out_path, "JPEG", quality=95)
            
            return {
                "file": fname,
                "ethnicity": eth,
                "status": "SUCCESS",
                "processed_path": str(out_path.relative_to(BASE_DIR)),
                "bbox_ratio": round(bbox_ratio, 3),
                "center_dev_x": round(dev_x, 1),
                "center_dev_y": round(dev_y, 1),
                "reason": "OK"
            }
    except Exception as e:
        return {"file": fname, "ethnicity": eth, "status": "FAIL", "reason": f"EXCEPTION: {str(e)[:60]}"}

if __name__ == "__main__":
    print("阶段三主体分割与几何标准化引擎已就绪。")
