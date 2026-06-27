#!/usr/bin/env python3
"""
"HermesFace → Cloudflare R2 异地备份"
用法: python3 scripts/sync_to_r2.py
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError, EndpointResolutionError
from pathlib import Path

# ── 读取配置 ────────────────────────────────────────────────
R2_ENDPOINT   = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_BUCKET     = os.environ.get("R2_BUCKET_NAME")

SOURCE_DIR    = Path("/opt/data")   # HermesFace 持久化目录
R2_PREFIX     = "hermesface-data"   # Bucket 内的对象路径前缀

EXCLUDE = {".tmp", ".pyc", ".log"}  # 排除的文件后缀
EXCLUDE_DIRS = {"__pycache__", ".git"}

# ── 工具函数 ────────────────────────────────────────────────
def check_env():
    missing = [v for v in
               ["R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET_NAME"]
               if not os.environ.get(v)]
    if missing:
        print(f"[R2] ✗ 缺少环境变量: {', '.join(missing)}")
        sys.exit(1)

def should_skip(path: Path) -> bool:
    if any(d in path.parts for d in EXCLUDE_DIRS):
        return True
    if path.suffix in EXCLUDE:
        return True
    return False

# ── 主逻辑 ─────────────────────────────────────────────────
def sync():
    check_env()

    # ── 文件数量安全检查 ──────────────────────────────────
    MAX_FILES = 2000
    files = [f for f in SOURCE_DIR.rglob("*") if f.is_file() and not should_skip(f)]
    if len(files) > MAX_FILES:
        print(f"[R2] ✗ 文件数量异常: {len(files)} 个，超出上限 {MAX_FILES}，中止同步")
        sys.exit(1)

    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )

    if not SOURCE_DIR.exists():
        print(f"[R2] ✗ 源目录不存在: {SOURCE_DIR}")
        sys.exit(1)

    uploaded, skipped, failed = 0, 0, 0

    for file_path in sorted(SOURCE_DIR.rglob("*")):
        if not file_path.is_file():
            continue
        if should_skip(file_path):
            skipped += 1
            continue

        key = f"{R2_PREFIX}/{file_path.relative_to(SOURCE_DIR)}"

        try:
            s3.upload_file(str(file_path), R2_BUCKET, key)
            print(f"[R2] ✓ {key}")
            uploaded += 1
        except (ClientError, EndpointResolutionError) as e:
            print(f"[R2] ✗ {key} — {e}")
            failed += 1

    print(f"\n[R2] 完成: {uploaded} 上传 / {skipped} 跳过 / {failed} 失败")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    sync()
