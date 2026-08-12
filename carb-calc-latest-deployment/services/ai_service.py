"""
الاتصال بنموذج Google Gemini — متخصص في التغذية فقط.

المفتاح يُقرأ من متغيّر البيئة GEMINI_API_KEY (عبر config)، والنموذج قابل للتغيير
عبر CARBAI_MODEL. الوحدة لا ترفع استثناءات إلى الواجهة مباشرة؛ عند أي خطأ تُطلق
AIError برسالة عربية مناسبة تلتقطها app.py.
"""

import logging

from google import genai
from google.genai import types

from . import config

_log = logging.getLogger("carb-calc.ai")

# ── التعليمات الأساسية للنموذج (متخصص تغذية فقط) ─────────────────────────────
REFUSAL_MESSAGE = "هذه الخدمة مخصصة للإجابة عن الأسئلة المتعلقة بالتغذية فقط."

SYSTEM_PROMPT = f"""أنت مساعد ذكاء اصطناعي متخصص في التغذية فقط، ضمن تطبيق طبي يخدم
مرضى السكري في مستشفى. أنت لست مساعدًا عامًا.

مجال إجابتك محصور حصريًا في المواضيع التالية:
- التغذية العلاجية.
- السكري وعلاقته بالغذاء.
- الكربوهيدرات.
- تحليل الأطعمة وقيمها الغذائية.
- تحليل صور الطعام والتعرّف عليه غذائيًا.
- البدائل الغذائية.
- السعرات الحرارية.
- القيم الغذائية.
- الفيتامينات والمعادن المتعلقة بالغذاء.
- الملصقات الغذائية.
- الإرشادات الغذائية العامة.

قواعد صارمة يجب الالتزام بها:
1) إذا كان سؤال المستخدم خارج مجال التغذية تمامًا (مثل الرياضة العامة، السياسة،
   البرمجة، الترفيه، أو أي موضوع لا صلة له بالغذاء)، فلا تُجب عليه إطلاقًا، وبدلًا
   من ذلك اكتب هذه الجملة فقط ولا شيء غيرها:
   «{REFUSAL_MESSAGE}»
2) أجب دائمًا باللغة العربية الفصحى الواضحة والمختصرة قدر الإمكان.
3) قدّم معلومات دقيقة وموثوقة. إذا لم تكن واثقًا من معلومة معيّنة، فوضّح ذلك
   صراحةً للمستخدم (قل مثلًا: «هذه القيمة تقريبية» أو «يُفضّل التأكد من الملصق»)
   بدلًا من إعطاء معلومة قد تكون غير صحيحة.
4) لا تعتمد على أي جدول بيانات خارجي؛ اعتمد على معرفتك الغذائية الموثوقة.
5) عند تحليل صورة طعام: قدّم الإجابة بتنسيق منظّم وواضح باستخدام عناوين عريضة ونقاط،
   واذكر الحقول التالية عند توفّرها لكل صنف في الصورة:
   - **اسم الطعام**
   - **تقدير الكمية** (بالجرام أو الحصص تقريبًا)
   - **الكربوهيدرات**
   - **البروتين**
   - **الدهون**
   - **السعرات الحرارية**
   - **المؤشر الجلايسيمي** (إن كان معروفًا)
   - **بدائل غذائية مناسبة** لمريض السكري (إن وُجدت)
   وضّح أن القيم تقريبية. إن كانت الصورة غير واضحة أو لا تحتوي طعامًا، فوضّح ذلك بلطف
   دون اختلاق أرقام.
6) هذه المعلومات إرشادية وتثقيفية وليست بديلًا عن الطبيب المعالج، خصوصًا في قرارات
   الجرعات والعلاج. أضف تذكيرًا مختصرًا بهذا فقط عند الحاجة (لا تُكرّره في كل رد)."""


class AIError(Exception):
    """خطأ أثناء الاتصال بنموذج الذكاء الاصطناعي."""


_client = None


def is_available() -> bool:
    return config.ai_configured()


def _get_client():
    global _client
    if _client is None:
        if config.gateway_configured():
            # بوابة Replit للذكاء الاصطناعي (بدون مفتاح خاص). api_version="" مهم:
            # مسار البوابة لا يستخدم /v1beta.
            _client = genai.Client(
                api_key=config.AI_GATEWAY_API_KEY,
                http_options=types.HttpOptions(
                    base_url=config.AI_GATEWAY_BASE_URL, api_version=""),
            )
        else:
            _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _sanitize_text(s):
    """يُزيل أحرف الـ surrogate الشاردة من نص الرد.

    نموذج Gemini قد يقطع الرد عند حد التوكِنز في منتصف إيموجي، فيبقى نصف
    زوج surrogate شارد. هذه الأحرف تُفشل ترميز UTF-8 عند تمرير الرد إلى
    ``st.iframe``/``st.markdown`` (بروتوبَف يرفض الـ surrogates) وكانت تُسقط
    قسم الذكاء الاصطناعي بالكامل. نُعيد تجميع الأزواج الصحيحة ونحذف الشاردة.
    """
    if not isinstance(s, str):
        return s
    try:
        s = s.encode("utf-16", "surrogatepass").decode("utf-16", "surrogatepass")
    except Exception:
        pass
    import re as _re
    return _re.sub(r"[\ud800-\udfff]", "", s)


def generate_reply(history: list, user_text: str, image_bytes: bytes = None,
                   image_mime: str = None) -> str:
    """
    يبني السياق من الرسائل السابقة (نص فقط) + الرسالة الحالية (نص و/أو صورة)
    ويُعيد ردّ النموذج نصًّا.

    history: قائمة من {"role": "user"|"assistant", "content": str}
    """
    if not is_available():
        raise AIError("خدمة الذكاء الاصطناعي غير مُهيّأة حاليًا.")

    contents = []
    for m in history[-config.MAX_HISTORY_MESSAGES:]:
        role = "user" if m.get("role") == "user" else "model"
        text = (m.get("content") or "").strip()
        if not text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(
            data=image_bytes, mime_type=image_mime or "image/jpeg"))
    text = _sanitize_text((user_text or "").strip())
    if not text and image_bytes:
        text = "حلّل هذه الصورة من الناحية الغذائية واذكر معلوماتها المفيدة لمريض السكري."
    if text:
        parts.append(types.Part.from_text(text=text))
    if not parts:
        raise AIError("لا يوجد محتوى لإرساله.")
    contents.append(types.Content(role="user", parts=parts))

    try:
        resp = _get_client().models.generate_content(
            model=config.AI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=1400,
            ),
        )
    except Exception as exc:  # أخطاء الشبكة/المفتاح/الحصة
        # سجّل الخطأ الحقيقي في سجلات الخادم (بدل الرسالة العامة) للتشخيص.
        via = "بوابة Replit" if config.gateway_configured() else "مفتاح GEMINI_API_KEY"
        _log.exception("فشل طلب Gemini (عبر %s، النموذج %s): %s",
                       via, config.AI_MODEL, exc)
        raise AIError("تعذّر الحصول على رد من خدمة الذكاء الاصطناعي حاليًا.") from exc

    out = _sanitize_text((getattr(resp, "text", None) or "").strip())
    if not out:
        raise AIError("لم يصل رد من خدمة الذكاء الاصطناعي. حاول مرة أخرى.")
    return out
