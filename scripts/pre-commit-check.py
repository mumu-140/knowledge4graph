#!/usr/bin/env python3
"""
提交前安全检查：清理 sourceRoot、检测敏感文件、报告体积。

用法:
  python3 scripts/pre-commit-check.py [--fix]

行为:
  1. 检查 index.json 是否包含 sourceRoot（本地路径，不应提交）
  2. 扫描 graphs/ 目录中的敏感文件
  3. 报告各项目体积

  --fix  自动移除 index.json 中的 sourceRoot 字段
"""

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
GRAPHS_DIR = PROJECT_ROOT / "packages" / "dashboard" / "public" / "graphs"
INDEX_FILE = GRAPHS_DIR / "index.json"

SENSITIVE_PATTERNS = {".env", "secret", "credential", "password", ".key", ".pem", ".p12", "token"}
SIZE_WARN_MB = 50
SIZE_TOTAL_WARN_MB = 200


def check_source_root(fix: bool) -> list[str]:
    issues = []
    if not INDEX_FILE.exists():
        return issues

    with open(INDEX_FILE, encoding="utf-8") as f:
        data = json.load(f)

    dirty = False
    for entry in data:
        if "sourceRoot" in entry:
            issues.append(f"index.json: project '{entry['id']}' contains sourceRoot: {entry['sourceRoot']}")
            if fix:
                del entry["sourceRoot"]
                dirty = True

    if fix and dirty:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("[fix] Removed sourceRoot fields from index.json")

    return issues


def check_sensitive_files() -> list[str]:
    issues = []
    if not GRAPHS_DIR.exists():
        return issues

    for root, _, files in os.walk(GRAPHS_DIR):
        for name in files:
            name_lower = name.lower()
            for pattern in SENSITIVE_PATTERNS:
                if pattern in name_lower:
                    rel = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)
                    issues.append(f"Sensitive file detected: {rel}")
                    break
    return issues


def check_sizes() -> list[str]:
    warnings = []
    if not GRAPHS_DIR.exists():
        return warnings

    total = 0
    for project_dir in sorted(GRAPHS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        size = sum(f.stat().st_size for f in project_dir.rglob("*") if f.is_file())
        size_mb = size / (1024 * 1024)
        total += size
        status = "⚠️" if size_mb > SIZE_WARN_MB else "✓"
        print(f"  {status} {project_dir.name}: {size_mb:.1f} MB")
        if size_mb > SIZE_WARN_MB:
            warnings.append(f"Project '{project_dir.name}' is {size_mb:.1f} MB (> {SIZE_WARN_MB} MB)")

    total_mb = total / (1024 * 1024)
    status = "⚠️" if total_mb > SIZE_TOTAL_WARN_MB else "✓"
    print(f"  {status} Total: {total_mb:.1f} MB")
    if total_mb > SIZE_TOTAL_WARN_MB:
        warnings.append(f"Total graphs size is {total_mb:.1f} MB (> {SIZE_TOTAL_WARN_MB} MB)")

    return warnings


def main():
    parser = argparse.ArgumentParser(description="Pre-commit safety checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues (remove sourceRoot)")
    args = parser.parse_args()

    print("=== Pre-commit Check ===\n")

    all_issues = []

    print("[1/3] Checking sourceRoot in index.json...")
    issues = check_source_root(fix=args.fix)
    all_issues.extend(issues)
    if issues and not args.fix:
        for i in issues:
            print(f"  ⚠️  {i}")
        print("  Run with --fix to auto-remove sourceRoot fields.\n")
    elif not issues:
        print("  ✓ Clean\n")
    else:
        print()

    print("[2/3] Scanning for sensitive files...")
    issues = check_sensitive_files()
    all_issues.extend(issues)
    if issues:
        for i in issues:
            print(f"  ❌ {i}")
    else:
        print("  ✓ No sensitive files found")
    print()

    print("[3/3] Checking project sizes...")
    warnings = check_sizes()
    all_issues.extend(warnings)
    print()

    if [i for i in all_issues if "Sensitive" in i]:
        print("❌ BLOCKED: Sensitive files detected. Remove them before committing.")
        return 1

    if all_issues and not args.fix:
        print("⚠️  Issues found. Review above and fix, or re-run with --fix.")
        return 1

    print("✓ All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
