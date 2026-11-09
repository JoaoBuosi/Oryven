"""Protect the Oryven persistent device-session token.

On Windows this uses CryptProtectData/CryptUnprotectData (DPAPI) for the current
Windows user. Tests/non-Windows use a chmod-600 file fallback only.
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path


class DeviceVaultError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


class DeviceSessionVault:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _protect_windows(self, raw: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob, backing = _blob(raw)
        out_blob = DATA_BLOB()
        if not crypt32.CryptProtectData(ctypes.byref(in_blob), "Oryven device session", None, None, None, 0, ctypes.byref(out_blob)):
            raise DeviceVaultError("DPAPI não conseguiu proteger a sessão.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
            _ = backing

    def _unprotect_windows(self, raw: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        in_blob, backing = _blob(raw)
        out_blob = DATA_BLOB()
        if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            raise DeviceVaultError("DPAPI não conseguiu restaurar a sessão.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
            _ = backing

    def save(self, token: str) -> None:
        raw = token.encode("utf-8")
        protected = self._protect_windows(raw) if sys.platform == "win32" else raw
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_bytes(protected)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def load(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            raw = self.path.read_bytes()
            plain = self._unprotect_windows(raw) if sys.platform == "win32" else raw
            value = plain.decode("utf-8")
            return value if value else None
        except (OSError, UnicodeError, DeviceVaultError):
            return None

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise DeviceVaultError("Não foi possível limpar a sessão persistente.") from exc
