#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复核脚本：利用 VLM 双图深度扫描 95 张人工判定不合格 (FAIL) 样本
- 逐样本载入【图A原始背景图】与【图B 512白底图】
- 对齐人工标注的不合格原因，深入剖析画面细节、具体硬伤、成因归纳
- 输出 JSON / CSV 详细复盘报告
"""

import os
import re
import csv
import json
import time
import base64
import io
import urllib.request
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
RAW_DIR = BASE_DIR / "dataset" / "raw"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
CSV_PATH = Path(r"C:\Users\26730\xwechat_files\wxid_iai84bkt5b6p22_fa89\msg\file\2026-10\民族服饰数据集人工终审结果清单_2026-10-30.csv")

OUT_JSON = PROCESSED_DIR / "95_fail_detailed_diagnosis.json"
OUT_CSV = PROCESSED_DIR / "95_fail_detailed_diagnosis.csv"

API_URL = "http://localhost:8317/v1/chat/completions"
API_KEY = "sk-eric10z4"
MODEL_NAME = "gemini-3.1-flash-lite"

def get_b64(path, max_dim=512):
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except:
        return ""

def load_95_fails():
    fails = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("human_decision") == "FAIL":
                fn = r.get("filename")
                eth = r.get("ethnicity")
                fails.append({
                    "item_id": r.get("item_id"),
                    "ethnicity": eth,
                    "filename": fn,
                    "human_reason": r.get("fail_reason", ""),
                    "human_code": r.get("fail_code", ""),
                    "human_detail": r.get("fail_detail", ""),
                    "raw_path": RAW_DIR / eth / fn,
                    "proc_path": PROCESSED_DIR / eth / fn
                })
    return fails

def diagnose_one(item):
    b64_r = get_b64(item["raw_path"])
    b64_p = get_b64(item["proc_path"])
    
    prompt = f"""你是一个计算机视觉数据集学术质检复核专家。
人类评审员在期中大作业终审中将该少数民族服饰样本判定为【不合格 (FAIL)】，人类记录的原因是：【{item['human_reason']}】。

请你仔细比对【图A：未处理原始图】与【图B：白底处理图】，给出非常客观、极其详尽的复盘诊断报告：
1. 画面真实内容解构：画面中具体是什么？（人物姿态、服装/物品、周围环境）。
2. 缺陷实证分析：指出具体硬伤所在（如是多人合影，指明有几个人在什么位置；如是布料，说明具体是什么织物；如是抠图破损，说明具体哪里坏了；如是插画，指出绘图特征；如是现代便服，指出具体穿着）。
3. 最终确认：是否完全认同人类评审员的淘汰决定？为什么？

请直接输出紧凑 JSON 格式（不要包含任何多余文字）：
{{
  "confirmed_issue": "核心问题简述 (10字内)",
  "detailed_analysis": "极其详细客观的中文剖析 (100-200字)",
  "agree_with_rejection": true,
  "key_flaws": ["硬伤点1", "硬伤点2"]
}}
"""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "text", "text": f"--- 样本 #{item['item_id']} [{item['ethnicity']}] {item['filename']} ---"},
                    {"type": "text", "text": "【图A：原始图】"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_r}"}},
                    {"type": "text", "text": "【图B：白底图】"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_p}"}}
                ]
            }
        ],
        "temperature": 0.1
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"].strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n", "", raw_text)
                raw_text = re.sub(r"\n```$", "", raw_text)
            parsed = json.loads(raw_text)
            return {
                "item_id": item["item_id"],
                "ethnicity": item["ethnicity"],
                "filename": item["filename"],
                "human_reason": item["human_reason"],
                "human_code": item["human_code"],
                "confirmed_issue": parsed.get("confirmed_issue", "人工判定不合格"),
                "detailed_analysis": parsed.get("detailed_analysis", ""),
                "agree_with_rejection": parsed.get("agree_with_rejection", True),
                "key_flaws": parsed.get("key_flaws", [])
            }
    except Exception as e:
        return {
            "item_id": item["item_id"],
            "ethnicity": item["ethnicity"],
            "filename": item["filename"],
            "human_reason": item["human_reason"],
            "human_code": item["human_code"],
            "confirmed_issue": "复核接口异常",
            "detailed_analysis": f"API调用失败: {str(e)[:60]}",
            "agree_with_rejection": True,
            "key_flaws": [str(e)[:40]]
        }

def main():
    fails = load_95_fails()
    print(f"开始对 {len(fails)} 张不合格样本执行 VLM 深度病因解构与复核...")
    
    results = []
    t0 = time.time()
    
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_map = {pool.submit(diagnose_one, item): item for item in fails}
        completed = 0
        for fut in as_completed(future_map):
            res = fut.result()
            results.append(res)
            completed += 1
            if completed % 15 == 0 or completed == len(fails):
                print(f"  [诊断进度: {completed}/{len(fails)}] 耗时: {time.time() - t0:.1f}s")
                
    results.sort(key=lambda x: x["item_id"])
    
    # 导出 JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    # 导出 CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        fields = ["item_id", "ethnicity", "filename", "human_reason", "human_code", "confirmed_issue", "detailed_analysis", "key_flaws"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            clean_r = dict(r)
            if isinstance(clean_r.get("key_flaws"), list):
                clean_r["key_flaws"] = "; ".join(clean_r["key_flaws"])
            writer.writerow(clean_r)
            
    print(f"\n全部 95 张样本深度诊断完成！耗时: {time.time() - t0:.1f}s")
    print(f"已导出 JSON: {OUT_JSON}")
    print(f"已导出 CSV: {OUT_CSV}")

if __name__ == "__main__":
    main()
