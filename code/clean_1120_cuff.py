#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1120号样本左袖下缘局部背景清理脚本 (Reproducible Local Cuff Cleanup for Sample 1120)

针对 1120 号样本 (Dai_wiki_16053360.jpg) 图像左侧袖子下方约 x105–215、y76–112
区域内残留的展柜暗背景微斑与锯齿边缘，进行严格受控的局部纯白背景合成。
保留全部蓝色长袖、袖口及衣身像素，绝不进行生成式绘图或缩放平移。

掩码语义：
- 单通道 8-bit 灰度图像 (512x512)
- 像素值 255：需要清理的展柜灰黑残留背景像素（合成为 [255, 255, 255] 纯白）
- 像素值 0：保留不变的原有像素（服装、已有的纯白底等）

基准哈希：
- 原图 (Dai_wiki_16053360.jpg) SHA1: 746134954de9b3c9efb8484ca3ebb303246878b7
- 修前处理图 SHA256: a9ed72881c081e8e5ed67b5312d3aec790995ad4c86a5533e0681044c8327fe4
- 修后目标图 SHA256: 91a6bee95e746c7fa2393a3cf2ea083d6849e63272abdf1302e05db7dae80ff0
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(".")
DEFAULT_INPUT = BASE_DIR / "dataset/reproducible_1120/1120_before_repair.jpg"
DEFAULT_MASK = BASE_DIR / "dataset/reproducible_1120/1120_cuff_cleanup_mask.png"
DEFAULT_OUTPUT = BASE_DIR / "dataset/images/val/1120.jpg"

EXPECTED_INPUT_SHA256 = "a9ed72881c081e8e5ed67b5312d3aec790995ad4c86a5533e0681044c8327fe4"
EXPECTED_OUTPUT_SHA256 = "91a6bee95e746c7fa2393a3cf2ea083d6849e63272abdf1302e05db7dae80ff0"

def clean_image(input_path: Path, mask_path: Path, output_path: Path) -> str:
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    if not mask_path.exists():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    # 1. 验证修前图
    in_bytes = input_path.read_bytes()
    in_sha256 = hashlib.sha256(in_bytes).hexdigest()
    if in_sha256 != EXPECTED_INPUT_SHA256:
        print(f"[Warning] Input SHA256 ({in_sha256}) differs from baseline ({EXPECTED_INPUT_SHA256})")

    # 2. 读取图像与掩码
    img = Image.open(input_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    
    if img.size != (512, 512):
        raise ValueError(f"Input size {img.size} != (512, 512)")
    if mask.size != (512, 512):
        raise ValueError(f"Mask size {mask.size} != (512, 512)")

    arr_img = np.array(img)
    arr_mask = np.array(mask)

    # 3. 掩码为 255 的位置置为纯白 (255, 255, 255)
    cleaned_arr = arr_img.copy()
    cleaned_arr[arr_mask == 255] = [255, 255, 255]

    # 4. 保存修后图像
    output_path.parent.mkdir(parents=True, exist_ok=True)
    res_img = Image.fromarray(cleaned_arr, mode="RGB")
    res_img.save(output_path, quality=95)

    # 5. 校验修后哈希
    out_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
    print(f"[Success] Applied mask ({np.sum(arr_mask == 255)} px) to {input_path.name} -> {output_path.name}")
    print(f"  Output SHA256: {out_sha256}")
    return out_sha256

def verify_output(target_path: Path) -> bool:
    if not target_path.exists():
        print(f"[FAILED] Target image not found: {target_path}")
        return False
    target_sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
    if target_sha256 == EXPECTED_OUTPUT_SHA256:
        print(f"[PASSED] Target {target_path.name} exactly matches expected SHA256: {target_sha256}")
        return True
    else:
        print(f"[FAILED] Target {target_path.name} SHA256 mismatch:")
        print(f"  Actual:   {target_sha256}")
        print(f"  Expected: {EXPECTED_OUTPUT_SHA256}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Deterministic local cuff cleanup for 1120.jpg")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to before-repair image")
    parser.add_argument("--mask", type=Path, default=DEFAULT_MASK, help="Path to cleanup mask PNG")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to write cleaned image")
    parser.add_argument("--verify", action="store_true", help="Verify target image hash only")
    args = parser.parse_args()

    if args.verify:
        ok = verify_output(args.output)
        sys.exit(0 if ok else 1)
    else:
        clean_image(args.input, args.mask, args.output)
        # Also sync processed cache if it exists
        proc_cache = BASE_DIR / "dataset/processed/Dai/Dai_wiki_16053360.jpg"
        if proc_cache.exists():
            clean_image(args.input, args.mask, proc_cache)
        ok = verify_output(args.output)
        sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
