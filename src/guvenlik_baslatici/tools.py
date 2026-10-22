"""Desteklenen araçların kaydı."""

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class Tool:
    """Komut adları ve olası yerel kurulum yollarıyla bir araç tanımı.

    web araçlarında komutlar yalnızca tespit için kullanılır; başlatıcı
    servis çalıştırmaz. Bir bileşenin bulunması tam kurulum kanıtı değildir.
    """

    key: str
    name: str
    commands: Tuple[str, ...]
    description: str
    web: bool = False
    windows_paths: Tuple[str, ...] = ()
    search_paths: Tuple[str, ...] = ()


TOOLS = (
    Tool("nmap", "Nmap", ("nmap",), "Ağ keşfi ve TCP/UDP port kontrolü",
         windows_paths=(r"%ProgramFiles(x86)%\Nmap\nmap.exe", r"%ProgramFiles%\Nmap\nmap.exe")),
    Tool("wireshark", "Wireshark", ("wireshark",), "Ağ paketlerini grafik arayüzde inceleme",
         windows_paths=(r"%ProgramFiles%\Wireshark\Wireshark.exe",)),
    Tool("burp", "Burp Suite", ("burpsuite", "burp"), "Web uygulaması güvenlik testi",
         windows_paths=(r"%ProgramFiles%\BurpSuiteCommunity\BurpSuiteCommunity.exe",
                        r"%ProgramFiles%\BurpSuitePro\BurpSuitePro.exe")),
    Tool("zap", "OWASP ZAP", ("zaproxy", "zap.sh", "zap"), "Web uygulaması güvenlik testi",
         windows_paths=(r"%ProgramFiles%\ZAP\Zed Attack Proxy\zap.bat",)),
    Tool("metasploit", "Metasploit Framework", ("msfconsole",), "Kontrollü güvenlik testi konsolu"),
    Tool("nessus", "Nessus", ("nessuscli", "nessusd"), "Kendi Nessus web arayüzünü açma",
         web=True, search_paths=("/opt/nessus/sbin/nessuscli", "/opt/nessus/sbin/nessusd")),
    Tool("openvas", "OpenVAS / Greenbone", ("gsad", "gvmd", "openvas"),
         "Kendi Greenbone web arayüzünü açma", web=True),
    Tool("nikto", "Nikto", ("nikto",), "Web sunucusu güvenlik kontrolleri"),
    Tool("sqlmap", "sqlmap", ("sqlmap",), "İzinli SQL enjeksiyonu testleri"),
    Tool("gobuster", "Gobuster", ("gobuster",), "Web ve DNS keşfi"),
    Tool("ffuf", "ffuf", ("ffuf",), "Web girdi ve uç nokta testleri"),
    Tool("wfuzz", "Wfuzz", ("wfuzz",), "Web uygulaması girdi testleri"),
    Tool("john", "John the Ripper", ("john",), "Parola özeti dayanıklılık denetimi"),
    Tool("hashcat", "Hashcat", ("hashcat",), "Parola özeti dayanıklılık denetimi"),
    Tool("aircrack", "Aircrack-ng", ("aircrack-ng",), "İzinli kablosuz ağ güvenlik testleri"),
    Tool("kismet", "Kismet", ("kismet",), "Kablosuz ağ inceleme"),
    Tool("tcpdump", "tcpdump", ("tcpdump",), "Komut satırından paket yakalama"),
    Tool("netcat", "Netcat", ("nc", "ncat", "netcat"), "Ağ bağlantısı testi ve veri aktarımı",
         windows_paths=(r"%ProgramFiles(x86)%\Nmap\ncat.exe",
                        r"%ProgramFiles%\Nmap\ncat.exe")),
    Tool("ghidra", "Ghidra", ("ghidraRun", "ghidra"), "Programların tersine mühendislik analizi"),
    Tool("volatility", "Volatility", ("vol", "volatility3", "volatility"),
         "Bellek dökümü adli analizi"),
)


def get_tool(selector: str, tools: Sequence[Tool] = TOOLS) -> Tool:
    """Verilen listenin 1 tabanlı numarasını veya araç anahtarını çöz."""
    selector = selector.strip().lower()
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(tools):
            return tools[index - 1]
    for tool in tools:
        if tool.key == selector:
            return tool
    raise ValueError("Geçersiz araç. Gösterilen listedeki numara veya araç anahtarını kullan.")
