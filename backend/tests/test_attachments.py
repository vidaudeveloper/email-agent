from pathlib import Path

import pytest

from app.attachments import AttachmentError, AttachmentStore


def test_add_url_and_list(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg", label="a.jpg")
    assert att.kind == "url"
    assert att.ref.startswith("@url:")
    assert store.get("s1", att.id).url == "https://example.com/a.jpg"
    assert len(store.list("s1")) == 1


def test_add_file_image(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    data = b"\xff\xd8\xff" + b"0" * 100  # pretend jpeg header
    att = store.add_file("s1", filename="x.jpg", content=data, mime="image/jpeg")
    assert att.kind == "image"
    assert att.ref == f"@image:{att.id}"
    assert store.file_path("s1", att.id).exists()


def test_reject_oversize(tmp_path: Path):
    store = AttachmentStore(root=tmp_path, max_image_bytes=10)
    with pytest.raises(AttachmentError):
        store.add_file("s1", filename="big.jpg", content=b"01234567890", mime="image/jpeg")


def test_delete(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg")
    store.delete("s1", att.id)
    assert store.list("s1") == []


def test_delete_file_removes_metadata_and_disk(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    data = b"\xff\xd8\xff" + b"0" * 50
    att = store.add_file("s1", filename="pic.jpg", content=data, mime="image/jpeg")
    file_path = store.file_path("s1", att.id)
    assert file_path.exists()

    store.delete("s1", att.id)

    assert store.list("s1") == []
    assert not file_path.exists()
    assert not store._meta_path("s1").exists()


def test_resolve_many_happy_path(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    a = store.add_url("s1", "https://example.com/a.jpg")
    b = store.add_url("s1", "https://example.com/b.jpg")

    resolved = store.resolve_many("s1", [a.id, b.id])

    assert [r.id for r in resolved] == [a.id, b.id]


def test_resolve_many_preserves_order(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    a = store.add_url("s1", "https://example.com/a.jpg")
    b = store.add_url("s1", "https://example.com/b.jpg")
    c = store.add_url("s1", "https://example.com/c.jpg")

    resolved = store.resolve_many("s1", [c.id, a.id, b.id])

    assert [r.id for r in resolved] == [c.id, a.id, b.id]


def test_resolve_many_empty_list(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    store.add_url("s1", "https://example.com/a.jpg")

    assert store.resolve_many("s1", []) == []


def test_resolve_many_not_found(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg")

    with pytest.raises(AttachmentError, match="Attachment not found"):
        store.resolve_many("s1", [att.id, "att_missing"])


def test_to_public_dict_url_passthrough(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    att = store.add_url("s1", "https://example.com/a.jpg", label="a.jpg")

    public = store.to_public_dict(att)

    assert public["url"] == "https://example.com/a.jpg"
    assert public["preview_url"] is None
    assert public["kind"] == "url"
    assert public["ref"] == att.ref


def test_to_public_dict_image_with_preview_prefix(tmp_path: Path):
    store = AttachmentStore(root=tmp_path)
    data = b"\xff\xd8\xff" + b"0" * 50
    att = store.add_file("s1", filename="pic.jpg", content=data, mime="image/jpeg")

    public = store.to_public_dict(att, preview_path_prefix="/api/sessions/s1/attachments")

    assert public["url"] == f"/api/sessions/s1/attachments/{att.id}/file"
    assert public["preview_url"] == f"/api/sessions/s1/attachments/{att.id}/file"
    assert public["kind"] == "image"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file.jpg",
        "http://",
    ],
)
def test_reject_invalid_url(tmp_path: Path, url: str):
    store = AttachmentStore(root=tmp_path)
    with pytest.raises(AttachmentError, match="http:// or https://"):
        store.add_url("s1", url)


# --- HTTP API tests ---

from fastapi.testclient import TestClient

from app.main import app

AUTH = {"Authorization": "Bearer dev-local-token"}


def _create_session(client: TestClient) -> str:
    r = client.post(
        "/v1/sessions",
        headers=AUTH,
        json={"expert_id": "vidau-creative-agent-oneclick"},
    )
    assert r.status_code == 200
    return r.json()["session_id"]


def test_upload_url_and_list(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/r.png"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "url"
    assert body["ref"].startswith("@url:")
    listed = client.get(f"/v1/sessions/{sid}/attachments", headers=AUTH).json()
    assert len(listed["attachments"]) == 1


def test_upload_file_and_download(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    data = b"\xff\xd8\xff" + b"0" * 100
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        files={"file": ("test.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "image"
    assert body["url"] == f"/v1/sessions/{sid}/attachments/{body['id']}/file"
    assert body["preview_url"] == f"/v1/sessions/{sid}/attachments/{body['id']}/file"

    r2 = client.get(
        f"/v1/sessions/{sid}/attachments/{body['id']}/file",
        headers=AUTH,
    )
    assert r2.status_code == 200
    assert r2.content == data


def test_delete_attachment(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/a.jpg"},
    )
    assert r.status_code == 200
    att_id = r.json()["id"]
    r2 = client.delete(
        f"/v1/sessions/{sid}/attachments/{att_id}",
        headers=AUTH,
    )
    assert r2.status_code == 200
    listed = client.get(f"/v1/sessions/{sid}/attachments", headers=AUTH).json()
    assert len(listed["attachments"]) == 0


def test_attachments_session_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    r = client.post(
        "/v1/sessions/nonexistent-session/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/a.jpg"},
    )
    assert r.status_code == 404


def test_attachments_unauthorized(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.get(f"/v1/sessions/{sid}/attachments")
    assert r.status_code == 401


def test_upload_invalid_url_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "ftp://example.com/a.jpg"},
    )
    assert r.status_code == 400


def test_upload_oversize_returns_400(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    monkeypatch.setattr(
        "app.main.get_attachment_store",
        lambda: AttachmentStore(root=tmp_path, max_image_bytes=10),
    )
    client = TestClient(app)
    sid = _create_session(client)
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        files={"file": ("big.jpg", b"01234567890", "image/jpeg")},
    )
    assert r.status_code == 400


def test_delete_unknown_attachment_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.delete(
        f"/v1/sessions/{sid}/attachments/att_missing",
        headers=AUTH,
    )
    assert r.status_code == 404


def test_file_for_url_attachment_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.main._attachment_store_root", lambda: tmp_path)
    client = TestClient(app)
    sid = _create_session(client)
    r = client.post(
        f"/v1/sessions/{sid}/attachments",
        headers=AUTH,
        json={"kind": "url", "url": "https://example.com/a.jpg"},
    )
    assert r.status_code == 200
    att_id = r.json()["id"]
    r2 = client.get(
        f"/v1/sessions/{sid}/attachments/{att_id}/file",
        headers=AUTH,
    )
    assert r2.status_code == 404
