"""Зашифрованный контейнер InfoCore."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


VAULT_PATH = Path(__file__).resolve().parent.parent / "CoreDB" / "infocore.vault"
LEGACY_DB_PATH = VAULT_PATH.parent / "database.sqlite3"
LEGACY_SCHEMA_PATH = VAULT_PATH.parent / "schema.json"
MAGIC = b"INFOCORE-VAULT-1\0"


class VaultError(Exception):
    """Ошибка открытия или сохранения защищённого контейнера."""


class Vault:
    def __init__(self, password: str) -> None:
        if not password:
            raise VaultError("Ключ не может быть пустым.")
        self.password = password
        self.workdir = Path(tempfile.mkdtemp(prefix="infocore-"))
        self.db_path = self.workdir / "database.sqlite3"
        self.schema_path = self.workdir / "schema.json"
        self.security_path = self.workdir / "security.log"
        self.imported_legacy = False
        self._closed = False

    @classmethod
    def exists(cls) -> bool:
        return VAULT_PATH.exists()

    @classmethod
    def create_or_open(cls, password: str) -> "Vault":
        vault = cls(password)
        try:
            if VAULT_PATH.exists():
                vault._decrypt()
            else:
                vault._import_legacy()
            vault._append_security("AUTH_SUCCESS", "Доступ разрешён")
            return vault
        except Exception:
            vault.cleanup()
            raise VaultError("Доступ запрещён: неверный ключ или повреждённый контейнер.")

    def close(self) -> None:
        if self._closed:
            return
        self._append_security("SESSION_END", "Сессия завершена")
        self._encrypt()
        if self.imported_legacy:
            LEGACY_DB_PATH.unlink(missing_ok=True)
            LEGACY_SCHEMA_PATH.unlink(missing_ok=True)
        self.cleanup()

    def cleanup(self) -> None:
        if not self._closed:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self._closed = True

    def _derive_key(self, salt: bytes) -> bytes:
        return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(
            self.password.encode("utf-8")
        )

    def _decrypt(self) -> None:
        raw = VAULT_PATH.read_bytes()
        if not raw.startswith(MAGIC) or len(raw) < len(MAGIC) + 28:
            raise VaultError("Неверный формат контейнера.")
        salt_start = len(MAGIC)
        salt = raw[salt_start:salt_start + 16]
        nonce = raw[salt_start + 16:salt_start + 28]
        encrypted = raw[salt_start + 28:]
        payload = AESGCM(self._derive_key(salt)).decrypt(nonce, encrypted, MAGIC)
        self._unpack(payload)

    def _import_legacy(self) -> None:
        self.imported_legacy = LEGACY_DB_PATH.exists() or LEGACY_SCHEMA_PATH.exists()
        if LEGACY_DB_PATH.exists():
            shutil.copy2(LEGACY_DB_PATH, self.db_path)
        else:
            self.db_path.touch()
        if LEGACY_SCHEMA_PATH.exists():
            shutil.copy2(LEGACY_SCHEMA_PATH, self.schema_path)
        else:
            self.schema_path.write_text('{"fields": []}\n', encoding="utf-8")
        self.security_path.touch()

    def _unpack(self, payload: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
            if "database.sqlite3" not in names or "schema.json" not in names:
                raise VaultError("Контейнер не содержит обязательных файлов.")
            for name, target in (("database.sqlite3", self.db_path), ("schema.json", self.schema_path)):
                target.write_bytes(archive.read(name))
            self.security_path.write_bytes(archive.read("security.log") if "security.log" in names else b"")

    def _pack(self) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in (self.db_path, self.schema_path, self.security_path):
                archive.write(path, path.name)
        return output.getvalue()

    def _encrypt(self) -> None:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        encrypted = AESGCM(self._derive_key(salt)).encrypt(nonce, self._pack(), MAGIC)
        temporary = VAULT_PATH.with_suffix(".vault.tmp")
        temporary.write_bytes(MAGIC + salt + nonce + encrypted)
        temporary.replace(VAULT_PATH)

    def _append_security(self, event: str, message: str) -> None:
        self.security_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().isoformat(timespec="microseconds")
        with self.security_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": timestamp, "event": event, "message": message}, ensure_ascii=False) + "\n")
