from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from starlette.responses import RedirectResponse

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.db.session import init_models


def create_app() -> FastAPI:
    settings = get_settings()
    
    # [설정 확인] 시작 시 root_path가 잘 들어갔는지 로그로 확인
    print(f"[Info] App starting with root_path='{settings.root_path}'")

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        # .env의 ROOT_PATH나 실행 인자 --root-path 값이 여기로 들어옵니다.
        root_path=settings.root_path or "",
        docs_url=None,    # 기본 문서 경로 비활성화 (커스텀 핸들러 사용)
        openapi_url=None, # 기본 openapi.json 비활성화
    )

    # [CORS 설정]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # 보안 강화 시 구체적인 도메인으로 변경 권장
        allow_origin_regex=".*",
        allow_credentials=True, # 쿠키/인증 헤더 사용 시 True 권장
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # [라우터 연결]
    app.include_router(api_router)

    # ---------------------------------------------------------
    # [문서 관련 커스텀 핸들러]
    # root_path 설정에 따라 동적으로 경로를 생성합니다.
    # ---------------------------------------------------------

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_plain():
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    async def docs_plain():
        # 기본 openapi 경로
        openapi_url = "/openapi.json"
        
        # 만약 root_path(/proxy/8001)가 설정되어 있다면, 브라우저에게
        # "/proxy/8001/openapi.json"을 찾아가라고 알려줍니다.
        if app.root_path:
            # 슬래시 중복 방지 처리
            root = app.root_path.rstrip("/")
            openapi_url = f"{root}{openapi_url}"
            
        return get_swagger_ui_html(openapi_url=openapi_url, title=f"{app.title} - Docs")

    # 루트(/) 접속 시 문서(/docs)로 리다이렉트
    @app.get("/", include_in_schema=False)
    async def index_redirect():
        # 리다이렉트 주소도 root_path를 고려해야 합니다.
        target_url = "/docs"
        if app.root_path:
             root = app.root_path.rstrip("/")
             target_url = f"{root}/docs"
             
        return RedirectResponse(url=target_url)

    @app.on_event("startup")
    async def startup_event():
        await init_models()

    return app


app = create_app()
