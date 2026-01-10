from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.models.memory import MemoryPost
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/", response_model=list[MemoryOut])
async def list_memories(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(MemoryPost).options(selectinload(MemoryPost.owner)))
    memories = result.scalars().all()
    return memories


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
    return memory


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(memory_id: UUID, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(MemoryPost).where(MemoryPost.id == memory_id).options(selectinload(MemoryPost.owner)))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
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
