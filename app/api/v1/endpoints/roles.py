import json
import random
from typing import Dict, Set
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_async_db, get_current_user
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.post import Post
from app.models.role import RoleAssignment, RoleChatMessage, ROLE_CHOICES
from app.models.user import User
from app.schemas.role import RoleAssignRequest, RoleAssignmentOut, RoleChatMessageOut

router = APIRouter(prefix="/posts/{post_id}/roles", tags=["roles"])


async def _get_post(db: AsyncSession, post_id: UUID) -> Post:
    result = await db.execute(select(Post).where(Post.id == post_id).options(selectinload(Post.participants)))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


class RoleChatManager:
    def __init__(self):
        self.connections: Dict[tuple[UUID, str], Set[WebSocket]] = {}

    async def connect(self, key: tuple[UUID, str], ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(key, set()).add(ws)

    def disconnect(self, key: tuple[UUID, str], ws: WebSocket):
        if key in self.connections:
            self.connections[key].discard(ws)
            if not self.connections[key]:
                self.connections.pop(key, None)

    async def broadcast(self, key: tuple[UUID, str], message: dict):
        for c in self.connections.get(key, set()):
            await c.send_text(json.dumps(message))


manager = RoleChatManager()


@router.post("/assign", response_model=list[RoleAssignmentOut])
async def assign_roles(
    post_id: UUID,
    payload: RoleAssignRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    post = await _get_post(db, post_id)
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can assign roles")
    candidates = [post.owner, *(post.participants or [])]
    unique_candidates = []
    seen = set()
    for c in candidates:
        if c.id not in seen:
            unique_candidates.append(c)
            seen.add(c.id)
    total_need = max(0, payload.police) + max(0, payload.thief)
    if total_need > len(unique_candidates):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인원이 부족합니다.")
    random.shuffle(unique_candidates)
    selected = unique_candidates[:total_need]
    new_rows = []
    # 기존 배정 및 역할 채팅 삭제
    await db.execute(delete(RoleAssignment).where(RoleAssignment.post_id == post_id))
    await db.execute(delete(RoleChatMessage).where(RoleChatMessage.post_id == post_id))
    idx = 0
    for _ in range(max(0, payload.police)):
        user = selected[idx]
        new_rows.append(RoleAssignment(post_id=post_id, user_id=user.id, role="police"))
        idx += 1
    for _ in range(max(0, payload.thief)):
        user = selected[idx]
        new_rows.append(RoleAssignment(post_id=post_id, user_id=user.id, role="thief"))
        idx += 1
    db.add_all(new_rows)
    await db.commit()
    # reload for response
    res = await db.execute(
        select(RoleAssignment, User)
            .join(User, User.id == RoleAssignment.user_id)
            .where(RoleAssignment.post_id == post_id)
    )
    rows = []
    for ra, u in res.all():
        ra.user_display_name = u.display_name
        ra.user_profile_image_url = u.profile_image_url
        rows.append(ra)
    return rows


@router.get("/me")
async def my_role(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    res = await db.execute(
        select(RoleAssignment, User)
        .join(User, User.id == RoleAssignment.user_id)
        .where(RoleAssignment.post_id == post_id, RoleAssignment.user_id == current_user.id)
    )
    row = res.first()
    if not row:
        return {"role": None}
    ra, u = row
    return {
        "role": ra.role if ra else None,
        "user_display_name": u.display_name if u else None,
        "user_profile_image_url": u.profile_image_url if u else None,
    }


@router.get("", response_model=list[RoleAssignmentOut])
async def list_roles(post_id: UUID, db: AsyncSession = Depends(get_async_db), current_user=Depends(get_current_user)):
    # 모든 참여자/시청자가 배정 결과를 볼 수 있도록 소유자 제한 해제
    res = await db.execute(
        select(RoleAssignment, User).join(User, User.id == RoleAssignment.user_id).where(RoleAssignment.post_id == post_id)
    )
    rows = []
    for ra, u in res.all():
        ra.user_display_name = u.display_name
        ra.user_profile_image_url = u.profile_image_url
        rows.append(ra)
    return rows


from pydantic import BaseModel


class CaptureRequest(BaseModel):
    user_id: UUID
    captured: bool


@router.post("/capture", response_model=RoleAssignmentOut)
async def toggle_capture(
    post_id: UUID,
    payload: CaptureRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    if isinstance(payload, dict):
        payload = CaptureRequest(**payload)
    # 경찰만 토글 가능
    res_role = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.post_id == post_id, RoleAssignment.user_id == current_user.id, RoleAssignment.role == "police"
        )
    )
    if not res_role.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="경찰만 체크할 수 있습니다.")

    res_target = await db.execute(
        select(RoleAssignment, User)
        .join(User, User.id == RoleAssignment.user_id)
        .where(RoleAssignment.post_id == post_id, RoleAssignment.user_id == payload.user_id)
    )
    row = res_target.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대상을 찾을 수 없습니다.")
    ra, u = row
    ra.is_captured = payload.captured
    await db.commit()
    await db.refresh(ra)
    ra.user_display_name = u.display_name
    ra.user_profile_image_url = u.profile_image_url

    # 실시간 알림: 경찰/도둑 채널 모두에 전송
    now = datetime.now(timezone.utc)
    content = (
        f"{u.display_name or '참여자'}님이 경찰에게 잡혔어요."
        if payload.captured
        else f"{u.display_name or '참여자'}님이 경찰로부터 풀려났어요."
    )
    broadcast_msg = {"type": "system", "content": content, "createdAt": now.isoformat()}
    await manager.broadcast((post_id, "police"), broadcast_msg)
    await manager.broadcast((post_id, "thief"), broadcast_msg)

    # 모든 도둑이 잡힌 경우 Game Over 안내
    if payload.captured:
        thief_res = await db.execute(
            select(RoleAssignment).where(RoleAssignment.post_id == post_id, RoleAssignment.role == "thief")
        )
        thieves = thief_res.scalars().all()
        if thieves and all(t.is_captured for t in thieves):
            game_over = {"type": "system", "content": "Game Over! 경찰이 승리했습니다.", "createdAt": now.isoformat()}
            await manager.broadcast((post_id, "police"), game_over)
            await manager.broadcast((post_id, "thief"), game_over)

    return ra


@router.websocket("/chat/ws")
async def role_chat_ws(websocket: WebSocket, post_id: UUID, role: str):
    if role not in ROLE_CHOICES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id_str = decode_token(token)
    if not user_id_str:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    key = (post_id, role)
    async with SessionLocal() as db:
        try:
            user_uuid = UUID(user_id_str)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        # 배정 확인
        res = await db.execute(
            select(RoleAssignment).where(
                RoleAssignment.post_id == post_id, RoleAssignment.user_id == user_uuid, RoleAssignment.role == role
            )
        )
        if not res.scalar_one_or_none():
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 히스토리
        hist_res = await db.execute(
            select(RoleChatMessage, User)
            .join(User, User.id == RoleChatMessage.user_id)
            .where(RoleChatMessage.post_id == post_id, RoleChatMessage.role == role)
            .order_by(RoleChatMessage.created_at.asc(), RoleChatMessage.id.asc())
        )
        history = []
        for msg, u in hist_res.all():
            created = msg.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            history.append(
                {
                    "userId": str(msg.user_id),
                    "userDisplayName": u.display_name if u else None,
                    "userProfileImageUrl": u.profile_image_url if u else None,
                    "content": msg.content,
                    "role": msg.role,
                    "createdAt": (created or msg.created_at).isoformat(),
                }
            )

        await manager.connect(key, websocket)
        if history:
            await websocket.send_text(json.dumps({"type": "history", "messages": history}))

        try:
            while True:
                data = await websocket.receive_text()
                msg = RoleChatMessage(post_id=post_id, user_id=user_uuid, role=role, content=data)
                db.add(msg)
                await db.commit()
                await db.refresh(msg)
                user_obj = await db.get(User, user_uuid)
                created = msg.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                payload = {
                    "userId": str(user_uuid),
                    "userDisplayName": user_obj.display_name if user_obj else None,
                    "userProfileImageUrl": user_obj.profile_image_url if user_obj else None,
                    "content": msg.content,
                    "role": role,
                    "createdAt": (created or msg.created_at).isoformat(),
                }
                await manager.broadcast(key, payload)
        except WebSocketDisconnect:
            manager.disconnect(key, websocket)
