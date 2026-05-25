from pathlib import Path
from uuid import uuid4
import logging
from fastapi import HTTPException, UploadFile, status
from app.config import get_settings

logger = logging.getLogger(__name__)

def validate_upload(file: UploadFile) -> str:
    settings = get_settings()
    extension = settings.allowed_content_types.get(file.content_type or "")
    if not extension:
        logger.warning("Upload rejected unsupported_content_type=%s file_name=%s", file.content_type, file.filename)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, JPG, PNG, and WEBP invoice files are supported",
        )
    return extension

async def save_upload(file: UploadFile) -> tuple[str, str]:
    settings = get_settings()
    extension = validate_upload(file)
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid4()}{extension}"
    destination = upload_dir / safe_name
    logger.info("Saving upload file_name=%s content_type=%s destination=%s", file.filename, file.content_type, safe_name)

    with destination.open("wb") as output:
        total_size = 0
        while chunk := await file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > settings.max_upload_bytes:
                destination.unlink(missing_ok=True)
                logger.warning("Upload rejected file_too_large file_name=%s size=%s", file.filename, total_size)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Invoice file must be {settings.max_upload_bytes // (1024 * 1024)} MB or smaller",
                )
            output.write(chunk)

    logger.info("Upload saved file_name=%s stored_name=%s size=%s", file.filename, safe_name, total_size)
    return str(destination), f"/uploads/{safe_name}"

def delete_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
        logger.info("Stored file deleted path=%s", path)
    except OSError:
        logger.exception("Stored file delete failed path=%s", path)
        pass
