from uuid import UUID
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.core.config import get_settings
from app.models.post import Post
from app.schemas.post import PostCreate, PostOut, PostUpdate
from app.models.associations import post_likes

router = APIRouter(prefix="/posts", tags=["posts"])


def _normalized_image_url(raw_url: str | None) -> str | None:
    """
    - If the URL has a (possibly expired) presign query, rebuild a plain object URL using current bucket/region.
    - Otherwise return as-is.
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


def _to_out(post: Post, is_liked: bool = False) -> PostOut:
    return PostOut(
        id=post.id,
        created_at=post.created_at,
        title=post.title,
        game_type=post.game_type,
        description=post.description,
        location_name=post.location_name,
        latitude=post.latitude,
        longitude=post.longitude,
        max_participants=post.max_participants,
        status=post.status,
        start_time=post.start_time,
        owner_id=post.owner_id,
        participants_count=len(post.participants or []),
        owner=post.owner,
        like_count=post.like_count,
        is_liked=is_liked,
        image_url=_normalized_image_url(post.image_url),
    )


@router.get("", response_model=list[PostOut])
async def list_posts(db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(Post).options(selectinload(Post.participants), selectinload(Post.owner)))
    posts = result.scalars().unique().all()
    liked_ids: set[UUID] = set()
    if posts:
        post_ids = [p.id for p in posts]
        liked_rows = await db.execute(select(post_likes.c.post_id).where(post_likes.c.user_id == current_user.id, post_likes.c.post_id.in_(post_ids)))
        liked_ids = set(liked_rows.scalars().all())
    return [_to_out(post, post.id in liked_ids) for post in posts]


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)
):
    post = Post(
        title=payload.title,
        description=payload.description,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        game_type=payload.game_type,
        max_participants=payload.max_participants,
        start_time=payload.start_time,
        owner_id=current_user.id,
        like_count=payload.like_count or 0,
        status=payload.status or "모집 중",
        image_url=payload.image_url,
    )
    db.add(post)
    await db.commit()
    # reload with relationships to avoid lazy load on response
    result = await db.execute(
        select(Post)
        .where(Post.id == post.id)
        .options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post_loaded = result.scalar_one()
    return _to_out(post_loaded, is_liked=False)


@router.post("/{post_id}/leave", response_model=PostOut)
async def leave_post(
    post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if current_user == post.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="작성자는 나갈 수 없습니다")
    if current_user not in post.participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="참여 중이 아닙니다")

    post.participants.remove(current_user)
    await db.commit()
    await db.refresh(post)

    return PostOut(
        id=post.id,
        created_at=post.created_at,
        title=post.title,
        game_type=post.game_type,
        description=post.description,
        location_name=post.location_name,
        latitude=post.latitude,
        longitude=post.longitude,
        max_participants=post.max_participants,
        status=post.status,
        start_time=post.start_time,
        owner_id=post.owner_id,
        participants_count=len(post.participants),
        owner=post.owner,
        like_count=post.like_count,
    )

@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    liked = False
    if current_user:
        liked_row = await db.execute(
            select(post_likes.c.post_id).where(
                post_likes.c.post_id == post_id,
                post_likes.c.user_id == current_user.id,
            )
        )
        liked = liked_row.scalar_one_or_none() is not None
    return _to_out(post, is_liked=liked)


@router.patch("/{post_id}", response_model=PostOut)
async def update_post(
    post_id: UUID,
    payload: PostUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can edit this post")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post)
    return _to_out(post, is_liked=False)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only author can delete this post")
    await db.delete(post)
    await db.commit()
    return None


@router.post("/{post_id}/join", response_model=PostOut)
async def join_post(
    post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if current_user in post.participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already joined")

    if len(post.participants) >= post.max_participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group is full")

    post.participants.append(current_user)
    await db.commit()
    await db.refresh(post)

    return PostOut(
        id=post.id,
        created_at=post.created_at,
        title=post.title,
        game_type=post.game_type,
        description=post.description,
        location_name=post.location_name,
        latitude=post.latitude,
        longitude=post.longitude,
        max_participants=post.max_participants,
        status=post.status,
        start_time=post.start_time,
        owner_id=post.owner_id,
        participants_count=len(post.participants),
        owner=post.owner,
        like_count=post.like_count,
    )


@router.post("/{post_id}/like", response_model=PostOut)
async def like_post(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.participants), selectinload(Post.owner))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    like_exists = await db.execute(
        select(post_likes.c.user_id).where(
            post_likes.c.post_id == post_id,
            post_likes.c.user_id == current_user.id,
        )
    )
    liked = like_exists.scalar_one_or_none() is not None

    if liked:
        await db.execute(
            delete(post_likes).where(
                post_likes.c.post_id == post_id,
                post_likes.c.user_id == current_user.id,
            )
        )
        post.like_count = max(0, (post.like_count or 0) - 1)
    else:
        await db.execute(insert(post_likes).values(post_id=post_id, user_id=current_user.id))
        post.like_count = (post.like_count or 0) + 1

    await db.commit()
    await db.refresh(post)

    return _to_out(post, is_liked=not liked)
