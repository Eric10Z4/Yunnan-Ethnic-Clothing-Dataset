# 当前主集人工评审工具 v3

该入口读取当前主集的 1,512 条公开索引，不包含已排除的 `0803`、`1166`。原来的 1,603 张候选集页面不再作为当前主集入口。

`data.js` 由五份已发布文件生成：官方标注、扩展标注、合并标注、`metadata.csv` 和映射清单。生成器仅核对 ID、路径、民族与必要的跨轨字段，再输出 ID、主集相对路径、民族、split、公开 caption 和公开来源页链接。不会导出清单内的本机绝对路径、原始图片缓存、VLM 初审日志或认证字段。

## 生成与启动

需要 Python 3.9 或以上版本，生成器仅使用标准库。在仓库根目录运行：

```console
python code/build_review_tool_data.py
python -m http.server 8000 --bind 127.0.0.1 --directory .
```

打开 `http://127.0.0.1:8000/audit_tool_v3/`。Windows 也可在仓库根目录确认 Python 可用后，双击本目录的 `双击打开评审系统.bat`，或运行 `python audit_tool_v3/serve_review_tool.py`：它先绑定本地服务，再打开浏览器；用完后在服务窗口按 Ctrl+C。端口被占用时可加 `--port 8001`，不需要自动打开浏览器时可加 `--no-browser`。无需登录或认证。

生成器默认只写 `audit_tool_v3/data.js`，拒绝将输出写入 `dataset/`。它不会爬取图片、调用模型、重标注、重新划分数据或改写任何五轨文件。输入缺失、数量不是 1,512、重复 ID、五轨 ID/路径/民族不一致或混入已排除样本时，生成失败；已有输入不会被修复或覆盖。

## 图片另外提供

轻量 Git 仓库不分发全量图像，也不会自动下载。经合法渠道取得主集后，请保留以下目录结构：

```text
dataset/images/train/0001.jpg
dataset/images/val/....jpg
dataset/images/test/....jpg
```

页面按每条索引中的实际 split 加载 `../dataset/images/<split>/<image_id>.jpg`，不会请求历史工具的 `images/<原始文件名>`。缺图时会显示缺失路径并禁用 PASS/FAIL，仍可浏览索引和导出待评审清单。直接打开 `index.html` 也可读取静态 `data.js`，但浏览器对 `file:` 页面的本地存储策略不同，优先使用上述本地 HTTP 服务。

## 评审记录与导出

- `J`、空格或回车：记录当前图片的 UI PASS；数字 `1`–`7`：记录 FAIL 及原因；左右箭头：导航。
- 每次判定会保存实际评审时间。浏览器存储键使用五轨输入指纹，旧快照或历史 1,603 张候选集记录不会自动混入当前统计。
- 导出 CSV 包含 `record_kind=ui_review_only`、`ui_decision`、样本 ID/路径、快照指纹、评审时间与导出时间。未评审项标为 `PENDING`；缺图不会自动判为不合格。
- CSV 的引号、逗号、换行会正确转义，可能被电子表格当作公式的文本会添加文本前缀。
- **浏览器 UI 判定属于复核意见，不是新的标注真值。** 本页面没有写文件或调用数据流水线的能力；导出后若要修改正式数据，需另行逐项核验。本次操作不会自动修改正式标注、排除样本或划分。
- 清除浏览器数据可能丢失本地进度，请及时导出。页面显示的 caption 和民族标签是已发布数据字段，供核对使用，不代表一次新的视觉判断或专家鉴定。

## 小样本验证

```console
python -m unittest discover -s code -p test_build_review_tool_data.py
node audit_tool_v3/test_review_state.cjs
```

测试使用临时合成的两条五轨记录和模拟页面，不对主集图片作判定，也不会写入 `dataset/`。当前 1,512 条入口另通过生成器只读核对数量、引用和排除 ID；这不等同重新运行图像质检或标注审计。
