#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Dataset chart template\n\nOptional template generator. Published reports/slides may contain manual edits.\nGeneration requires an explicit draft output; this module does nothing on import.'

from pathlib import Path
from generator_cli import generation_args


def generate(project_root, output, figures_dir=None):
    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-
    import matplotlib.pyplot as plt
    import matplotlib
    from pathlib import Path
    import json
    from collections import Counter
    import shutil

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False

    BASE_DIR = Path(project_root)
    FIG_DIR = Path(output)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 民族分布堆叠柱状图 (1,512 组真实数据)
    eth_data_1512 = {
        "苗族 (Miao)": (187, 35, 41),
        "傣族 (Dai)": (175, 37, 37),
        "藏族 (Tibetan)": (143, 31, 29),
        "彝族 (Yi)": (139, 29, 30),
        "壮族 (Zhuang)": (128, 28, 27),
        "白族 (Bai)": (97, 21, 21),
        "纳西族 (Naxi)": (81, 17, 18),
        "佤族 (Wa)": (72, 16, 15),
        "景颇族 (Jingpo)": (21, 5, 4),
        "哈尼族 (Hani)": (20, 4, 4),
    }

    eths = list(eth_data_1512.keys())
    trains = [v[0] for v in eth_data_1512.values()]
    vals = [v[1] for v in eth_data_1512.values()]
    tests = [v[2] for v in eth_data_1512.values()]

    plt.figure(figsize=(10.5, 5.2), dpi=300)
    x = range(len(eths))
    width = 0.55

    plt.bar(x, trains, width, label='训练集 Train (1,063张, 70.3%)', color='#1b3c73')
    plt.bar(x, vals, width, bottom=trains, label='验证集 Val (223张, 14.8%)', color='#3f72af')
    bottom_te = [trains[i] + vals[i] for i in range(len(trains))]
    plt.bar(x, tests, width, bottom=bottom_te, label='测试集 Test (226张, 14.9%)', color='#90caf9')

    plt.xlabel('民族类别 (Ethnic Groups)', fontsize=11, fontweight='bold')
    plt.ylabel('有效样本数量 (Images)', fontsize=11, fontweight='bold')
    plt.title('云南少数民族服饰图像生成数据集 (YECID-1512) 民族分布与子集划分统计', fontsize=12.5, fontweight='bold', pad=12)
    plt.xticks(x, eths, rotation=25, ha='right', fontsize=9.5)
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    for i, total in enumerate([sum(v) for v in eth_data_1512.values()]):
        pct = total / 1512.0 * 100.0
        plt.text(i, total + 3, f"{total} ({pct:.1f}%)", ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#111')

    plt.ylim(0, 310)
    plt.legend(frameon=True, facecolor='white', framealpha=0.9, loc='upper right')
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_ethnicity_split_distribution.png")
    plt.close()
    print("Saved fig1_ethnicity_split_distribution.png")

    # 2. 全流程质量清洗与精炼漏斗图
    stages = [
        '阶段一：全网多源原始采集',
        '阶段二：六级漏斗过滤去重',
        '阶段三：Rembg主体分割与白底标准化',
        '阶段四：双图严格VLM初筛',
        '阶段五：人机协同定向精修与去瑕疵',
        '最终交付：YECID-1512 纯金主集'
    ]
    counts = [6259, 5424, 5424, 1765, 1514, 1512]
    colors = ['#455a64', '#1976d2', '#0288d1', '#0097a7', '#00796b', '#2e7d32']

    plt.figure(figsize=(9.5, 5.0), dpi=300)
    bars = plt.barh(stages[::-1], counts[::-1], color=colors[::-1], height=0.55)
    plt.xlabel('样本留存数量 (Count)', fontsize=11, fontweight='bold')
    plt.title('民族服饰数据集全流程质量清洗与精炼漏斗 (Quality Funnel)', fontsize=12.5, fontweight='bold', pad=12)
    plt.grid(axis='x', linestyle='--', alpha=0.5)

    for bar in bars:
        w = bar.get_width()
        y = bar.get_y() + bar.get_height() / 2
        plt.text(w + 100, y, f"{int(w):,} 张", ha='left', va='center', fontsize=9.5, fontweight='bold', color='#222')

    plt.xlim(0, 7200)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_quality_funnel.png")
    plt.close()
    print("Saved fig2_quality_funnel.png")

    # 3. 细粒度核心属性标注分布多面板图
    ann_dir = BASE_DIR / "dataset/annotations"
    with open(ann_dir / "extended_fine_grained_attributes.jsonl", "r", encoding="utf-8") as f:
        ext_list = [json.loads(l) for l in f if l.strip()]

    with open(ann_dir / "captions.jsonl", "r", encoding="utf-8") as f:
        off_list = [json.loads(l) for l in f if l.strip()]

    collar_cnt = Counter(r["top_structure"]["collar_type"] for r in ext_list)
    opening_cnt = Counter(r["top_structure"]["opening_style"] for r in ext_list)
    sleeve_cnt = Counter(r["top"]["sleeve_length"] for r in off_list)
    bottom_cnt = Counter(r["bottom_structure"]["garment_type"] for r in ext_list)
    head_cnt = Counter(r["headwear_details"]["type"] for r in ext_list)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), dpi=300)

    def plot_sub(ax, counter, title, color):
        items = counter.most_common(7)
        labels = [k.replace(" (right-lapel)", "") for k, v in items]
        vals = [v for k, v in items]
        bars = ax.barh(labels[::-1], vals[::-1], color=color, height=0.55)
        ax.set_title(title, fontsize=11, fontweight='bold', pad=8)
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        for b in bars:
            w = b.get_width()
            y = b.get_y() + b.get_height() / 2
            ax.text(w + 10, y, f"{int(w)}", ha='left', va='center', fontsize=8.5, fontweight='bold')
        ax.set_xlim(0, max(vals) * 1.18)

    plot_sub(axes[0, 0], sleeve_cnt, '上衣袖长 (Sleeve Length)', '#1b3c73')
    plot_sub(axes[0, 1], collar_cnt, '领型结构 (Collar Type)', '#3f72af')
    plot_sub(axes[0, 2], opening_cnt, '开襟方式 (Opening Style)', '#00796b')
    plot_sub(axes[1, 0], bottom_cnt, '下装类别 (Bottom Garment Type)', '#d84315')
    plot_sub(axes[1, 1], head_cnt, '头饰类别 (Headwear Type)', '#6a1b9a')

    # 统计信息板
    ax_info = axes[1, 2]
    ax_info.axis('off')
    summary_text = (
        "【细粒度结构标注总体指标】\n\n"
        "• 主集有效图文对：1,512 组\n"
        "• 标注体系：三轨兼容 (官方/扩展/合并)\n"
        "• 受控核心字段：领型/开襟/袖长/下装/头饰\n"
        "• 材质反幻觉：未知材质严格规范为 unknown\n"
        "• 部件存在性：无上衣样本 145 组各字段标 none\n"
        "• 质量门禁状态：PASSED (1,512组 0 违规)\n"
        "• 生产离线单测：10 项真实 mock 全部通过\n"
        "• 视觉变体测试：16 异常触发RETRY, 对照成功"
    )
    ax_info.text(0.05, 0.5, summary_text, fontsize=10.0, va='center', ha='left',
                 bbox=dict(boxstyle='round,pad=0.8', facecolor='#f0f4f8', edgecolor='#3f72af', linewidth=1.5))

    plt.suptitle('民族服饰细粒度核心属性与结构标注分布 (Fine-grained Visual Attributes)', fontsize=13.5, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_attribute_distribution.png")
    plt.close()
    print("Saved fig3_attribute_distribution.png")

    # 4. 确保 fig4 存在
    src_fig4 = BASE_DIR / "dataset/reproducible_1120/1120_cuff_zoom_comparison.png"
    if src_fig4.exists():
        shutil.copy2(src_fig4, FIG_DIR / "fig4_sample_1120_repair.png")
        print("Saved fig4_sample_1120_repair.png")


def main():
    args = generation_args(__file__, 'Dataset chart template', directory=True, suffix=None)
    generate(args.project_root, args.output, args.figures_dir)


if __name__ == "__main__":
    main()
