"""Çekirdek mantık: araç bulma, URL doğrulama ve başlatma.

Bu modül hiçbir hedefi kendiliğinden taramaz; araçlara yalnızca kullanıcının verdiği
argümanlar iletilir ve komut shell üzerinden çalıştırılmaz (shell=False).
"""

import ipaddress
import logging
import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from typing import Dict, Optional, Sequence
from urllib.parse import urlparse

from .tools import Tool

log = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 127
EXIT_INTERRUPTED = 130


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


def _expand_candidate(candidate: str) -> str:
    """Ortam değişkenlerini ve kullanıcı dizini kısaltmasını genişletir."""
    return os.path.expanduser(os.path.expandvars(candidate))


def _is_executable(candidate: str) -> bool:
    """Bir adayın gerçekten çalıştırılabilir normal bir dosya olduğunu doğrular."""
    try:
        expanded = _expand_candidate(candidate)
        return os.path.isfile(expanded) and os.access(expanded, os.X_OK)
    except (OSError, TypeError):
        return False


def _resolve(candidate: str) -> Optional[str]:
    """Bir komut veya yolu çözer; yerel dizindeki komutları mutlak döndürür."""
    if not isinstance(candidate, str) or "\x00" in candidate:
        return None
    expanded = _expand_candidate(candidate)
    if not expanded:
        return None

    # Çıplak bir komut yerel dizinde varsa PATH'teki başka bir dosyaya geçme.
    if os.path.isfile(expanded):
        if os.access(expanded, os.X_OK):
            return os.path.abspath(expanded)
        return None

    # Eğik çizgi içeren adaylar yol olarak kabul edilir; bunları PATH'te aramak,
    # özellikle bozuk --exec/config değerlerinde beklenmedik fallback yaratır.
    if os.path.isabs(expanded) or os.sep in expanded or (os.altsep and os.altsep in expanded):
        return None
    return shutil.which(expanded)


def find_executable(
    tool: Tool,
    override: Optional[str] = None,
    config_paths: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Aracın çalıştırılabilir dosyasını sırayla arar.

    Sıra: --exec, yapılandırma, PATH, platforma özgü arama yolları ve Windows yolları.
    --exec verilip bulunamazsa başka yere bakılmaz.
    """
    if override is not None:
        return _resolve(override)

    configured = (config_paths or {}).get(tool.key)
    if configured is not None:
        found = _resolve(configured)
        if found:
            log.debug("%s yapılandırmadan bulundu: %s", tool.key, found)
            return found
        log.warning("%s için yapılandırmadaki yol geçersiz: %s", tool.key, configured)

    for command in tool.commands:
        # Otomatik keşifte mevcut dizini PATH dışında ayrıca tercih etme.
        # Yerel yollar ancak --exec/config ile açıkça belirtildiğinde çözülür.
        found = shutil.which(command)
        if found:
            found = os.path.abspath(found)
            log.debug("%s PATH'te bulundu: %s", tool.key, found)
            return found

    for candidate in getattr(tool, "search_paths", ()):
        found = _resolve(candidate)
        if found:
            log.debug("%s bilinen kurulum yolunda bulundu: %s", tool.key, found)
            return found

    if sys.platform.startswith("win"):
        for candidate in getattr(tool, "windows_paths", ()):
            found = _resolve(candidate)
            if found:
                log.debug("%s bilinen Windows yolunda bulundu: %s", tool.key, found)
                return found
    return None


def is_valid_web_url(url: str) -> bool:
    """Yalnızca güvenli, geçerli portlu http/https adreslerini kabul eder."""
    if not isinstance(url, str) or not url:
        return False
    if any(
        character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
        for character in url
    ):
        return False
    try:
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or "@" in parts.netloc:
            return False
        hostname = parts.hostname
        if not hostname:
            return False

        # .port, sayısal olmayan ve aralık dışındaki portları ValueError ile bildirir.
        parts.port  # noqa: B018 - geçersiz port ValueError fırlatır
        netloc = parts.netloc
        if netloc.startswith("["):
            closing_bracket = netloc.find("]")
            if closing_bracket < 0:
                return False
            suffix = netloc[closing_bracket + 1 :]
            if suffix and (not suffix.startswith(":") or suffix == ":"):
                return False
            try:
                ipaddress.IPv6Address(hostname)
            except ValueError:
                return False
        elif ":" in netloc:
            # IPv6 adresleri köşeli parantezle yazılmalıdır; boş port da geçersizdir.
            if netloc.count(":") != 1 or netloc.rsplit(":", 1)[1] == "":
                return False
        return True
    except (ValueError, UnicodeError):
        return False


def launch(
    tool: Tool,
    args: Sequence[str] = (),
    *,
    override: Optional[str] = None,
    url: Optional[str] = None,
    config_paths: Optional[Dict[str, str]] = None,
) -> int:
    """Aracı başlatır veya web arayüzünü açar. Çıkış kodunu döndürür."""
    if tool.web:
        return _open_web(tool, args, override, url)

    if url:
        _eprint("--url yalnızca Nessus veya OpenVAS için kullanılabilir.")
        return EXIT_USAGE

    executable = find_executable(tool, override, config_paths)
    if not executable or not _is_executable(executable):
        _eprint("%s çalıştırılabilir dosyası bulunamadı." % tool.name)
        _eprint("Aracı kur, yapılandırma dosyasında yolunu belirt veya --exec kullan.")
        return EXIT_NOT_FOUND

    command = [executable] + list(args)
    print("Çalıştırılıyor: " + " ".join(shlex.quote(part) for part in command), flush=True)
    try:
        returncode = subprocess.run(command, shell=False).returncode
        if returncode < 0:
            return 128 + (-returncode)
        return returncode
    except KeyboardInterrupt:
        print("\nİşlem kesildi.")
        return EXIT_INTERRUPTED
    except OSError as error:
        _eprint("Başlatılamadı: %s" % error)
        return EXIT_ERROR


def _open_web(tool: Tool, args: Sequence[str], override: Optional[str], url: Optional[str]) -> int:
    if override is not None or args:
        _eprint("Web arayüzü araçları için --exec veya komut argümanı değil, --url kullan.")
        return EXIT_USAGE
    if not url:
        _eprint("Kendi kurulumunun adresini --url ile belirt. Servis önceden çalışıyor olmalı.")
        return EXIT_USAGE
    if not is_valid_web_url(url):
        _eprint("Geçerli bir http:// veya https:// adresi kullan.")
        return EXIT_USAGE
    print("Web arayüzü: %s" % url)
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as error:  # Tarayıcı sağlayıcısı platforma göre farklı istisnalar verir.
        _eprint("Tarayıcı açılamadı: %s" % error)
        return EXIT_ERROR
    if not opened:
        print("Tarayıcı açılamadı; yukarıdaki adresi kendi tarayıcında aç.")
    return EXIT_OK
