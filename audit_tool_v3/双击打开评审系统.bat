@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo 启动当前主集人工评审工具 v3，关闭服务请按 Ctrl+C。
echo 主集图片需另外放入 dataset/images，缺图时不能作出判定。
python audit_tool_v3/serve_review_tool.py
pause
