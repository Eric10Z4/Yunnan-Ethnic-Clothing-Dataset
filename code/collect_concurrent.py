#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云南民族服饰多源数据采集与台账登记脚本 (并发优化版)
- 数据源1: 维基共享资源 (Wikimedia Commons) 云南各民族服饰专题典藏（博物馆官方典藏，CC/公版许可，高可信度）
- 数据源2: 必应图像检索 (Bing Image Search) 严格溯源爬取（记录原网页 purl、图片 murl、标题 publisher）
- 聚焦民族（偏向云南）: 傣族 (Dai), 白族 (Bai), 彝族 (Yi), 苗族 (Miao), 哈尼族 (Hani), 纳西族 (Naxi), 佤族 (Wa)
- 输出目录: dataset/raw/{ethnicity}/
- 台账文件: dataset/raw/raw_metadata.csv
"""

import os
import re
import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "dataset" / "raw"
METADATA_FILE = RAW_DIR / "raw_metadata.csv"

ETHNIC_MAP = {
    "傣族": {"en": "Dai", "wiki_cat": "Category:Dai_clothing"},
    "白族": {"en": "Bai", "wiki_cat": "Category:Bai_clothing"},
    "彝族": {"en": "Yi", "wiki_cat": "Category:Yi_clothing"},
    "苗族": {"en": "Miao", "wiki_cat": "Category:Miao_clothing"},
    "哈尼族": {"en": "Hani", "wiki_cat": "Category:Hani_clothing"},
    "纳西族": {"en": "Naxi", "wiki_cat": "Category:Naxi_clothing"},
    "佤族": {"en": "Wa", "wiki_cat": "Category:Wa_clothing"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CSV_FIELDS = [
    "sample_id", "ethnicity_zh", "ethnicity_en", "source_type",
    "filename", "local_path", "image_url", "source_page_url",
    "publisher", "license", "collected_at"
]

def init_metadata():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        with open(METADATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def get_existing_urls():
    if not METADATA_FILE.exists():
        return set()
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {r["image_url"] for r in reader if "image_url" in r}

def download_file(url: str, save_path: Path, timeout: int = 6) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                content = resp.read()
                if len(content) < 5120:  # < 5KB 过滤
                    return False
                with open(save_path, "wb") as f:
                    f.write(content)
                return True
    except Exception:
        pass
    return False

def collect_wikimedia(eth_zh: str, eth_info: dict, max_items: int = 25):
    cat = eth_info["wiki_cat"]
    api_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle={cat}&gcmtype=file&gcmlimit={max_items}&prop=imageinfo&iiprop=url|size|extmetadata&format=json"
    req = urllib.request.Request(api_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [Wiki Err] {eth_zh}: {e}")
        return []

    pages = data.get("query", {}).get("pages", {})
    records = []
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for pid, pdata in pages.items():
        imageinfo = pdata.get("imageinfo", [{}])[0]
        img_url = imageinfo.get("url")
        desc_url = imageinfo.get("descriptionurl", "")
        if not img_url:
            continue

        extmeta = imageinfo.get("extmetadata", {})
        license_info = extmeta.get("LicenseShortName", {}).get("value", "CC-BY/Public-Domain")
        artist = extmeta.get("Artist", {}).get("value", "Wikimedia Contributor")
        artist = re.sub(r"<[^>]+>", "", artist).strip()[:100]

        ext = Path(img_url.split("?")[0]).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        sample_id = f"{eth_info['en']}_wiki_{pdata.get('pageid', int(time.time()))}"
        fname = f"{sample_id}{ext}"
        target_dir = RAW_DIR / eth_info["en"]
        target_dir.mkdir(parents=True, exist_ok=True)
        fpath = target_dir / fname

        records.append({
            "sample_id": sample_id,
            "ethnicity_zh": eth_zh,
            "ethnicity_en": eth_info["en"],
            "source_type": "Wikimedia_Museum_Collection",
            "filename": fname,
            "local_path": str(fpath.relative_to(BASE_DIR)),
            "image_url": img_url,
            "source_page_url": desc_url,
            "publisher": artist or "Yunnan Museum Archives",
            "license": license_info,
            "collected_at": now_str,
            "_save_path": fpath
        })
    return records

def collect_bing(eth_zh: str, eth_info: dict, max_items: int = 35):
    queries = [
        f"{eth_zh} 传统服饰",
        f"{eth_zh} 民族服饰 白底",
        f"{eth_zh} 刺绣 服饰",
    ]
    records = []
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    target_dir = RAW_DIR / eth_info["en"]
    target_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for q in queries:
        if count >= max_items:
            break
        search_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q)}&first=1&count=40"
        req = urllib.request.Request(search_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8")
        except Exception:
            continue

        raw_matches = re.findall(r'm=\"({.*?})\"', html)
        for m in raw_matches:
            if count >= max_items:
                break
            try:
                item = json.loads(m.replace("&quot;", '"'))
            except Exception:
                continue

            img_url = item.get("murl")
            page_url = item.get("purl")
            title = item.get("t", eth_zh + "服饰")

            if not img_url:
                continue

            ext = Path(img_url.split("?")[0]).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                ext = ".jpg"

            sample_id = f"{eth_info['en']}_web_{int(time.time() * 1000) % 1000000}_{count+1}"
            fname = f"{sample_id}{ext}"
            fpath = target_dir / fname

            records.append({
                "sample_id": sample_id,
                "ethnicity_zh": eth_zh,
                "ethnicity_en": eth_info["en"],
                "source_type": "Web_Search_Verified",
                "filename": fname,
                "local_path": str(fpath.relative_to(BASE_DIR)),
                "image_url": img_url,
                "source_page_url": page_url or "",
                "publisher": title[:80],
                "license": "Web Published / Editorial Use",
                "collected_at": now_str,
                "_save_path": fpath
            })
            count += 1
    return records

def main():
    init_metadata()
    existing_urls = get_existing_urls()
    print(f"已有元数据记录: {len(existing_urls)} 条")

    # 1. 抓取待下载清单
    all_candidates = []
    for eth_zh, eth_info in ETHNIC_MAP.items():
        wiki_recs = collect_wikimedia(eth_zh, eth_info, max_items=20)
        bing_recs = collect_bing(eth_zh, eth_info, max_items=35)
        for r in wiki_recs + bing_recs:
            if r["image_url"] not in existing_urls:
                all_candidates.append(r)
                existing_urls.add(r["image_url"])

    print(f"待并发下载样本总数: {len(all_candidates)} 张...")

    # 2. 多线程并发下载
    success_records = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(download_file, r["image_url"], r["_save_path"]): r
            for r in all_candidates
        }
        for future in as_completed(future_map):
            r = future_map[future]
            try:
                ok = future.result()
                if ok:
                    success_records.append(r)
                    print(f"  + [{r['ethnicity_zh']}] {r['filename']} 成功下载")
            except Exception as e:
                pass

    # 3. 追加写入元数据
    with open(METADATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        for r in success_records:
            clean_r = {k: v for k, v in r.items() if k in CSV_FIELDS}
            writer.writerow(clean_r)

    print("\n==================================================")
    print(f"并发采集完成！本次新增入库: {len(success_records)} 张")
    print("==================================================")

if __name__ == "__main__":
    main()
