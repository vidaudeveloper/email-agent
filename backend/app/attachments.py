from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_MAX_IMAGE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_VIDEO_BYTES = 100 * 1024 * 1024


class AttachmentError(Exception):
    """Validation or lookup failure for session attachments."""


@dataclass
class Attachment:
    id: str
    kind: str
    label: str
    ref: str
    url: str | None = None
    preview_url: str | None = None
    mime: str | None = None
    size: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Attachment:
        return cls(
            id=data["id"],
            kind=data["kind"],
            label=data["label"],
            ref=data["ref"],
            url=data.get("url"),
            preview_url=data.get("preview_url"),
            mime=data.get("mime"),
            size=data.get("size"),
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )


class AttachmentStore:
    def __init__(
        self,
        root: Path | str,
        *,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
        max_video_bytes: int = DEFAULT_MAX_VIDEO_BYTES,
    ) -> None:
        self.root = Path(root)
        self.max_image_bytes = max_image_bytes
        self.max_video_bytes = max_video_bytes

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "attachments.json"

    def _files_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "attachments"

    def _new_id(self) -> str:
        return f"att_{uuid.uuid4().hex[:12]}"

    def _load_all(self, session_id: str) -> dict[str, Attachment]:
        path = self._meta_path(session_id)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("attachments") or []
        return {item["id"]: Attachment.from_dict(item) for item in items}

    def _save_all(self, session_id: str, attachments: dict[str, Attachment]) -> None:
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "attachments": [
                asdict(att)
                for att in sorted(attachments.values(), key=lambda a: a.created_at)
            ]
        }
        self._meta_path(session_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AttachmentError("URL must start with http:// or https://")

    @staticmethod
    def _kind_from_mime(mime: str) -> str:
        lower = mime.lower()
        if lower.startswith("image/"):
            return "image"
        if lower.startswith("video/"):
            return "video"
        raise AttachmentError(f"Unsupported mime type: {mime}")

    @staticmethod
    def _ref_for_kind(kind: str, attachment_id: str) -> str:
        return f"@{kind}:{attachment_id}"

    def add_url(
        self,
        session_id: str,
        url: str,
        *,
        label: str | None = None,
    ) -> Attachment:
        self._validate_url(url)
        attachment_id = self._new_id()
        att = Attachment(
            id=attachment_id,
            kind="url",
            label=label or url,
            ref=self._ref_for_kind("url", attachment_id),
            url=url,
            size=0,
        )
        attachments = self._load_all(session_id)
        attachments[attachment_id] = att
        self._save_all(session_id, attachments)
        return att

    def add_file(
        self,
        session_id: str,
        *,
        filename: str,
        content: bytes,
        mime: str,
    ) -> Attachment:
        kind = self._kind_from_mime(mime)
        size = len(content)
        limit = self.max_image_bytes if kind == "image" else self.max_video_bytes
        if size > limit:
            raise AttachmentError(f"{kind} exceeds max size of {limit} bytes")

        attachment_id = self._new_id()
        files_dir = self._files_dir(session_id)
        files_dir.mkdir(parents=True, exist_ok=True)
        file_path = files_dir / attachment_id
        file_path.write_bytes(content)

        att = Attachment(
            id=attachment_id,
            kind=kind,
            label=filename,
            ref=self._ref_for_kind(kind, attachment_id),
            mime=mime,
            size=size,
        )
        attachments = self._load_all(session_id)
        attachments[attachment_id] = att
        self._save_all(session_id, attachments)
        return att

    def list(self, session_id: str) -> list[Attachment]:
        attachments = self._load_all(session_id)
        return sorted(attachments.values(), key=lambda a: a.created_at)

    def get(self, session_id: str, attachment_id: str) -> Attachment:
        att = self._load_all(session_id).get(attachment_id)
        if att is None:
            raise AttachmentError(f"Attachment not found: {attachment_id}")
        return att

    def delete(self, session_id: str, attachment_id: str) -> None:
        attachments = self._load_all(session_id)
        att = attachments.pop(attachment_id, None)
        if att is None:
            raise AttachmentError(f"Attachment not found: {attachment_id}")

        if att.kind in {"image", "video"}:
            path = self.file_path(session_id, attachment_id)
            if path.exists():
                path.unlink()

        if attachments:
            self._save_all(session_id, attachments)
        else:
            meta_path = self._meta_path(session_id)
            if meta_path.exists():
                meta_path.unlink()

    def resolve_many(self, session_id: str, ids: list[str]) -> list[Attachment]:
        if not ids:
            return []
        attachments = self._load_all(session_id)
        resolved: list[Attachment] = []
        for attachment_id in ids:
            att = attachments.get(attachment_id)
            if att is None:
                raise AttachmentError(f"Attachment not found: {attachment_id}")
            resolved.append(att)
        return resolved

    def file_path(self, session_id: str, attachment_id: str) -> Path:
        return self._files_dir(session_id) / attachment_id

    def to_public_dict(
        self,
        att: Attachment,
        *,
        preview_path_prefix: str | None = None,
    ) -> dict[str, Any]:
        url = att.url
        preview_url = att.preview_url
        if preview_path_prefix and att.kind in {"image", "video"}:
            base = preview_path_prefix.rstrip("/")
            file_url = f"{base}/{att.id}/file"
            if url is None:
                url = file_url
            if preview_url is None and att.kind == "image":
                preview_url = file_url
        return {
            "id": att.id,
            "kind": att.kind,
            "label": att.label,
            "ref": att.ref,
            "url": url,
            "preview_url": preview_url,
            "mime": att.mime,
            "size": att.size,
            "created_at": att.created_at,
        }
