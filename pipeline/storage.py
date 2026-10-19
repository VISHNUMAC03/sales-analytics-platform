"""
Raw storage ("the data lake").

Before we touch any data we keep an exact, untouched copy of it, organised by
source and run:  data/raw/<source>/<run_id>/<file>

Why? If a bug in our cleaning code damages data, we can always re-process
from the original. In production this folder would be an Amazon S3 bucket;
set S3_BUCKET in .env and every file is uploaded there too.
"""

import json
import logging
import shutil
from pathlib import Path

from pipeline.config import S3_BUCKET

logger = logging.getLogger(__name__)


def _raw_path(raw_dir: Path, source: str, run_id: str, filename: str) -> Path:
    path = raw_dir / source / run_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _upload_to_s3(local_path: Path, source: str, run_id: str) -> None:
    if not S3_BUCKET:
        return
    import boto3  # imported here so the project works without AWS set up

    key = f"raw/{source}/{run_id}/{local_path.name}"
    boto3.client("s3").upload_file(str(local_path), S3_BUCKET, key)
    logger.info("Uploaded %s to s3://%s/%s", local_path.name, S3_BUCKET, key)


def land_file(src: Path, raw_dir: Path, source: str, run_id: str) -> Path:
    """Copy a source file, unchanged, into the raw zone."""
    dest = _raw_path(raw_dir, source, run_id, src.name)
    shutil.copy2(src, dest)
    _upload_to_s3(dest, source, run_id)
    return dest


def land_json(payload: dict, raw_dir: Path, source: str, run_id: str, filename: str) -> Path:
    """Save an API response, unchanged, into the raw zone."""
    dest = _raw_path(raw_dir, source, run_id, filename)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _upload_to_s3(dest, source, run_id)
    return dest
