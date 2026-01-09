from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import AuthProvider, User
from app.schemas.auth import Token
from app.schemas.user import KakaoUserCreate, UserCreate, UserOut
from app.services.kakao_auth import KakaoOAuthClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, db: AsyncSession = Depends(get_async_db)):
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        display_name=payload.display_name,
        phone_number=payload.phone_number,
        location_name=payload.location_name,
        run_speed=payload.run_speed,
        stamina=payload.stamina,
        provider=AuthProvider.local,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_db)
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/kakao", response_model=Token)
async def kakao_login(payload: KakaoUserCreate, db: AsyncSession = Depends(get_async_db)):
    """
    카카오 액세스 토큰을 서버에서 검증한 뒤 사용자 생성/로그인.
    """
    kakao_client = KakaoOAuthClient()
    kakao_profile = await kakao_client.verify_access_token(payload.access_token)
    if not kakao_profile:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Kakao token")

    kakao_id = str(kakao_profile["id"])
    kakao_email = payload.email or kakao_profile.get("kakao_account", {}).get("email")
    kakao_nickname = payload.display_name or kakao_profile.get("properties", {}).get("nickname") or "놀자Go 사용자"

    result = await db.execute(
        select(User).where(User.provider == AuthProvider.kakao, User.provider_account_id == kakao_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=kakao_email,
            provider=AuthProvider.kakao,
            provider_account_id=kakao_id,
            display_name=kakao_nickname,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}
