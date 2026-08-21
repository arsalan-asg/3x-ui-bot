#!/usr/bin/env python3
"""
XUI Panel Bot — ربات مدیریت پنل 3x-ui (sanaei)
رباتی که به پنل 3x-ui وصل میشه و کاربر ایجاد/حذف/مدیریت می‌کنه.
فقط ادمین‌ها اجازه استفاده دارن.

متغیرهای محیطی (Railway Variables):
    BOT_TOKEN          توکن ربات تلگرام
    ADMIN_IDS           آیدی عددی ادمین‌ها (کاما جدا) مثال: 6582070627,123456
    PANEL_URL           آدرس پنل  مثال: https://panel.example.com
    PANEL_USERNAME      یوزرنیم ادمین پنل
    PANEL_PASSWORD      پسورد ادمین پنل
    PANEL_INBOUND_ID    آیدی اینباند پیش‌فرض (اختیاری، اگه نباشه اولین vless رو برمی‌داره)
    PANEL_SUBSCRIPTION_HOST  هاست اشتراک (اختیاری، پیش‌فرض از PANEL_URL)
"""

import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.error
import http.cookiejar
from datetime import datetime, timedelta

# ───────────────────────── کانفیگ ─────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
PANEL_URL = os.environ.get("PANEL_URL", "").rstrip("/")
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_INBOUND_ID = os.environ.get("PANEL_INBOUND_ID", "")
SUB_HOST = os.environ.get("PANEL_SUBSCRIPTION_HOST", PANEL_URL).rstrip("/")

API = f"{PANEL_URL}/xui/API"

# ───────────────────────── ابزارهای HTTP ─────────────────────────
def _make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)), cj

_opener, _cj = _make_opener()

def _req(method, url, data=None, headers=None, timeout=30):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def panel_login():
    """لاگین به پنل و ذخیره کوکی."""
    _req("POST", f"{API}/login",
         {"username": PANEL_USERNAME, "password": PANEL_PASSWORD})
    # 3x-ui returns session cookie; _cj now holds it

def api_get(path):
    return _req("GET", f"{API}/{path}")

def api_post(path, data):
    return _req("POST", f"{API}/{path}", data)

# ───────────────────────── توابع پنل ─────────────────────────
def get_inbounds():
    panel_login()
    r = api_get("inbounds")
    return r.get("obj", [])

def find_default_inbound(inbounds):
    """پیدا کردن اینباند پیش‌فرض (vless ترجیحی)."""
    if PANEL_INBOUND_ID:
        for ib in inbounds:
            if str(ib.get("id")) == str(PANEL_INBOUND_ID):
                return ib
    # اولین vless
    for ib in inbounds:
        if ib.get("protocol") == "vless":
            return ib
    # اولین هر چی
    return inbounds[0] if inbounds else None

def get_client_traffic(email):
    """گرفتن آمار ترافیک یه کلاینت."""
    try:
        r = api_get("inbounds/getClientTraffics/%3D" + email)
        return r
    except Exception:
        return None

def add_client(inbound, email, total_gb, days, limit_ip=0):
    """اضافه کردن کلاینت جدید به اینباند."""
    settings = json.loads(inbound.get("settings", "{}"))
    clients = settings.get("clients", [])

    client_id = str(uuid.uuid4())
    sub_id = str(uuid.uuid4()).replace("-", "")[:16]
    expiry = int((datetime.now() + timedelta(days=days)).timestamp() * 1000) if days else 0
    total_bytes = int(total_gb * 1024**3) if total_gb else 0

    new_client = {
        "id": client_id,
        "subId": sub_id,
        "email": email,
        "limitIp": limit_ip,
        "totalGB": total_bytes,
        "expiryTime": expiry,
        "enable": True,
        "tgId": "",
        "flow": "",
    }
    clients.append(new_client)
    settings["clients"] = clients

    payload = {
        "id": inbound.get("id"),
        "settings": json.dumps(settings),
    }
    panel_login()
    r = api_post("inbounds/addClient", payload)
    return r.get("success", False), new_client, sub_id

def remove_client(inbound, email):
    """حذف کلاینت از اینباند."""
    settings = json.loads(inbound.get("settings", "{}"))
    clients = [c for c in settings.get("clients", []) if c.get("email") != email]
    settings["clients"] = clients
    payload = {"id": inbound.get("id"), "settings": json.dumps(settings)}
    panel_login()
    r = api_post("inbounds/addClient", payload)
    return r.get("success", False)

def list_clients(inbound):
    settings = json.loads(inbound.get("settings", "{}"))
    return settings.get("clients", [])

# ───────────────────────── ساخت لینک vless ─────────────────────────
def build_vless_link(inbound, client, host_override=None):
    """ساخت لینک vless از تنظیمات اینباند + کلاینت."""
    listen = inbound.get("listen", "")
    port = inbound.get("port", 443)
    stream = json.loads(inbound.get("streamSettings", "{}"))
    net = stream.get("network", "tcp")
    security = stream.get("security", "none")

    host = host_override or PANEL_URL.replace("https://", "").replace("http://", "").split("/")[0]

    params = {
        "encryption": "none",
        "security": security,
        "type": net,
    }

    if net == "ws":
        ws = stream.get("wsSettings", {})
        params["host"] = ws.get("host", host)
        params["path"] = ws.get("path", "/")
    elif net == "grpc":
        grpc = stream.get("grpcSettings", {})
        params["serviceName"] = grpc.get("serviceName", "")
        params["mode"] = "multi"
    elif net == "tcp":
        tcp = stream.get("tcpSettings", {})
        if tcp.get("header", {}).get("type") == "http":
            params["headerType"] = "http"
            params["host"] = tcp.get("header", {}).get("request", {}).get("headers", {}).get("Host", [""])[0]

    if security == "tls":
        tls = stream.get("tlsSettings", {})
        params["sni"] = tls.get("serverName", host) or host
        params["fp"] = "chrome"
        params["alpn"] = "http/1.1"
    elif security == "reality":
        reality = stream.get("realitySettings", {})
        params["sni"] = reality.get("serverNames", [""])[0] or host
        params["fp"] = reality.get("fingerprint", "chrome")
        params["pbk"] = reality.get("publicKey", "")
        params["sid"] = reality.get("shortIds", [""])[0]
        params["spx"] = "/"
        params["type"] = net

    q = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())
    remark = urllib.parse.quote(f"sLv-{client.get('email','')}-1")
    return f"vless://{client.get('id')}@{host}:{port}?{q}#{remark}"

import urllib.parse

def build_subscription_url(sub_id):
    return f"{SUB_HOST}/sub/{sub_id}"

# ───────────────────────── خروجی مثل عکس ─────────────────────────
def format_user_output(client, link, sub_url):
    name = client.get("email", "?")
    proto = "ALL"
    transport = "ALL"
    total_gb = client.get("totalGB", 0) / 1024**3
    vol = f"{total_gb:.1f}GB" if total_gb else "نامحدود"
    days = "نامحدود"
    if client.get("expiryTime"):
        exp = datetime.fromtimestamp(client["expiryTime"] / 1000)
        days = str((exp - datetime.now()).days)

    return (
        "✅ کاربر با موفقیت ساخته شد!\n\n"
        f"👤 نام: {name}\n"
        f"🔐 پروتکل: {proto} | 🚀 ترنسپورت: {transport}\n"
        f"📊 حجم: {vol}\n"
        f"⌛ انقضا: {days} روز\n\n"
        "🔗 لینک اصلی کانفیگ:\n"
        f"{link}\n\n"
        "🌐 آدرس اشتراک:\n"
        f"{sub_url}"
    )

# ───────────────────────── ربات تلگرام ─────────────────────────
def tg(method, data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def is_admin(uid):
    return uid in ADMIN_IDS

def send_message(chat_id, text, reply_to=None, parse_mode=None):
    d = {"chat_id": chat_id, "text": text}
    if reply_to:
        d["reply_to_message_id"] = reply_to
    if parse_mode:
        d["parse_mode"] = parse_mode
    return tg("sendMessage", d)

def send_photo(chat_id, photo_path, caption=None, reply_to=None):
    # ارسال عکس با multipart
    import mimetypes
    boundary = "----xuibotboundary"
    mtype = mimetypes.guess_type(photo_path)[0] or "image/png"
    with open(photo_path, "rb") as f:
        raw = f.read()
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode()
    if reply_to:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="reply_to_message_id"\r\n\r\n{reply_to}\r\n'.encode()
    if caption:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="photo"; filename="qr.png"\r\n'.encode()
    body += f"Content-Type: {mtype}\r\n\r\n".encode()
    body += raw
    body += f"\r\n--{boundary}--\r\n".encode()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    req = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def generate_qr(text, path="/tmp/qr.png"):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(path)
        return path
    except ImportError:
        return None

# ───────────────────────── دستورات ─────────────────────────
def cmd_adduser(msg, args):
    chat_id = msg["chat"]["id"]
    reply_to = msg.get("message_id")
    if not args:
        send_message(chat_id, "استفاده:\n/adduser <نام> <حجم_GB> <روز>\nمثال: /adduser ali 100 180", reply_to)
        return
    name = args[0]
    total_gb = float(args[1]) if len(args) > 1 else 0
    days = int(args[2]) if len(args) > 2 else 0

    try:
        inbounds = get_inbounds()
        ib = find_default_inbound(inbounds)
        if not ib:
            send_message(chat_id, "❌ هیچ اینباندی پیدا نشد!", reply_to)
            return
        ok, client, sub_id = add_client(ib, name, total_gb, days)
        if not ok:
            send_message(chat_id, "❌ خطا در ساخت کاربر!", reply_to)
            return
        link = build_vless_link(ib, client)
        sub = build_subscription_url(sub_id)
        out = format_user_output(client, link, sub)
        send_message(chat_id, out, reply_to)
        qr_path = generate_qr(link)
        if qr_path:
            send_photo(chat_id, qr_path, caption="📱 QR کد کانفیگ", reply_to=reply_to)
    except Exception as e:
        send_message(chat_id, f"❌ خطا: {e}", reply_to)

def cmd_deluser(msg, args):
    chat_id = msg["chat"]["id"]
    reply_to = msg.get("message_id")
    if not args:
        send_message(chat_id, "استفاده: /deluser <نام>", reply_to)
        return
    name = args[0]
    try:
        inbounds = get_inbounds()
        ib = find_default_inbound(inbounds)
        if remove_client(ib, name):
            send_message(chat_id, f"✅ کاربر {name} حذف شد.", reply_to)
        else:
            send_message(chat_id, f"❌ کاربر {name} پیدا نشد یا حذف نشد.", reply_to)
    except Exception as e:
        send_message(chat_id, f"❌ خطا: {e}", reply_to)

def cmd_list(msg, args):
    chat_id = msg["chat"]["id"]
    reply_to = msg.get("message_id")
    try:
        inbounds = get_inbounds()
        ib = find_default_inbound(inbounds)
        clients = list_clients(ib)
        if not clients:
            send_message(chat_id, "هیچ کاربری نیست.", reply_to)
            return
        lines = [f"👥 تعداد کاربران: {len(clients)}\n"]
        for c in clients:
            exp = ""
            if c.get("expiryTime"):
                exp = (datetime.fromtimestamp(c["expiryTime"]/1000) - datetime.now()).days
            lines.append(f"• {c.get('email')} — باقی‌مانده: {exp} روز")
        send_message(chat_id, "\n".join(lines), reply_to)
    except Exception as e:
        send_message(chat_id, f"❌ خطا: {e}", reply_to)

def cmd_help(msg, args):
    chat_id = msg["chat"]["id"]
    text = (
        "🤖 دستورات ربات پنل 3x-ui:\n\n"
        "/adduser <نام> <حجم_GB> <روز> — ساخت کاربر جدید\n"
        "/deluser <نام> — حذف کاربر\n"
        "/list — لیست کاربران\n"
        "/info <نام> — اطلاعات کاربر\n"
        "/help — همین راهنما\n\n"
        "فقط ادمین‌ها مجاز هستند."
    )
    send_message(chat_id, text, msg.get("message_id"))

def cmd_info(msg, args):
    chat_id = msg["chat"]["id"]
    reply_to = msg.get("message_id")
    if not args:
        send_message(chat_id, "استفاده: /info <نام>", reply_to)
        return
    name = args[0]
    try:
        inbounds = get_inbounds()
        ib = find_default_inbound(inbounds)
        clients = list_clients(ib)
        for c in clients:
            if c.get("email") == name:
                link = build_vless_link(ib, c)
                sub = build_subscription_url(c.get("subId", ""))
                send_message(chat_id, format_user_output(c, link, sub), reply_to)
                return
        send_message(chat_id, f"❌ کاربر {name} پیدا نشد.", reply_to)
    except Exception as e:
        send_message(chat_id, f"❌ خطا: {e}", reply_to)

# ───────────────────────── حلقه اصلی ─────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نیست")
        return
    if not ADMIN_IDS:
        print("❌ ADMIN_IDS تنظیم نیست")
        return
    if not PANEL_URL or not PANEL_USERNAME or not PANEL_PASSWORD:
        print("❌ تنظیمات پنل ناقصه")
        return

    print(f"🤖 ربات پنل شروع شد | ادمین‌ها: {ADMIN_IDS}")
    offset = 0
    while True:
        try:
            updates = tg("getUpdates", {"offset": offset, "timeout": 30})
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                if "message" not in u:
                    continue
                msg = u["message"]
                text = msg.get("text", "")
                user = msg.get("from", {})
                if not is_admin(user.get("id")):
                    continue
                if not text.startswith("/"):
                    continue
                parts = text.split()
                cmd, args = parts[0].lower(), parts[1:]
                # حذف @botname از انتهای دستور
                if "@" in cmd:
                    cmd = cmd.split("@")[0]
                if cmd == "/start" or cmd == "/help":
                    cmd_help(msg, args)
                elif cmd == "/adduser":
                    cmd_adduser(msg, args)
                elif cmd == "/deluser":
                    cmd_deluser(msg, args)
                elif cmd == "/list":
                    cmd_list(msg, args)
                elif cmd == "/info":
                    cmd_info(msg, args)
        except urllib.error.HTTPError as e:
            if e.code == 409:
                time.sleep(5)
            else:
                print(f"HTTP {e.code}: {e.reason}")
                time.sleep(2)
        except Exception as e:
            print(f"خطا: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
