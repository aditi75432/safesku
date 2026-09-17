from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="SafeSKU API",
    version="0.1.0",
    description="Evidence-grounded product safety intelligence API.",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
    }
