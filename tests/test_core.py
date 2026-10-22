import stat
from types import SimpleNamespace

import pytest

from guvenlik_baslatici import core
from guvenlik_baslatici.core import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_USAGE,
    _resolve,
    find_executable,
    is_valid_web_url,
    launch,
)
from guvenlik_baslatici.tools import get_tool


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8834",
        "https://localhost",
        "https://[::1]:443/x?next=https%3A%2F%2Fexample.test#fragment",
    ],
)
def test_valid_urls(url):
    assert is_valid_web_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://x",
        "javascript:alert(1)",
        "https://",
        "http://h:99999",
        "http://h:abc",
        "http://h:",
        "http://[not-an-ipv6]",
        "http://[::1",
        "http://user:password@example.test",
        "http://@example.test",
        "http://example.test/a path",
        "http://example.test/\nnext",
        "127.0.0.1:8834",
    ],
)
def test_invalid_urls(url):
    assert not is_valid_web_url(url)


def _make_exe(tmp_path, name="fake", content="#!/bin/sh\nexit 0\n"):
    path = tmp_path / name
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def _fake_tool(**overrides):
    values = {
        "key": "demo",
        "name": "Demo",
        "commands": ("demo",),
        "search_paths": (),
        "windows_paths": (),
        "web": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_find_uses_path(monkeypatch, tmp_path):
    path = _make_exe(tmp_path, "path-demo")
    monkeypatch.setattr(core.shutil, "which", lambda command: path if command == "demo" else None)
    assert find_executable(_fake_tool()) == path


def test_find_override_does_not_fall_back(monkeypatch):
    calls = []

    def fake_which(command):
        calls.append(command)
        return "/usr/bin/demo"

    monkeypatch.setattr(core.shutil, "which", fake_which)
    assert find_executable(_fake_tool(), override="/yok/olmayan/demo") is None
    assert find_executable(_fake_tool(), override="") is None
    assert calls == []


def test_find_priority_override_then_config_then_path_then_search(tmp_path, monkeypatch):
    override = _make_exe(tmp_path, "override")
    configured = _make_exe(tmp_path, "configured")
    path_exe = _make_exe(tmp_path, "path")
    search = _make_exe(tmp_path, "search")
    tool = _fake_tool(search_paths=(search,))
    monkeypatch.setattr(core.shutil, "which", lambda command: path_exe)

    assert find_executable(tool, override=override, config_paths={"demo": configured}) == override
    assert find_executable(tool, config_paths={"demo": configured}) == configured
    assert find_executable(tool) == path_exe

    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    assert find_executable(tool) == search


def test_find_invalid_config_warns_then_falls_back(tmp_path, monkeypatch, caplog):
    path_exe = _make_exe(tmp_path, "path")
    monkeypatch.setattr(core.shutil, "which", lambda command: path_exe)
    result = find_executable(
        _fake_tool(), config_paths={"demo": str(tmp_path / "missing-demo")}
    )
    assert result == path_exe
    assert "yapılandırmadaki yol geçersiz" in caplog.text


def test_find_search_paths_before_windows_paths(tmp_path, monkeypatch):
    search = _make_exe(tmp_path, "search")
    windows = _make_exe(tmp_path, "windows")
    tool = _fake_tool(search_paths=(search,), windows_paths=(windows,))
    monkeypatch.setattr(core.sys, "platform", "win32")
    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    assert find_executable(tool) == search


def test_find_windows_path_branch(tmp_path, monkeypatch):
    windows = _make_exe(tmp_path, "windows")
    tool = _fake_tool(windows_paths=(windows,))
    monkeypatch.setattr(core.sys, "platform", "win32")
    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    assert find_executable(tool) == windows


def test_resolve_expands_environment_and_tilde(tmp_path, monkeypatch):
    exe = _make_exe(tmp_path, "env-demo")
    monkeypatch.setenv("DEMO_EXECUTABLE", exe)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert _resolve("$DEMO_EXECUTABLE") == exe
    assert _resolve("~/env-demo") == exe


def test_resolve_local_naked_and_metacharacter_executable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    name = "local;demo"
    _make_exe(tmp_path, name)
    assert _resolve(name) == str((tmp_path / name).resolve())


def test_find_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    assert find_executable(_fake_tool()) is None


def test_launch_not_found_and_does_not_run(monkeypatch, capsys):
    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: pytest.fail("çalıştırılmamalı"))
    assert launch(_fake_tool()) == EXIT_NOT_FOUND
    assert "bulunamadı" in capsys.readouterr().err


def test_launch_checks_executable_before_running(monkeypatch):
    monkeypatch.setattr(core, "find_executable", lambda *a, **k: "/tmp/not-an-executable")
    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: pytest.fail("çalıştırılmamalı"))
    assert launch(_fake_tool()) == EXIT_NOT_FOUND


def test_launch_passes_args_without_shell_and_normalizes_signal(tmp_path, monkeypatch):
    executable = _make_exe(tmp_path, "fake;tool")
    calls = {}

    class Result:
        returncode = -9

    def fake_run(command, **kwargs):
        calls["command"], calls["kwargs"] = command, kwargs
        return Result()

    monkeypatch.setattr(core.subprocess, "run", fake_run)
    code = launch(_fake_tool(), ["-p", "80; rm -rf /", "127.0.0.1"], override=executable)
    assert code == 137
    assert calls["command"] == [executable, "-p", "80; rm -rf /", "127.0.0.1"]
    assert calls["kwargs"]["shell"] is False


def test_launch_keyboard_interrupt(tmp_path, monkeypatch):
    executable = _make_exe(tmp_path)

    def boom(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(core.subprocess, "run", boom)
    assert launch(_fake_tool(), override=executable) == EXIT_INTERRUPTED


def test_launch_oserror(tmp_path, monkeypatch):
    executable = _make_exe(tmp_path)

    def boom(*args, **kwargs):
        raise PermissionError("izin yok")

    monkeypatch.setattr(core.subprocess, "run", boom)
    assert launch(_fake_tool(), override=executable) == EXIT_ERROR


def test_url_rejected_for_normal_tool():
    assert launch(_fake_tool(), url="http://x") == EXIT_USAGE


def test_web_tool_requires_url():
    assert launch(get_tool("nessus")) == EXIT_USAGE


def test_web_tool_rejects_args_and_exec():
    assert launch(get_tool("nessus"), ["x"], url="https://127.0.0.1:8834") == EXIT_USAGE
    assert launch(get_tool("nessus"), override="x", url="https://127.0.0.1:8834") == EXIT_USAGE


def test_invalid_web_url_does_not_call_browser(monkeypatch):
    monkeypatch.setattr(
        core.webbrowser, "open", lambda *args, **kwargs: pytest.fail("tarayıcı çağrılmamalı")
    )
    assert launch(get_tool("openvas"), url="https://user:pass@example.test") == EXIT_USAGE


def test_web_tool_browser_success(monkeypatch):
    opened = []
    monkeypatch.setattr(core.webbrowser, "open", lambda url, new=0: opened.append(url) or True)
    assert launch(get_tool("openvas"), url="https://127.0.0.1:9392?ui=1#home") == EXIT_OK
    assert opened == ["https://127.0.0.1:9392?ui=1#home"]


def test_web_tool_browser_false_is_manual_success(monkeypatch, capsys):
    monkeypatch.setattr(core.webbrowser, "open", lambda url, new=0: False)
    assert launch(get_tool("openvas"), url="https://127.0.0.1:9392") == EXIT_OK
    assert "https://127.0.0.1:9392" in capsys.readouterr().out


def test_web_tool_browser_exception_is_error(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("browser unavailable")

    monkeypatch.setattr(core.webbrowser, "open", boom)
    assert launch(get_tool("openvas"), url="https://127.0.0.1:9392") == EXIT_ERROR
    assert "Tarayıcı açılamadı" in capsys.readouterr().err


def test_automatic_detection_does_not_prefer_current_directory(tmp_path, monkeypatch):
    local = tmp_path / "local"
    system = tmp_path / "system"
    local.mkdir()
    system.mkdir()
    _make_exe(local, "demo")
    expected = _make_exe(system, "demo")
    monkeypatch.chdir(local)
    monkeypatch.setattr(core.shutil, "which", lambda command: expected)
    assert find_executable(_fake_tool()) == expected


def test_resolve_null_byte_is_rejected():
    assert _resolve("bad\x00path") is None


def test_nessus_detected_from_standard_search_path(tmp_path, monkeypatch):
    executable = _make_exe(tmp_path, "nessuscli")
    monkeypatch.setattr(core.shutil, "which", lambda command: None)
    tool = _fake_tool(commands=("nessuscli",), search_paths=(executable,), web=True)
    assert find_executable(tool) == executable
