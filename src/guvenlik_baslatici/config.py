"""Yapılandırma dosyası okuma.

Biçim (JSON):
    {"paths": {"nmap": "/opt/nmap/bin/nmap", "ghidra": "~/ghidra/ghidraRun"}}
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

ENV_VAR = "GUVENLIK_BASLATICI_CONFIG"


class ConfigError(Exception):
    """Yapılandırma dosyası okunamadığında veya geçersiz olduğunda fırlatılır."""


@dataclass
class Config:
    paths: Dict[str, str] = field(default_factory=dict)


def _expand_path(value: str) -> Path:
    """Yapılandırma yollarında ortam değişkenlerini ve ``~`` işaretini açar."""
    return Path(os.path.expanduser(os.path.expandvars(value)))


def default_config_path() -> Path:
    env = os.environ.get(ENV_VAR)
    if env is not None:
        return _expand_path(env)
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return _expand_path(base) / "guvenlik-baslatici" / "config.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return _expand_path(base) / "guvenlik-baslatici" / "config.json"


def load_config(path: Optional[Path] = None) -> Config:
    """Yapılandırmayı yükler.

    path verilirse dosya mutlaka var olmalıdır. Verilmezse varsayılan konuma bakılır
    ve dosya yoksa boş yapılandırma döner.
    """
    env_path = os.environ.get(ENV_VAR)
    explicit = path is not None or env_path is not None
    try:
        config_path = _expand_path(os.fspath(path)) if path is not None else default_config_path()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise ConfigError("Yapılandırma yolu geçersiz: %s" % error) from error
    try:
        is_file = config_path.is_file()
    except (OSError, ValueError) as error:
        raise ConfigError("Yapılandırmaya erişilemedi: %s" % error) from error
    if not is_file:
        if explicit:
            raise ConfigError("Yapılandırma dosyası bulunamadı: %s" % config_path)
        return Config()
    try:
        text = config_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, TypeError, UnicodeError, ValueError) as error:
        raise ConfigError("Yapılandırma okunamadı (%s): %s" % (config_path, error)) from error
    if not isinstance(data, dict):
        raise ConfigError("Yapılandırmanın kökü bir JSON nesnesi olmalı.")
    paths = data.get("paths", {})
    if not isinstance(paths, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in paths.items()
    ):
        raise ConfigError('"paths" alanı {"araç": "yol"} biçiminde olmalı.')
    return Config(paths=dict(paths))
