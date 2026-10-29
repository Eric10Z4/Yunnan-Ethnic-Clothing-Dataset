#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三 · 步骤三：VLM 视觉大模型全量自动化抠图验收质检 (VLM Judge Visual Quality Control)
- 遍历 dataset/processed/ 目录下的全部 2,539 张 512x512 纯白底样本
- 采用 5 张一组批量送审多模态模型 (gemini-3.1-flash-lite via CPA 代理)
- 核心质检维度：
  1. 纯白背景完整度 (无残留复杂背景块、无烟雾噪点)
  2. 抠图边缘自然度 (无严重羽化缺失、无大面积未抠除杂色)
  3. 主体规范性 (单主体着装、无多人合照残留、无恶性截断)
- 判定分级：
  * PASS: 图像纯净、单主体端正、抠图合格 (可直接准入阶段四)
  * REVIEW: 存在轻度发丝残缺或小范围边缘瑕疵 (交由人工审核闭环)
  * FAIL: 多人合影、主体严重破损、严重背景脏斑 (直接剔除)
- 支持断点续跑、并发加速，生成 vlm_qc_summary.csv 与交互式 HTML 审核面板
"""

import os
import re
import csv
import json
import time
import base64
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"
JSONL_LOG = PROCESSED_DIR / "vlm_qc_results.jsonl"
CSV_SUMMARY = PROCESSED_DIR / "vlm_qc_summary.csv"
HTML_DASHBOARD = PROCESSED_DIR / "review_dashboard.html"

API_URL = "http://localhost:8317/v1/chat/completions"
API_KEY = "sk-eric10z4"
MODEL_NAME = "gemini-3.1-flash-lite"
BATCH_SIZE = 5

def load_processed_images():
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for d in sorted(PROCESSED_DIR.iterdir()):
        if d.is_dir():
            for f in sorted(d.glob("*")):
                if f.suffix.lower() in extensions:
                    images.append(f)
    return images

def load_existing_records():
    seen = {}
    if JSONL_LOG.exists():
        with open(JSONL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        seen[obj["filename"]] = obj
                    except:
                        pass
    return seen

def evaluate_batch(batch_files):
    content = [
        {
            "type": "text",
            "text": "你是一个极其严格的计算机视觉数据集质检专家。下面有几张 512x512 纯白底民族服饰图像。\n"
                    "请针对每一张图片进行严格检查：\n"
                    "1. 抠图质量：边缘是否有原背景残余、烟雾污斑或异常杂色？\n"
                    "2. 主体规范：必须是【单人穿着】或【单件服饰展示】！严禁多人合影！主体是否完整（有无断头、残缺断臂）？\n"
                    "3. 背景纯度：是否完全为纯白底？\n"
                    "请直接返回严格的 JSON 数组（不要输出任何多余字符），数组长度必须与图片数量完全一致：\n"
                    '[{"filename": "...", "status": "PASS" | "REVIEW" | "FAIL", "score": 1-100, "defects": ["..."], "summary": "..."}]'
        }
    ]
    
    file_map = {}
    for idx, f in enumerate(batch_files, 1):
        with open(f, "rb") as fp:
            b64 = base64.b64encode(fp.read()).decode("utf-8")
        file_map[idx] = f.name
        content.append({"type": "text", "text": f"--- 图片 #{idx} [文件名: {f.name}, 民族: {f.parent.name}] ---"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"].strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n", "", raw_text)
                raw_text = re.sub(r"\n```$", "", raw_text)
            parsed = json.loads(raw_text)
            
            standardized = []
            for i, item in enumerate(parsed):
                fn = file_map.get(i+1, batch_files[i].name if i < len(batch_files) else "")
                item["filename"] = item.get("filename") or fn
                if not item["filename"] or item["filename"] not in [f.name for f in batch_files]:
                    item["filename"] = batch_files[i].name
                item["ethnicity"] = next((f.parent.name for f in batch_files if f.name == item["filename"]), "Unknown")
                standardized.append(item)
            return standardized
    except Exception as e:
        return [{
            "filename": f.name,
            "ethnicity": f.parent.name,
            "status": "REVIEW",
            "score": 70,
            "defects": [f"API_TIMEOUT_OR_PARSE_ERROR: {str(e)[:40]}"],
            "summary": "自动质检接口响应超时或解析异常，打标为复核"
        } for f in batch_files]

def generate_html_dashboard(records):
    records_json = json.dumps(records, ensure_ascii=False)
    
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>云南少数民族服饰图像数据集 VLM 抠图智能验收与人工复核面板</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        header { background: #fff; padding: 20px 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-bottom: 24px; }
        h1 { margin: 0 0 10px 0; font-size: 24px; color: #1a1a1a; }
        .stats-bar { display: flex; gap: 20px; font-size: 15px; margin-top: 15px; }
        .stat-item { padding: 10px 18px; border-radius: 8px; font-weight: bold; }
        .stat-total { background: #eef2f7; color: #2c3e50; }
        .stat-pass { background: #e8f5e9; color: #2e7d32; }
        .stat-review { background: #fff8e1; color: #f57f17; }
        .stat-fail { background: #ffebee; color: #c62828; }
        .filter-bar { display: flex; gap: 12px; margin: 20px 0; }
        .filter-btn { padding: 8px 16px; border: 1px solid #ccc; background: #fff; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }
        .filter-btn.active { background: #1976d2; color: #fff; border-color: #1976d2; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }
        .card { background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); transition: transform 0.2s; position: relative; border: 2px solid transparent; }
        .card:hover { transform: translateY(-4px); box-shadow: 0 6px 16px rgba(0,0,0,0.1); }
        .card.card-pass { border-color: #a5d6a7; }
        .card.card-review { border-color: #ffe082; }
        .card.card-fail { border-color: #ef9a9a; }
        .thumb-wrapper { width: 100%; height: 260px; background: #fff; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #eee; }
        .thumb-wrapper img { max-width: 100%; max-height: 100%; object-fit: contain; }
        .card-body { padding: 14px; font-size: 13px; }
        .card-title { font-weight: bold; font-size: 14px; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 8px; }
        .badge-pass { background: #4caf50; color: #fff; }
        .badge-review { background: #ff9800; color: #fff; }
        .badge-fail { background: #f44336; color: #fff; }
        .score { float: right; font-weight: bold; font-size: 14px; }
        .score-pass { color: #2e7d32; }
        .score-review { color: #f57f17; }
        .score-fail { color: #c62828; }
        .defects { color: #c62828; font-size: 12px; margin-top: 6px; line-height: 1.4; }
        .summary { color: #666; font-size: 12px; margin-top: 6px; line-height: 1.4; }
    </style>
</head>
<body>
    <header>
        <h1>🏛️ 云南少数民族服饰图像数据集 · VLM 智能验收与人工复核面板</h1>
        <div style="color: #666; font-size: 14px;">计算机视觉期中大作业 | 阶段三：512x512 纯白底抠图验收闭环</div>
        <div class="stats-bar" id="statsBar"></div>
        <div class="filter-bar">
            <button class="filter-btn active" onclick="setFilter('ALL')">全部显示</button>
            <button class="filter-btn" onclick="setFilter('PASS')">✅ PASS (优选合规)</button>
            <button class="filter-btn" onclick="setFilter('REVIEW')">⚠️ REVIEW (需人工复核)</button>
            <button class="filter-btn" onclick="setFilter('FAIL')">❌ FAIL (建议剔除)</button>
        </div>
    </header>
    <div class="grid" id="imageGrid"></div>

    <script>
        const records = """ + records_json + """;
        let currentFilter = 'ALL';

        function renderStats() {
            const total = records.length;
            const pass = records.filter(r => r.status === 'PASS').length;
            const review = records.filter(r => r.status === 'REVIEW').length;
            const fail = records.filter(r => r.status === 'FAIL').length;

            document.getElementById('statsBar').innerHTML = `
                <div class="stat-item stat-total">总质检样本: ${total} 张</div>
                <div class="stat-item stat-pass">PASS (直接准入): ${pass} 张 (${(pass/total*100).toFixed(1)}%)</div>
                <div class="stat-item stat-review">REVIEW (边缘瑕疵): ${review} 张 (${(review/total*100).toFixed(1)}%)</div>
                <div class="stat-item stat-fail">FAIL (不合规/合影): ${fail} 张 (${(fail/total*100).toFixed(1)}%)</div>
            `;
        }

        function setFilter(status) {
            currentFilter = status;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            renderGrid();
        }

        function renderGrid() {
            const grid = document.getElementById('imageGrid');
            const filtered = records.filter(r => currentFilter === 'ALL' || r.status === currentFilter);
            grid.innerHTML = filtered.map(r => `
                <div class="card card-${r.status.toLowerCase()}">
                    <div class="thumb-wrapper">
                        <img src="${r.ethnicity}/${r.filename}" loading="lazy" alt="${r.filename}">
                    </div>
                    <div class="card-body">
                        <div>
                            <span class="badge badge-${r.status.toLowerCase()}">${r.status}</span>
                            <span class="score score-${r.status.toLowerCase()}">${r.score} 分</span>
                        </div>
                        <div class="card-title" title="${r.filename}">[${r.ethnicity}] ${r.filename}</div>
                        ${r.defects && r.defects.length ? `<div class="defects"><strong>⚠️ 缺陷：</strong>${r.defects.join(', ')}</div>` : ''}
                        <div class="summary">${r.summary || '质检合格'}</div>
                    </div>
                </div>
            `).join('');
        }

        renderStats();
        renderGrid();
    </script>
</body>
</html>
"""
    with open(HTML_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Dashboard] 可视化审核面板已生成: {HTML_DASHBOARD}")

def run_vlm_qc():
    print("==================================================")
    print("启动阶段三 · 步骤三：VLM 视觉模型全量自动化抠图验收质检")
    print("==================================================")
    
    all_images = load_processed_images()
    existing_records = load_existing_records()
    print(f"总计待质检图像: {len(all_images)} 张 | 历史已完成: {len(existing_records)} 张")
    
    pending_images = [img for img in all_images if img.name not in existing_records]
    print(f"本次待执行批量评估: {len(pending_images)} 张，批大小: {BATCH_SIZE}...")
    
    batches = [pending_images[i:i+BATCH_SIZE] for i in range(0, len(pending_images), BATCH_SIZE)]
    print(f"切分为 {len(batches)} 个多模态并行批次，启动 5 线程并发质检...")
    
    t0 = time.time()
    completed_count = 0
    newly_evaluated = []
    
    if len(batches) > 0:
        with ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(evaluate_batch, b): b for b in batches}
            for fut in as_completed(future_map):
                b_results = fut.result()
                newly_evaluated.extend(b_results)
                completed_count += len(b_results)
                
                with open(JSONL_LOG, "a", encoding="utf-8") as f:
                    for item in b_results:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        existing_records[item["filename"]] = item
                        
                if completed_count % 50 == 0 or completed_count >= len(pending_images):
                    elapsed = time.time() - t0
                    fps = completed_count / max(0.1, elapsed)
                    print(f"  [质检进度: {completed_count}/{len(pending_images)}] 速度: {fps:.2f} 图/秒 | 耗时: {elapsed:.1f}s")
                    
    all_evaluated = list(existing_records.values())
    all_evaluated.sort(key=lambda x: (x.get("ethnicity", ""), -x.get("score", 0)))
    
    csv_fields = ["filename", "ethnicity", "status", "score", "defects", "summary"]
    with open(CSV_SUMMARY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_evaluated:
            clean_r = dict(r)
            if isinstance(clean_r.get("defects"), list):
                clean_r["defects"] = "; ".join(clean_r["defects"])
            writer.writerow(clean_r)
            
    generate_html_dashboard(all_evaluated)
    
    pass_cnt = sum(1 for r in all_evaluated if r.get("status") == "PASS")
    review_cnt = sum(1 for r in all_evaluated if r.get("status") == "REVIEW")
    fail_cnt = sum(1 for r in all_evaluated if r.get("status") == "FAIL")
    
    total_time = time.time() - t0
    print("\n==================================================")
    print("VLM 智能质检验收全部完成！")
    print(f"总验收样本: {len(all_evaluated)} 张 | 耗时: {total_time:.1f} 秒")
    print(f"  PASS   (优选合规): {pass_cnt} 张 ({pass_cnt/len(all_evaluated)*100:.1f}%)")
    print(f"  REVIEW (需人工复核): {review_cnt} 张 ({review_cnt/len(all_evaluated)*100:.1f}%)")
    print(f"  FAIL   (合影/残破剔除): {fail_cnt} 张 ({fail_cnt/len(all_evaluated)*100:.1f}%)")
    print(f"详细质检台账: {CSV_SUMMARY}")
    print(f"可视化审核面板: {HTML_DASHBOARD}")
    print("==================================================")

if __name__ == "__main__":
    run_vlm_qc()
