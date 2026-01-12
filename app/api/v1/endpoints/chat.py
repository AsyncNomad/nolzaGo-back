import json
from typing import Dict, Set
from uuid import UUID
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.chat import ChatMessage
from app.models.post import Post
from app.schemas.chat import ChatMessageCreate, ChatMessageOut
from app.services import get_gemini_summarizer

router = APIRouter(prefix="/posts/{post_id}/chat", tags=["chat"])


async def _get_post(db: AsyncSession, post_id: UUID) -> Post:
    result = await db.execute(select(Post).where(Post.id == post_id).options(selectinload(Post.participants)))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def _ensure_membership(db: AsyncSession, post: Post, user_id: UUID) -> None:
    if post.owner_id == user_id:
        return
    if not any(p.id == user_id for p in post.participants):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join the post before chatting")


class ChatRoomManager:
    def __init__(self):
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}

    async def connect(self, post_id: UUID, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(post_id, set()).add(websocket)

    def disconnect(self, post_id: UUID, websocket: WebSocket):
        if post_id in self.active_connections:
            self.active_connections[post_id].discard(websocket)
            if not self.active_connections[post_id]:
                self.active_connections.pop(post_id, None)

    async def broadcast(self, post_id: UUID, message: dict):
        for connection in self.active_connections.get(post_id, set()):
            await connection.send_text(json.dumps(message))


manager = ChatRoomManager()


@router.get("/messages", response_model=list[ChatMessageOut])
async def list_messages(post_id: UUID, db: AsyncSession = Depends(get_async_db)):
    await _get_post(db, post_id)
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.post_id == post_id).options(selectinload(ChatMessage.user))
    )
    messages = result.scalars().all()
    for m in messages:
        if m.created_at and m.created_at.tzinfo is None:
            m.created_at = m.created_at.replace(tzinfo=timezone.utc)
        if m.user:
            m.user_display_name = m.user.display_name
            m.user_profile_image_url = m.user.profile_image_url
    return messages


@router.post("/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    post_id: UUID,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    post = await _get_post(db, post_id)
    await _ensure_membership(db, post, current_user.id)
    message = ChatMessage(content=payload.content, post_id=post_id, user_id=current_user.id)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    if message.created_at and message.created_at.tzinfo is None:
        message.created_at = message.created_at.replace(tzinfo=timezone.utc)
    message.user_display_name = current_user.display_name
    message.user_profile_image_url = current_user.profile_image_url
    return message


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket, post_id: UUID):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id_str = decode_token(token)
    if not user_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with SessionLocal() as db:
        post = await _get_post(db, post_id)
        try:
            user_uuid = UUID(user_id_str)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        await _ensure_membership(db, post, user_uuid)

        await manager.connect(post_id, websocket)

        try:
            while True:
                data = await websocket.receive_text()
                message = ChatMessage(content=data, post_id=post_id, user_id=user_uuid)
                db.add(message)
                await db.commit()
                await db.refresh(message)
                created = message.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                payload = {
                    "userId": str(user_uuid),
                    "userDisplayName": message.user.display_name if message.user else None,
                    "userProfileImageUrl": message.user.profile_image_url if message.user else None,
                    "content": message.content,
                    "createdAt": (created or message.created_at).isoformat(),
                }
                await manager.broadcast(post_id, payload)
        except WebSocketDisconnect:
            manager.disconnect(post_id, websocket)


@router.get("/summary")
async def chat_summary(post_id: UUID, question: str | None = None, db: AsyncSession = Depends(get_async_db)):
    """
    Gemini API를 사용해 최근 채팅을 3줄로 요약합니다.
    키가 없거나 오류 시 기본 문구를 반환합니다. 선택적으로 질문을 넣으면 함께 전달됩니다.
    """
    post = await _get_post(db, post_id)
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.post_id == post_id).order_by(ChatMessage.created_at.desc())
    )
    messages = result.scalars().all()
    summarizer = get_gemini_summarizer()
    summary = await summarizer.summarize([m.content for m in messages], question=question)
    return {
        "post_id": str(post.id),
        "summary": summary,
        "messages_count": len(messages),
    }
