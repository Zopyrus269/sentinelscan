"""In-memory fake Firestore client for logstore read-layer tests.

query.py and rollup.py build multi-clause `.where().where().order_by().limit().stream()`
chains and Increment/ArrayUnion merge writes against real Firestore semantics. Hand-built
MagicMock chains for every filter combination would be unreadable at this scale, so this
fakes just enough of the Firestore Python client -- where/order_by/limit filtering over
in-memory documents, and transform-sentinel-aware merge writes -- to exercise the real
filtering and aggregation logic in `apps.backend.logstore.query`/`rollup` against realistic
seeded data, without a live Firestore project.

Not a general-purpose Firestore emulator: only the operators and chains those two modules
actually use are implemented (`==`, `>=`, `<=`, `>`, `<`, `array_contains`; `order_by` +
`limit`; `set(merge=...)` and `get()`).
"""
import uuid
from typing import Any, Dict, Optional

from firebase_admin import firestore


def _get_field(data: Dict[str, Any], field: str) -> Any:
    value: Any = data
    for part in field.split("."):
        if value is None:
            return None
        value = value.get(part)
    return value


def _matches(data: Dict[str, Any], field: str, op: str, expected: Any) -> bool:
    actual = _get_field(data, field)
    if op == "==":
        return actual == expected
    if op == ">=":
        return actual is not None and actual >= expected
    if op == "<=":
        return actual is not None and actual <= expected
    if op == ">":
        return actual is not None and actual > expected
    if op == "<":
        return actual is not None and actual < expected
    if op == "array_contains":
        return isinstance(actual, list) and expected in actual
    raise ValueError(f"fake firestore does not support operator: {op}")


def _resolve_value(existing: Any, new: Any) -> Any:
    """Applies one field's new value onto its existing value, honoring Increment/ArrayUnion
    transform sentinels the way real Firestore would, recursing into nested maps."""
    if isinstance(new, firestore.Increment):
        return (existing or 0) + new.value
    if isinstance(new, firestore.ArrayUnion):
        merged = list(existing or [])
        for value in new.values:
            if value not in merged:
                merged.append(value)
        return merged
    if isinstance(new, dict):
        merged_map = dict(existing or {})
        for key, value in new.items():
            merged_map[key] = _resolve_value(merged_map.get(key), value)
        return merged_map
    return new


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: Optional[Dict[str, Any]]):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return dict(self._data) if self._data is not None else None


class _FakeDocumentRef:
    def __init__(self, collection: "_FakeCollection", doc_id: str):
        self._collection = collection
        self.id = doc_id

    def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        existing = self._collection.docs.get(self.id) if merge else None
        merged = dict(existing or {})
        for key, value in data.items():
            merged[key] = _resolve_value(merged.get(key), value)
        self._collection.docs[self.id] = merged

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id, self._collection.docs.get(self.id))


class _FakeQuery:
    def __init__(self, collection: "_FakeCollection", filters=None, order=None, limit_n=None):
        self._collection = collection
        self._filters = filters or []
        self._order = order
        self._limit = limit_n

    def where(self, field: str, op: str, value: Any) -> "_FakeQuery":
        return _FakeQuery(self._collection, self._filters + [(field, op, value)], self._order, self._limit)

    def order_by(self, field: str, direction: Any = None) -> "_FakeQuery":
        return _FakeQuery(self._collection, self._filters, (field, direction), self._limit)

    def limit(self, n: int) -> "_FakeQuery":
        return _FakeQuery(self._collection, self._filters, self._order, n)

    def stream(self):
        results = [
            _FakeSnapshot(doc_id, data)
            for doc_id, data in self._collection.docs.items()
            if all(_matches(data, field, op, value) for field, op, value in self._filters)
        ]
        if self._order:
            field, direction = self._order
            reverse = direction == firestore.Query.DESCENDING
            results.sort(key=lambda s: _get_field(s.to_dict(), field) or "", reverse=reverse)
        if self._limit is not None:
            results = results[: self._limit]
        return results


class _FakeCollection:
    def __init__(self):
        self.docs: Dict[str, Dict[str, Any]] = {}

    def document(self, doc_id: Optional[str] = None) -> _FakeDocumentRef:
        return _FakeDocumentRef(self, doc_id or str(uuid.uuid4()))

    def where(self, field: str, op: str, value: Any) -> _FakeQuery:
        return _FakeQuery(self).where(field, op, value)

    def order_by(self, field: str, direction: Any = None) -> _FakeQuery:
        return _FakeQuery(self).order_by(field, direction)

    def stream(self):
        return _FakeQuery(self).stream()


class FakeFirestoreClient:
    """Fakes `db.collection(name)`; each named collection is independent and persistent
    for the lifetime of one client instance -- construct a fresh one per test."""

    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}

    def collection(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())

    def seed(self, collection: str, doc_id: str, data: Dict[str, Any]) -> None:
        """Test convenience: pre-populates a document directly, bypassing set()'s merge
        logic -- use this to set up fixture state, not to exercise the merge path itself."""
        self.collection(collection).docs[doc_id] = data
