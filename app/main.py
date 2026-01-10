from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.db.session import init_models


def create_app() -> FastAPI:
    settings = get_settings()
    # Debug print to verify CORS/root_path settings at startup
    print(f"[settings] root_path={settings.root_path} allowed_hosts={settings.allowed_hosts}")
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        root_path=settings.root_path or "",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex=".*",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.on_event("startup")
    async def startup_event():
        await init_models()

    return app


app = create_app()
