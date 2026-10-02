"""Qdrant-backed chunk store. Tenant + document ACLs are enforced INSIDE the vector query via payload filters,
so unauthorized chunks are never retrieved (rather than retrieved and then hidden)."""
import uuid
import warnings
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from .acl import AccessScope

PAYLOAD_KEYS = ("tenant_id", "doc_id", "visibility", "owner_id", "group_ids")


@dataclass
class Hit:
    text: str
    source: str
    page: int
    doc_id: str
    score: float


def _eq(key: str, value: str) -> qm.FieldCondition:
    return qm.FieldCondition(key=key, match=qm.MatchValue(value=value))


def build_filter(scope: AccessScope, document_ids: list[str] | None = None) -> qm.Filter:
    must: list = [_eq("tenant_id", scope.tenant_id)]
    if document_ids:
        must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=list(document_ids))))
    if not scope.is_admin:
        should: list = [_eq("visibility", "tenant"), _eq("owner_id", scope.user_id)]
        if scope.group_ids:
            should.append(qm.FieldCondition(key="group_ids", match=qm.MatchAny(any=sorted(scope.group_ids))))
        must.append(qm.Filter(should=should))
    return qm.Filter(must=must)


def _doc_selector(tenant_id: str, doc_id: str) -> qm.FilterSelector:
    return qm.FilterSelector(filter=qm.Filter(must=[_eq("tenant_id", tenant_id), _eq("doc_id", doc_id)]))


class QdrantStore:
    def __init__(self, client: QdrantClient, collection: str, dim: int) -> None:
        self.client, self.collection, self.dim = client, collection, dim
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection, vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE)
            )
        with warnings.catch_warnings():  # payload indexes are no-ops (with a warning) in embedded mode
            warnings.simplefilter("ignore")
            for key in PAYLOAD_KEYS:
                self.client.create_payload_index(self.collection, key, qm.PayloadSchemaType.KEYWORD)

    def upsert_chunks(
        self, *, tenant_id: str, doc_id: str, owner_id: str, visibility: str, group_ids: list[str],
        source: str, items: list[tuple[str, int]], vectors: list[list[float]],
    ) -> None:
        points = [
            qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "tenant_id": tenant_id, "doc_id": doc_id, "owner_id": owner_id, "visibility": visibility,
                    "group_ids": group_ids, "source": source, "page": page, "text": text,
                },
            )
            for (text, page), vec in zip(items, vectors, strict=True)
        ]
        for i in range(0, len(points), 128):
            self.client.upsert(self.collection, points[i : i + 128])

    def search(self, vector: list[float], scope: AccessScope, k: int, document_ids: list[str] | None = None) -> list[Hit]:
        res = self.client.query_points(
            self.collection, query=vector, query_filter=build_filter(scope, document_ids), limit=k, with_payload=True
        )
        return [
            Hit(p.payload["text"], p.payload["source"], p.payload["page"], p.payload["doc_id"], float(p.score))
            for p in res.points
        ]

    def delete_document(self, tenant_id: str, doc_id: str) -> None:
        self.client.delete(self.collection, points_selector=_doc_selector(tenant_id, doc_id))

    def update_acl(self, tenant_id: str, doc_id: str, visibility: str, group_ids: list[str]) -> None:
        self.client.set_payload(
            self.collection,
            payload={"visibility": visibility, "group_ids": group_ids},
            points=_doc_selector(tenant_id, doc_id),
        )

    def ping(self) -> None:
        self.client.get_collections()
