# 上游代码快照

本目录由 `.github/workflows/upstream-check.yml` 自动维护，**不要手工编辑**。

- `hasscc/` — 本项目的直接基座（国内服分支）
- `marcelwestra/` — fork 网络的根（国际服分支，仍在维护）

工作流每周一抓取一次上游文件。有变动时会提交新快照，并开一个带完整 diff 的 Issue。

这些文件仅作比对参考。本仓库已重构过架构，**不要用上游文件直接覆盖 `custom_components/niu/`**。
