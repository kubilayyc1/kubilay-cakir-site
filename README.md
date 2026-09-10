# Kubilay Çakır

Flask + SQLite kişisel site: giriş/kayıt, anahtarsız havale/EFT ödeme bildirimi, tam admin paneli, Instagram.

## Çalıştırma

```bash
cd /workspace/kubilay-cakir
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Uygulama: http://127.0.0.1:8766

## Ödeme (keyless)

1. Kullanıcı `/odeme` üzerinde IBAN’a havale yapar (kart bilgisi toplanmaz).
2. `POST /api/payment-notify` → `pending` kayıt.
3. Admin `/admin` → Ödemeler: `approved` / `rejected` / `pending`.

Varsayılan banka: VakıfBank · Alıcı Kubilay Çakır · IBAN ayarlardan düzenlenebilir.

## Admin

`/admin` — üyeler (ara/filtre, engelle, sil, admin yap), ödeme bildirimleri, site/IBAN ayarları, istatistikler.
