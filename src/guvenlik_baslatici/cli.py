"""Komut satırı arayüzü."""

import argparse
import json
import logging
import os
import shlex
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import __version__
from .config import Config, ConfigError, load_config
from .core import EXIT_INTERRUPTED, EXIT_OK, EXIT_USAGE, find_executable, launch
from .tools import TOOLS, Tool, get_tool

NOTICE = "Yalnızca kendi sistemlerinde veya açıkça izin verilen hedeflerde kullan."

EPILOG = """Örnekler:
  guvenlik-baslatici                       etkileşimli menü
  guvenlik-baslatici list                  yalnızca tespit edilen araçlar
  guvenlik-baslatici list --json           aynı listeyi JSON olarak yazdır
  guvenlik-baslatici run nmap -- --help    araca argüman ilet (-- ile ayır)
  guvenlik-baslatici run nessus --url https://127.0.0.1:8834
  guvenlik-baslatici run ghidra --exec ~/ghidra/ghidraRun

Başlatıcı seçenekleri -- öncesine, aracın kendi argümanları -- sonrasına yazılır.
Sıra numaraları list çıktısına bağlıdır; sabit araç anahtarlarını tercih et.
"""


def installed_tools(config: Config) -> Tuple[Tool, ...]:
    """Hiçbir program çalıştırmadan tespit edilen araçları döndür."""
    return tuple(tool for tool in TOOLS if find_executable(tool, None, config.paths))


def _status(tool: Tool) -> str:
    return "web — servis durumu kontrol edilmedi" if tool.web else "bulundu"


def print_list(config: Config, tools=None) -> Tuple[Tool, ...]:
    if tools is None:
        tools = installed_tools(config)
    print("\nKURULU GÜVENLİK ARAÇLARI — YEREL BAŞLATICI")
    print(NOTICE + "\n")
    for index, tool in enumerate(tools, 1):
        print("%2d. %-22s [%s] %s" % (index, tool.name, tool.key, _status(tool)))
    if tools:
        print("\nTespit edilen araç sayısı: %d" % len(tools))
    else:
        print("Desteklenen 20 araçtan hiçbiri tespit edilemedi.")
        print("Kurulu bir araç görünmüyorsa PATH'e ekle veya yapılandırmada yolunu belirt.")
    print("Tespit: yapılandırma, PATH ve tanımlı kurulum yolları; tam disk taraması yapılmaz.")
    print("Bu araç eksik programları kurmaz ve servisleri başlatmaz.")
    return tools


def list_json(config: Config) -> str:
    rows = [
        {
            "index": index,
            "key": tool.key,
            "name": tool.name,
            "description": tool.description,
            "web": tool.web,
            "path": find_executable(tool, None, config.paths),
        }
        for index, tool in enumerate(installed_tools(config), 1)
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2)


def menu(config: Config, input_fn: Callable[[str], str] = input) -> int:
    last_exit = EXIT_OK
    try:
        while True:
            # Gösterilen anlık liste ile seçimler aynı numaraları kullanır.
            tools = print_list(config)
            choice = input_fn("\nAraç numarası/anahtarı (yenile: r, çıkış: q): ").strip()
            if choice.lower() in ("q", "quit", "exit", "çıkış"):
                return last_exit
            if choice.lower() in ("r", "yenile"):
                continue
            try:
                tool = get_tool(choice, tools)
            except ValueError as error:
                print("Hata: %s" % error)
                input_fn("\nMenüye dönmek için Enter...")
                continue

            print("\n%s: %s" % (tool.name, tool.description))
            if tool.web:
                url = input_fn("Kendi web arayüzünün tam adresi (boş: geri): ").strip()
                if url:
                    last_exit = launch(tool, [], url=url)
            else:
                print("Argümanlar araca doğrudan iletilir. Otomatik hedef eklenmez.")
                text = input_fn("Araç argümanları (boş: argümansız başlat): ")
                try:
                    args = shlex.split(text)
                except ValueError as error:
                    print("Hata: argümanlar çözümlenemedi: %s" % error)
                    input_fn("\nMenüye dönmek için Enter...")
                    continue
                last_exit = launch(tool, args, config_paths=config.paths)
            input_fn("\nMenüye dönmek için Enter...")
    except EOFError:
        print("\nÇıkılıyor.")
        return last_exit
    except KeyboardInterrupt:
        print("\nİşlem kesildi.")
        return EXIT_INTERRUPTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guvenlik-baslatici",
        description="Kurulu güvenlik araçlarını listeler ve başlatır. " + NOTICE,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument("--config", type=Path, metavar="DOSYA", help="Yapılandırma dosyası (JSON)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ayrıntılı günlük")
    sub = parser.add_subparsers(dest="command")

    list_parser = sub.add_parser("list", help="Yalnızca tespit edilen araçları listele")
    list_parser.add_argument("--json", action="store_true", help="JSON çıktısı")

    run_parser = sub.add_parser(
        "run", help="Bir aracı başlat",
        epilog="Başlatıcı seçenekleri -- öncesine, araç argümanları -- sonrasına yazılır.",
    )
    run_parser.add_argument("tool", help="Araç anahtarı veya list çıktısındaki güncel numara")
    run_parser.add_argument("--exec", dest="override", metavar="DOSYA",
                            help="Alternatif çalıştırılabilir dosya yolu")
    run_parser.add_argument("--url", help="Nessus/OpenVAS için kendi web arayüzünün adresi")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    try:
        return _main(argv)
    except KeyboardInterrupt:
        print("\nİşlem kesildi.")
        return EXIT_INTERRUPTED
    except BrokenPipeError:
        # `... | head` gibi kapanan bir boru hattında traceback basma.
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(devnull, sys.stdout.fileno())
            finally:
                os.close(devnull)
        except (OSError, ValueError):
            pass
        return EXIT_OK


def _main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    tool_args = []
    separated = "--" in raw
    if separated:
        boundary = raw.index("--")
        tool_args = raw[boundary + 1:]
        raw = raw[:boundary]
    # argparse.REMAINDER kullanılmaz: araçtan sonraki --exec/--url yutulmaz.
    args = parser.parse_args(raw)
    if separated and args.command != "run":
        parser.error("-- ile ayrılan araç argümanları yalnızca run komutunda kullanılabilir.")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print("Hata: %s" % error, file=sys.stderr)
        return EXIT_USAGE

    if args.command == "list":
        if args.json:
            print(list_json(config))
        else:
            print_list(config)
        return EXIT_OK

    if args.command == "run":
        try:
            selector = args.tool.strip()
            # Anahtarlar manuel --exec/uzak --url kullanımını korur.
            tools = installed_tools(config) if selector.isdigit() else TOOLS
            tool = get_tool(selector, tools)
        except ValueError as error:
            parser.error(str(error))
        return launch(tool, tool_args, override=args.override, url=args.url,
                      config_paths=config.paths)

    if not sys.stdin.isatty():
        print_list(config)
        return EXIT_OK
    return menu(config)


if __name__ == "__main__":
    sys.exit(main())
