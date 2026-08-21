#!/usr/bin/env python3
"""
XUI Panel Bot — ربات مدیریت پنل 3x-ui (sanaei) - آخرین نسخه
رباتی که به پنل 3x-ui وصل میشه و کاربر ایجاد/حذف/مدیریت می‌کنه.
فقط ادمین‌ها اجازه استفاده دارن.
پشتیبانی از هر دو روش: API Token (پیشنهادی) یا یوزر/پسورد

متغیرهای محیطی (Railway Variables):
    BOT_TOKEN          توکن ربات تلگرام
    ADMIN_IDS           آیدی عددی ادمین‌ها (کاما جدا)
    PANEL_URL           آدرس پنل  مثال: https://panel.example.com
    PANEL_API_TOKEN     توکن API پنل (توی Settings→Security ساخته میشه) - اولویت داره
    PANEL_USERNAME      یوزرنیم ادمین پنل (اگه توکن نباشه)
    PANEL_PASSWORD      پسورد ادمین پنل (اگه توکن نباشه)
    PANEL_INBOUND_ID    آیدی اینباند پیش‌فرض (اختیاری)
    PANEL_SUBSCRIPTION_HOST  هاست اشتراک (اختیاری)
"""

import os
import json
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from datetime import datetime, timedelta

# ───────────────────────── کانفیگ ─────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
PANEL_URL = os.environ.get("PANEL_URL", "").rstrip("/")
PANEL_API_TOKEN = os.environ.get("PANEL_API_TOKEN", "")
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_INBOUND_ID = os.environ.get("PANEL_INBOUND_ID", "")
SUB_HOST = os.environ.get("PANEL_SUBSCRIPTION_HOST", PANEL_URL).rstrip("/")


# نسخه‌های مختلف پنل، مسیر پایه‌ی API متفاوتی دارن:
#   - x-ui قدیمی (vaxilu)      -> /xui/API/...
#   - 3x-ui جدید (MHSanaei)    -> /panel/api/...
# چون نمی‌دونیم کدومه، اول 3x-ui رو امتحان می‌کنیم و اگه با 404 مواجه شدیم
# خودکار سراغ مسیر قدیمی می‌ریم و از اون به بعد همونو استفاده می‌کنیم.
_api_base_candidates = [f"{PANEL_URL}/panel/api", f"{PANEL_URL}/xui/API"]
_api_base_index = 0

def API():
    return _api_base_candidates[_api_base_index]

# ───────────────────────── ابزارهای HTTP ─────────────────────────
_opener = None
_cj = None

def _ensure_opener():
    global _opener, _cj
    if _opener is None:
        _cj = http.cookiejar.CookieJar()
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))

def _req(method, path, data=None, timeout=30):
    url = f"{API()}/{path}"
    # اولویت: api_token در query string
    if PANEL_API_TOKEN:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}api_token={urllib.parse.quote(PANEL_API_TOKEN, safe='')}"
    h = {"Content-Type": "application/json"}
    if PANEL_API_TOKEN:
        h["Authorization"] = f"Bearer {PANEL_API_TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    _ensure_opener()
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def panel_login():
    """فقط وقتی توکن نیست صدا زده میشه."""
    _ensure_opener()
    _req("POST", "login", {"username": PANEL_USERNAME, "password": PANEL_PASSWORD})

def _switch_api_base():
    """اگه مسیر فعلی جواب نداد، مسیر دیگه رو امتحان کن."""
    global _api_base_index
    if _api_base_index < len(_api_base_candidates) - 1:
        _api_base_index += 1
        print(f"⚠️ مسیر API عوض شد به: {API()}")
        return True
    return False

def api_get(path):
    try:
        return _req("GET", path)
    except urllib.error.HTTPError as e:
        if e.code == 404 and _switch_api_base():
            return api_get(path)
        if e.code in (401, 403) and not PANEL_API_TOKEN:
            panel_login()
            return _req("GET", path)
        raise

def api_post(path, data):
    try:
        return _req("POST", path, data)
    except urllib.error.HTTPError as e:
        if e.code == 404 and _switch_api_base():
            return api_post(path, data)
        if e.code in (401, 403) and not PANEL_API_TOKEN:
            panel_login()
            return _req("POST", path, data)
        raise

# ───────────────────────── توابع پنل ─────────────────────────
def safe_json(val, default=None):
    """
    بعضی نسخه‌های پنل، فیلدهایی مثل settings/streamSettings رو به‌صورت
    رشته‌ی JSON برمی‌گردونن، بعضی‌ها به‌صورت آبجکت/دیکشنری آماده.
    این تابع هر دو حالت رو پشتیبانی می‌کنه.
    """
    if val is None:
        return default if default is not None else {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (bytes, bytearray)):
        val = val.decode()
    if isinstance(val, str):
        if not val.strip():
            return default if default is not None else {}
        return json.loads(val)
    return default if default is not None else {}

def get_inbounds():
    r = api_get("inbounds/list")
    return r.get("obj", [])

def find_default_inbound(inbounds):
    if PANEL_INBOUND_ID:
        for ib in inbounds:
            if str(ib.get("id")) == str(PANEL_INBOUND_ID):
                return ib
    for ib in inbounds:
        if ib.get("protocol") == "vless":
            return ib
    return inbounds[0] if inbounds else None

def add_client(inbound, email, total_gb, days, limit_ip=0):
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
        "flow": "",
    }
    clients.append(new_client)
    settings["clients"] = clients
    payload = {"id": inbound.get("id"), "settings": json.dumps(settings)}
    r = api_post("inbounds/addClient", payload)
    return r.get("success", False), new_client, sub_id

def remove_client(inbound, email):
    settings = json.loads(inbound.get("settings", "{}"))
    clients = [c for c in settings.get("clients", []) if c.get("email") != email]
    settings["clients"] = clients
    payload = {"id": inbound.get("id"), "settings": json.dumps(settings)}
    r = api_post("inbounds/addClient", payload)
    return r.get("success", False)

def list_clients(inbound):
    settings = json.loads(inbound.get("settings", "{}"))
    return settings.get("clients", [])

# ───────────────────────── ساخت لینک vless ─────────────────────────
def build_vless_link(inbound, client, host_override=None):
    port = inbound.get("port", 443)
    stream = json.loads(inbound.get("streamSettings", "{}"))
    net = stream.get("network", "tcp")
    security = stream.get("security", "none")
    host = host_override or PANEL_URL.replace("https://", "").replace("http://", "").split("/")[0]

    params = {"encryption": "none", "security": security, "type": net}
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

    if security in ("tls", "reality"):
        tls = stream.get("tlsSettings", {}) or stream.get("realitySettings", {})
        params["sni"] = tls.get("serverName", host) or host
        params["fp"] = "chrome"
        params["alpn"] = "http/1.1"
        if security == "reality":
            reality = stream.get("realitySettings", {})
            params["pbk"] = reality.get("publicKey", "")
            params["sid"] = reality.get("shortIds", [""])[0]
            params["spx"] = "/"

    q = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())
    remark = urllib.parse.quote(f"sLv-{client.get('email','')}-1")
    return f"vless://{client.get('id')}@{host}:{port}?{q}#{remark}"

def build_subscription_url(sub_id):
    return f"{SUB_HOST}/sub/{sub_id}"

# ───────────────────────── خروجی مثل عکس ─────────────────────────
def format_user_output(client, link, sub_url):
    name = client.get("email", "?")
    total_gb = client.get("totalGB", 0) / 1024**3
    vol = f"{total_gb:.1f}GB" if total_gb else "نامحدود"
    days = "نامحدود"
    if client.get("expiryTime"):
        days = str((datetime.fromtimestamp(client["expiryTime"]/1000) - datetime.now()).days)
    return (
        "✅ کاربر با موفقیت ساخته شد!\n\n"
        f"👤 نام: {name}\n"
        f"🔐 پروتکل: ALL | 🚀 ترنسپورت: ALL\n"
        f"📊 حجم: {vol}\n"
        f"⌛ انقضا: {days} روز\n\n"
        "🔗 لینک اصلی کانفیگ:\n"
        f"{link}\n\n"
        "🌐 آدرس اشتراک:\n"
        f"{sub_url}"
    )

# ───────────────────────── ربات تلگرام ─────────────────────────
def tg(method, data=None, timeout=35):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(data or {}).encode(),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def check_bot_token():
    """چک می‌کنه توکن بات معتبره و بهمون میگه بات چیه (برای دیباگ توی لاگ Railway)."""
    try:
        r = tg("getMe", timeout=15)
        if r.get("ok"):
            info = r["result"]
            print(f"✅ توکن بات معتبره: @{info.get('username')}")
            return True
        else:
            print(f"❌ توکن بات نامعتبره: {r}")
            return False
    except Exception as e:
        print(f"❌ نمیشه به تلگرام وصل شد (توکن یا شبکه رو چک کنید): {e}")
        return False

def clear_webhook():
    """
    مهم‌ترین دلیل رایج «بات بالا میاد ولی جواب نمیده»:
    اگه یه وبهوک روی این توکن ست شده باشه، getUpdates همیشه با خطای 409
    مواجه میشه و بات هیچ‌وقت آپدیتی دریافت نمی‌کنه، بدون هیچ ارور واضحی.
    این تابع در شروع کار، هر وبهوکی که ست شده رو پاک می‌کنه.
    """
    try:
        info = tg("getWebhookInfo", timeout=15)
        url = info.get("result", {}).get("url", "")
        if url:
            print(f"⚠️ یک وبهوک فعال پیدا شد ({url}) — در حال حذف...")
            tg("deleteWebhook", {"drop_pending_updates": True}, timeout=15)
            print("✅ وبهوک حذف شد. حالا getUpdates باید کار کنه.")
        else:
            print("✅ هیچ وبهوکی ست نشده — مسیر برای getUpdates بازه.")
    except Exception as e:
        print(f"❌ نتونستم وضعیت وبهوک رو چک کنم: {e}")

def is_admin(uid):
    return uid in ADMIN_IDS

def send_message(chat_id, text, reply_to=None):
    d = {"chat_id": chat_id, "text": text}
    if reply_to:
        d["reply_to_message_id"] = reply_to
    return tg("sendMessage", d)

def send_photo(chat_id, photo_path, caption=None, reply_to=None):
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

# ───────────────────────── حلقه اصلی ─────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نیست")
        return
    if not ADMIN_IDS:
        print("❌ ADMIN_IDS تنظیم نیست")
        return
    if not PANEL_URL:
        print("❌ PANEL_URL تنظیم نیست")
        return
    if not PANEL_API_TOKEN and (not PANEL_USERNAME or not PANEL_PASSWORD):
        print("❌ یا PANEL_API_TOKEN یا PANEL_USERNAME+PANEL_PASSWORD لازمه")
        return

    mode = "API Token" if PANEL_API_TOKEN else "Username/Password"
    print(f"🤖 ربات پنل شروع شد | متد: {mode} | ادمین‌ها: {ADMIN_IDS}")

    if not check_bot_token():
        return
    clear_webhook()

    offset = 0
    while True:
        try:
            # نکته: تایم‌اوت urlopen (35) باید از تایم‌اوت long-poll (30) بیشتر باشه
            # وگرنه دقیقاً همون لحظه‌ای که تلگرام می‌خواد جواب بده Read timeout می‌گیریم.
            updates = tg("getUpdates", {"offset": offset, "timeout": 30}, timeout=35)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                if "message" not in u:
                    continue
                msg = u["message"]
                text = msg.get("text", "")
                user = msg.get("from", {})
                uid = user.get("id")
                print(f"📩 پیام از {uid} ({user.get('username','?')}): {text!r}")
                if not is_admin(uid):
                    print(f"⛔ {uid} ادمین نیست. ADMIN_IDS فعلی: {ADMIN_IDS}")
                    continue
                if not text.startswith("/"):
                    continue
                parts = text.split()
                cmd, args = parts[0].lower(), parts[1:]
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
