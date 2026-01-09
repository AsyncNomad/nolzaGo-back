# nolzaGo backend (FastAPI + PostgreSQL)

동네 인증 기반 놀이 서비스 **놀자Go** 백엔드 초안입니다. FastAPI와 PostgreSQL(Async SQLAlchemy)로 구성되어 있으며, 카카오 소셜 로그인(서버 검증), 단체 채팅(WebSocket), 카카오맵 연동, Gemini 요약을 포함합니다.

## 주요 기능 스케치
- 인증: 이메일/비밀번호 가입(확인 포함) 및 JWT 발급, 카카오 액세스 토큰 서버 검증 로그인.
- 홈: 놀이 모집 글 작성/조회/수정, 참가/탈퇴, 현재 참가 인원·위치(위도/경도) 포함.
- 채팅: 모집글별 메시지 REST/WebSocket 브로드캐스트, 늦은 참가자를 위한 Gemini 요약 엔드포인트.
- 사용자 능력치/동네 정보: 러닝 속도·체력, 위치명 필드 포함.

## 빠른 시작
1) 의존성 설치
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2) 환경 변수 설정: `.env.example`를 `.env`로 복사 후 값 수정
```bash
cp .env.example .env
```
필드:
- `NOLZAGO_KAKAO_REST_API_KEY`: 카카오 REST API 키(서버 검증 시 사용 예정)
- `NOLZAGO_KAKAO_MAP_REST_API_KEY`: 카카오맵 REST API 키(지도/지오코딩)
- `NOLZAGO_GEMINI_API_KEY`: Gemini 요약용 API 키(없으면 기본 안내 문구 반환)
3) 서버 실행
```bash
uvicorn app.main:app --reload
```

## API 개요
- `GET /api/v1/health` 헬스체크
- 인증
  - `POST /api/v1/auth/signup` 이메일 가입(비밀번호 확인 포함)
  - `POST /api/v1/auth/token` 이메일 로그인(OAuth2 password flow)
  - `POST /api/v1/auth/kakao` 카카오 로그인(액세스 토큰 서버 검증)
- 모집글
  - `GET /api/v1/posts` 모집글 목록
  - `POST /api/v1/posts` 모집글 작성(인증 필요)
  - `GET /api/v1/posts/{id}` 모집글 상세
  - `PATCH /api/v1/posts/{id}` 모집글 수정(작성자만)
  - `POST /api/v1/posts/{id}/join` 모집글 참가
  - `POST /api/v1/posts/{id}/leave` 모집글 참가 취소(참여자용)
- 채팅
  - `GET /api/v1/posts/{id}/chat/messages` 메시지 조회
  - `POST /api/v1/posts/{id}/chat/messages` 메시지 작성(참여자만)
  - `GET /api/v1/posts/{id}/chat/summary` Gemini 기반 3줄 요약(키 없으면 기본 문구, `question` 쿼리로 질문 동시 전달 가능)
  - `WS /api/v1/posts/{id}/chat/ws?token=JWT` 단체 채팅방 WebSocket. `POST /posts/{id}/join` 이후 JWT로 연결하면 브로드캐스트·DB 저장. 클라이언트가 연결 종료 시 방 나가기.
- 지도
  - `GET /api/v1/maps/geocode?query=주소` 카카오맵 REST API로 좌표 조회

## 데이터베이스
- Async SQLAlchemy + `asyncpg` 사용.
- 앱 시작 시 `Base.metadata.create_all`로 테이블을 생성합니다. 추후 마이그레이션은 Alembic을 붙이면 됩니다.

## TODO LIST
- 카카오 프로필 동기화/에러 로깅 강화, 토큰 만료 처리 보강.
- 위치 인증(좌표/행정동) 모델링 및 검증 로직 구현.
- 채팅 권한/메시지 포맷 보강, WebSocket 부하 제어·레이트 리미트.
- 테스트 코드(Pytest) 및 Alembic 마이그레이션 도입.
