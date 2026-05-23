#!/usr/bin/env python3
"""
将 understand-anything 生成的知识图谱导入 knowledge4graph。

用法:
  python3 scripts/import-project.py <project-id> <source-root> [--skip-source] [--size-limit MB]

示例:
  python3 scripts/import-project.py ppt-agent /path/to/skills/ppt-agent
  python3 scripts/import-project.py big-project /path/to/repo --size-limit 50
  python3 scripts/import-project.py big-project /path/to/repo --skip-source

行为:
  1. 从 <source-root>/.understand-anything/ 复制 knowledge-graph.json、meta.json、config.json
  2. 计算知识图谱引用的所有源文件总大小
  3. 总大小 < 阈值（默认 100MB）→ 提取源码到 files/ 目录
  4. 总大小 >= 阈值 → 警告并跳过源码（远程部署时无源码预览）
  5. 更新 public/graphs/index.json
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
GRAPHS_DIR = PROJECT_ROOT / "packages" / "dashboard" / "public" / "graphs"
INDEX_FILE = GRAPHS_DIR / "index.json"

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".webm",
    ".pdf", ".zip", ".tar", ".gz", ".bz2",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
}

EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".jsx": "jsx", ".json": "json", ".md": "markdown",
    ".html": "markup", ".css": "css", ".yaml": "yaml", ".yml": "yaml",
    ".sh": "bash", ".bash": "bash", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".java": "java", ".c": "c", ".cpp": "cpp",
    ".h": "c", ".hpp": "cpp", ".txt": "text", ".toml": "toml",
    ".xml": "markup", ".sql": "sql",
}


def detect_language(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return EXT_TO_LANG.get(ext, "text")


def load_graph(graph_path: Path) -> dict:
    with open(graph_path, encoding="utf-8") as f:
        return json.load(f)


def collect_source_files(graph: dict, source_root: Path) -> list[dict]:
    """收集知识图谱引用的所有可读源文件。"""
    results = []
    seen = set()

    for node in graph.get("nodes", []):
        fp = node.get("filePath")
        if not fp or fp in seen:
            continue
        seen.add(fp)

        if Path(fp).suffix.lower() in BINARY_EXTENSIONS:
            continue

        abs_path = source_root / fp
        if not abs_path.is_file():
            continue

        try:
            size = abs_path.stat().st_size
            results.append({"relative": fp, "absolute": str(abs_path), "size": size})
        except OSError:
            continue

    return results


def extract_sources(files: list[dict], output_dir: Path, source_root: Path) -> int:
    """提取源文件内容为 JSON，返回成功数。"""
    count = 0
    for entry in files:
        abs_path = Path(entry["absolute"])
        rel_path = entry["relative"]

        try:
            content = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        out_file = output_dir / f"{rel_path}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        out_file.write_text(json.dumps({
            "path": rel_path,
            "language": detect_language(rel_path),
            "content": content,
            "sizeBytes": len(content.encode("utf-8")),
            "lineCount": line_count,
        }, ensure_ascii=False), encoding="utf-8")
        count += 1

    return count


def update_index(project_id: str, name: str, description: str, source_root: str, has_source: bool):
    """更新 index.json，新增或更新项目条目。"""
    index: list[dict] = []
    if INDEX_FILE.exists():
        with open(INDEX_FILE, encoding="utf-8") as f:
            index = json.load(f)

    entry = {
        "id": project_id,
        "name": name,
        "description": description,
        "hasSource": has_source,
    }
    if has_source:
        entry["sourceMode"] = "bundled"
    else:
        entry["sourceMode"] = "none"
    entry["sourceRoot"] = source_root

    existing = next((i for i, e in enumerate(index) if e["id"] == project_id), None)
    if existing is not None:
        index[existing] = entry
    else:
        index.append(entry)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="导入知识图谱项目")
    parser.add_argument("project_id", help="项目 ID（用于 URL）")
    parser.add_argument("source_root", help="项目源码根目录")
    parser.add_argument("--name", help="项目显示名（默认取 README 或 ID）")
    parser.add_argument("--description", default="", help="项目描述")
    parser.add_argument("--skip-source", action="store_true", help="跳过源码提取")
    parser.add_argument("--size-limit", type=int, default=100, help="源码大小上限（MB），超过则跳过（默认 100）")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    ua_dir = source_root / ".understand-anything"

    graph_file = ua_dir / "knowledge-graph.json"
    if not graph_file.exists():
        print(f"ERROR: {graph_file} not found", file=sys.stderr)
        print("Run /understand on the project first.", file=sys.stderr)
        return 1

    # 目标目录
    target_dir = GRAPHS_DIR / args.project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. 复制图谱数据
    shutil.copy2(graph_file, target_dir / "knowledge-graph.json")
    for extra in ["meta.json", "config.json"]:
        src = ua_dir / extra
        if src.exists():
            shutil.copy2(src, target_dir / extra)

    print(f"[+] Graph data copied to {target_dir}")

    # 2. 加载图谱，收集源文件
    graph = load_graph(graph_file)
    project_name = args.name or graph.get("projectName", args.project_id)
    project_desc = args.description or graph.get("projectDescription", "")

    source_files = collect_source_files(graph, source_root)
    total_size = sum(f["size"] for f in source_files)
    total_mb = total_size / (1024 * 1024)

    print(f"[i] Source files: {len(source_files)}, total: {total_mb:.1f} MB")

    # 3. 决定是否提取源码
    has_source = False
    if args.skip_source:
        print("[i] --skip-source: skipping source extraction")
    elif total_mb >= args.size_limit:
        print(f"[!] Source size ({total_mb:.1f} MB) exceeds limit ({args.size_limit} MB)")
        print("[!] Skipping source extraction. Remote deployment will have no source preview.")
        print(f"[i] To force: re-run with --size-limit {int(total_mb) + 10}")
    else:
        files_dir = target_dir / "files"
        if files_dir.exists():
            shutil.rmtree(files_dir)
        count = extract_sources(source_files, files_dir, source_root)
        has_source = True
        print(f"[+] Extracted {count} source files to {files_dir}")

    # 4. 更新 index.json
    update_index(args.project_id, project_name, project_desc, str(source_root), has_source)
    print(f"[+] Updated {INDEX_FILE}")

    print(f"\nDone. Visit /?project={args.project_id} to view.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
