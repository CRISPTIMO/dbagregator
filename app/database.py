"""Работа с локальной SQLite-базой и JSON-схемой полей."""

from __future__ import annotations

import json
import sqlite3
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_DB_DIR = ROOT_DIR / "CoreDB"
DATABASE_PATH = CORE_DB_DIR / "database.sqlite3"
SCHEMA_PATH = CORE_DB_DIR / "schema.json"


class Database:
    def __init__(self, db_path: Path | None = None, schema_path: Path | None = None) -> None:
        CORE_DB_DIR.mkdir(parents=True, exist_ok=True)
        self.schema_path = schema_path or SCHEMA_PATH
        self.connection = sqlite3.connect(db_path or DATABASE_PATH)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def fields(self) -> list[str]:
        if not self.schema_path.exists():
            return []
        content = json.loads(self.schema_path.read_text(encoding="utf-8"))
        fields = content.get("fields") if isinstance(content, dict) else None
        if not isinstance(fields, list) or any(
            not isinstance(field, str) or not field.strip() or not field.isprintable()
            for field in fields
        ):
            raise ValueError("Некорректная схема: fields должен содержать список названий полей.")
        if len({field.casefold() for field in fields}) != len(fields):
            raise ValueError("В схеме есть повторяющиеся поля.")
        return fields

    def add_field(self, field_name: str) -> bool:
        """Добавляет новое поле в схему базы данных."""
        field_name = field_name.strip()
        fields = self.fields()
        if not field_name or field_name.casefold() in {field.casefold() for field in fields}:
            return False
        if not field_name.isprintable():
            raise ValueError("Название поля не должно содержать управляющие символы.")
        fields.append(field_name)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.schema_path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"fields": fields}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.schema_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True

    def add(self, data: dict[str, Any]) -> int:
        now = datetime.now().astimezone().isoformat(timespec="microseconds")
        cursor = self.connection.execute(
            "INSERT INTO records (data, created_at, updated_at) VALUES (?, ?, ?)",
            (json.dumps(data, ensure_ascii=False), now, now),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get(self, record_id: int) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT id, data, created_at, updated_at FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def all(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, data, created_at, updated_at FROM records ORDER BY id"
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update(self, record_id: int, data: dict[str, Any]) -> bool:
        existing = self.get(record_id)
        if existing is None:
            return False
        if existing["data"] == data:
            return True
        now = datetime.now().astimezone().isoformat(timespec="microseconds")
        cursor = self.connection.execute(
            """
            UPDATE records
            SET data = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(data, ensure_ascii=False), now, record_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM records WHERE id = ?", (record_id,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = json.loads(row["data"])
        if not isinstance(data, dict):
            raise ValueError(f"Повреждены данные записи #{row['id']}.")
        for field in self.fields():
            data.setdefault(field, None)
        return {
            "id": row["id"],
            "data": data,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
