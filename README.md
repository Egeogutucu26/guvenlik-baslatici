# guvenlik-baslatici

Python 3.8+ ile çalışan, yerel güvenlik araçlarını bulup başlatan küçük bir komut satırı başlatıcısıdır. Çalışma zamanında yalnızca standart kütüphane kullanır.

> **Kapsam ve sorumluluk:** Bu proje araçların yeniden yazılmış sürümü değildir. Bulunan programları başlatır veya Nessus/Greenbone için kullanıcının açıkça verdiği web adresini açar. Kendiliğinden hedef taramaz, paket kurmaz ve yönetici yetkisi istemez. Yalnızca kendi sistemlerinde veya yazılı izin verilen hedeflerde kullanın.

## Kali/Linux'ta ZIP'i kurmadan kullanma

Kaynak ağacından çalıştırmak için önce ZIP'i açıp proje köküne geçin. `src` düzeni nedeniyle `PYTHONPATH=src` belirtmek gerekir:

```bash
unzip guvenlik-baslatici-1.1.0.zip
cd guvenlik-baslatici
PYTHONPATH=src python3 -m guvenlik_baslatici --version
PYTHONPATH=src python3 -m guvenlik_baslatici
PYTHONPATH=src python3 -m guvenlik_baslatici list --json
```

Bu kullanım sistem Python'una kurulum gerektirmez. Projede bir kurulum script'i veya bağımsız `setup.py` yoktur; kaynak kullanımı için `cd` ile doğru kökte olmak ve `PYTHONPATH=src` vermek yeterlidir.

İsteğe bağlı olarak sistem Python'unu değiştirmeden sanal ortam kurulabilir:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Bu adımdan sonra `guvenlik-baslatici` komutu kullanılabilir. Geliştirme bağımlılıkları için `python -m pip install -e ".[dev]"` kullanın. `sudo pip` veya sistem geneline kurulum önerilmez.

## Kullanım

```bash
guvenlik-baslatici                              # etkileşimli menü
guvenlik-baslatici list                         # kurulu olduğu tespit edilen araçlar
guvenlik-baslatici list --json                  # aynı snapshot'ın JSON çıktısı
guvenlik-baslatici run nmap -- --help           # -- sonrasını araca aynen iletir
guvenlik-baslatici run nmap -- -p 80,443 127.0.0.1
guvenlik-baslatici run nmap --exec /opt/nmap/bin/nmap -- --help
guvenlik-baslatici run --exec /opt/nmap/bin/nmap nmap -- --help
guvenlik-baslatici run nessus --url https://127.0.0.1:8834
```

`run` bir alt komuttur; `--run` diye bir seçenek yoktur. `--exec`, `--url` gibi başlatıcı seçenekleri araç argümanlarını ayıran `--` işaretinden önce yazın. `--` sonrasındaki bütün değerler araca aktarılır. Yukarıdaki iki `--exec` biçimi de geçerlidir: seçenek araç adından önce veya sonra gelebilir.

### Menü ve liste snapshot'ı

- Menü, `list` ve `list --json` yalnızca çalıştırılabilir dosyası mevcut olduğu tespit edilen araçları gösterir.
- Her liste bir **installed snapshot**'tır. Menüye her dönüşte liste otomatik yenilenir; `r` de açıkça yenileme yapar.
- Menü numaraları her snapshot'taki güncel `1..N` sırasına aittir ve kurulu araçlar değiştiğinde değişebilir. Araç anahtarları (`nmap`, `nessus` gibi) sabittir ve betiklerde tercih edilmelidir.
- Menüde `q`, son başlatmanın çıkış durumunu döndürür; henüz başlatma yoksa `0` döner. `Ctrl+C` çıkış kodu `130`'dur.

Doğrudan `run` çağrısı başlatılan aracın çıkış durumunu döndürür. POSIX'te sinyal nedeniyle negatif dönen durumlar `128 + sinyal` biçimine normalize edilir. Yaygın başlatıcı durumları: `2` kullanım/yapılandırma hatası ve `127` çalıştırılabilir bulunamadı.

### Nessus ve Greenbone web araçları

Yerel tespit yalnızca çalıştırılabilir dosya kanıtına dayanır:

- Nessus için PATH'te `nessuscli` veya `nessusd`, ayrıca `/opt/nessus/sbin` altındaki bu dosyalar aranır.
- Greenbone için PATH'te `gsad`, `gvmd` veya `openvas` aranır.

Bir web çalıştırılabilirinin bulunması servisin çalıştığını veya kurulumun eksiksiz olduğunu kanıtlamaz. Yerel kurulum olmadan uzak ya da önceden çalışan bir web arayüzünü açıkça açmak için anahtarı ve URL'yi verin:

```bash
guvenlik-baslatici run nessus --url https://nessus.example.test:8834
guvenlik-baslatici run openvas --url https://greenbone.example.test:9392
```

URL yalnızca `http` veya `https` şeması kabul eder; boşluk, kontrol karakteri ve kullanıcı bilgisi (`kullanici:sifre@host`) reddedilir. Uzak web erişimi için yerel çalıştırılabilir bulunması gerekmez.

## Yapılandırma ve arama sırası

PATH'te olmayan araçlar için JSON yapılandırması kullanılabilir:

```json
{
  "paths": {
    "nmap": "$HOME/bin/nmap",
    "ghidra": "~/ghidra/ghidraRun"
  }
}
```

Yol değerlerinde ortam değişkenleri ve `~` genişletilir. Yapılandırma dosyası seçimi şöyledir:

1. `--config DOSYA`
2. `GUVENLIK_BASLATICI_CONFIG` ortam değişkeninin gösterdiği dosya
3. Linux/macOS'ta `~/.config/guvenlik-baslatici/config.json`, Windows'ta `%APPDATA%\\guvenlik-baslatici\\config.json`

İlk iki seçenek açıkça belirtilmiş sayılır; dosya yoksa veya geçersizse kullanım/yapılandırma hatası verilir. Varsayılan dosya yoksa boş yapılandırma ile devam edilir. Çalıştırılabilir arama sırası `--exec` → yapılandırma → PATH → aracın `search_paths` değerleri → Windows'a özgü kurulum yollarıdır. `--exec` açıkça verilmişse bulunamaz olduğunda sessizce başka konuma düşülmez.

## Güvenli çalışma ilkeleri

- Komutlar liste olarak ve `shell=False` ile çalıştırılır; shell enjeksiyonu için metin birleştirilmez.
- Otomatik hedef, seçenek veya saldırı ayarı eklenmez; hedefleri ve argümanları her zaman kullanıcı verir.
- Web adresleri yalnızca `http`/`https` olarak doğrulanır.

## Geliştirme

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
python -m build --sdist --wheel
```

## Lisans

MIT
