import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from ragplatform.api.app import create_app
from ragplatform.config import Settings
from ragplatform.embedding import HashEmbedder, NullReranker
from ragplatform.services import make_services
from ragplatform.vectorstore import QdrantStore

from .fakes import FakeLLM

PASSWORD = "correct-horse-battery"


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        app_env="test", database_url="sqlite://", auto_create_tables=True, queue_mode="inline",
        upload_dir=str(tmp_path / "uploads"), embedder="hash", reranker="none", abstain_threshold=0.2,
        max_docs_per_tenant=5, ask_rate_limit_per_min=5,
    )


@pytest.fixture
def client(settings, llm):
    embedder = HashEmbedder()
    store = QdrantStore(QdrantClient(":memory:"), "chunks", embedder.dim)
    services = make_services(settings, embedder, store, NullReranker(), llm)
    return TestClient(create_app(settings, services))


class Helper:
    def __init__(self, client: TestClient) -> None:
        self.c = client

    def tenant(self, name: str, email: str) -> dict:
        r = self.c.post("/tenants", json={"tenant_name": name, "admin_email": email, "admin_password": PASSWORD})
        assert r.status_code == 201, r.text
        return {"admin": self.login(email), **r.json()}

    def login(self, email: str, password: str = PASSWORD) -> dict:
        r = self.c.post("/auth/login", data={"username": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def user(self, admin: dict, email: str, role: str = "viewer", group_ids=()) -> dict:
        r = self.c.post("/users", headers=admin, json={"email": email, "password": PASSWORD, "role": role, "group_ids": list(group_ids)})
        assert r.status_code == 201, r.text
        return {"headers": self.login(email), **r.json()}

    def group(self, admin: dict, name: str) -> str:
        r = self.c.post("/groups", headers=admin, json={"name": name})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload(self, headers: dict, text: str, name: str = "doc.txt", visibility: str = "tenant", group_ids=()):
        return self.c.post(
            "/documents", headers=headers, files={"file": (name, text.encode(), "text/plain")},
            data={"visibility": visibility, "group_ids": list(group_ids)},
        )

    def ask(self, headers: dict, question: str, **extra):
        return self.c.post("/ask", headers=headers, json={"question": question, **extra})


@pytest.fixture
def h(client):
    return Helper(client)
