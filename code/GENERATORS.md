# 可选的报告、图表和PPT模板生成器

本次同步了本地更新后的 Word 和图表生成源码，保留原有模板内容。
发布的 Word/PPT 另含人工修订，不能把模板生成结果当作发布稿的逐字节重现。
这次代码修复没有运行任何文档或图表生成器，也没有改写已发布文件。

## 输出保护

三个生成器均不在导入时生成内容，必须显式提供输出位置。
输出不能位于所选项目的 `dataset/` 或 `report/` 中；已有草稿默认拒绝覆盖。
`--force` 只允许覆盖这些保护目录之外的草稿，不解除发布目录保护。

## 在独立草稿目录生成

先安装 `code/requirements.txt` 中的相应依赖。下面仅为可选命令示例，
不是定稿数据核验步骤。请先创建一个独立草稿父目录，例如 `../drafts`。

```console
python code/generate_report_charts.py --project-root . --output-dir ../drafts/charts-new
python code/build_report_docx.py --project-root . --figures-dir ../drafts/charts-new --output ../drafts/report-new.docx
python code/build_slides_pptx.py --project-root . --figures-dir ../drafts/charts-new --output ../drafts/slides-new.pptx
```

图表脚本只读取所选项目的现有标注和1120对照材料；它不会补采、重标或重新划分数据。
模板中的历史文字与统计口径仍应由作者核对，尤其不要将不同候选池画成同一数量漏斗。

只查看命令帮助不会生成文件：

```console
python code/build_report_docx.py --help
python code/generate_report_charts.py --help
python code/build_slides_pptx.py --help
```

## 离线验证

```console
python -m unittest discover -s code -p test_generator_safety.py -v
```

测试仅检查导入无生成副作用、显式输出、禁止覆盖发布目录及草稿覆盖保护，
不生成报告、PPT、图表或处理主集图片。
