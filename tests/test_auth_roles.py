from .conftest import PASSWORD


def test_login_failures_are_uniform(h, client):
    h.tenant("Univ A", "admin@a.dz")
    wrong_pw = client.post("/auth/login", data={"username": "admin@a.dz", "password": "nope-nope-nope"})
    unknown = client.post("/auth/login", data={"username": "ghost@a.dz", "password": PASSWORD})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_protected_endpoints_require_token(client):
    for method, url in [("get", "/me"), ("get", "/documents"), ("post", "/ask"), ("get", "/users")]:
        assert getattr(client, method)(url).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_duplicate_tenant_or_email_rejected(h, client):
    h.tenant("Univ A", "admin@a.dz")
    r = client.post("/tenants", json={"tenant_name": "Univ A", "admin_email": "x@x.dz", "admin_password": PASSWORD})
    assert r.status_code == 409
    r = client.post("/tenants", json={"tenant_name": "Other", "admin_email": "ADMIN@a.dz", "admin_password": PASSWORD})
    assert r.status_code == 409


def test_bootstrap_token_enforced(settings, llm):
    from fastapi.testclient import TestClient
    from qdrant_client import QdrantClient

    from ragplatform.api.app import create_app
    from ragplatform.embedding import HashEmbedder, NullReranker
    from ragplatform.services import make_services
    from ragplatform.vectorstore import QdrantStore

    settings.bootstrap_token = "letmein"
    emb = HashEmbedder()
    c = TestClient(create_app(settings, make_services(settings, emb, QdrantStore(QdrantClient(":memory:"), "c", emb.dim), NullReranker(), llm)))
    body = {"tenant_name": "Tenant", "admin_email": "a@t.dz", "admin_password": PASSWORD}
    assert c.post("/tenants", json=body).status_code == 403
    assert c.post("/tenants", json=body, headers={"X-Bootstrap-Token": "letmein"}).status_code == 201


def test_role_enforcement(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    viewer = h.user(t["admin"], "v@a.dz", "viewer")
    editor = h.user(t["admin"], "e@a.dz", "editor")
    assert h.upload(viewer["headers"], "hello world").status_code == 403
    assert h.upload(editor["headers"], "hello world").status_code == 202
    assert client.post("/users", headers=editor["headers"], json={"email": "z@a.dz", "password": "x" * 12}).status_code == 403
    assert client.get("/audit", headers=viewer["headers"]).status_code == 403
    assert client.get("/groups", headers=viewer["headers"]).status_code == 403


def test_deactivated_user_token_stops_working(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    u = h.user(t["admin"], "v@a.dz")
    assert client.get("/me", headers=u["headers"]).status_code == 200
    assert client.patch(f"/users/{u['id']}", headers=t["admin"], json={"is_active": False}).status_code == 200
    assert client.get("/me", headers=u["headers"]).status_code == 401


def test_admin_cannot_demote_self(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    me = client.get("/me", headers=t["admin"]).json()
    assert client.patch(f"/users/{me['id']}", headers=t["admin"], json={"role": "viewer"}).status_code == 400


def test_login_rate_limited(h, client):
    for _ in range(10):
        client.post("/auth/login", data={"username": "x@x.dz", "password": "bad-password-1"})
    assert client.post("/auth/login", data={"username": "x@x.dz", "password": "bad-password-1"}).status_code == 429
