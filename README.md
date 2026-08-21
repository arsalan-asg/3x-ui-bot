# X-UI Panel Bot

ربات تلگرام برای مدیریت پنل **۳x-ui (sanaei)** - آخرین نسخه.
کاربر جدید می‌سازه، حذف می‌کنه، لیست می‌کنه و لینک vless + آدرس اشتراک + QR کد میده.

## ویژگی‌ها
- ✅ ساخت کاربر با حجم و زمان دلخواه
- ✅ حذف کاربر
- ✅ لیست کاربران
- ✅ نمایش اطلاعات کاربر (لینک + اشتراک + QR)
- ✅ فقط ادمین‌ها اجازه دارن
- ✅ پشتیبانی از **API Token** (پیشنهادی) یا یوزر/پسورد
- ✅ خروجی دقیقاً مشابه پنل اصلی

## نصب روی Railway

1. این ریپو رو توی Railway ایجاد/دیپلوی کن.
2. توی بخش **Variables** اینا رو ست کن:

| متغیر | توضیح | مثال |
|------|------|------|
| `BOT_TOKEN` | توکن ربات تلگرام | `123456:ABCdef...` |
| `ADMIN_IDS` | آیدی عددی ادمین (کاما جدا) | `6582070627,123456` |
| `PANEL_URL` | آدرس پنل ۳x-ui | `https://panel.example.com` |
| `PANEL_API_TOKEN` | توکن API پنل (Settings→Security) - **اولویت داره** | `a1b2c3...` |
| `PANEL_USERNAME` | یوزرنیم ادمین پنل (اگه توکن نباشه) | `admin` |
| `PANEL_PASSWORD` | پسورد ادمین پنل (اگه توکن نباشه) | `pass123` |
| `PANEL_INBOUND_ID` | آیدی اینباند (اختیاری) | `1` |
| `PANEL_SUBSCRIPTION_HOST` | هاست اشتراک (اختیاری) | `https://sub.example.com` |

> **نکته:** اگه `PANEL_API_TOKEN` ست باشه، ربات با توکن وصل میشه (نیازی به لاگین نیست).
> اگه نباشه، از `PANEL_USERNAME` + `PANEL_PASSWORD` استفاده می‌کنه.

3. Railway خودش با `Procfile` ربات رو اجرا می‌کنه.

## دستورات
```
/adduser <نام> <حجم_GB> <روز>
/deluser <نام>
/list
/info <نام>
/help
```

مثال:
```
/adduser ali 100 180
```
→ کاربر `ali` با ۱۰۰GB و ۱۸۰ روز می‌سازه و لینک vless + اشتراک + QR میده.

## ساختار فایل‌ها
```
panel-bot/
├── bot.py            # کد اصلی ربات
├── requirements.txt  # کتابخونه‌ها
├── Procfile          # دستور اجرا برای Railway
└── README.md         # همین فایل
```

## نحوه کار با API Token
توی پنل ۳x-ui:
1. برو `Settings` → `Security`
2. بخش **API Token** رو پیدا کن و یه توکن بساز
3. اون رو توی Railway Variables به عنوان `PANEL_API_TOKEN` ست کن

ربات باهاش درخواست‌ها رو می‌زنه:
```
GET /xui/API/inbounds?api_token=TOKEN
Authorization: Bearer TOKEN
```

## نکات
- ربات فقط با پروتکل‌های `vless` کار می‌کنه (پیش‌فرض اولین اینباند vless).
- اگه `PANEL_INBOUND_ID` ست نشه، اولین اینباند vless رو انتخاب می‌کنه.
- خروجی دقیقاً فرمت پنل اصلی رو داره.

## عیب‌یابی
- **ربات جواب نمیده:** چک کن `BOT_TOKEN` و `ADMIN_IDS` درسته.
- **خطای لاگین/توکن:** چک کن `PANEL_URL` و `PANEL_API_TOKEN`.
- **۴۰۹ Conflict:** فقط یک نمونه از ربات باید اجرا بشه.
