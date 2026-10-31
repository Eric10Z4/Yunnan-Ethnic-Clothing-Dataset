#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产标注函数真实离线单元测试套件 (Production Pipeline Offline Unit Tests)
直接 mock 网络响应并真实调用生产函数 process_batch 及 run_pipeline，
不使用测试镜像字典断言。
"""

import os
import json
import unittest
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")

import importlib.util
spec = importlib.util.spec_from_file_location("pipeline_mod", BASE_DIR / "code/04_v2_annotation_pipeline.py")
pipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipe)

# Mock base64 to avoid local disk reads
pipe.get_b64 = lambda *a, **kw: "mocked-base64-data"

test_items = [
    {"image_id": f"{i:04}", "path": f"images/train/{i:04}.jpg", "ethnicity": "Bai", "local_dest": "fixture", "meta": {}}
    for i in [1, 2, 3]
]

def make_rec(i, color="blue", has_top=True):
    return {
        "index": i,
        "has_top": has_top,
        "official_top": {
            "color": color,
            "pattern": "none",
            "material": "unknown",
            "sleeve_length": "long sleeves"
        },
        "official_bottom_or_dress": "black trousers",
        "official_headwear": "none",
        "official_caption": f"Item {i} with a {color} long-sleeved top and black trousers.",
        "extended_structure": {
            "collar_type": "standing collar",
            "opening_style": "front-opening",
            "closure": "buttons",
            "decoration_location": [],
            "bottom_type": "trousers",
            "headwear_type": "none"
        },
        "vlm_confidence": 0.95
    }

class MockResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        return json.dumps({"choices": [{"message": {"content": self.payload}}]}).encode("utf-8")

class TestProductionPipeline(unittest.TestCase):

    def test_01_plain_top_pattern_none(self):
        """测试 1：真实调用 process_batch，验证 pattern=none 规范为 solid color 且保留上衣"""
        payload = json.dumps([make_rec(1), make_rec(2), make_rec(3)])
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(payload)):
            out = pipe.process_batch(test_items)
            
        self.assertEqual(len(out), 3)
        for res in out:
            self.assertEqual(res["status"], "SUCCESS")
            top = res["official"]["top"]
            self.assertEqual(top["color"], "blue")
            self.assertEqual(top["pattern"], "solid color")
            self.assertEqual(top["sleeve_length"], "long sleeves")

    def test_02_absent_top(self):
        """测试 2：真实调用 process_batch，验证无上衣样本各字段为 none 且结构为 none"""
        payload = json.dumps([make_rec(1, has_top=False), make_rec(2), make_rec(3)])
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(payload)):
            out = pipe.process_batch(test_items)
            
        self.assertEqual(out[0]["status"], "SUCCESS")
        top0 = out[0]["official"]["top"]
        ext0 = out[0]["extended"]["top_structure"]
        self.assertEqual(top0["sleeve_length"], "none")
        self.assertNotEqual(top0["sleeve_length"], "sleeveless")
        self.assertEqual(ext0["collar_type"], "none")
        self.assertEqual(ext0["opening_style"], "none")
        self.assertEqual(len(ext0["decoration_location"]), 0)

    def test_03_shuffled_binding(self):
        """测试 3：真实调用 process_batch，验证乱序响应基于 index 正确归位"""
        shuffled = [make_rec(3, "green"), make_rec(1, "red"), make_rec(2, "blue")]
        payload = json.dumps(shuffled)
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(payload)):
            out = pipe.process_batch(test_items)
            
        colors = [x["official"]["top"]["color"] for x in out]
        self.assertEqual(colors, ["red", "blue", "green"])

    def test_04_missing_and_duplicate_index(self):
        """测试 4：真实调用 process_batch，验证缺失和重复 index 严格进入 RETRY"""
        # 缺失 index 2
        payload_missing = json.dumps([make_rec(1), make_rec(3)])
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(payload_missing)):
            out_missing = pipe.process_batch(test_items)
        self.assertEqual(out_missing[1]["status"], "RETRY")
        self.assertIn("Missing response index 2", out_missing[1]["error"])
        
        # 重复 index 1
        payload_dup = json.dumps([make_rec(1, "red"), make_rec(1, "green"), make_rec(2), make_rec(3)])
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(payload_dup)):
            out_dup = pipe.process_batch(test_items)
        self.assertEqual(out_dup[0]["status"], "RETRY")
        self.assertIn("Duplicate index 1", out_dup[0]["error"])

    def test_05_api_error_and_incomplete_response(self):
        """测试 5：真实调用 process_batch，验证异常和不完整响应进入 RETRY，不产生假数据"""
        # API 异常
        with patch.object(pipe.urllib.request, "urlopen", side_effect=TimeoutError("Connection timed out")):
            out_err = pipe.process_batch(test_items)
        self.assertTrue(all(x["status"] == "RETRY" for x in out_err))
        self.assertTrue(all("official" not in x for x in out_err))
        
        # 缺少核心视觉字段
        incomplete_payload = json.dumps([{"index": i} for i in [1, 2, 3]])
        with patch.object(pipe.urllib.request, "urlopen", return_value=MockResponse(incomplete_payload)):
            out_inc = pipe.process_batch(test_items)
        self.assertTrue(all(x["status"] == "RETRY" for x in out_inc))

if __name__ == "__main__":
    unittest.main()
