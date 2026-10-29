#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, csv, json, time, urllib.request, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
RAW_DIR = BASE_DIR / "dataset" / "raw"
METADATA_FILE = RAW_DIR / "raw_metadata.csv"

TARGET_CONFIGS = [
    {"zh": "景颇族", "en": "Jingpo", "target": 120, "queries": ["景颇族 服饰 单人 模特", "景颇族 传统服饰 平铺", "德宏 景颇族 盛装 单人"]},
    {"zh": "哈尼族", "en": "Hani", "target": 120, "queries": ["哈尼族 服饰 单人 模特", "哈尼族 传统服饰 单人", "元阳 哈尼族 服饰 模特"]},
    {"zh": "佤族", "en": "Wa", "target": 120, "queries": ["佤族 服饰 单人 模特", "佤族 传统服饰 单人", "西盟 佤族 服饰 模特"]},
    {"zh": "纳西族", "en": "Naxi", "target": 120, "queries": ["纳西族 服饰 单人 模特", "纳西族 传统服饰 单人", "丽江 纳西族 服饰 模特"]},
    {"zh": "白族", "en": "Bai", "target": 120, "queries": ["白族 服饰 单人 模特", "大理 白族 服饰 单人 模特", "白族 盛装 单人 影棚"]},
    {"zh": "彝族", "en": "Yi", "target": 100, "queries": ["彝族 服饰 单人 模特", "楚雄 彝绣 服饰 单人 模特", "凉山 彝族 服装 单人"]},
    {"zh": "藏族", "en": "Tibetan", "target": 100, "queries": ["藏族 藏袍 单人 模特", "迪庆 藏族 服饰 单人 模特", "藏族 服饰 模特 影棚"]},
    {"zh": "苗族", "en": "Miao", "target": 80, "queries": ["苗族 盛装 单人 模特 影棚", "苗族 银冠 刺绣 单人"]},
    {"zh": "傣族", "en": "Dai", "target": 80, "queries": ["傣族 筒裙 单人 模特", "西双版纳 傣装 单人 模特 影棚"]},
    {"zh": "壮族", "en": "Zhuang", "target": 80, "queries": ["壮族 传统服饰 单人 模特", "壮锦 服饰 单人 模特 影棚"]}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

CSV_FIELDS = ["sample_id", "ethnicity_zh", "ethnicity_en", "source_type", "filename", "local_path", "image_url", "source_page_url", "publisher", "license", "collected_at"]

def load_existing_urls():
    if not METADATA_FILE.exists(): return set()
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        return {r["image_url"] for r in csv.DictReader(f) if "image_url" in r}

def download_image(url: str, save_path: Path, timeout: int = 4) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read()
                if len(body) < 6144: return False
                with open(save_path, "wb") as f: f.write(body)
                return True
    except: pass
    return False

def search_bing(query: str, max_pages: int = 3) -> list:
    results, seen = [], set()
    for p in range(max_pages):
        first = p * 35 + 1
        url = f"https://cn.bing.com/images/async?q={urllib.parse.quote(query)}&first={first}&count=35&mmasync=1"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                matches = re.findall(r'm="({.*?})"', html)
                if not matches: break
                for m in matches:
                    try:
                        obj = json.loads(m.replace("&quot;", '"'))
                        if obj.get("murl") and obj["murl"] not in seen:
                            seen.add(obj["murl"])
                            results.append({"image_url": obj["murl"], "source_page_url": obj.get("purl", ""), "publisher": (obj.get("t") or "Web Photo")[:80]})
                    except: pass
        except: break
        time.sleep(0.05)
    return results

def run_targeted_harvest():
    existing_urls = load_existing_urls()
    print("继续执行剩余民族定向单人样本采集...")
    total_added = 0
    
    for cfg in TARGET_CONFIGS:
        eth_zh = cfg["zh"]
        eth_en = cfg["en"]
        target_cnt = cfg["target"]
        target_dir = RAW_DIR / eth_en
        target_dir.mkdir(parents=True, exist_ok=True)
        
        current_targeted = len(list(target_dir.glob("*targeted*")))
        needed = max(0, target_cnt - current_targeted)
        if needed <= 0:
            print(f"[{eth_zh}] 本地已有 {current_targeted} 张定向样本，已达标跳过。")
            continue
            
        candidates = []
        for q in cfg["queries"]:
            cands = search_bing(q, max_pages=3)
            for c in cands:
                if c["image_url"] not in existing_urls:
                    candidates.append(c)
                    existing_urls.add(c["image_url"])
            if len(candidates) >= needed * 1.3: break
            
        print(f"[{eth_zh}] 目标需补: {needed} 张 | 候选链接: {len(candidates)} 条，并发下载...")
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        download_queue = []
        for i, c in enumerate(candidates):
            ext = Path(c["image_url"].split("?")[0]).suffix.lower()
            if ext not in [".jpg", ".jpeg", ".png", ".webp"]: ext = ".jpg"
            sample_id = f"{eth_en}_targeted_{int(time.time() % 100000)}_{i+1}"
            fname = f"{sample_id}{ext}"
            fpath = target_dir / fname
            download_queue.append({
                "sample_id": sample_id, "ethnicity_zh": eth_zh, "ethnicity_en": eth_en, "source_type": "Web_Search_Targeted_Single",
                "filename": fname, "local_path": str(fpath.relative_to(BASE_DIR)), "image_url": c["image_url"], "source_page_url": c["source_page_url"],
                "publisher": c["publisher"], "license": "Web Published / Editorial Use", "collected_at": now_str, "_save_path": fpath
            })
            
        success_records = []
        with ThreadPoolExecutor(max_workers=14) as pool:
            future_map = {pool.submit(download_image, r["image_url"], r["_save_path"]): r for r in download_queue}
            for fut in as_completed(future_map):
                r = future_map[fut]
                try:
                    if fut.result():
                        success_records.append(r)
                        if len(success_records) >= needed: break
                except: pass
                
        with open(METADATA_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            for r in success_records:
                writer.writerow({k: v for k, v in r.items() if k in CSV_FIELDS})
        total_added += len(success_records)
        print(f"  -> {eth_zh} 本次入库: {len(success_records)} 张 (该民族定向总计: {current_targeted + len(success_records)})")

    print(f"\n全部定向单人样本抓取完成！本次新增: {total_added} 张")

if __name__ == "__main__":
    run_targeted_harvest()
