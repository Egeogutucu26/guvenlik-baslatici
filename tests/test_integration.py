"""Gerçek güvenlik araçları/ağ kullanmadan modül ve alt süreç duman testleri."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def clean_env(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["GUVENLIK_BASLATICI_CONFIG"] = str(config)
    return env


def invoke(env, *args):
    return subprocess.run(
        [sys.executable, "-m", "guvenlik_baslatici", *args],
        env=env, capture_output=True, text=True, timeout=10, shell=False,
    )


def test_module_version(clean_env):
    result = invoke(clean_env, "--version")
    assert result.returncode == 0
    assert "1.1.0" in result.stdout


def test_exec_after_tool_runs_python_and_preserves_literal_arguments(clean_env):
    argument = "hello world; $(echo NOT_EXECUTED) & literal"
    result = invoke(
        clean_env, "run", "nmap", "--exec", sys.executable, "--",
        "-c", "import json, sys; print(json.dumps(sys.argv[1:]))", argument,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == [argument]


def test_explicit_override_not_found(clean_env, tmp_path):
    result = invoke(clean_env, "run", "nmap", "--exec", str(tmp_path / "missing-tool"))
    assert result.returncode == 127
    assert "bulunamadı" in result.stderr


def test_url_after_tool_reaches_url_validator(clean_env):
    result = invoke(clean_env, "run", "nessus", "--url", "file:///tmp/not-a-web-url")
    assert result.returncode == 2
    assert "http://" in result.stderr
    assert "komut argümanı" not in result.stderr


def test_native_exit_code_preserved(clean_env):
    result = invoke(
        clean_env, "run", "nmap", "--exec", sys.executable, "--",
        "-c", "import sys; sys.exit(7)",
    )
    assert result.returncode == 7
