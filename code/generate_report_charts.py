#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import json
from collections import Counter

# Set fonts
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

base_dir = Path(r"C:\Users\26730\Desktop\课程相关\计算机视觉\期中实验")
fig_dir = base_dir / "report" / "figures"
fig_dir.mkdir(parents=True, exist_ok=True)

# 1. Ethnicity Distribution across Train / Val / Test
eth_data = {
    "苗族 (Miao)": (174, 37, 37),
    "傣族 (Dai)": (172, 37, 37),
    "彝族 (Yi)": (148, 32, 32),
    "藏族 (Tibetan)": (139, 30, 30),
    "壮族 (Zhuang)": (107, 23, 23),
    "白族 (Bai)": (95, 20, 20),
    "哈尼族 (Hani)": (82, 18, 17),
    "纳西族 (Naxi)": (74, 16, 15),
    "佤族 (Wa)": (60, 13, 13),
    "景颇族 (Jingpo)": (59, 12, 13),
}

eths = list(eth_data.keys())
trains = [v[0] for v in eth_data.values()]
vals = [v[1] for v in eth_data.values()]
tests = [v[2] for v in eth_data.values()]

plt.figure(figsize=(10, 5), dpi=300)
x = range(len(eths))
width = 0.55

plt.bar(x, trains, width, label='训练集 Train (70%)', color='#2b5c8f')
plt.bar(x, vals, width, bottom=trains, label='验证集 Val (15%)', color='#4a90e2')
bottom_te = [trains[i] + vals[i] for i in range(len(trains))]
plt.bar(x, tests, width, bottom=bottom_te, label='测试集 Test (15%)', color='#82c0ff')

plt.xlabel('民族类别 (Ethnic Groups)', fontsize=11, fontweight='bold')
plt.ylabel('样本数量 (Number of Images)', fontsize=11, fontweight='bold')
plt.title('云南少数民族服饰图像生成数据集 (YECID-1584) 分布与划分统计', fontsize=13, fontweight='bold', pad=12)
plt.xticks(x, eths, rotation=25, ha='right', fontsize=9.5)
plt.grid(axis='y', linestyle='--', alpha=0.5)

# Add totals on top
for i, total in enumerate([sum(v) for v in eth_data.values()]):
    plt.text(i, total + 4, str(total), ha='center', va='bottom', fontsize=9, fontweight='bold', color='#111')

plt.ylim(0, 280)
plt.legend(frameon=True, facecolor='white', framealpha=0.9)
plt.tight_layout()
plt.savefig(fig_dir / "fig1_ethnicity_split_distribution.png")
plt.close()
print("Saved fig1_ethnicity_split_distribution.png")

# 2. Quality Funnel Filtering Chart
stages = [
    '阶段一：全网多源原始采集',
    '阶段二：六级漏斗过滤去重',
    '阶段三：Rembg抠图与512白底规范化',
    '阶段三：双图严格VLM多模态终审',
    '阶段三：两轮双盲人工独立复审',
    '最终交付：YECID-1584 纯金数据集'
]
counts = [7751, 5424, 5423, 1765, 1603, 1584]
colors = ['#455a64', '#1976d2', '#0288d1', '#0097a7', '#00796b', '#2e7d32']

plt.figure(figsize=(9, 5), dpi=300)
bars = plt.barh(stages[::-1], counts[::-1], color=colors[::-1], height=0.55)
plt.xlabel('有效样本数量 (Count)', fontsize=11, fontweight='bold')
plt.title('民族服饰数据集全流程人机协同质量清洗漏斗 (Data Quality Funnel)', fontsize=13, fontweight='bold', pad=12)
plt.grid(axis='x', linestyle='--', alpha=0.5)

for bar in bars:
    w = bar.get_width()
    y = bar.get_y() + bar.get_height() / 2
    plt.text(w + 100, y, f"{int(w)} 张", ha='left', va='center', fontsize=9.5, fontweight='bold', color='#222')

plt.xlim(0, 8800)
plt.tight_layout()
plt.savefig(fig_dir / "fig2_quality_funnel.png")
plt.close()
print("Saved fig2_quality_funnel.png")
