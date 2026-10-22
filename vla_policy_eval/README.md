# 路线 A：学习策略直接控制（公开 VLA 策略在 RoboCerebra 上的评测与诊断）

本目录存放路线 A 的代码，由负责同学推送。阶段结果见飞书原文档《RoboCerebra复现：实验结果与下一阶段方案》，以及合并文档 `../notes/RoboCerebra_阶段汇总_合并版_2026-10-22.md` 的第 3 节。

## 建议的目录结构

| 目录 | 内容 |
|---|---|
| `scripts/` | 评测与诊断脚本，如 `33_native_libero_probe.py`、`34_executor_validation_batch.py`、`35_scoring_semantics_probe.py` |
| `configs/` | 策略、任务与种子配置 |
| `results/` | 汇总表（CSV / Markdown）与少量关键图 |

原始输出（`outputs/` 下的回合数据、视频）和模型权重体积大，不入库；在 README 里写明存放位置与 Hugging Face 模型名、revision 即可。

## 推送方式

1. 接受仓库协作邀请后克隆：`git clone https://github.com/Vincent-Leon/robocerebra-realtime.git`
2. 新建分支：`git checkout -b route-a`
3. 把代码放进本目录，提交后推送：`git push -u origin route-a`
4. 在 GitHub 上发起合并请求。

注意：
- 不提交任何密钥。根目录的 `.gitignore` 已排除所有 `.env` 文件。
- 不提交 `*.npz`、`*.hdf5`、`*.mp4` 等大文件。
