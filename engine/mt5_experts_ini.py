"""Localizar pasta de dados MT5 e ajustar [Experts] em config/common.ini (somente lógica + I/O explícito)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Chaves verificadas no build Clear 6286 (common.ini em %APPDATA%\\MetaQuotes\\Terminal\\<id>\\config\\).
# Referência MetaQuotes: seção [Experts] em common.ini (AllowLiveTrading, Enabled, Api).
EXPERTS_SECTION = "Experts"

# Permitir algotrading / negociação automática na plataforma (UI: «Permitir algotrading»).
KEY_ALLOW_LIVE_TRADING = "AllowLiveTrading"
# Uso de Expert Advisors na plataforma (MetaQuotes: Enabled).
KEY_ENABLED = "Enabled"
# API Python externa: Api=0 → opção «Desativar API Python externa» DESLIGADA (tradeapi_disabled=False neste build).
KEY_API = "Api"

TARGET_EXPERT_VALUES: dict[str, str] = {
    KEY_ALLOW_LIVE_TRADING: "1",
    KEY_ENABLED: "1",
    KEY_API: "0",
}

DOCUMENTED_EXPERT_KEYS = (
    KEY_ALLOW_LIVE_TRADING,
    KEY_ENABLED,
    KEY_API,
    "AllowDllImport",
    "Account",
    "Profile",
    "Chart",
)


@dataclass(frozen=True)
class TerminalDataFolder:
    data_dir: Path
    common_ini: Path
    origin_exe_dir: Path | None
    server: str | None


def default_metatrader_terminal_root() -> Path:
    appdata = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal"
    return appdata


def _read_ini_value(ini_text: str, section: str, key: str) -> str | None:
    in_section = False
    section_header = f"[{section}]"
    key_prefix = f"{key}="
    for line in ini_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped.lower() == section_header.lower()
            continue
        if in_section and stripped.startswith(key_prefix):
            return stripped[len(key_prefix) :].strip()
    return None


def detect_ini_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    return "utf-8"


def read_text_file(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    enc = detect_ini_encoding(raw)
    return raw.decode(enc), enc


def write_text_file(path: Path, text: str, encoding: str) -> None:
    if encoding == "utf-16":
        path.write_text(text, encoding="utf-16")
    else:
        path.write_text(text, encoding="utf-8")


def _parse_common_ini_meta(common_ini: Path) -> tuple[str | None, Path | None]:
    try:
        text, _enc = read_text_file(common_ini)
    except OSError:
        return None, None
    server = _read_ini_value(text, "Common", "Server")
    origin: Path | None = None
    origin_file = common_ini.parent.parent / "origin.txt"
    if origin_file.is_file():
        try:
            raw = origin_file.read_bytes()
            enc = detect_ini_encoding(raw)
            origin_raw = raw.decode(enc).strip()
        except OSError:
            origin_raw = ""
        if origin_raw:
            origin = Path(origin_raw)
    return server, origin


def _normalize_exe_dir(path: Path | str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        p = p.resolve()
    except OSError:
        p = p.absolute()
    return str(p).rstrip("\\/").lower()


def iter_terminal_data_folders(root: Path | None = None) -> Iterable[TerminalDataFolder]:
    base = root or default_metatrader_terminal_root()
    if not base.is_dir():
        return
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        common_ini = child / "config" / "common.ini"
        if not common_ini.is_file():
            continue
        server, origin = _parse_common_ini_meta(common_ini)
        yield TerminalDataFolder(
            data_dir=child,
            common_ini=common_ini,
            origin_exe_dir=origin,
            server=server,
        )


def find_terminal_data_folder(
    *,
    mt5_path: str | Path | None = None,
    server_substring: str | None = "ClearInvestimentos",
    data_dir_override: str | Path | None = None,
    root: Path | None = None,
) -> TerminalDataFolder | None:
    if data_dir_override:
        data = Path(data_dir_override)
        common_ini = data / "config" / "common.ini"
        if common_ini.is_file():
            server, origin = _parse_common_ini_meta(common_ini)
            return TerminalDataFolder(data, common_ini, origin, server)
        return None

    want_dir = _normalize_exe_dir(mt5_path)
    matches: list[TerminalDataFolder] = []
    for folder in iter_terminal_data_folders(root):
        if want_dir and _normalize_exe_dir(folder.origin_exe_dir) == want_dir:
            return folder
        if server_substring and folder.server and server_substring.lower() in folder.server.lower():
            matches.append(folder)
    if len(matches) == 1:
        return matches[0]
    if want_dir is None and matches:
        return matches[0]
    return None


def patch_common_ini_experts(ini_text: str) -> tuple[str, list[str]]:
    """
    Ajusta ou insere chaves em [Experts]. Retorna (novo_texto, lista de alterações human-readable).
    """
    lines = ini_text.splitlines(keepends=True)
    section_re = re.compile(r"^\[Experts\]\s*$", re.IGNORECASE)
    key_res = {
        key: re.compile(rf"^{re.escape(key)}=", re.IGNORECASE)
        for key in TARGET_EXPERT_VALUES
    }

    section_start: int | None = None
    section_end: int | None = None
    for idx, line in enumerate(lines):
        if section_re.match(line.rstrip("\r\n")):
            section_start = idx
            section_end = len(lines)
            for j in range(idx + 1, len(lines)):
                if lines[j].startswith("[") and j > idx:
                    section_end = j
                    break
            break

    changes: list[str] = []
    if section_start is None:
        block = [f"[{EXPERTS_SECTION}]\n"]
        for key, val in TARGET_EXPERT_VALUES.items():
            block.append(f"{key}={val}\n")
            changes.append(f"adicionou [{EXPERTS_SECTION}] {key}={val}")
        if ini_text and not ini_text.endswith(("\n", "\r\n")):
            lines.append("\n")
        lines.extend(block)
        return "".join(lines), changes

    key_line_index: dict[str, int] = {}
    for idx in range(section_start + 1, section_end or len(lines)):
        raw = lines[idx].rstrip("\r\n")
        for key, pattern in key_res.items():
            if pattern.match(raw):
                key_line_index[key] = idx

    for key, want in TARGET_EXPERT_VALUES.items():
        if key in key_line_index:
            idx = key_line_index[key]
            old_line = lines[idx].rstrip("\r\n")
            old_val = old_line.split("=", 1)[1].strip() if "=" in old_line else ""
            if old_val == want:
                continue
            lines[idx] = f"{key}={want}\n"
            changes.append(f"{key}: {old_val or '?'} → {want}")
        else:
            insert_at = section_end or len(lines)
            lines.insert(insert_at, f"{key}={want}\n")
            if section_end is not None:
                section_end += 1
            changes.append(f"inseriu {key}={want}")

    return "".join(lines), changes


def backup_common_ini(common_ini: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = common_ini.with_name(f"common.ini.bak-{stamp}")
    shutil.copy2(common_ini, dest)
    return dest


def read_experts_flags(common_ini: Path) -> dict[str, str | None]:
    """Lê chaves alvo em [Experts] (None se ausente ou arquivo ilegível)."""
    try:
        text, _enc = read_text_file(common_ini)
    except OSError:
        return {}
    return {key: _read_ini_value(text, EXPERTS_SECTION, key) for key in TARGET_EXPERT_VALUES}


def read_experts_flags_for_data_dir(data_dir: str | Path) -> dict[str, str | None]:
    common_ini = Path(data_dir) / "config" / "common.ini"
    if not common_ini.is_file():
        return {}
    return read_experts_flags(common_ini)


def apply_experts_ini_fix(
    common_ini: Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    text, encoding = read_text_file(common_ini)
    new_text, changes = patch_common_ini_experts(text)
    if not changes:
        return ["Nenhuma alteração necessária em [Experts]."]
    if dry_run:
        return [f"[dry-run] {c}" for c in changes]
    backup_common_ini(common_ini)
    write_text_file(common_ini, new_text, encoding)
    return changes


def normalize_terminal_executable(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.is_dir():
        exe = p / "terminal64.exe"
        if exe.is_file():
            p = exe
    try:
        p = p.resolve()
    except OSError:
        p = p.absolute()
    return str(p)


def paths_mismatch(configured: str | None, connected: str | None) -> bool:
    if not configured or not connected:
        return False
    a = _normalize_exe_dir(Path(configured).parent if Path(configured).name.lower() == "terminal64.exe" else configured)
    b = _normalize_exe_dir(Path(connected).parent if Path(connected).name.lower() == "terminal64.exe" else connected)
    if not a or not b:
        return False
    return a != b


def _windows_terminal64_processes() -> list[str]:
    """Caminhos de terminal64.exe em execução (Windows). Lista vazia fora do Windows ou se indisponível."""
    import subprocess
    import sys

    if sys.platform != "win32":
        return []
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" "
        "| ForEach-Object { $_.ExecutablePath }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def count_running_terminal64() -> int:
    return len(_windows_terminal64_processes())


def list_running_terminal64_paths() -> list[str]:
    return _windows_terminal64_processes()
