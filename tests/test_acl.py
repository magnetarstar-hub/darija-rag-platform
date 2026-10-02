import itertools

from qdrant_client import QdrantClient

from ragplatform.acl import AccessScope
from ragplatform.embedding import HashEmbedder
from ragplatform.vectorstore import QdrantStore

HR = "La grille salariale confidentielle du personnel administratif est publiée en annexe."


def test_restricted_document_visible_only_to_group_members_and_admin(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    rh = h.group(t["admin"], "RH")
    member = h.user(t["admin"], "m@a.dz", "viewer", [rh])
    outsider = h.user(t["admin"], "o@a.dz", "viewer")
    editor = h.user(t["admin"], "e@a.dz", "editor")

    doc = h.upload(editor["headers"], HR, "salaires.txt", "restricted", [rh]).json()

    q = "grille salariale confidentielle du personnel"
    assert [s["source"] for s in h.ask(member["headers"], q).json()["sources"]] == ["salaires.txt"]
    assert [s["source"] for s in h.ask(t["admin"], q).json()["sources"]] == ["salaires.txt"]
    assert [s["source"] for s in h.ask(editor["headers"], q).json()["sources"]] == ["salaires.txt"]  # owner
    assert h.ask(outsider["headers"], q).json()["sources"] == []

    assert client.get(f"/documents/{doc['id']}", headers=outsider["headers"]).status_code == 404
    assert client.get("/documents", headers=outsider["headers"]).json() == []
    assert client.get(f"/documents/{doc['id']}", headers=member["headers"]).status_code == 200


def test_changing_permissions_takes_effect_in_retrieval(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    rh = h.group(t["admin"], "RH")
    outsider = h.user(t["admin"], "o@a.dz")
    doc = h.upload(t["admin"], HR, "salaires.txt").json()  # tenant-wide
    q = "grille salariale confidentielle du personnel"
    assert h.ask(outsider["headers"], q).json()["sources"]

    r = client.patch(f"/documents/{doc['id']}/permissions", headers=t["admin"], json={"visibility": "restricted", "group_ids": [rh]})
    assert r.status_code == 200
    assert h.ask(outsider["headers"], q).json()["sources"] == []  # vector payload updated, not just the DB

    r = client.patch(f"/documents/{doc['id']}/permissions", headers=t["admin"], json={"visibility": "tenant", "group_ids": []})
    assert h.ask(outsider["headers"], q).json()["sources"]


def test_adding_user_to_group_grants_access_immediately(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    rh = h.group(t["admin"], "RH")
    u = h.user(t["admin"], "u@a.dz")
    h.upload(t["admin"], HR, "salaires.txt", "restricted", [rh])
    q = "grille salariale confidentielle du personnel"
    assert h.ask(u["headers"], q).json()["sources"] == []
    client.patch(f"/users/{u['id']}", headers=t["admin"], json={"group_ids": [rh]})
    assert h.ask(u["headers"], q).json()["sources"]


def test_groups_from_other_tenants_are_rejected(h):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    gb = h.group(b["admin"], "RH")
    assert h.upload(a["admin"], HR, "x.txt", "restricted", [gb]).status_code == 400
    assert h.upload(a["admin"], HR, "x.txt", "restricted", []).status_code == 400


def test_only_owner_or_admin_can_delete_or_change_permissions(h, client):
    t = h.tenant("Univ A", "admin@a.dz")
    e1, e2 = h.user(t["admin"], "e1@a.dz", "editor"), h.user(t["admin"], "e2@a.dz", "editor")
    doc = h.upload(e1["headers"], HR, "x.txt").json()
    assert client.delete(f"/documents/{doc['id']}", headers=e2["headers"]).status_code == 403
    assert client.patch(f"/documents/{doc['id']}/permissions", headers=e2["headers"], json={"visibility": "tenant"}).status_code == 403
    assert client.delete(f"/documents/{doc['id']}", headers=e1["headers"]).status_code == 204


def test_post_retrieval_guard_blocks_drifted_vector_payload(h, client, llm, monkeypatch):
    """Simulate the vector store leaking a chunk (payload drift): the DB-backed guard must still drop it."""
    t = h.tenant("Univ A", "admin@a.dz")
    rh = h.group(t["admin"], "RH")
    outsider = h.user(t["admin"], "o@a.dz")
    h.upload(t["admin"], HR, "salaires.txt", "restricted", [rh])

    store = client.app.state.services.store
    original = store.search
    admin_scope = AccessScope(tenant_id=client.get("/me", headers=t["admin"]).json()["tenant_id"], user_id="x", group_ids=frozenset(), is_admin=True)
    monkeypatch.setattr(store, "search", lambda vec, scope, k, ids=None: original(vec, admin_scope, k, ids))  # leaks!

    r = h.ask(outsider["headers"], "grille salariale confidentielle du personnel").json()
    assert r["sources"] == []
    assert all("grille salariale" not in str(c) for c in llm.calls)


def test_qdrant_filter_matches_python_rule_for_all_combinations():
    emb = HashEmbedder()
    store = QdrantStore(QdrantClient(":memory:"), "c", emb.dim)
    docs = []
    for tenant, vis, owner, groups in itertools.product(["t1", "t2"], ["tenant", "restricted"], ["alice", "bob"], [[], ["g1"], ["g2"], ["g1", "g2"]]):
        doc_id = f"{tenant}-{vis}-{owner}-{'_'.join(groups) or 'none'}"
        docs.append((doc_id, {"tenant_id": tenant, "visibility": vis, "owner_id": owner, "group_ids": groups}))
        store.upsert_chunks(
            tenant_id=tenant, doc_id=doc_id, owner_id=owner, visibility=vis, group_ids=groups,
            source=doc_id, items=[("texte commun", 1)], vectors=emb.embed(["texte commun"]),
        )
    vec = emb.embed(["texte commun"])[0]
    for tenant, user, groups, admin in itertools.product(["t1", "t2"], ["alice", "carol"], [frozenset(), frozenset({"g1"}), frozenset({"g1", "g2"})], [False, True]):
        scope = AccessScope(tenant, user, groups, admin)
        expected = {d for d, p in docs if scope.allows(p)}
        got = {hit.doc_id for hit in store.search(vec, scope, 1000)}
        assert got == expected, (scope, got ^ expected)
