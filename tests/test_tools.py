import pytest

from guvenlik_baslatici.tools import TOOLS, get_tool


def test_twenty_tools_with_unique_keys():
    assert len(TOOLS) == 20
    assert len({tool.key for tool in TOOLS}) == 20


@pytest.mark.parametrize("selector, key", [
    ("1", "nmap"), ("20", "volatility"), ("NMAP", "nmap"), (" sqlmap ", "sqlmap"),
])
def test_get_tool_valid(selector, key):
    assert get_tool(selector).key == key


@pytest.mark.parametrize("selector", ["0", "21", "", "yok", "-1"])
def test_get_tool_invalid(selector):
    with pytest.raises(ValueError):
        get_tool(selector)


def test_all_tools_have_detection_commands():
    assert all(tool.commands for tool in TOOLS)


def test_get_tool_filtered_numbering():
    tools = (get_tool("hashcat"), get_tool("volatility"))
    assert get_tool("1", tools).key == "hashcat"
    assert get_tool("2", tools).key == "volatility"
    assert get_tool("volatility", tools).key == "volatility"
    with pytest.raises(ValueError):
        get_tool("nmap", tools)
    with pytest.raises(ValueError):
        get_tool("3", tools)


def test_get_tool_empty_list():
    with pytest.raises(ValueError):
        get_tool("1", ())


def test_nessus_has_standard_linux_detection_path():
    assert "/opt/nessus/sbin/nessuscli" in get_tool("nessus").search_paths
