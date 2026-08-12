#!/usr/bin/env python3
"""
FinCast 사전학습 가중치를 Hugging Face에서 받아 로컬 `.pth`로 저장한다.

사용 전:
  1) FinCast-fts 클론 후 `pip install -e .` (또는 PYTHONPATH=/path/to/FinCast-fts/src)
  2) 이 스크립트로 체크포인트 다운로드
  3) BINNAIR_PREDICTOR_TYPE=fincast
     BINNAIR_FINCAST_CHECKPOINT=...
     BINNAIR_FINCAST_REPO=.../FinCast-fts/src
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_REPO_ID = "Vincent05R/FinCast"
DEFAULT_FILENAME = "fincast.pth"
# HF 카드에 파일명이 다를 수 있어 --filename / --list 로 확인


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download FinCast checkpoint from Hugging Face."
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help=f"Hugging Face model repo. Default: {DEFAULT_REPO_ID}",
    )
    parser.add_argument(
        "--filename",
        default=DEFAULT_FILENAME,
        help=(
            "File inside the repo to download. "
            f"Default: {DEFAULT_FILENAME} (override if HF file name differs)"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="models/fincast",
        help="Local directory for the checkpoint. Default: models/fincast",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_files",
        help="List files in the HF repo and exit (no download).",
    )
    return parser.parse_args()


def list_repo_files(repo_id: str) -> int:
    from huggingface_hub import list_repo_files

    files = list_repo_files(repo_id=repo_id, repo_type="model")
    print(f"Files in {repo_id}:")
    for name in files:
        print(f"  {name}")
    return 0


def download_checkpoint(repo_id: str, filename: str, out_dir: Path) -> Path:
    from huggingface_hub import hf_hub_download

    out_dir.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(out_dir),
        local_dir_use_symlinks=False,
    )
    return Path(path)


def main() -> int:
    args = parse_args()
    try:
        if args.list_files:
            return list_repo_files(args.repo_id)
        out = download_checkpoint(
            args.repo_id, args.filename, Path(args.out_dir)
        )
        print(f"Downloaded: {out}")
        print("Set env:")
        print(f"  BINNAIR_PREDICTOR_TYPE=fincast")
        print(f"  BINNAIR_FINCAST_CHECKPOINT={out}")
        print("  BINNAIR_FINCAST_REPO=/path/to/FinCast-fts/src")
        return 0
    except Exception as e:
        print(f"FinCast download failed: {e}", file=sys.stderr)
        print(
            "Tip: python scripts/download_fincast_weights.py --list",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
