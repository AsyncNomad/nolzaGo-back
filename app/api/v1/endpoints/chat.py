import json
from typing import Dict, Set
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.chat import ChatMessage
from app.models.chat_read import ChatRead
from app.models.post import Post
from app.models.user import User
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
        self.join_announced: Dict[tuple[UUID, UUID], bool] = {}  # (post_id, user_id) -> announced
        self.system_messages: Dict[UUID, list[dict]] = {}  # post_id -> list of system messages

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


async def _ensure_read_row(db: AsyncSession, post_id: UUID, user_id: UUID) -> ChatRead:
    res = await db.execute(select(ChatRead).where(ChatRead.post_id == post_id, ChatRead.user_id == user_id))
    row = res.scalar_one_or_none()
    if not row:
        row = ChatRead(post_id=post_id, user_id=user_id, unread_count=0, last_read_at=None)
        db.add(row)
    return row


async def _mark_read(db: AsyncSession, post_id: UUID, user_id: UUID, read_time=None):
    row = await _ensure_read_row(db, post_id, user_id)
    if read_time:
        row.last_read_at = read_time.replace(tzinfo=None) if read_time.tzinfo else read_time
    row.unread_count = 0
    db.add(row)


async def _bump_unread(db: AsyncSession, post: Post, sender_id: UUID, created_at):
    user_ids = {sender_id, post.owner_id}
    user_ids.update([p.id for p in post.participants])
    ts = created_at.replace(tzinfo=None) if created_at and created_at.tzinfo else created_at
    for uid in user_ids:
        row = await _ensure_read_row(db, post.id, uid)
        if uid == sender_id:
            row.last_read_at = ts
            row.unread_count = 0
        else:
            row.unread_count = (row.unread_count or 0) + 1
        db.add(row)


def _out_message(m: ChatMessage) -> ChatMessageOut:
    created = m.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return ChatMessageOut(
        id=m.id,
        content=m.content,
        post_id=m.post_id,
        user_id=m.user_id,
        user=m.user,
        user_display_name=getattr(m.user, "display_name", None),
        user_profile_image_url=getattr(m.user, "profile_image_url", None),
        created_at=created,
    )


@router.get("/messages", response_model=list[ChatMessageOut])
async def list_messages(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    await _get_post(db, post_id)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.post_id == post_id)
        .options(selectinload(ChatMessage.user))
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    messages = result.scalars().all()
    # mark as read
    last_ts = messages[-1].created_at if messages else None
    if last_ts and last_ts.tzinfo:
        last_ts = last_ts.replace(tzinfo=None)
    if current_user:
        row = await _ensure_read_row(db, post_id, current_user.id)
        if last_ts:
            row.last_read_at = last_ts
        row.unread_count = 0
        db.add(row)
        await db.commit()
    return [_out_message(m) for m in messages]


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
    await _bump_unread(db, post, current_user.id, message.created_at)
    await db.commit()
    return _out_message(message)


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

        # 미리 사용자 정보 로드해 lazy-load를 피한다.
        user_row = await db.execute(select(User).where(User.id == user_uuid))
        user_obj = user_row.scalar_one_or_none()
        user_display_name = user_obj.display_name if user_obj else None
        user_profile_image_url = user_obj.profile_image_url if user_obj else None
        # 이미 입장 안내가 저장돼 있는지 확인(재접속 시 중복 방지)
        existing_join = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.post_id == post_id,
                ChatMessage.user_id == user_uuid,
                ChatMessage.content.ilike('%입장하셨습니다%'),
            )
            .order_by(ChatMessage.created_at.asc())
        )
        if existing_join.scalar_one_or_none():
            manager.join_announced[(post_id, user_uuid)] = True

        # 입장 시 기존 메시지 전달
        history_q = (
            select(ChatMessage)
            .where(ChatMessage.post_id == post_id)
            .options(selectinload(ChatMessage.user))
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        history_res = await db.execute(history_q)
        history_msgs = []
        for msg in history_res.scalars().all():
            created = msg.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            is_system = "입장하셨습니다" in (msg.content or "")
            history_msgs.append(
                {
                    "userId": None if is_system else str(msg.user_id),
                    "userDisplayName": None if is_system else getattr(msg.user, "display_name", None),
                    "userProfileImageUrl": None if is_system else getattr(msg.user, "profile_image_url", None),
                    "content": msg.content,
                    "createdAt": (created or msg.created_at).isoformat(),
                    "system": is_system,
                    "type": "system" if is_system else "chat",
                }
            )

        merged_msgs = history_msgs
        merged_msgs.sort(key=lambda m: m.get("createdAt", ""))

        await manager.connect(post_id, websocket)
        # 히스토리를 먼저 전송
        if merged_msgs:
            await websocket.send_text(json.dumps({"type": "history", "messages": merged_msgs}))
        # 입장 알림
        join_key = (post_id, user_uuid)
        if not manager.join_announced.get(join_key):
            manager.join_announced[join_key] = True
            now_iso = datetime.now(timezone.utc).isoformat()
            join_notice = {
                "type": "system",
                "content": f"{user_display_name or '참여자'}님이 입장하셨습니다",
                "createdAt": now_iso,
                "userId": None,
                "userDisplayName": None,
                "userProfileImageUrl": None,
            }
            # DB에 기록해 재접속해도 동일 위치에 남도록 함
            db_join = ChatMessage(content=join_notice["content"], post_id=post.id, user_id=user_uuid)
            db.add(db_join)
            await db.commit()
            await db.refresh(db_join)
            created_join = db_join.created_at
            if created_join and created_join.tzinfo is None:
                created_join = created_join.replace(tzinfo=timezone.utc)
            join_notice["createdAt"] = (created_join or db_join.created_at).isoformat()
            # 새 입장 알림 브로드캐스트
            await manager.broadcast(post_id, join_notice)

        try:
            while True:
                data = await websocket.receive_text()
                message = ChatMessage(content=data, post_id=post_id, user_id=user_uuid)
                db.add(message)
                await db.commit()
                await db.refresh(message)
                await _bump_unread(db, post, user_uuid, message.created_at)
                await db.commit()
                created = message.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                payload = {
                    "userId": str(user_uuid),
                    "userDisplayName": user_display_name,
                    "userProfileImageUrl": user_profile_image_url,
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
    # 최신 메시지 80개까지만 취하되, 프롬프트는 시간 순서(오래된 → 최신)로 정렬
    contents = list(reversed([m.content for m in messages][:80]))
    summary = await summarizer.summarize(contents, question=question)
    return {
        "post_id": str(post.id),
        "summary": summary,
        "messages_count": len(messages),
    }
