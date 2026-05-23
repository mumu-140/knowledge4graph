---
name: publish-graph
description: 将 understand-anything 生成的知识图谱导入 knowledge4graph 仪表盘并部署到 Cloudflare Pages。在用户想添加新项目图谱、更新已有图谱或部署到线上时使用。
---

# publish-graph

将知识图谱导入 knowledge4graph 并安全部署。

## 前置条件

1. 目标项目已运行 `/understand`，存在 `<project-root>/.understand-anything/knowledge-graph.json`
2. knowledge4graph 仓库本地可用（默认 `/Users/mumu/workspace/knowledge4graph`）
3. Node.js ≥ 22、pnpm ≥ 10 已安装

## 流程

### Step 1 — 导入

```bash
cd <knowledge4graph-repo>
python3 scripts/import-project.py <project-id> <project-source-root> [options]
```

参数：
- `<project-id>` — URL 标识符，仅小写字母、数字、连字符（如 `my-project`）
- `<project-source-root>` — 项目源码根目录的绝对路径

选项：
- `--name "显示名"` — 项目在仪表盘的显示名称
- `--description "描述"` — 项目简介
- `--skip-source` — 跳过源码提取（远程无源码预览）
- `--size-limit <MB>` — 源码大小上限，默认 100MB

脚本自动完成：
- 复制 knowledge-graph.json / meta.json / config.json
- 源码 < 阈值 → 提取到 `files/` 目录
- 更新 `public/graphs/index.json`

### Step 2 — 安全检查

导入完成后，运行预提交检查脚本：

```bash
python3 scripts/pre-commit-check.py --fix
```

脚本自动执行三项检查：
1. **sourceRoot 清理** — 移除 index.json 中的本地路径（`--fix` 自动修复）
2. **敏感文件扫描** — 检测 .env、密钥、凭据等文件，发现则阻断
3. **体积报告** — 单项目 > 50MB 或总计 > 200MB 时警告

如脚本报 `❌ BLOCKED`，必须先处理再继续。

### Step 3 — 本地构建验证

```bash
pnpm build
```

构建失败则停止，不进入提交步骤。

### Step 4 — 提交

安全检查和构建通过后（Step 2 的 `--fix` 已自动清理 sourceRoot）：

```bash
git add packages/dashboard/public/graphs/
git status --short
```

确认变更列表无异常后提交：
```bash
git commit -m "Add <project-id> knowledge graph"
```

### Step 5 — 部署（需用户确认）

**在推送前必须询问用户是否确认部署。**

告知用户：
- 推送到 main 分支将自动触发 GitHub Actions 部署到 Cloudflare Pages
- 部署完成后访问 `https://knowledge4graph.pages.dev/?project=<project-id>`

用户确认后：
```bash
git push origin main
```

推送后检查 Action 状态：
```bash
gh run list --limit 1
```

如失败，用 `gh run view <run-id> --log` 查看日志并协助排查。

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| 导入脚本报 knowledge-graph.json not found | 未运行 /understand | 先对目标项目运行 /understand |
| 构建失败 | 图谱 JSON 格式错误 | 检查 knowledge-graph.json 是否合法 JSON |
| Action 部署失败：CLOUDFLARE_API_TOKEN | GitHub Secrets 未配置 | 在 repo Settings → Secrets 添加 |
| 源码预览不可用 | 源码超限被跳过或用了 --skip-source | 重新导入并调高 --size-limit |
