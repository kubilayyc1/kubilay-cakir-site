#!/usr/bin/env python3
"""Kubilay Çakır — auth, keyless IBAN ödeme bildirimi, tam admin paneli."""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.environ.get("RENDER_DISK_PATH") or os.environ.get("DATA_DIR") or BASE_DIR
os.makedirs(_data_dir, exist_ok=True)
DB_PATH = os.path.join(_data_dir, "users.db")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "kubilaycakir54@yahoo.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Kubilay8181")

DEFAULT_IBAN = "TR83 0015 7000 0000 0205 4704 26"
DEFAULT_BANK = "Enpara"
DEFAULT_RECIPIENT = "Kubilay Mert Çakır"

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
            INSERT INTO users (name, email, password_hash, is_admin, is_blocked)
            VALUES (?, ?, ?, 1, 0)
            """,
            ("Admin", ADMIN_EMAIL, pw_hash),
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
    }


@app.context_processor
def inject_site():
    try:
        return {"site": site_ctx()}
    except Exception:
        return {
            "site": {
                "site_title": "Kubilay Çakır",
                "tagline": "Kişisel alan · havale ile güvenli ödeme · Instagram",
                "instagram_handle": "kubilayyc1",
                "instagram_url": "https://instagram.com/kubilayyc1",
                "registration_open": True,
                "maintenance_mode": False,
                "payment_ready": True,
                "bank": {
                    "iban": DEFAULT_IBAN,
                    "iban_plain": DEFAULT_IBAN.replace(" ", ""),
                    "bank_name": DEFAULT_BANK,
                    "recipient": DEFAULT_RECIPIENT,
                },
            }
        }


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_db().execute(
        """
        SELECT id, name, email, is_admin, is_blocked, created_at
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
    if user and user.get("is_admin"):
        return None
    allowed = {
        "login_page",
        "api_login",
        "api_logout",
        "logout_redirect",
        "static",
        "favicon",
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
            "pending": "Ödeme bildiriminiz alındı. Yönetici onayından sonra tamamlanır.",
            "approved": "Ödemeniz onaylandı. Teşekkürler!",
            "rejected": "Ödeme bildiriminiz reddedildi. Gerekirse tekrar deneyin.",
        }.get(row["status"], "Ödeme kaydı güncellendi."),
        "payment_id": row["id"],
        "conversation_id": row["conversation_id"],
        "amount": row["amount"],
        "note": row["note"],
        "error_message": None,
    }
    return render_template("odeme_sonuc.html", user=user, result=result)


@app.route("/admin")
@login_required_page
@admin_required
def admin_page():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    filter_role = (request.args.get("role") or "all").strip()
    filter_block = (request.args.get("blocked") or "all").strip()

    sql = """
        SELECT id, name, email, created_at, is_admin, is_blocked
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
        SELECT id, name, email, password_hash, is_admin, is_blocked
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
    return jsonify(
        {
            "ok": True,
            "payment_id": payment_id,
            "status": "pending",
            "conversation_id": conversation_id,
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
@admin_required_api
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
@admin_required_api
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
