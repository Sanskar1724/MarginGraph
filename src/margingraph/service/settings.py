"""Process settings, read once from environment variables.

Everything a deployment changes lives here, so the same image runs on a laptop
(SQLite, in-memory cache) and on a hosted stack (Postgres, Redis).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    database_url: str = "sqlite:///data/margingraph.db"
    redis_url: str = ""
    artifacts_dir: str = "artifacts"
    config_path: str = "configs/default.yaml"
    admin_key: str = ""
    # how long an instance trusts its cached catalog / model version before re-checking
    version_ttl_s: float = 5.0
    response_cache_ttl_s: int = 300
    max_loaded_models: int = 4
    log_requests: bool = True
    preload_models: bool = True
    dashboard_url: str = ""
    dashboard_token: str = ""
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    @property
    def is_production(self) -> bool:
        return self.env == "production"


DEV_ADMIN_KEY = "dev-admin-key"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    e = os.environ.get
    env = e("MARGINGRAPH_ENV", "development")
    admin = e("MARGINGRAPH_ADMIN_KEY", "")
    if not admin:
        if env == "production":
            raise RuntimeError("MARGINGRAPH_ADMIN_KEY must be set when MARGINGRAPH_ENV=production")
        admin = DEV_ADMIN_KEY
    return Settings(
        env=env,
        database_url=e("DATABASE_URL", "sqlite:///data/margingraph.db"),
        redis_url=e("REDIS_URL", ""),
        artifacts_dir=e("MARGINGRAPH_ARTIFACTS", "artifacts"),
        config_path=e("MARGINGRAPH_CONFIG", "configs/default.yaml"),
        admin_key=admin,
        version_ttl_s=float(e("MARGINGRAPH_VERSION_TTL_S", "5")),
        response_cache_ttl_s=int(e("MARGINGRAPH_RESPONSE_CACHE_TTL_S", "300")),
        max_loaded_models=int(e("MARGINGRAPH_MAX_LOADED_MODELS", "4")),
        log_requests=_bool(e("MARGINGRAPH_LOG_REQUESTS"), True),
        preload_models=_bool(e("MARGINGRAPH_PRELOAD"), True),
        dashboard_url=e("MARGINGRAPH_DASHBOARD_URL", ""),
        dashboard_token=e("MARGINGRAPH_DASHBOARD_TOKEN", ""),
        cors_origins=[o.strip() for o in e("MARGINGRAPH_CORS_ORIGINS", "*").split(",") if o.strip()],
    )
