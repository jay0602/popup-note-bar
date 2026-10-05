"""Persistent note storage for Popup Note Bar."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Note:
    id: str
    title: str
    content: str
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, title: str = "新記事", content: str = "") -> "Note":
        now = utc_now()
        return cls(uuid.uuid4().hex, title.strip() or "新記事", content, now, now)

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or "未命名記事"),
            content=str(data.get("content") or ""),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


class NoteStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.notes: list[Note] = []

    def load(self) -> list[Note]:
        if not self.path.exists():
            self.notes = [Note.create("歡迎使用", "按 Ctrl + Alt + N 隨時叫出記事欄。")]
            self.save()
            return self.notes

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.notes = [Note.from_dict(item) for item in raw.get("notes", [])]
        except (OSError, ValueError, TypeError, KeyError):
            self.notes = [Note.create("資料讀取失敗", "原始檔案仍保留，請檢查 notes.json。")]
        if not self.notes:
            self.notes = [Note.create()]
        self.sort()
        return self.notes

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "notes": [asdict(note) for note in self.notes]}
        handle, temp_name = tempfile.mkstemp(
            prefix="notes-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temp_file:
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def sort(self) -> None:
        self.notes.sort(key=lambda item: item.updated_at, reverse=True)

    def add(self, title: str = "新記事") -> Note:
        note = Note.create(title)
        self.notes.insert(0, note)
        self.save()
        return note

    def get(self, note_id: str) -> Note | None:
        return next((note for note in self.notes if note.id == note_id), None)

    def update(self, note_id: str, title: str, content: str) -> Note | None:
        note = self.get(note_id)
        if note is None:
            return None
        note.title = title.strip() or self.title_from_content(content)
        note.content = content
        note.updated_at = utc_now()
        self.sort()
        self.save()
        return note

    def delete(self, note_id: str) -> bool:
        changed = any(note.id == note_id for note in self.notes)
        self.notes = [note for note in self.notes if note.id != note_id]
        if not self.notes:
            self.notes.append(Note.create())
        if changed:
            self.save()
        return changed

    def search(self, query: str) -> list[Note]:
        needle = query.strip().casefold()
        if not needle:
            return list(self.notes)
        return [
            note
            for note in self.notes
            if needle in note.title.casefold() or needle in note.content.casefold()
        ]

    @staticmethod
    def title_from_content(content: str) -> str:
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
        return first_line[:40] or "新記事"
