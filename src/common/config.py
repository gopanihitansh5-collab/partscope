"""Runtime configuration.

Provider-neutral by design: the same code runs against a local SQLite file in
development and PostgreSQL (with pgvector) in a deployed environment. Nothing
here requires a cloud service.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Industrial Parts Intelligence Platform"
    app_env: str = "development"
    app_log_level: str = "INFO"
    app_version: str = "0.1.0"

    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"
    cors_origins: str = "http://localhost:3000"

    data_dir: str = str(REPO_ROOT / "data")
    artifact_dir: str = str(REPO_ROOT / "artifacts")
    upload_dir: str = str(REPO_ROOT / "uploads")

    vision_image_size: int = 64
    vision_top_k: int = 5

    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.08

    forecast_horizon_days: int = 30

    max_upload_bytes: int = 8 * 1024 * 1024
    allowed_image_types: str = "image/png,image/jpeg,image/webp"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_image_type_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def artifact_path(self) -> Path:
        return Path(self.artifact_dir)

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    def ensure_dirs(self) -> None:
        for path in (self.data_path, self.artifact_path, self.upload_path):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
