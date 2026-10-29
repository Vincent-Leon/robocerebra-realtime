#!/bin/bash
# 经代理从 ModelScope 下载模型仓库的全部文件（curl，断点续传），下载后按接口给出的大小与 sha256 校验。
# 用法: dl_modelscope.sh <仓库，如 Qwen/Qwen3-VL-2B-Instruct> <目标目录> [<仓库> <目标目录> ...]
# 依次处理每一对；进度写到标准输出（建议 setsid nohup 后台运行并重定向到日志）。
export https_proxy=${https_proxy:-http://202.204.62.109:7890} http_proxy=${http_proxy:-http://202.204.62.109:7890}
API=https://www.modelscope.cn/api/v1/models
while [ $# -ge 2 ]; do
  repo=$1; dest=$2; shift 2
  mkdir -p "$dest"
  echo "[$(date +%T)] start $repo -> $dest"
  curl -s --retry 5 "$API/$repo/repo/files?Revision=master&Recursive=true" -o "$dest/.files.json" || { echo "文件列表获取失败 $repo"; continue; }
  python3 - "$dest/.files.json" > "$dest/.files.tsv" <<'EOF'
import json, sys
for f in json.load(open(sys.argv[1]))["Data"]["Files"]:
    if f["Type"] == "blob": print(f"{f['Path']}\t{f['Size']}\t{f.get('Sha256') or ''}")
EOF
  bad=0
  while IFS=$'\t' read -r path size sha; do
    out="$dest/$path"; mkdir -p "$(dirname "$out")"
    have=$(stat -c %s "$out" 2>/dev/null || echo 0)
    if [ "$have" != "$size" ]; then
      for try in 1 2 3 4 5; do
        curl -sL --retry 3 -C - -o "$out" "$API/$repo/repo?Revision=master&FilePath=$path" && [ "$(stat -c %s "$out")" = "$size" ] && break
        echo "[$(date +%T)] 重试 $try $path（已有 $(stat -c %s "$out" 2>/dev/null) / $size）"; sleep 5
      done
    fi
    if [ "$(stat -c %s "$out" 2>/dev/null)" != "$size" ]; then echo "大小不符 $path"; bad=1; continue; fi
    if [ -n "$sha" ] && [ "$size" -gt 1000000 ]; then
      [ "$(sha256sum "$out" | cut -d' ' -f1)" = "$sha" ] || { echo "sha256 不符 $path"; bad=1; }
    fi
  done < "$dest/.files.tsv"
  echo "[$(date +%T)] done $repo bad=$bad size=$(du -sh "$dest" | cut -f1)"
done
echo "[$(date +%T)] ALL-DONE"
