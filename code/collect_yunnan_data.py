#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云南民族服饰多源数据采集与台账登记脚本 (Pilot Collector)
- 数据源1: 维基共享资源 (Wikimedia Commons) 云南各民族服饰专题典藏（云南省博物馆、云南民族博物馆等官方典藏，CC/公版许可，高可信度）
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

def download_file(url: str, save_path: Path, timeout: int = 12) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                content = resp.read()
                # 过滤过小字节数（<5KB可能是占位符或icon）
                if len(content) < 5120:
                    return False
                with open(save_path, "wb") as f:
                    f.write(content)
                return True
    except Exception:
        pass
    return False

def collect_from_wikimedia(eth_zh: str, eth_info: dict, max_items: int = 25):
    print(f"\n[Wikimedia] 开始采集 {eth_zh} ({eth_info['en']}) 官方博物馆典藏...")
    cat = eth_info["wiki_cat"]
    api_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle={cat}&gcmtype=file&gcmlimit={max_items}&prop=imageinfo&iiprop=url|size|extmetadata&format=json"
    
    req = urllib.request.Request(api_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [Wikimedia Error] {cat}: {e}")
        return 0

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        print(f"  [Wikimedia] {cat} 未找到文件。")
        return 0

    target_dir = RAW_DIR / eth_info["en"]
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_urls = get_existing_urls()

    downloaded = 0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for pid, pdata in pages.items():
        imageinfo = pdata.get("imageinfo", [{}])[0]
        img_url = imageinfo.get("url")
        desc_url = imageinfo.get("descriptionurl", "")
        if not img_url or img_url in existing_urls:
            continue

        extmeta = imageinfo.get("extmetadata", {})
        license_info = extmeta.get("LicenseShortName", {}).get("value", "CC-BY/Public-Domain")
        artist = extmeta.get("Artist", {}).get("value", "Wikimedia Contributor")
        # 清除HTML标签
        artist = re.sub(r"<[^>]+>", "", artist).strip()[:100]

        ext = Path(img_url.split("?")[0]).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        sample_id = f"{eth_info['en']}_wiki_{pdata.get('pageid', downloaded+1)}"
        fname = f"{sample_id}{ext}"
        fpath = target_dir / fname

        if download_file(img_url, fpath):
            record = {
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
                "collected_at": now_str
            }
            with open(METADATA_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerow(record)
            existing_urls.add(img_url)
            downloaded += 1
            print(f"  + [Wiki] {eth_zh}: {fname} ({license_info})")

    return downloaded

def collect_from_bing(eth_zh: str, eth_info: dict, max_items: int = 40):
    print(f"\n[Bing Image] 开始检索采集 {eth_zh} ({eth_info['en']}) 真实溯源服饰...")
    queries = [
        f"{eth_zh} 传统服饰",
        f"{eth_zh} 民族服饰 白底",
        f"{eth_zh} 服饰 刺绣",
    ]
    target_dir = RAW_DIR / eth_info["en"]
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_urls = get_existing_urls()

    downloaded = 0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for q in queries:
        if downloaded >= max_items:
            break
        search_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q)}&first=1&count=60"
        req = urllib.request.Request(search_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  [Bing Error] {q}: {e}")
            continue

        raw_matches = re.findall(r'm=\"({.*?})\"', html)
        for m in raw_matches:
            if downloaded >= max_items:
                break
            m_clean = m.replace("&quot;", '"')
            try:
                item = json.loads(m_clean)
            except Exception:
                continue

            img_url = item.get("murl")
            page_url = item.get("purl")
            title = item.get("t", eth_zh + "服饰")

            if not img_url or img_url in existing_urls:
                continue

            ext = Path(img_url.split("?")[0]).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                ext = ".jpg"

            sample_id = f"{eth_info['en']}_web_{int(time.time() * 1000) % 1000000}_{downloaded+1}"
            fname = f"{sample_id}{ext}"
            fpath = target_dir / fname

            if download_file(img_url, fpath):
                record = {
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
                    "collected_at": now_str
                }
                with open(METADATA_FILE, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                    writer.writerow(record)
                existing_urls.add(img_url)
                downloaded += 1
                print(f"  + [Web] {eth_zh}: {fname} (来自: {title[:20]}...)")
                time.sleep(0.3)

    return downloaded

def main():
    init_metadata()
    print("==================================================")
    print("开始执行云南代表性民族服饰图像多源采集探查...")
    print("==================================================")

    stats = {}
    for eth_zh, eth_info in ETHNIC_MAP.items():
        w_cnt = collect_from_wikimedia(eth_zh, eth_info, max_items=20)
        b_cnt = collect_from_bing(eth_zh, eth_info, max_items=35)
        stats[eth_zh] = {
            "en": eth_info["en"],
            "wikimedia": w_cnt,
            "web": b_cnt,
            "total": w_cnt + b_cnt
        }

    print("\n==================================================")
    print("初步采集完成！统计结果如下：")
    print("==================================================")
    grand_total = 0
    for eth_zh, res in stats.items():
        print(f"  {eth_zh} ({res['en']}): 博物馆典藏 {res['wikimedia']} 张 | 溯源网页 {res['web']} 张 | 合计 {res['total']} 张")
        grand_total += res["total"]
    print(f"总计已采集入库样本数: {grand_total} 张")
    print(f"台账文件: {METADATA_FILE}")

if __name__ == "__main__":
    main()
