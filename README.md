# Kubilay Çakır

Flask + SQLite kişisel site: giriş/kayıt, anahtarsız havale/EFT ödeme bildirimi, TR/EN dil seçici, teşekkür PNG kartı, tam admin paneli + Kadir yardımcı rolü, Instagram.

## Çalıştırma

```bash
cd /workspace/kubilay-cakir
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Uygulama: http://127.0.0.1:8766

## Dil (TR/EN)

- Varsayılan: Türkçe
- `/lang/tr` veya `/lang/en` — cookie + session `lang`
- Nav’da **TR | EN** toggle

## Ödeme (keyless)

1. Kullanıcı `/odeme` üzerinde IBAN’a havale yapar (kart bilgisi toplanmaz).
2. `POST /api/payment-notify` → `pending` kayıt.
3. Admin veya yardımcı `/admin` / `/admin/odemeler` → Ödemeler: `approved` / `rejected` / `pending`.
4. Sonuç sayfasında teşekkür kartı: `/api/payment-card/<id>.png` (Pillow, 1080×1350).

Varsayılan banka: Enpara · Alıcı Kubilay Mert Çakır · IBAN ayarlardan düzenlenebilir.

## Roller

- **Admin** (`kubilaycakir54@yahoo.com`): tüm panel — üyeler, ödemeler, ayarlar.
- **Yardımcı / Helper** (Kadir): yalnızca ödemeler (`/admin/odemeler`). Kullanıcı ban/silme ve ayarlar 403.
  - E-posta: `kadir@kubilaycakir.com` (veya ayarlardaki `helper_email`)
  - Şifre: env `HELPER_PASSWORD` (varsayılan `KadirYardimci2026!`)
  - Admin UI’dan kullanıcıya “Yardımcı Yap” ile de atanabilir.

## WhatsApp

FAB ve ödeme bildirimi: `905331211580` · Kadir Karadeniz.
