import json

import pytest

from guvenlik_baslatici.config import ConfigError, default_config_path, load_config


def test_missing_default_returns_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("GUVENLIK_BASLATICI_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_config().paths == {}


def test_missing_explicit_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GUVENLIK_BASLATICI_CONFIG", raising=False)
    with pytest.raises(ConfigError):
        load_config(tmp_path / "yok.json")


def test_missing_env_path_is_explicit_and_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GUVENLIK_BASLATICI_CONFIG", str(tmp_path / "yok.json"))
    with pytest.raises(ConfigError):
        load_config()


def test_valid_config(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"paths": {"nmap": "/opt/nmap"}}), encoding="utf-8")
    assert load_config(path).paths == {"nmap": "/opt/nmap"}


def test_explicit_tilde_path_is_expanded(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"paths": {"nmap": "~/nmap"}}), encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert load_config("~/c.json").paths == {"nmap": "~/nmap"}


def test_env_tilde_path_is_expanded(tmp_path, monkeypatch):
    path = tmp_path / "env.json"
    path.write_text(json.dumps({"paths": {"demo": "/tmp/demo"}}), encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("GUVENLIK_BASLATICI_CONFIG", "~/env.json")
    assert load_config().paths == {"demo": "/tmp/demo"}


@pytest.mark.parametrize(
    "content", ["{bozuk", "[]", '{"paths": []}', '{"paths": {"a": 1}}']
)
def test_invalid_config(tmp_path, content):
    path = tmp_path / "c.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_env_var_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("GUVENLIK_BASLATICI_CONFIG", str(tmp_path / "x.json"))
    assert default_config_path() == tmp_path / "x.json"


def test_invalid_encoding_is_config_error(tmp_path):
    path = tmp_path / "bad-encoding.json"
    path.write_bytes(b"{\xff\xfe")
    with pytest.raises(ConfigError, match="Yapılandırma okunamadı"):
        load_config(path)


def test_unknown_tool_key_is_accepted(tmp_path):
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps({"paths": {"future-tool": "/opt/future"}}), encoding="utf-8")
    assert load_config(path).paths == {"future-tool": "/opt/future"}


def test_windows_default_path(monkeypatch, tmp_path):
    monkeypatch.delenv("GUVENLIK_BASLATICI_CONFIG", raising=False)
    monkeypatch.setattr("guvenlik_baslatici.config.sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    assert default_config_path() == tmp_path / "AppData" / "guvenlik-baslatici" / "config.json"


def test_file_access_check_error_is_config_error(tmp_path, monkeypatch):
    from pathlib import Path

    def denied(path):
        raise PermissionError("erişim reddedildi")

    monkeypatch.setattr(Path, "is_file", denied)
    with pytest.raises(ConfigError, match="Yapılandırmaya erişilemedi"):
        load_config(tmp_path / "config.json")
