from uuid import UUID
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.core.config import get_settings
from app.models.memory import MemoryPost
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])


def _normalize_url(raw_url: str | None) -> str | None:
    """
    만료된 presigned URL을 표준 버킷 URL로 변환해 썸네일이 깨지지 않도록 함.
    """
    if not raw_url:
        return None
    if "X-Amz-Signature" not in raw_url and "X-Amz-SignedHeaders" not in raw_url:
        return raw_url
    settings = get_settings()
    if not all([settings.aws_bucket, settings.aws_region]):
        return raw_url
    parsed = urlparse(raw_url)
    key = parsed.path.lstrip("/")
    if not key:
        return raw_url
    return f"https://{settings.aws_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


# Accept both with and without trailing slash to avoid 307 redirects
@router.get("", response_model=list[MemoryOut], include_in_schema=False)
@router.get("/", response_model=list[MemoryOut])
async def list_memories(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(MemoryPost).options(selectinload(MemoryPost.owner)))
    memories = result.scalars().all()
    for m in memories:
        m.image_url = _normalize_url(m.image_url)
    return memories


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)
):
    memory = MemoryPost(
        title=payload.title,
        content=payload.content,
        image_url=payload.image_url,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        owner_id=current_user.id,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    memory.image_url = _normalize_url(memory.image_url)
    return memory


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(memory_id: UUID, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(MemoryPost).where(MemoryPost.id == memory_id).options(selectinload(MemoryPost.owner)))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    memory.image_url = _normalize_url(memory.image_url)
    return memory


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(MemoryPost).where(MemoryPost.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if memory.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can edit this memory")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(memory, field, value)

    await db.commit()
    await db.refresh(memory)
    return memory


@router.post("/{memory_id}/like", response_model=MemoryOut)
async def like_memory(memory_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(MemoryPost).where(MemoryPost.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    memory.like_count += 1
    await db.commit()
    await db.refresh(memory)
    return memory
