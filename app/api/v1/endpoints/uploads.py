import uuid
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import mimetypes

from app.core.config import get_settings
from app.api.deps import get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


def _s3_client():
    settings = get_settings()
    if not all([settings.aws_region, settings.aws_access_key_id, settings.aws_secret_access_key]):
        raise HTTPException(
            status_code=500,
            detail="S3 자격증명이 설정되지 않았습니다. AWS_REGION/ACCESS_KEY_ID/SECRET_ACCESS_KEY를 확인하세요.",
        )
    try:
        client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Failed to init S3 client") from exc
    return client


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    settings = get_settings()
    if not settings.aws_bucket:
        raise HTTPException(status_code=500, detail="S3 버킷이 설정되지 않았습니다. AWS_BUCKET을 확인하세요.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미지 파일만 업로드 가능합니다")

    ext = ""
    if file.filename and "." in file.filename:
        ext = file.filename[file.filename.rfind(".") :]
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    key = f"posts/{uuid.uuid4()}{ext}"
    client = _s3_client()
    try:
        file.file.seek(0)
        # Block Public Access가 켜져 있어도 동작하도록 ACL 없이 업로드 후 presigned URL 반환
        client.upload_fileobj(
            file.file,
            settings.aws_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        signed = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_bucket, "Key": key},
            ExpiresIn=60 * 60 * 24 * 7,  # 7일
        )
        return {"url": signed, "key": key}
    except ClientError as exc:
        logger.error("S3 upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"S3 업로드 실패: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        logger.error("S3 upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"S3 업로드 실패: {exc}") from exc
