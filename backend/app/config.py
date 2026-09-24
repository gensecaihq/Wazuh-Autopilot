"""Process-level configuration from environment variables.

Runtime-editable settings (Wazuh connection, model provider, policy, ...) live in
the database and are managed from the UI; the values here only seed them on
first boot.
"""

import os
import secrets
from functools import lru_cache
from pathlib import Path

VERSION = "3.0.0"


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("AUTOPILOT_DATA_DIR", "/data"))
        self.database_url = os.getenv("DATABASE_URL") or f"sqlite:///{self.data_dir / 'autopilot.db'}"
        self.secret_key = os.getenv("AUTOPILOT_SECRET_KEY") or self._persistent_secret()
        self.token_ttl_minutes = int(os.getenv("AUTOPILOT_TOKEN_TTL_MINUTES", "720"))
        self.demo_mode = _bool("AUTOPILOT_DEMO_MODE")
        self.seed_history = _bool("AUTOPILOT_SEED_HISTORY", self.demo_mode)
        self.ui_dist = Path(os.getenv("AUTOPILOT_UI_DIST", Path(__file__).resolve().parents[2] / "ui" / "dist"))
        self.skills_dir = Path(__file__).resolve().parent / "skills"
        self.cors_origins = [o for o in os.getenv("AUTOPILOT_CORS_ORIGINS", "").split(",") if o]
        self.scheduler_enabled = _bool("AUTOPILOT_SCHEDULER", True)

        # First-boot seeds (editable later in Settings)
        self.admin_email = os.getenv("AUTOPILOT_ADMIN_EMAIL", "admin@autopilot.local")
        self.admin_password = os.getenv("AUTOPILOT_ADMIN_PASSWORD", "Autopilot!2026" if self.demo_mode else "")
        self.org_name = os.getenv("AUTOPILOT_ORG_NAME", "Acme Corp" if self.demo_mode else "My Organization")
        self.wazuh_mcp_url = os.getenv("WAZUH_MCP_URL", "")
        self.wazuh_mcp_api_key = os.getenv("WAZUH_MCP_API_KEY", "")
        self.model_provider = os.getenv("MODEL_PROVIDER", "demo" if self.demo_mode else "bedrock")
        self.model_id = os.getenv("MODEL_ID", "")
        self.model_base_url = os.getenv("MODEL_BASE_URL", "")
        self.model_api_key = os.getenv("MODEL_API_KEY", "")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.ingest_key = os.getenv("AUTOPILOT_INGEST_KEY", "")

    def _persistent_secret(self) -> str:
        # Keep sessions valid across restarts without forcing operators to set a key.
        path = self.data_dir / ".secret_key"
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            if path.exists():
                return path.read_text().strip()
            key = secrets.token_urlsafe(48)
            path.write_text(key)
            path.chmod(0o600)
            return key
        except OSError:
            return secrets.token_urlsafe(48)


@lru_cache
def get_config() -> Config:
    return Config()
