from alembic import command
from alembic.config import Config


def test_migrations_apply_and_match_models(tmp_path, monkeypatch):
    """Fails if someone changes models.py without adding a migration."""
    monkeypatch.setenv("RAG_DATABASE_URL", f"sqlite:///{tmp_path / 'm.db'}")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if models and migrations have drifted
    command.downgrade(cfg, "base")
