#!/usr/bin/env python3
"""Kubilay Çakır — auth, keyless IBAN ödeme bildirimi, tam admin paneli."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from functools import wraps
from urllib.parse import quote, urlparse

from io import BytesIO

from flask import (
    Flask,
    abort,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from PIL import Image, ImageDraw, ImageFont
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.environ.get("RENDER_DISK_PATH") or os.environ.get("DATA_DIR") or BASE_DIR
os.makedirs(_data_dir, exist_ok=True)
DB_PATH = os.path.join(_data_dir, "users.db")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "kubilaycakir54@yahoo.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Kubilay8181")
HELPER_EMAIL_DEFAULT = "kadir@kubilaycakir.com"
HELPER_PASSWORD = os.environ.get("HELPER_PASSWORD", "KadirYardimci2026!")
HELPER_NAME = "Kadir Karadeniz"
SITE_PUBLIC_URL = os.environ.get("SITE_PUBLIC_URL", "https://kubilay-cakir.onrender.com")

DEFAULT_IBAN = "TR83 0015 7000 0000 0205 4704 26"
DEFAULT_BANK = "Enpara"
DEFAULT_RECIPIENT = "Kubilay Mert Çakır"
DEFAULT_WHATSAPP = "905331211580"  # Kadir Karadeniz
DEFAULT_WHATSAPP_LABEL = "Kadir Karadeniz"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kubilay")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "kubilay-cakir-dev-secret-change-in-prod-2026"
)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
)

DEFAULT_SETTINGS = {
    "site_title": "Kubilay Çakır",
    "tagline": "Kişisel alan · havale ile güvenli ödeme · Instagram",
    "instagram_handle": "kubilayyc1",
    "registration_open": "1",
    "maintenance_mode": "0",
    "bank_iban": DEFAULT_IBAN,
    "bank_name": DEFAULT_BANK,
    "bank_recipient": DEFAULT_RECIPIENT,
}


PAYMENT_STATUSES = {"pending", "approved", "rejected"}

I18N = {
    "tr": {
        "nav_home": "Ana Sayfa",
        "nav_payment": "Ödeme",
        "nav_admin": "Admin",
        "nav_helper": "Ödemeler",
        "nav_login": "Giriş",
        "nav_register": "Kayıt",
        "nav_logout": "Çıkış",
        "nav_whatsapp": "WhatsApp",
        "nav_menu": "Menüyü aç",
        "brand_credit": "Kurucu Yardımcısı · Kadir Karadeniz",
        "footer_credit_label": "Kurucu Yardımcısı",
        "footer_credit_name": "Kadir Karadeniz",
        "footer_note": "Kart bilgisi toplanmaz · Havale / EFT bildirimi",
        "footer_payment": "Ödeme",
        "footer_login": "Giriş",
        "wa_fab_aria": "WhatsApp ile Kadir Karadeniz",
        "wa_fab_text": "WhatsApp",
        "wa_fab_sub": "Kadir",
        "wa_hello": "Merhaba Kadir,",
        "hero_eyebrow": "Kişisel · Güvenli · Zarif",
        "hero_credit": "Kurucu Yardımcısı · Kadir Karadeniz",
        "hero_pay": "Ödeme Ekranı",
        "hero_admin": "Yönetim",
        "hero_login_pay": "Ödeme İçin Giriş Yap",
        "hero_register": "Hesap Oluştur",
        "hero_pill_havale": "Havale / EFT",
        "hero_pill_nocard": "Kart bilgisi yok",
        "hero_pill_admin": "Yönetici onayı",
        "ig_title": "Instagram",
        "ig_sub": "Beni Instagram’da takip edin",
        "ig_open": "Profili Aç",
        "lock_note": "Ödeme ekranı için giriş yapmanız gerekir.",
        "lock_note_reg": " Hesabınız yoksa birkaç saniyede kayıt olabilirsiniz.",
        "pay_title": "Ödeme",
        "pay_welcome": "Hoş geldiniz, {name} · Havale / EFT ile güvenli bildirim",
        "pay_step1": "Adım 1",
        "pay_bank_title": "Banka Bilgileri",
        "pay_bank_sub": "Tutarı aşağıdaki hesaba havale / EFT ile gönderin. Kart numarası veya CVV istenmez.",
        "pay_recipient": "Alıcı",
        "pay_bank": "Banka",
        "pay_iban": "IBAN",
        "pay_copy": "Kopyala",
        "pay_step_li1": "Yukarıdaki IBAN’a havale / EFT yapın.",
        "pay_step_li2": "Tutarı ve isteğe bağlı notu girin.",
        "pay_step_li3": "Ödeme Bildirimi Gönder ile kayıt oluşturun; Kadir’e WhatsApp mesajı açılır.",
        "pay_step2": "Adım 2",
        "pay_notify_title": "Ödeme Bildirimi",
        "pay_notify_sub": "Havale yaptıktan sonra bildiriminizi gönderin. Onay bekleyen kayıt oluşturulur.",
        "pay_amount": "Tutar (₺)",
        "pay_note": "Açıklama / Not",
        "pay_optional": "(isteğe bağlı)",
        "pay_note_ph": "Örn. dekont no, referans…",
        "pay_submit": "Ödeme Bildirimi Gönder",
        "pay_sending": "Gönderiliyor…",
        "pay_invalid_amount": "Geçerli bir tutar girin",
        "pay_toast_ok": "Bildirim alındı — Kadir'e WhatsApp açılıyor",
        "pay_fail": "Bildirim gönderilemedi",
        "pay_conn": "Bağlantı hatası",
        "result_title": "Ödeme Sonucu",
        "result_approved": "Onaylandı",
        "result_pending": "Bildirim Alındı",
        "result_rejected": "Reddedildi",
        "result_msg_pending": "Ödeme bildiriminiz alındı. Yönetici onayından sonra tamamlanır.",
        "result_msg_approved": "Ödemeniz onaylandı. Teşekkürler!",
        "result_msg_rejected": "Ödeme bildiriminiz reddedildi. Gerekirse tekrar deneyin.",
        "result_msg_other": "Ödeme kaydı güncellendi.",
        "result_amount": "Tutar",
        "result_note": "Not",
        "result_id": "Kayıt No",
        "result_ref": "Referans",
        "result_status": "Durum",
        "badge_approved": "onaylandı",
        "badge_rejected": "reddedildi",
        "badge_pending": "beklemede",
        "result_wa": "WhatsApp’ta Kadir’e Bildir",
        "result_new": "Yeni Bildirim",
        "result_home": "Ana Sayfa",
        "share_title": "Teşekkür Kartı",
        "share_download": "PNG İndir",
        "share_copy": "Bağlantıyı Kopyala",
        "share_web": "Paylaş",
        "share_copied": "Bağlantı kopyalandı",
        "card_pending": "Ödeme bildirimi alındı",
        "card_approved": "Ödeme bildirimi onaylandı",
        "card_rejected": "Ödeme bildirimi reddedildi",
        "card_credit": "Kurucu Yardımcısı · Kadir Karadeniz",
        "login_title": "Giriş Yap",
        "login_sub": "Ödeme bildirimi ve kişisel alan için oturum açın",
        "login_email": "E-posta",
        "login_password": "Şifre",
        "login_btn": "Giriş Yap",
        "login_switch": "Hesabınız yok mu?",
        "login_switch_link": "Kayıt olun",
        "login_welcome": "Hoş geldiniz",
        "login_fail": "Giriş başarısız",
        "reg_title": "Hesap Oluştur",
        "reg_closed": "Kayıtlar Kapalı",
        "reg_closed_sub": "Şu an yeni hesap oluşturulamaz. Daha sonra tekrar deneyin.",
        "reg_to_login": "Giriş Sayfası",
        "reg_sub": "Birkaç saniyede kayıt olun — kart bilgisi istenmez",
        "reg_name": "Ad Soyad",
        "reg_email": "E-posta",
        "reg_password": "Şifre",
        "reg_btn": "Kayıt Ol",
        "reg_switch": "Zaten hesabınız var mı?",
        "reg_switch_link": "Giriş yapın",
        "reg_ok": "Hesap oluşturuldu",
        "reg_fail": "Kayıt başarısız",
        "account_kicker": "Hesap",
    },
    "en": {
        "nav_home": "Home",
        "nav_payment": "Payment",
        "nav_admin": "Admin",
        "nav_helper": "Payments",
        "nav_login": "Log in",
        "nav_register": "Sign up",
        "nav_logout": "Log out",
        "nav_whatsapp": "WhatsApp",
        "nav_menu": "Open menu",
        "brand_credit": "Co-founder · Kadir Karadeniz",
        "footer_credit_label": "Co-founder",
        "footer_credit_name": "Kadir Karadeniz",
        "footer_note": "No card data collected · Wire / EFT notification",
        "footer_payment": "Payment",
        "footer_login": "Log in",
        "wa_fab_aria": "WhatsApp Kadir Karadeniz",
        "wa_fab_text": "WhatsApp",
        "wa_fab_sub": "Kadir",
        "wa_hello": "Hello Kadir,",
        "hero_eyebrow": "Personal · Secure · Elegant",
        "hero_credit": "Co-founder · Kadir Karadeniz",
        "hero_pay": "Payment Screen",
        "hero_admin": "Admin",
        "hero_login_pay": "Log in to Pay",
        "hero_register": "Create Account",
        "hero_pill_havale": "Wire / EFT",
        "hero_pill_nocard": "No card data",
        "hero_pill_admin": "Admin approval",
        "ig_title": "Instagram",
        "ig_sub": "Follow me on Instagram",
        "ig_open": "Open Profile",
        "lock_note": "You need to log in to use the payment screen.",
        "lock_note_reg": " If you don’t have an account, you can register in seconds.",
        "pay_title": "Payment",
        "pay_welcome": "Welcome, {name} · Secure wire / EFT notification",
        "pay_step1": "Step 1",
        "pay_bank_title": "Bank Details",
        "pay_bank_sub": "Transfer the amount to the account below. No card number or CVV required.",
        "pay_recipient": "Recipient",
        "pay_bank": "Bank",
        "pay_iban": "IBAN",
        "pay_copy": "Copy",
        "pay_step_li1": "Send a wire / EFT to the IBAN above.",
        "pay_step_li2": "Enter the amount and an optional note.",
        "pay_step_li3": "Submit Payment Notification to create a record; WhatsApp to Kadir opens.",
        "pay_step2": "Step 2",
        "pay_notify_title": "Payment Notification",
        "pay_notify_sub": "After transferring, send your notification. A pending record is created.",
        "pay_amount": "Amount (₺)",
        "pay_note": "Description / Note",
        "pay_optional": "(optional)",
        "pay_note_ph": "e.g. receipt no, reference…",
        "pay_submit": "Send Payment Notification",
        "pay_sending": "Sending…",
        "pay_invalid_amount": "Enter a valid amount",
        "pay_toast_ok": "Notification received — opening WhatsApp to Kadir",
        "pay_fail": "Could not send notification",
        "pay_conn": "Connection error",
        "result_title": "Payment Result",
        "result_approved": "Approved",
        "result_pending": "Notification Received",
        "result_rejected": "Rejected",
        "result_msg_pending": "Your payment notification was received. It will complete after admin approval.",
        "result_msg_approved": "Your payment was approved. Thank you!",
        "result_msg_rejected": "Your payment notification was rejected. Please try again if needed.",
        "result_msg_other": "Payment record updated.",
        "result_amount": "Amount",
        "result_note": "Note",
        "result_id": "Record No",
        "result_ref": "Reference",
        "result_status": "Status",
        "badge_approved": "approved",
        "badge_rejected": "rejected",
        "badge_pending": "pending",
        "result_wa": "Notify Kadir on WhatsApp",
        "result_new": "New Notification",
        "result_home": "Home",
        "share_title": "Thank-you Card",
        "share_download": "Download PNG",
        "share_copy": "Copy Link",
        "share_web": "Share",
        "share_copied": "Link copied",
        "card_pending": "Payment notification received",
        "card_approved": "Payment notification approved",
        "card_rejected": "Payment notification rejected",
        "card_credit": "Co-founder · Kadir Karadeniz",
        "login_title": "Log In",
        "login_sub": "Sign in for payment notifications and your personal area",
        "login_email": "Email",
        "login_password": "Password",
        "login_btn": "Log In",
        "login_switch": "Don’t have an account?",
        "login_switch_link": "Sign up",
        "login_welcome": "Welcome",
        "login_fail": "Login failed",
        "reg_title": "Create Account",
        "reg_closed": "Registration Closed",
        "reg_closed_sub": "New accounts cannot be created right now. Please try later.",
        "reg_to_login": "Login Page",
        "reg_sub": "Register in seconds — no card details required",
        "reg_name": "Full Name",
        "reg_email": "Email",
        "reg_password": "Password",
        "reg_btn": "Sign Up",
        "reg_switch": "Already have an account?",
        "reg_switch_link": "Log in",
        "reg_ok": "Account created",
        "reg_fail": "Registration failed",
        "account_kicker": "Account",
    },
}


def get_lang() -> str:
    lang = (request.cookies.get("lang") or session.get("lang") or "tr").lower()
    return lang if lang in ("tr", "en") else "tr"


def t(key: str, **kwargs) -> str:
    lang = get_lang()
    text = I18N.get(lang, I18N["tr"]).get(key) or I18N["tr"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text



def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_column(db, table: str, column: str, ddl: str) -> None:
    cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_blocked INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    ensure_column(db, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
    ensure_column(db, "users", "is_blocked", "is_blocked INTEGER NOT NULL DEFAULT 0")
    ensure_column(db, "users", "is_helper", "is_helper INTEGER NOT NULL DEFAULT 0")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_email TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            note TEXT,
            conversation_id TEXT,
            token TEXT,
            payment_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    ensure_column(db, "payments", "admin_note", "admin_note TEXT")
    ensure_column(db, "payments", "updated_at", "updated_at TEXT")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    for k, v in DEFAULT_SETTINGS.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    db.commit()
    ensure_admin(db)
    ensure_helper(db)
    db.close()


def ensure_admin(db):
    pw_hash = generate_password_hash(ADMIN_PASSWORD)
    row = db.execute(
        "SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,)
    ).fetchone()
    if row:
        db.execute(
            "UPDATE users SET is_admin = 1, is_blocked = 0, password_hash = ? WHERE email = ?",
            (pw_hash, ADMIN_EMAIL),
        )
    else:
        db.execute(
            """
            INSERT INTO users (name, email, password_hash, is_admin, is_blocked, is_helper)
            VALUES (?, ?, ?, 1, 0, 0)
            """,
            ("Admin", ADMIN_EMAIL, pw_hash),
        )
    db.commit()


def helper_email_from_settings(db) -> str:
    row = db.execute(
        "SELECT value FROM settings WHERE key = ?", ("helper_email",)
    ).fetchone()
    if row and (row["value"] or "").strip():
        return row["value"].strip().lower()
    return HELPER_EMAIL_DEFAULT


def ensure_helper(db):
    """Seed/ensure Kadir helper account (is_helper=1, is_admin=0).
    Full admins can also promote helpers in the admin UI.
    """
    email = helper_email_from_settings(db)
    pw_hash = generate_password_hash(HELPER_PASSWORD)
    row = db.execute(
        "SELECT id, is_admin FROM users WHERE email = ?", (email,)
    ).fetchone()
    if row:
        # Do not demote a full admin; just ensure helper flag if not admin
        if row["is_admin"]:
            db.execute(
                "UPDATE users SET is_blocked = 0, name = ? WHERE email = ?",
                (HELPER_NAME, email),
            )
        else:
            db.execute(
                """
                UPDATE users SET is_helper = 1, is_admin = 0, is_blocked = 0,
                    password_hash = ?, name = ?
                WHERE email = ?
                """,
                (pw_hash, HELPER_NAME, email),
            )
    else:
        db.execute(
            """
            INSERT INTO users (name, email, password_hash, is_admin, is_blocked, is_helper)
            VALUES (?, ?, ?, 0, 0, 1)
            """,
            (HELPER_NAME, email, pw_hash),
        )
    db.commit()


def get_setting(key: str, default: str | None = None) -> str:
    row = get_db().execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    if row:
        return row["value"]
    if default is not None:
        return default
    return DEFAULT_SETTINGS.get(key, "")


def get_all_settings() -> dict:
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    out = dict(DEFAULT_SETTINGS)
    out.update({r["key"]: r["value"] for r in rows})
    return out


def set_setting(key: str, value: str) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    db.commit()



def whatsapp_ctx(settings: dict | None = None) -> dict:
    s = settings or get_all_settings()
    raw = (s.get("whatsapp_phone") or DEFAULT_WHATSAPP).strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("0") and len(digits) == 11:
        digits = "90" + digits[1:]
    if not digits.startswith("90") and len(digits) == 10:
        digits = "90" + digits
    label = (s.get("whatsapp_label") or DEFAULT_WHATSAPP_LABEL).strip()
    display = "+90 (533) 121 15 80" if digits.endswith("5331211580") else f"+{digits}"
    return {
        "phone": digits,
        "label": label,
        "url": f"https://wa.me/{digits}",
        "display": display,
    }


def whatsapp_payment_url(user: dict, amount: float, note: str, payment_id: int) -> str:
    wa = whatsapp_ctx()
    note_part = f"\nNot: {note}" if note else ""
    text = (
        f"Merhaba Kadir, siteden yeni ödeme bildirimi.\n"
        f"Kayıt: #{payment_id}\n"
        f"Kişi: {user.get('name')} ({user.get('email')})\n"
        f"Tutar: ₺{amount:.2f}{note_part}\n"
        f"Lütfen admin panelinden kontrol eder misin?"
    )
    return f"{wa['url']}?text={quote(text)}"


def bank_ctx(settings: dict | None = None) -> dict:
    s = settings or get_all_settings()
    iban = (s.get("bank_iban") or DEFAULT_IBAN).strip()
    return {
        "iban": iban,
        "iban_plain": iban.replace(" ", ""),
        "bank_name": (s.get("bank_name") or DEFAULT_BANK).strip(),
        "recipient": (s.get("bank_recipient") or DEFAULT_RECIPIENT).strip(),
    }


def site_ctx() -> dict:
    s = get_all_settings()
    handle = (s.get("instagram_handle") or "kubilayyc1").lstrip("@")
    bank = bank_ctx(s)
    return {
        "site_title": s.get("site_title") or "Kubilay Çakır",
        "tagline": s.get("tagline") or "",
        "instagram_handle": handle,
        "instagram_url": f"https://instagram.com/{handle}",
        "registration_open": s.get("registration_open", "1") == "1",
        "maintenance_mode": s.get("maintenance_mode", "0") == "1",
        "payment_ready": True,
        "bank": bank,
        "whatsapp": whatsapp_ctx(s),
    }


@app.context_processor
def inject_site():
    lang = "tr"
    try:
        lang = get_lang()
    except Exception:
        lang = "tr"
    base = {"lang": lang, "t": t, "og_locale": "tr_TR" if lang == "tr" else "en_US"}
    try:
        base["site"] = site_ctx()
        return base
    except Exception:
        base["site"] = {
            "site_title": "Kubilay Çakır",
            "tagline": "Kişisel alan · havale ile güvenli ödeme · Instagram",
            "instagram_handle": "kubilayyc1",
            "instagram_url": "https://instagram.com/kubilayyc1",
            "registration_open": True,
            "maintenance_mode": False,
            "payment_ready": True,
            "whatsapp": {
                "phone": DEFAULT_WHATSAPP,
                "label": DEFAULT_WHATSAPP_LABEL,
                "url": f"https://wa.me/{DEFAULT_WHATSAPP}",
                "display": "+90 (533) 121 15 80",
            },
            "bank": {
                "iban": DEFAULT_IBAN,
                "iban_plain": DEFAULT_IBAN.replace(" ", ""),
                "bank_name": DEFAULT_BANK,
                "recipient": DEFAULT_RECIPIENT,
            },
        }
        return base


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_db().execute(
        """
        SELECT id, name, email, is_admin, is_helper, is_blocked, created_at
        FROM users WHERE id = ?
        """,
        (uid,),
    ).fetchone()
    if not row:
        return None
    if row["is_blocked"]:
        session.clear()
        return None
    user = dict(row)
    user["is_admin"] = bool(user.get("is_admin"))
    user["is_helper"] = bool(user.get("is_helper"))
    user["is_blocked"] = bool(user.get("is_blocked"))
    return user


def login_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"ok": False, "error": "Giriş gerekli"}), 401
        return fn(user, *args, **kwargs)

    return wrapper


def login_required_page(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login_page", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login_page", next=request.path))
        if not user.get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def admin_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"ok": False, "error": "Giriş gerekli"}), 401
        if not user.get("is_admin"):
            return jsonify({"ok": False, "error": "Yetkisiz"}), 403
        return fn(user, *args, **kwargs)

    return wrapper


def helper_or_admin_required(fn):
    """Page access for full admin or helper (payments-only)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login_page", next=request.path))
        if not (user.get("is_admin") or user.get("is_helper")):
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def helper_or_admin_api(fn):
    """API access for payment approve/reject/note — admin or helper."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"ok": False, "error": "Giriş gerekli"}), 401
        if not (user.get("is_admin") or user.get("is_helper")):
            return jsonify({"ok": False, "error": "Yetkisiz"}), 403
        return fn(user, *args, **kwargs)

    return wrapper


def same_origin_ok() -> bool:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    origin = request.headers.get("Origin")
    if origin:
        try:
            o = urlparse(origin)
            host = request.headers.get("X-Forwarded-Host") or request.host
            if o.netloc and o.netloc.lower() != host.lower():
                if o.netloc.lower() != request.host.lower():
                    return False
        except Exception:
            return False
    return True


def require_same_origin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not same_origin_ok():
            return jsonify({"ok": False, "error": "Geçersiz istek kaynağı"}), 403
        return fn(*args, **kwargs)

    return wrapper


def admin_count(db=None) -> int:
    db = db or get_db()
    row = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE is_admin = 1 AND is_blocked = 0"
    ).fetchone()
    return int(row["c"])


def status_badge_class(status: str) -> str:
    s = (status or "").lower()
    if s in ("approved", "success"):
        return "badge-ok"
    if s in ("rejected", "failure", "error"):
        return "badge-bad"
    return "badge-pending"


@app.before_request
def maintenance_gate():
    if request.path.startswith("/static"):
        return None
    try:
        mm = get_setting("maintenance_mode", "0") == "1"
    except Exception:
        return None
    if not mm:
        return None
    user = current_user()
    if user and (user.get("is_admin") or user.get("is_helper")):
        return None
    allowed = {
        "login_page",
        "api_login",
        "api_logout",
        "logout_redirect",
        "static",
        "favicon",
        "set_lang",
    }
    if request.endpoint in allowed:
        return None
    return (
        render_template(
            "maintenance.html",
            user=user,
            site=site_ctx(),
        ),
        503,
    )


# ── Pages ──────────────────────────────────────────────────────────────


@app.route("/lang/<code>")
def set_lang(code):
    code = (code or "").lower()
    if code not in ("tr", "en"):
        abort(404)
    session["lang"] = code
    nxt = request.args.get("next") or request.referrer or url_for("index")
    # stay on same site
    try:
        from urllib.parse import urlparse as _up
        p = _up(nxt)
        if p.netloc and p.netloc.lower() not in (
            request.host.lower(),
            (request.headers.get("X-Forwarded-Host") or "").lower(),
        ):
            nxt = url_for("index")
    except Exception:
        nxt = url_for("index")
    resp = make_response(redirect(nxt))
    resp.set_cookie(
        "lang",
        code,
        max_age=60 * 60 * 24 * 365,
        httponly=False,
        samesite="Lax",
    )
    return resp


@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/giris")
def login_page():
    if current_user():
        return redirect(url_for("payment_page"))
    return render_template(
        "login.html", user=None, next=request.args.get("next", "/odeme")
    )


@app.route("/kayit")
def register_page():
    if current_user():
        return redirect(url_for("payment_page"))
    if not site_ctx()["registration_open"]:
        return render_template(
            "register.html", user=None, registration_closed=True
        )
    return render_template("register.html", user=None, registration_closed=False)


@app.route("/odeme")
@login_required_page
def payment_page():
    return render_template(
        "odeme.html",
        user=current_user(),
        bank=site_ctx()["bank"],
    )


@app.route("/odeme/sonuc/<int:payment_id>")
@login_required_page
def payment_result(payment_id):
    user = current_user()
    row = get_db().execute(
        "SELECT * FROM payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if not row:
        abort(404)
    if row["user_id"] != user["id"] and not user.get("is_admin"):
        abort(403)
    result = {
        "ok": row["status"] == "approved",
        "status": row["status"],
        "message": {
            "pending": t("result_msg_pending"),
            "approved": t("result_msg_approved"),
            "rejected": t("result_msg_rejected"),
        }.get(row["status"], t("result_msg_other")),
        "payment_id": row["id"],
        "conversation_id": row["conversation_id"],
        "amount": row["amount"],
        "note": row["note"],
        "error_message": None,
        "card_status_label": {
            "pending": t("card_pending"),
            "approved": t("card_approved"),
            "rejected": t("card_rejected"),
        }.get(row["status"], t("card_pending")),
        "share_url": url_for(
            "payment_card_png", payment_id=row["id"], _external=True
        ),
        "card_png_url": url_for("payment_card_png", payment_id=row["id"]),
    }
    result["whatsapp_url"] = whatsapp_payment_url(
        {"name": user.get("name"), "email": row["user_email"]},
        float(row["amount"] or 0),
        row["note"] or "",
        row["id"],
    )
    return render_template("odeme_sonuc.html", user=user, result=result)


@app.route("/admin")
@login_required_page
def admin_page():
    user = current_user()
    if user and user.get("is_helper") and not user.get("is_admin"):
        return redirect(url_for("admin_payments_page"))
    if not user or not user.get("is_admin"):
        abort(403)
    db = get_db()
    q = (request.args.get("q") or "").strip()
    filter_role = (request.args.get("role") or "all").strip()
    filter_block = (request.args.get("blocked") or "all").strip()

    sql = """
        SELECT id, name, email, created_at, is_admin, is_helper, is_blocked
        FROM users WHERE 1=1
    """
    params: list = []
    if q:
        sql += " AND (name LIKE ? OR email LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])
    if filter_role == "admin":
        sql += " AND is_admin = 1"
    elif filter_role == "member":
        sql += " AND is_admin = 0"
    if filter_block == "yes":
        sql += " AND is_blocked = 1"
    elif filter_block == "no":
        sql += " AND is_blocked = 0"
    sql += " ORDER BY id ASC"
    users = db.execute(sql, params).fetchall()

    payments = db.execute(
        """
        SELECT id, user_email, amount, currency, note, status,
               conversation_id, payment_id, admin_note, created_at, updated_at
        FROM payments
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    total = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    blocked = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE is_blocked = 1"
    ).fetchone()["c"]
    admins = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE is_admin = 1"
    ).fetchone()["c"]
    pay_count = db.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
    pay_pending = db.execute(
        "SELECT COUNT(*) AS c FROM payments WHERE status = 'pending'"
    ).fetchone()["c"]
    pay_approved = db.execute(
        "SELECT COUNT(*) AS c FROM payments WHERE status IN ('approved', 'success')"
    ).fetchone()["c"]
    recent_signups = db.execute(
        """
        SELECT id, name, email, created_at FROM users
        ORDER BY id DESC LIMIT 8
        """
    ).fetchall()

    settings = get_all_settings()
    return render_template(
        "admin.html",
        user=current_user(),
        users=users,
        payments=payments,
        settings=settings,
        stats={
            "total": total,
            "blocked": blocked,
            "admins": admins,
            "members": total - admins,
            "payments": pay_count,
            "payments_pending": pay_pending,
            "payments_approved": pay_approved,
        },
        recent_signups=recent_signups,
        q=q,
        filter_role=filter_role,
        filter_block=filter_block,
        bank=bank_ctx(settings),
        status_badge_class=status_badge_class,
    )


@app.route("/admin/odemeler")
@login_required_page
@helper_or_admin_required
def admin_payments_page():
    """Helper (and admin) payments-only view: approve / reject / pending."""
    db = get_db()
    payments = db.execute(
        """
        SELECT id, user_email, amount, currency, note, status,
               conversation_id, payment_id, admin_note, created_at, updated_at
        FROM payments
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()
    pay_count = db.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
    pay_pending = db.execute(
        "SELECT COUNT(*) AS c FROM payments WHERE status = 'pending'"
    ).fetchone()["c"]
    pay_approved = db.execute(
        "SELECT COUNT(*) AS c FROM payments WHERE status IN ('approved', 'success')"
    ).fetchone()["c"]
    return render_template(
        "admin_odemeler.html",
        user=current_user(),
        payments=payments,
        stats={
            "payments": pay_count,
            "payments_pending": pay_pending,
            "payments_approved": pay_approved,
        },
        status_badge_class=status_badge_class,
    )


def _load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_payment_card_image(
    *,
    brand: str,
    amount: float,
    status: str,
    status_label: str,
    credit: str,
    site_url: str,
    payment_id: int,
) -> bytes:
    W, H = 1080, 1350
    bg = (12, 12, 14)
    gold = (201, 162, 39)
    gold_light = (232, 201, 112)
    muted = (180, 175, 160)
    white = (245, 240, 230)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # gold frame
    margin = 48
    for i, col in enumerate([(60, 48, 18), gold, (60, 48, 18)]):
        inset = margin - 4 + i * 3
        draw.rectangle([inset, inset, W - inset, H - inset], outline=col, width=2)

    # top accent bar
    draw.rectangle([margin + 20, margin + 28, W - margin - 20, margin + 34], fill=gold)

    font_brand = _load_font(64)
    font_sub = _load_font(28)
    font_amount = _load_font(92)
    font_status = _load_font(40)
    font_small = _load_font(26)
    font_tiny = _load_font(22)

    def center_text(text, y, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y), text, font=font, fill=fill)

    center_text(brand or "Kubilay Çakır", 180, font_brand, gold_light)
    center_text("K", 280, _load_font(72), gold)

    # status pill background
    pill = status_label
    bbox = draw.textbbox((0, 0), pill, font=font_status)
    pw, ph = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px = (W - pw) / 2 - 36
    py = 420
    if status == "approved":
        fill = (30, 55, 35)
        outline = (125, 186, 122)
        tfill = (160, 220, 160)
    elif status == "rejected":
        fill = (55, 30, 30)
        outline = (224, 112, 112)
        tfill = (240, 160, 160)
    else:
        fill = (55, 48, 25)
        outline = gold
        tfill = gold_light
    draw.rounded_rectangle(
        [px, py, px + pw + 72, py + ph + 40], radius=28, fill=fill, outline=outline, width=2
    )
    center_text(pill, py + 16, font_status, tfill)

    center_text(f"₺{amount:,.2f}", 580, font_amount, white)
    center_text(f"#{payment_id}", 700, font_sub, muted)

    # divider
    draw.line([(220, 780), (W - 220, 780)], fill=gold, width=2)

    center_text(credit, 860, font_small, gold_light)
    center_text(site_url.replace("https://", "").replace("http://", ""), 960, font_tiny, muted)
    center_text("Havale / EFT · Kart bilgisi yok", 1040, font_tiny, muted)

    draw.rectangle(
        [margin + 20, H - margin - 34, W - margin - 20, H - margin - 28], fill=gold
    )

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@app.route("/api/payment-card/<int:payment_id>.png")
@login_required_page
def payment_card_png(payment_id):
    user = current_user()
    row = get_db().execute(
        "SELECT * FROM payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if not row:
        abort(404)
    if (
        row["user_id"] != user["id"]
        and not user.get("is_admin")
        and not user.get("is_helper")
    ):
        abort(403)
    status = row["status"] or "pending"
    label = {
        "pending": t("card_pending"),
        "approved": t("card_approved"),
        "rejected": t("card_rejected"),
    }.get(status, t("card_pending"))
    png = render_payment_card_image(
        brand=site_ctx()["site_title"],
        amount=float(row["amount"] or 0),
        status=status,
        status_label=label,
        credit=t("card_credit"),
        site_url=SITE_PUBLIC_URL,
        payment_id=row["id"],
    )
    resp = make_response(png)
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Content-Disposition"] = (
        f'inline; filename="odeme-kart-{payment_id}.png"'
    )
    resp.headers["Cache-Control"] = "private, max-age=60"
    return resp


@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"))


@app.errorhandler(403)
def forbidden(_e):
    return render_template("403.html", user=current_user()), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("403.html", user=current_user()), 404


# ── Auth API ───────────────────────────────────────────────────────────


@app.route("/api/register", methods=["POST"])
@require_same_origin
def api_register():
    if get_setting("registration_open", "1") != "1":
        return jsonify({"ok": False, "error": "Kayıtlar şu an kapalı"}), 403
    if get_setting("maintenance_mode", "0") == "1":
        return jsonify({"ok": False, "error": "Site bakımda"}), 503

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Ad soyad en az 2 karakter olmalı"}), 400
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Geçerli bir e-posta girin"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Şifre en az 6 karakter olmalı"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        return jsonify({"ok": False, "error": "Bu e-posta zaten kayıtlı"}), 409

    pw_hash = generate_password_hash(password)
    cur = db.execute(
        """
        INSERT INTO users (name, email, password_hash, is_admin, is_blocked)
        VALUES (?, ?, ?, 0, 0)
        """,
        (name, email, pw_hash),
    )
    db.commit()
    session.clear()
    session["user_id"] = cur.lastrowid
    session.permanent = True
    user = current_user()
    return jsonify({"ok": True, "user": user}), 201


@app.route("/api/login", methods=["POST"])
@require_same_origin
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"ok": False, "error": "E-posta ve şifre gerekli"}), 400

    row = get_db().execute(
        """
        SELECT id, name, email, password_hash, is_admin, is_helper, is_blocked
        FROM users WHERE email = ?
        """,
        (email,),
    ).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"ok": False, "error": "E-posta veya şifre hatalı"}), 401
    if row["is_blocked"]:
        return jsonify({"ok": False, "error": "Hesabınız engellenmiş"}), 403

    session.clear()
    session["user_id"] = row["id"]
    session.permanent = True
    return jsonify(
        {
            "ok": True,
            "user": {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "is_admin": bool(row["is_admin"]),
                "is_helper": bool(row["is_helper"]),
            },
        }
    )


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "authenticated": False}), 401
    return jsonify({"ok": True, "authenticated": True, "user": user})


# ── Keyless payment notify ─────────────────────────────────────────────


@app.route("/api/payment-notify", methods=["POST"])
@login_required_api
@require_same_origin
def api_payment_notify(user):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    note = (data.get("note") or "").strip()
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Geçerli bir tutar girin"}), 400
    if amount_f <= 0:
        return jsonify({"ok": False, "error": "Tutar 0'dan büyük olmalı"}), 400
    if amount_f > 1_000_000:
        return jsonify({"ok": False, "error": "Tutar çok yüksek"}), 400
    if len(note) > 500:
        return jsonify({"ok": False, "error": "Not en fazla 500 karakter olabilir"}), 400

    conversation_id = f"havale-{user['id']}-{uuid.uuid4().hex[:12]}"
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO payments
            (user_id, user_email, amount, currency, note, conversation_id, status)
        VALUES (?, ?, ?, 'TRY', ?, ?, 'pending')
        """,
        (user["id"], user["email"], amount_f, note or None, conversation_id),
    )
    db.commit()
    payment_id = cur.lastrowid
    log.info(
        "payment_notify id=%s user_id=%s amount=%.2f",
        payment_id,
        user["id"],
        amount_f,
    )
    wa_url = whatsapp_payment_url(user, amount_f, note, payment_id)
    return jsonify(
        {
            "ok": True,
            "payment_id": payment_id,
            "status": "pending",
            "conversation_id": conversation_id,
            "whatsapp_url": wa_url,
            "redirect": url_for("payment_result", payment_id=payment_id),
        }
    )


# ── Admin APIs ─────────────────────────────────────────────────────────


@app.route("/api/admin/users/<int:user_id>/block", methods=["POST"])
@admin_required_api
@require_same_origin
def admin_block_user(admin, user_id):
    data = request.get_json(silent=True) or {}
    block = bool(data.get("blocked", True))
    db = get_db()
    target = db.execute(
        "SELECT id, email, is_admin, is_blocked FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not target:
        return jsonify({"ok": False, "error": "Kullanıcı bulunamadı"}), 404
    if target["id"] == admin["id"] and block:
        return jsonify({"ok": False, "error": "Kendinizi engelleyemezsiniz"}), 400
    if target["is_admin"] and block and admin_count(db) <= 1:
        return jsonify({"ok": False, "error": "Son yönetici engellenemez"}), 400
    db.execute(
        "UPDATE users SET is_blocked = ? WHERE id = ?",
        (1 if block else 0, user_id),
    )
    db.commit()
    return jsonify({"ok": True, "blocked": block})


@app.route("/api/admin/users/<int:user_id>/admin", methods=["POST"])
@admin_required_api
@require_same_origin
def admin_set_admin(admin, user_id):
    data = request.get_json(silent=True) or {}
    make_admin = bool(data.get("is_admin", True))
    db = get_db()
    target = db.execute(
        "SELECT id, is_admin FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not target:
        return jsonify({"ok": False, "error": "Kullanıcı bulunamadı"}), 404
    if target["id"] == admin["id"] and not make_admin:
        return jsonify({"ok": False, "error": "Kendi yönetici yetkinizi kaldıramazsınız"}), 400
    if target["is_admin"] and not make_admin and admin_count(db) <= 1:
        return jsonify({"ok": False, "error": "Son yönetici yetkisi kaldırılamaz"}), 400
    db.execute(
        "UPDATE users SET is_admin = ? WHERE id = ?",
        (1 if make_admin else 0, user_id),
    )
    db.commit()
    return jsonify({"ok": True, "is_admin": make_admin})


@app.route("/api/admin/users/<int:user_id>/helper", methods=["POST"])
@admin_required_api
@require_same_origin
def admin_set_helper(admin, user_id):
    """Full admin can promote/demote payment helpers (Kadir role)."""
    data = request.get_json(silent=True) or {}
    make_helper = bool(data.get("is_helper", True))
    db = get_db()
    target = db.execute(
        "SELECT id, is_admin, is_helper FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not target:
        return jsonify({"ok": False, "error": "Kullanıcı bulunamadı"}), 404
    if target["is_admin"] and make_helper:
        # Admins already have full access; keep is_helper=0 to avoid confusion
        return jsonify(
            {"ok": False, "error": "Yöneticiler zaten tüm yetkiye sahip"}
        ), 400
    db.execute(
        "UPDATE users SET is_helper = ? WHERE id = ?",
        (1 if make_helper else 0, user_id),
    )
    db.commit()
    return jsonify({"ok": True, "is_helper": make_helper})


@app.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required_api
@require_same_origin
def admin_delete_user(admin, user_id):
    db = get_db()
    target = db.execute(
        "SELECT id, is_admin FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not target:
        return jsonify({"ok": False, "error": "Kullanıcı bulunamadı"}), 404
    if target["id"] == admin["id"]:
        return jsonify({"ok": False, "error": "Kendinizi silemezsiniz"}), 400
    if target["is_admin"] and admin_count(db) <= 1:
        return jsonify({"ok": False, "error": "Son yönetici silinemez"}), 400
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/payments/<int:payment_id>/note", methods=["POST"])
@helper_or_admin_api
@require_same_origin
def admin_payment_note(admin, payment_id):
    data = request.get_json(silent=True) or {}
    note = (data.get("admin_note") or data.get("note") or "").strip()
    db = get_db()
    row = db.execute(
        "SELECT id FROM payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Ödeme kaydı yok"}), 404
    db.execute(
        """
        UPDATE payments SET admin_note = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (note or None, payment_id),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/payments/<int:payment_id>/status", methods=["POST"])
@helper_or_admin_api
@require_same_origin
def admin_payment_status(admin, payment_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in PAYMENT_STATUSES:
        return jsonify(
            {"ok": False, "error": "Geçersiz durum (pending/approved/rejected)"}
        ), 400
    db = get_db()
    row = db.execute(
        "SELECT id FROM payments WHERE id = ?", (payment_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Ödeme kaydı yok"}), 404
    db.execute(
        """
        UPDATE payments SET status = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (status, payment_id),
    )
    db.commit()
    log.info("payment_status id=%s status=%s by=%s", payment_id, status, admin["id"])
    return jsonify({"ok": True, "status": status})


@app.route("/api/admin/settings", methods=["POST"])
@admin_required_api
@require_same_origin
def admin_save_settings(admin):
    data = request.get_json(silent=True) or {}
    allowed = {
        "site_title",
        "tagline",
        "instagram_handle",
        "registration_open",
        "maintenance_mode",
        "bank_iban",
        "bank_name",
        "bank_recipient",
        "helper_email",
        "whatsapp_phone",
        "whatsapp_label",
    }
    updated = []
    for key in allowed:
        if key not in data:
            continue
        val = data[key]
        if key in ("registration_open", "maintenance_mode"):
            val = "1" if str(val) in ("1", "true", "True", "on", "yes") else "0"
        else:
            val = str(val or "").strip()
            if key == "instagram_handle":
                val = val.lstrip("@")
            if key == "site_title" and not val:
                return jsonify({"ok": False, "error": "Site başlığı boş olamaz"}), 400
            if key == "bank_iban":
                plain = val.replace(" ", "").upper()
                if not plain.startswith("TR") or len(plain) < 15:
                    return jsonify({"ok": False, "error": "Geçerli bir IBAN girin"}), 400
                # pretty-print groups of 4
                val = " ".join(plain[i : i + 4] for i in range(0, len(plain), 4))
            if key == "bank_recipient" and not val:
                return jsonify({"ok": False, "error": "Alıcı adı boş olamaz"}), 400
        set_setting(key, val)
        updated.append(key)
    if "helper_email" in updated:
        ensure_helper(get_db())
    return jsonify({"ok": True, "updated": updated, "settings": get_all_settings()})


@app.route("/logout")
def logout_redirect():
    session.clear()
    return redirect(url_for("index"))


init_db()
log.info("startup keyless_iban=1")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8766"))
    app.run(host="0.0.0.0", port=port, debug=False)
