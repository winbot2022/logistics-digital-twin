#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 日本語フォントのインストール（Noto Sans CJK）
mkdir -p ~/.fonts
apt-get update && apt-get install -y fonts-noto-cjk
