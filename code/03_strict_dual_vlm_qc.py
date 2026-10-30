#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段三 · 终极版：双图联合严格质检审查引擎 (Strict Dual-Image VLM QC Engine)
- 同时输入【图A：未处理原始背景图】与【图B：512x512 纯白底后处理图】
- 严格执行六大一票否决红线：
  1. NOT_REAL_PHOTO: 严禁插画、手绘、3D/CG渲染、动漫、AI绘画
  2. FACE_ONLY_NO_CLOTHING: 严禁面部大特写、自拍、大头照、纯妆容，必须有充足服装面积
  3. NOT_GARMENT: 严禁方形布料、扎染面料、桌布、挂毯、布片、挂件
  4. INVALID_ETHNIC_COSTUME: 严禁现代日常便服、T恤牛仔、非少数民族服饰
  5. MULTI_PERSON: 严禁多人合影、并排合照
  6. BAD_SEGMENTATION: 严禁严重残破截断、大面积污斑
- 4张一组批量推理 + 5线程并发 + 实时JSONL落盘断点续跑
- 产物：
  - dataset/processed/strict_dual_vlm_qc.jsonl (全量增量日志)
  - dataset/processed/strict_dual_vlm_qc_summary.csv (全量汇总表)
  - dataset/processed/strict_gold_pass_manifest.csv (仅含通过严格检验的极品黄金样本)
  - dataset/processed/strict_review_dashboard.html (更新可视化审核看板)
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

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
RAW_DIR = BASE_DIR / "dataset" / "raw"
PROCESSED_DIR = BASE_DIR / "dataset" / "processed"

JSONL_LOG = PROCESSED_DIR / "strict_dual_vlm_qc.jsonl"
CSV_SUMMARY = PROCESSED_DIR / "strict_dual_vlm_qc_summary.csv"
GOLD_MANIFEST = PROCESSED_DIR / "strict_gold_pass_manifest.csv"
HTML_DASHBOARD = PROCESSED_DIR / "strict_review_dashboard.html"

API_URL = "http://localhost:8317/v1/chat/completions"
API_KEY = "sk-eric10z4"
MODEL_NAME = "gemini-3.1-flash-lite"
BATCH_PAIRS = 4  # 每批送审 4 对图片 (共8张图)
MAX_WORKERS = 8  # 6 线程并发

PROMPT_SYSTEM = """你是一个极其严谨的计算机视觉“少数民族服饰数据集”国家级学术质检专家。
你将同时审阅同一个样本的【图A：未处理原始背景图】与【图B：抠图白底后处理图】。
结合两张图的互补信息，严格执行以下“六大一票否决红线”，杜绝任何不合格样本流入数据集。

【致命一票否决项（出现任何一项，必须直接判定 FAIL，得分 0-30 分）】：

1. 真实摄影否决（NOT_REAL_PHOTO）：
   - 严禁任何插画、漫画、二次元、国画、手绘、电脑线稿、3D/CG建模渲染图、AI生成艺术插画！
   - 必须是真实相机/单反拍摄的【真实实体照片】（Real Photograph）。如果图A或图B是画出来的，一律 0 分否决！

2. 面部大特写/缺乏服饰否决（FACE_ONLY_NO_CLOTHING）：
   - 严禁纯人脸大特写、头部大头照、自拍照、纯妆容特写！
   - 如果画面主要是一张人脸，脖子以下服饰严重缺失、不可见，或仅露极小衣领边角，无法辨析核心服饰形制款式，必须直接一票否决！
   - 本项目为服饰数据集，服装必须是主体！必须至少展示清晰可见的上身核心服装（如门襟、衣袖、坎肩/马甲、围腰）或完整的全身/大半身穿着。

3. 服装主体否决（NOT_GARMENT）：
   - 严禁方形布料、扎染面料布匹、桌布、挂毯、布料样卡、单独的鞋垫、小荷包挂件、刺绣布条！
   - 必须是真正穿在人身上的整套/半身服饰，或者是成衣单品展示（整件上衣、完整裙装、整套袍服、整件刺绣马甲、完整民族头饰冠帽）。

4. 民族服饰真实性否决（INVALID_ETHNIC_COSTUME）：
   - 严禁普通现代日常便服（T恤、牛仔裤、现代西服、普通吊带裙、日常连帽卫衣混入）。
   - 必须具备中国 56 个经确认民族（重点聚焦云南代表性少数民族）可明确查验的传统形制特征。

5. 单主体否决（MULTI_PERSON）：
   - 严禁多人合影、群舞演出合照、情侣合照（画面中绝不能出现 2 人及以上）。
   - 画面只能有【一位穿着特定民族服饰的人物】或【一件成衣单品展示】。

6. 抠图与几何缺陷否决（BAD_SEGMENTATION）：
   - 严禁严重断头断肢、服饰主体被切掉 1/3 以上、大面积黑色/灰色烟雾噪点、边缘大块未抠除杂乱背景。

【最终判定规则】：
- PASS：必须同时满足【100% 真实实拍摄影照片】+【真实少数民族服饰（有充分的服装面积展示）】+【抠图干净、纯白底、居中完整】。
- FAIL：只要触发上述 6 条一票否决项中的任意一条，立即判定 FAIL。

请严格输出紧凑 JSON 格式（不要包含任何多余文字）：
[
  {
    "index": 1,
    "filename": "...",
    "status": "PASS" | "FAIL",
    "defect_type": "NONE" | "NOT_REAL_PHOTO" | "FACE_ONLY_NO_CLOTHING" | "NOT_GARMENT" | "INVALID_ETHNIC_COSTUME" | "MULTI_PERSON" | "BAD_SEGMENTATION",
    "score": 0-100,
    "reason": "详细扼要的中文判定理由（指出属于哪类缺陷或为何合格）"
  }
]
"""

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

def load_all_pairs():
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    pairs = []
    for d in sorted(PROCESSED_DIR.iterdir()):
        if d.is_dir():
            eth = d.name
            for proc_file in sorted(d.glob("*")):
                if proc_file.suffix.lower() in extensions:
                    raw_file = RAW_DIR / eth / proc_file.name
                    if raw_file.exists():
                        pairs.append({
                            "ethnicity": eth,
                            "filename": proc_file.name,
                            "proc_path": proc_file,
                            "raw_path": raw_file
                        })
    return pairs

def load_completed_records():
    seen = {}
    if JSONL_LOG.exists():
        with open(JSONL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if "filename" in obj:
                            seen[obj["filename"]] = obj
                    except:
                        pass
    return seen

def evaluate_batch(batch_items):
    content = [
        {
            "type": "text",
            "text": PROMPT_SYSTEM + f"\n\n请针对以下 {len(batch_items)} 个样本（每个样本提供【图A原图】与【图B白底图】）进行严格逐一判定，输出严格包含 {len(batch_items)} 个元素的 JSON 数组："
        }
    ]
    
    file_map = {}
    for idx, item in enumerate(batch_items, 1):
        file_map[idx] = item["filename"]
        b64_r = get_b64(item["raw_path"])
        b64_p = get_b64(item["proc_path"])
        content.append({"type": "text", "text": f"\n--- 样本 #{idx} [{item['ethnicity']}] {item['filename']} ---"})
        content.append({"type": "text", "text": f"【图A：原图 #{idx}】"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_r}"}})
        content.append({"type": "text", "text": f"【图B：白底图 #{idx}】"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_p}"}})
        
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"].strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n", "", raw_text)
                raw_text = re.sub(r"\n```$", "", raw_text)
            parsed = json.loads(raw_text)
            
            standardized = []
            for i, p_item in enumerate(parsed):
                fn = file_map.get(i+1, batch_items[i]["filename"] if i < len(batch_items) else "")
                p_item["filename"] = p_item.get("filename") or fn
                if not p_item["filename"] or p_item["filename"] not in [x["filename"] for x in batch_items]:
                    p_item["filename"] = batch_items[i]["filename"]
                p_item["ethnicity"] = next((x["ethnicity"] for x in batch_items if x["filename"] == p_item["filename"]), "Unknown")
                standardized.append(p_item)
            return standardized
    except Exception as e:
        return [{
            "filename": item["filename"],
            "ethnicity": item["ethnicity"],
            "status": "FAIL",
            "defect_type": "API_TIMEOUT",
            "score": 0,
            "reason": f"质检接口超时或解析异常: {str(e)[:40]}"
        } for item in batch_items]

def generate_outputs(all_records):
    # 1. 导出 CSV 汇总
    csv_fields = ["filename", "ethnicity", "status", "defect_type", "score", "reason"]
    with open(CSV_SUMMARY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_records:
            writer.writerow(r)
            
    # 2. 导出 PASS 黄金样本集
    pass_records = [r for r in all_records if r.get("status") == "PASS"]
    pass_records.sort(key=lambda x: (x.get("ethnicity", ""), -int(x.get("score", 0))))
    with open(GOLD_MANIFEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in pass_records:
            writer.writerow(r)
            
    print(f"[Export] 全量汇总已保存至: {CSV_SUMMARY}")
    print(f"[Export] 严格通过黄金样本已保存至: {GOLD_MANIFEST} (共 {len(pass_records)} 张)")

def main():
    print("==================================================")
    print("启动全量【图A原图 + 图B白底图】双图协同严格深度审查")
    print("==================================================")
    
    all_pairs = load_all_pairs()
    completed_map = load_completed_records()
    print(f"总计配对样本量: {len(all_pairs)} 对 | 历史已审查: {len(completed_map)} 对")
    
    pending_items = [p for p in all_pairs if p["filename"] not in completed_map]
    print(f"本次待执行审查: {len(pending_items)} 对，每批次: {BATCH_PAIRS} 对，线程数: {MAX_WORKERS}...")
    
    batches = [pending_items[i:i+BATCH_PAIRS] for i in range(0, len(pending_items), BATCH_PAIRS)]
    print(f"共切分为 {len(batches)} 个并发多模态质检批次...")
    
    t0 = time.time()
    completed_count = 0
    new_results = []
    
    if len(batches) > 0:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {pool.submit(evaluate_batch, b): b for b in batches}
            for fut in as_completed(future_map):
                res_list = fut.result()
                new_results.extend(res_list)
                completed_count += len(res_list)
                
                with open(JSONL_LOG, "a", encoding="utf-8") as f:
                    for item in res_list:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        completed_map[item["filename"]] = item
                        
                if completed_count % 100 == 0 or completed_count >= len(pending_items):
                    elapsed = time.time() - t0
                    fps = completed_count / max(0.1, elapsed)
                    pass_c = sum(1 for r in new_results if r.get("status") == "PASS")
                    print(f"  [质检进度: {completed_count}/{len(pending_items)}] 速度: {fps:.2f} 对/秒 | PASS数: {pass_c} | 耗时: {elapsed:.1f}s")
                    
    all_records = list(completed_map.values())
    all_records.sort(key=lambda x: (x.get("ethnicity", ""), x.get("filename", "")))
    generate_outputs(all_records)
    
    pass_total = sum(1 for r in all_records if r.get("status") == "PASS")
    fail_total = sum(1 for r in all_records if r.get("status") == "FAIL")
    print("\n==================================================")
    print(f"全量双图严格审查圆满结束！耗时: {time.time() - t0:.1f} 秒")
    print(f"总计审查样本: {len(all_records)} 张")
    print(f"  ✅ PASS (100%纯净真实少数民族服饰): {pass_total} 张 ({pass_total/len(all_records)*100:.1f}%)")
    print(f"  ❌ FAIL (违规拦截): {fail_total} 张 ({fail_total/len(all_records)*100:.1f}%)")
    print("==================================================")

if __name__ == "__main__":
    main()
