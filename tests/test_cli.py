import json

import pytest

from guvenlik_baslatici import cli, core
from guvenlik_baslatici.config import Config
from guvenlik_baslatici.tools import get_tool


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GUVENLIK_BASLATICI_CONFIG", str(config))
    monkeypatch.setattr(cli, "find_executable", lambda *args: None)


def detect(monkeypatch, *keys):
    monkeypatch.setattr(
        cli, "find_executable",
        lambda tool, *args: "/test/" + tool.commands[0] if tool.key in keys else None,
    )


def capture_launch(monkeypatch, exit_code=0):
    seen = {}

    def fake(tool, args, **kwargs):
        seen.update(tool=tool.key, args=list(args), **kwargs)
        return exit_code

    monkeypatch.setattr(cli, "launch", fake)
    return seen


def test_list_text_hides_missing(capsys, monkeypatch):
    detect(monkeypatch, "hashcat", "volatility")
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert " 1. Hashcat" in out and " 2. Volatility" in out
    assert "Nmap" not in out and "Nessus" not in out


def test_list_empty(capsys):
    assert cli.main(["list"]) == 0
    assert "hiçbiri tespit edilemedi" in capsys.readouterr().out


def test_list_json(capsys, monkeypatch):
    detect(monkeypatch, "nmap")
    assert cli.main(["list", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["index"] == 1
    assert rows[0]["key"] == "nmap"
    assert rows[0]["path"] == "/test/nmap"


def test_list_empty_json(capsys):
    assert cli.main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


@pytest.mark.parametrize("key", ["nessus", "openvas"])
def test_web_tools_only_listed_when_detected(key, monkeypatch, capsys):
    detect(monkeypatch, key)
    assert cli.main(["list", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["key"] for row in rows] == [key]
    assert rows[0]["web"] is True
    assert rows[0]["path"]


def test_detection_uses_core_without_starting_programs(monkeypatch):
    monkeypatch.setattr(cli, "find_executable", core.find_executable)
    monkeypatch.setattr(core, "_resolve", lambda c: "/bin/nmap" if c == "nmap" else None)
    monkeypatch.setattr(core.shutil, "which", lambda c: "/bin/nmap" if c == "nmap" else None)
    assert [tool.key for tool in cli.installed_tools(Config())] == ["nmap"]


def test_run_forwards_args_after_double_dash(monkeypatch):
    seen = capture_launch(monkeypatch)
    assert cli.main(["run", "nmap", "--", "-p", "80,443", "127.0.0.1"]) == 0
    assert seen["tool"] == "nmap"
    assert seen["args"] == ["-p", "80,443", "127.0.0.1"]


@pytest.mark.parametrize("argv", [
    ["run", "nessus", "--url", "https://127.0.0.1:8834"],
    ["run", "--url", "https://127.0.0.1:8834", "nessus"],
])
def test_url_option_before_or_after_tool(argv, monkeypatch):
    seen = capture_launch(monkeypatch)
    assert cli.main(argv) == 0
    assert seen["url"] == "https://127.0.0.1:8834"
    assert seen["args"] == []


@pytest.mark.parametrize("argv", [
    ["run", "ghidra", "--exec", "/opt/a b/ghidraRun", "--", "--help"],
    ["run", "--exec", "/opt/a b/ghidraRun", "ghidra", "--", "--help"],
])
def test_exec_option_before_or_after_tool(argv, monkeypatch):
    seen = capture_launch(monkeypatch)
    assert cli.main(argv) == 0
    assert seen["override"] == "/opt/a b/ghidraRun"
    assert seen["args"] == ["--help"]


def test_options_after_boundary_are_forwarded_not_interpreted(monkeypatch):
    seen = capture_launch(monkeypatch)
    assert cli.main(["run", "nmap", "--", "--exec", "x", "--url", "y", "--"]) == 0
    assert seen["args"] == ["--exec", "x", "--url", "y", "--"]
    assert seen["override"] is None and seen["url"] is None


def test_config_paths_forwarded(tmp_path, monkeypatch):
    path = tmp_path / "custom.json"
    path.write_text('{"paths": {"nmap": "/custom/nmap"}}', encoding="utf-8")
    seen = capture_launch(monkeypatch)
    assert cli.main(["--config", str(path), "run", "nmap"]) == 0
    assert seen["config_paths"] == {"nmap": "/custom/nmap"}


def test_run_by_filtered_number(monkeypatch):
    detect(monkeypatch, "hashcat", "volatility")
    seen = capture_launch(monkeypatch)
    assert cli.main(["run", "1"]) == 0
    assert seen["tool"] == "hashcat"
    assert cli.main(["run", "2"]) == 0
    assert seen["tool"] == "volatility"


@pytest.mark.parametrize("argv", [
    ["run", "yok"], ["run", "1"], ["run", "nmap", "-p", "80"],
    ["list", "--", "x"],
])
def test_invalid_cli_exits_2(argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2


@pytest.mark.parametrize("code", [1, 2, 127, 130])
def test_run_exit_codes_preserved(code, monkeypatch):
    capture_launch(monkeypatch, code)
    assert cli.main(["run", "nmap"]) == code


def test_bad_config_returns_usage_error(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{bozuk", encoding="utf-8")
    assert cli.main(["--config", str(bad), "list"]) == 2
    assert "Hata" in capsys.readouterr().err


def test_missing_env_config_returns_usage_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GUVENLIK_BASLATICI_CONFIG", str(tmp_path / "missing.json"))
    assert cli.main(["list"]) == 2
    assert "Hata" in capsys.readouterr().err


def test_no_command_non_tty_lists(capsys, monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main([]) == 0
    assert "hiçbiri tespit edilemedi" in capsys.readouterr().out


def test_menu_quit_and_invalid(capsys):
    answers = iter(["999", "", "nmap", "", "q"])
    assert cli.menu(Config(), input_fn=lambda prompt: next(answers)) == 0
    assert "Geçersiz araç" in capsys.readouterr().out


@pytest.mark.parametrize("code", [0, 1, 2, 127, 130])
def test_menu_launches_and_preserves_last_exit(code, monkeypatch):
    detect(monkeypatch, "hashcat")
    seen = capture_launch(monkeypatch, code)
    answers = iter(["1", "--help", "", "q"])
    assert cli.menu(Config(), input_fn=lambda prompt: next(answers)) == code
    assert seen["tool"] == "hashcat" and seen["args"] == ["--help"]


def test_menu_refresh_and_automatic_redetection(monkeypatch):
    calls = []
    states = iter([(), (get_tool("hashcat"),), (get_tool("nmap"),)])

    def discover(config):
        calls.append(True)
        return next(states)

    monkeypatch.setattr(cli, "installed_tools", discover)
    seen = capture_launch(monkeypatch)
    answers = iter(["r", "1", "", "", "q"])
    assert cli.menu(Config(), input_fn=lambda prompt: next(answers)) == 0
    assert len(calls) == 3 and seen["tool"] == "hashcat"


def test_menu_unclosed_quotes_does_not_launch(monkeypatch, capsys):
    detect(monkeypatch, "nmap")
    seen = capture_launch(monkeypatch)
    answers = iter(["1", "'", "", "q"])
    assert cli.menu(Config(), input_fn=lambda prompt: next(answers)) == 0
    assert not seen
    assert "çözümlenemedi" in capsys.readouterr().out


def test_menu_web_url_forwarded(monkeypatch):
    detect(monkeypatch, "nessus")
    seen = capture_launch(monkeypatch)
    answers = iter(["1", "https://127.0.0.1:8834", "", "q"])
    assert cli.menu(Config(), input_fn=lambda prompt: next(answers)) == 0
    assert seen["url"] == "https://127.0.0.1:8834" and seen["args"] == []


def test_menu_interrupt_returns_130():
    def interrupt(prompt):
        raise KeyboardInterrupt

    assert cli.menu(Config(), input_fn=interrupt) == 130


def test_menu_eof_returns_zero_without_launch():
    def eof(prompt):
        raise EOFError

    assert cli.menu(Config(), input_fn=eof) == 0


def test_main_interrupt_returns_130(monkeypatch):
    def interrupt(argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_main", interrupt)
    assert cli.main([]) == 130


def test_version_matches(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "1.1.0" in capsys.readouterr().out


def test_broken_pipe_is_swallowed_and_fd_closed(monkeypatch):
    def boom(argv=None):
        raise BrokenPipeError

    closed = []
    monkeypatch.setattr(cli, "_main", boom)
    monkeypatch.setattr(cli.os, "open", lambda *a, **k: 123)
    monkeypatch.setattr(cli.os, "dup2", lambda *a, **k: None)
    monkeypatch.setattr(cli.os, "close", lambda fd: closed.append(fd))
    assert cli.main(["list"]) == 0
    assert closed == [123]
