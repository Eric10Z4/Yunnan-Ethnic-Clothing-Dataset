#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段一：数据获取与来源登记 (Data Acquisition & Source Logging)
- 记录检索词、来源页面URL、采集时间、发布者、许可协议信息、分配样本原始ID
- 支持从本地已有图片清单或搜索链接下载，并将元数据记录到 dataset/raw/raw_metadata.csv
"""

import os
import csv
import datetime
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "dataset" / "raw"
RAW_METADATA_FILE = RAW_DIR / "raw_metadata.csv"

FIELDS = [
    "raw_id",
    "filename",
    "ethnicity",
    "search_keyword",
    "source_url",
    "page_url",
    "publisher",
    "license",
    "collected_at"
]

def init_raw_dir():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_METADATA_FILE.exists():
        with open(RAW_METADATA_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
        print(f"[Init] 已创建原始元数据表: {RAW_METADATA_FILE}")

def download_image(url: str, save_path: Path, timeout: int = 15) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception as e:
        print(f"[Download Error] {url} -> {e}")
    return False

def record_sample(raw_id: str, filename: str, ethnicity: str, search_keyword: str,
                  source_url: str, page_url: str, publisher: str, license_info: str):
    init_raw_dir()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "raw_id": raw_id,
        "filename": filename,
        "ethnicity": ethnicity,
        "search_keyword": search_keyword,
        "source_url": source_url,
        "page_url": page_url,
        "publisher": publisher,
        "license": license_info,
        "collected_at": now_str
    }
    with open(RAW_METADATA_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow(record)
    print(f"[Recorded] {raw_id} ({ethnicity}) - {filename}")

if __name__ == "__main__":
    init_raw_dir()
    print("阶段一脚本初始化完成。通过 download_image() 与 record_sample() 批量获取并登记来源。")
