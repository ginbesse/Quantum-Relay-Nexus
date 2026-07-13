# Quantum Relay Nexus

Bu proje, 2070'lerin sunucu iletişim sistemine benzeyen bir “gelecek düzeyi” aktarım mimarisi sunar. Dosya, dizin ve mesaj aktarımı yapabilir; paketler sıkıştırılır ve TCP üzerinden taşınır.

## Yeni özellikler
- TCP tabanlı yüksek hızda veri aktarımı
- Dosya ve dizin transferi
- Sıkıştırılmış paketler
- Termux uyumlu CLI arayüzü
- Gelecek sistem hissi veren isimlendirme ve akış

## Kurulum
```bash
python3 -m pip install --user pytest
```

## Test
```bash
python3 -m pytest -q
```

## Sunucu başlatma
```bash
python3 teleport_app.py --mode server --host 0.0.0.0 --port 9000 --storage ./teleport_storage
```

## İstemci gönderme
```bash
python3 teleport_app.py --mode client --target-host 192.168.1.10 --target-port 9000 --message "merhaba"
```

```bash
python3 teleport_app.py --mode client --target-host 192.168.1.10 --target-port 9000 --file ./payload.txt --name payload.txt
```

```bash
python3 teleport_app.py --mode client --target-host 192.168.1.10 --target-port 9000 --dir ./future_bundle --name future_bundle --password lattice
```

## Termux notu
Termux'ta çalıştırmak için aynı komutlar kullanılabilir. İki cihaz aynı Wi-Fi ağında olmalı ve hedef IP adresi doğru verilmelidir.
