from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.deps import RequestIdDep, SessionDep
from src.common.config import settings
from src.monitoring.audit import record_audit
from src.monitoring.metrics import VISION_LATENCY
from src.schemas.agent import UploadResponse
from src.schemas.vision import (
    SimilarImageResponse,
    VisionEvaluateResponse,
    VisionIdentifyResponse,
)
from src.vision import service as vision_service

router = APIRouter(tags=["vision"])

SUFFIX_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


async def store_upload(file: UploadFile, request_id: str | None, session: SessionDep) -> UploadResponse:
    if file.content_type not in settings.allowed_image_type_list:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{file.content_type}'. Allowed: "
            f"{', '.join(settings.allowed_image_type_list)}",
        )
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds the size limit.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image_format = image.format
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}") from exc

    if width < 32 or height < 32:
        raise HTTPException(status_code=400, detail="Image is too small (minimum 32x32).")
    if width > 8000 or height > 8000:
        raise HTTPException(status_code=400, detail="Image dimensions exceed the limit.")

    suffix = SUFFIX_BY_TYPE.get(file.content_type or "", Path(file.filename or "").suffix or ".png")
    image_id = f"{uuid.uuid4().hex}{suffix}"
    path = settings.upload_path / image_id
    path.write_bytes(data)

    digest = hashlib.sha256(data).hexdigest()
    record_audit(
        session,
        actor="api-user",
        action="vision.upload",
        entity_type="upload",
        entity_id=image_id,
        payload={
            "content_type": file.content_type,
            "bytes": len(data),
            "width": width,
            "height": height,
            "format": image_format,
            "sha256": digest,
        },
        request_id=request_id,
    )
    return UploadResponse(
        image_id=image_id,
        filename=file.filename or image_id,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        sha256=digest,
        width=width,
        height=height,
    )


def _resolve_image(image_id: str) -> Path:
    path = (settings.upload_path / Path(image_id).name).resolve()
    if not str(path).startswith(str(settings.upload_path.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Uploaded image not found")
    return path


@router.post("/vision/upload", response_model=UploadResponse)
async def upload(
    session: SessionDep, request_id: RequestIdDep, file: UploadFile = File(...)
) -> UploadResponse:
    return await store_upload(file, request_id, session)


@router.post("/vision/identify", response_model=VisionIdentifyResponse)
async def identify(
    session: SessionDep,
    file: UploadFile | None = File(default=None),
    image_id: str | None = Form(default=None),
    top_k: int | None = Form(default=None),
) -> VisionIdentifyResponse:
    if file is not None:
        upload_response = await store_upload(file, None, session)
        path = _resolve_image(upload_response.image_id)
    elif image_id:
        path = _resolve_image(image_id)
    else:
        raise HTTPException(status_code=400, detail="Provide a file or an image_id.")

    response = vision_service.identify(session, path, top_k=top_k)
    VISION_LATENCY.observe(response.latency_ms / 1000)
    return response


@router.post("/vision/identify/{image_id}", response_model=VisionIdentifyResponse)
def identify_by_id(image_id: str, session: SessionDep) -> VisionIdentifyResponse:
    response = vision_service.identify(session, _resolve_image(image_id))
    VISION_LATENCY.observe(response.latency_ms / 1000)
    return response


@router.post("/vision/similar", response_model=SimilarImageResponse)
async def similar(
    session: SessionDep,
    file: UploadFile | None = File(default=None),
    image_id: str | None = Form(default=None),
    top_k: int = Form(default=5),
) -> SimilarImageResponse:
    if file is not None:
        upload_response = await store_upload(file, None, session)
        path = _resolve_image(upload_response.image_id)
    elif image_id:
        path = _resolve_image(image_id)
    else:
        raise HTTPException(status_code=400, detail="Provide a file or an image_id.")
    return vision_service.similar(session, path, top_k=top_k)


@router.post("/vision/evaluate", response_model=VisionEvaluateResponse)
def evaluate(session: SessionDep) -> VisionEvaluateResponse:
    return VisionEvaluateResponse(**vision_service.evaluate_holdout(session))
