"""The most important tests: one organization must never see another's data."""

SECRET_A = "Le budget secret du laboratoire alpha est de 4200000 dinars pour la saison."


def test_tenant_cannot_read_or_touch_other_tenants_documents(h, client):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    doc = h.upload(a["admin"], SECRET_A, "budget.txt").json()
    assert doc["status"] == "ready"

    assert client.get("/documents", headers=b["admin"]).json() == []
    assert client.get(f"/documents/{doc['id']}", headers=b["admin"]).status_code == 404
    assert client.delete(f"/documents/{doc['id']}", headers=b["admin"]).status_code == 404
    r = client.patch(f"/documents/{doc['id']}/permissions", headers=b["admin"], json={"visibility": "tenant"})
    assert r.status_code == 404
    assert client.get(f"/documents/{doc['id']}", headers=a["admin"]).status_code == 200  # untouched


def test_retrieval_never_crosses_tenants(h, llm):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    h.upload(a["admin"], SECRET_A, "budget.txt")
    h.upload(b["admin"], "Le règlement de B exige un dossier complet avant juillet.", "reg.txt")

    r = h.ask(b["admin"], "Quel est le budget secret du laboratoire alpha ?").json()
    assert all(s["source"] != "budget.txt" for s in r["sources"])
    assert all("4200000" not in str(call) for call in llm.calls)  # the LLM never even saw A's data

    r = h.ask(a["admin"], "Quel est le budget secret du laboratoire alpha ?").json()
    assert [s["source"] for s in r["sources"]] == ["budget.txt"]


def test_document_id_filter_cannot_reach_other_tenant(h):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    doc = h.upload(a["admin"], SECRET_A, "budget.txt").json()
    r = h.ask(b["admin"], "budget secret laboratoire", document_ids=[doc["id"]]).json()
    assert r["sources"] == [] and r["abstained"]


def test_same_file_can_exist_in_two_tenants(h):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    assert h.upload(a["admin"], "contenu identique", "x.txt").status_code == 202
    assert h.upload(b["admin"], "contenu identique", "x.txt").status_code == 202


def test_admin_user_listing_is_tenant_scoped(h, client):
    a, b = h.tenant("Univ A", "admin@a.dz"), h.tenant("Univ B", "admin@b.dz")
    h.user(a["admin"], "u@a.dz")
    assert {u["email"] for u in client.get("/users", headers=b["admin"]).json()} == {"admin@b.dz"}
    other_user = client.get("/users", headers=a["admin"]).json()[1]["id"]
    assert client.patch(f"/users/{other_user}", headers=b["admin"], json={"role": "admin"}).status_code == 404
