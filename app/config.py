import os
from dataclasses import dataclass, field
from functools import lru_cache


def _csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [v.strip() for v in raw.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    app_base_url: str = field(default_factory=lambda: os.getenv("APP_BASE_URL", "http://localhost:8000"))
    session_secret: str = field(default_factory=lambda: os.getenv("SESSION_SECRET", ""))

    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_AUTH_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_AUTH_CLIENT_SECRET", ""))
    google_redirect_url: str = field(default_factory=lambda: os.getenv("GOOGLE_AUTH_REDIRECT_URL", ""))
    google_discovery_url: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_DISCOVERY_URL",
            "https://accounts.google.com/.well-known/openid-configuration",
        )
    )

    allowed_email_domains: list[str] = field(default_factory=lambda: _csv("ALLOWED_EMAIL_DOMAINS"))

    node_exporter_port: int = field(default_factory=lambda: int(os.getenv("NODE_EXPORTER_PORT", "9100")))
    discovery_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("DISCOVERY_TIMEOUT_SECONDS", "5")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    if not s.session_secret:
        raise RuntimeError("SESSION_SECRET is required")
    return s
