"""
إعدادات ميزة الذكاء الاصطناعي — تُقرأ بالكامل من متغيّرات البيئة.

لا تضع أي مفتاح أو قيمة حساسة داخل الكود. لتغيير أي إعداد لاحقًا (عند نقل المشروع
لخادم المستشفى مثلاً) يكفي تعديل متغيّرات البيئة دون لمس الكود:

- بوابة Replit للذكاء الاصطناعي (مفضّلة، بدون مفتاح خاص): تُوفَّر تلقائياً عبر
  AI_INTEGRATIONS_GEMINI_BASE_URL + AI_INTEGRATIONS_GEMINI_API_KEY.
- GEMINI_API_KEY    : مفتاح Google Gemini الخاص (بديل احتياطي إن لم تتوفّر البوابة).
- DATABASE_URL      : رابط قاعدة بيانات PostgreSQL (لحفظ المحادثات).
- CARBAI_MODEL      : اسم النموذج (افتراضي gemini-2.5-flash).
- CARBAI_MSG_LIMIT  : حد الرسائل اليومي لكل مستخدم (افتراضي 15).
- CARBAI_IMG_LIMIT  : حد الصور اليومي لكل مستخدم (افتراضي 5).
- CARBAI_HISTORY    : عدد الرسائل السابقة المُرسلة للنموذج كسياق (افتراضي 20).
"""

import os


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


GEMINI_API_KEY: str = (os.environ.get("GEMINI_API_KEY") or "").strip()
# بوابة Replit للذكاء الاصطناعي (Gemini) — تُوفَّر تلقائياً ولا تحتاج مفتاحاً خاصاً.
# عند توفّرها تُستخدم بدل GEMINI_API_KEY (الذي قد يكون محظوراً من Google).
AI_GATEWAY_BASE_URL: str = (os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL") or "").strip()
AI_GATEWAY_API_KEY: str = (os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY") or "").strip()
DATABASE_URL: str = (os.environ.get("DATABASE_URL") or "").strip()
AI_MODEL: str = (os.environ.get("CARBAI_MODEL") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"

DAILY_MSG_LIMIT: int = _int_env("CARBAI_MSG_LIMIT", 15)
DAILY_IMG_LIMIT: int = _int_env("CARBAI_IMG_LIMIT", 5)
MAX_HISTORY_MESSAGES: int = _int_env("CARBAI_HISTORY", 20)


def gateway_configured() -> bool:
    """هل بوابة Replit للذكاء الاصطناعي متوفّرة؟"""
    return bool(AI_GATEWAY_BASE_URL and AI_GATEWAY_API_KEY)


def ai_configured() -> bool:
    """هل الذكاء الاصطناعي متاح؟ (بوابة Replit أو مفتاح Gemini خاص)"""
    return gateway_configured() or bool(GEMINI_API_KEY)


def db_configured() -> bool:
    """هل رابط قاعدة البيانات متوفّر؟"""
    return bool(DATABASE_URL)
