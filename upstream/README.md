# 上游代码快照

本目录由 `.github/workflows/upstream-check.yml` 自动维护，**不要手工编辑**。
每次运行会整个重建，手工改动会被覆盖。

- `hasscc/` — 本项目的直接基座（国内服分支）
- `marcelwestra/` — fork 网络的根（国际服分支，仍在维护）

工作流每周一抓取一次上游文件。有变动时会提交新快照，并开一个带完整 diff 的 Issue。

## 为什么 manifest.json 和 __init__.py 带 .txt 后缀

hassfest 的集成发现逻辑（`script/hassfest/model.py` 的 `Integration.load_dir`）
会把任何含有 `__init__.py` 或 `manifest.json` 的目录当作一个集成来校验。
快照目录若保留原名，会被识别成「域名 niu 但目录名叫 hasscc」的非法集成，导致 CI 报错：

```
[ERROR] [MANIFEST] Domain does not match dir name
```

加 `.txt` 后缀即可绕开发现逻辑。其余 `.py` 文件保持原扩展名，
这样 GitHub 在 diff 中仍能提供语法高亮。

## 使用方式

这些文件仅作比对参考。本仓库已重构过架构，
**不要用上游文件直接覆盖 `custom_components/niu/`**。
