import re
import os
import json
import unicodedata
import time
import html
import base64
import zlib
import logging
import streamlit as st


# ─── شعار الموقع (يُضمَّن كـ base64 لأن مجلد assets لا يُخدَّم عبر الويب) ──────
@st.cache_data(show_spinner=False)
def _logo_uri(name: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "assets", name)
    mime = "image/jpeg" if name.lower().endswith((".jpg", ".jpeg")) else "image/png"
    try:
        with open(path, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


LOGO_MARK = _logo_uri("logo_mark.png")
HOWTO_STEPS = _logo_uri("howto_steps.jpeg")
HOWTO_ALTS = _logo_uri("howto_alts.jpeg")
INS_ICR_IMG = _logo_uri("insulin_icr.png")
INS_ISF_IMG = _logo_uri("insulin_isf.png")
INS_CORR_IMG = _logo_uri("insulin_correction.png")
PROD_BAR = _logo_uri("prod_bar.jpg")
PROD_LAYS = _logo_uri("prod_lays.png")
PROD_BISCUIT = _logo_uri("prod_biscuit.png")
PROD_LUSINE = _logo_uri("prod_lusine.jpg")
JAZAN_LOGO = _logo_uri("jazan_logo.png")

# ─── تذييل الموقع (مصدر واحد يُستخدم في الصفحة الرئيسية والقائمة الجانبية معًا) ───
SITE_FOOTER_HTML = (
    f"<div class='sf-logo'><img src='{JAZAN_LOGO}' alt='تجمع جازان الصحي'></div>"
    f"<div class='sf-org'>قسم التغذية العلاجية<br>"
    f"مركز الغدد الصماء والسكري<br>"
    f"مستشفى الملك فهد المركزي بجازان</div>"
    f"<div class='sf-block'>"
    f"<div class='sf-role'>إعداد</div>"
    f"<div class='sf-name'>ليلى يحيى مجرشي</div></div>"
    f"<div class='sf-block'>"
    f"<div class='sf-role'>مراجعة</div>"
    f"<div class='sf-name'>أحمد يحيى الصعدي<br>غادة إسماعيل الحازمي</div></div>"
)

# ─── المحتوى التعريفي لكل قسم: يُعرض داخل نافذة معلومات عند الضغط على أيقونة ⓘ ───
# يشمل: الشرح + الصور التوضيحية + البطاقات التعليمية (طريقة الاستخدام/المعادلة/الأمثلة).
# العناصر التفاعلية (الحاسبات، المدخلات، الأزرار، بطاقات المنتجات، النتائج) تبقى في الصفحة.
INFO_DESC = {
    "info-per-gram": "اعرف كمية الكربوهيدرات في كل جرام من الطعام "
    "لتتمكن من حساب الكمية التي تتناولها بدقة.",
    "info-alternatives": "يعرض هذا القسم كمية الكربوهيدرات الموجودة في الكمية "
    "المحددة لكل طعام، ليساعد على معرفة محتوى الكربوهيدرات ومقارنة الأطعمة "
    "المختلفة بسهولة.",
    "info-label-calc": "يساعدك هذا القسم على حساب كمية الكربوهيدرات من بيانات "
    "الملصق الغذائي بسهولة عبر حاسبة واحدة.",
    "info-insulin-calc": "يساعدك هذا القسم على حساب معامل الكربوهيدرات (ICR) "
    "ومعامل التصحيح (ISF) بطريقة سهلة ودقيقة، مما يساعد على تقدير جرعة الإنسولين "
    "المناسبة بناءً على كمية الكربوهيدرات ومستوى سكر الدم.",
}

# بطاقة المعادلة التعليمية (قسم الكربوهيدرات لكل جرام)
EQ_CARD_HTML = (
    "<div class='eq-card'>"
    "<div class='eq-badge'>💡 المعادلة</div>"
    "<div class='eq-line'>"
    "<span class='eq-term'>وزن الطعام (جرام)</span>"
    "<span class='eq-op'>×</span>"
    "<span class='eq-term'>نسبة الكربوهيدرات لكل جرام</span>"
    "<span class='eq-op'>=</span>"
    "<span class='eq-total'>إجمالي الكربوهيدرات</span>"
    "</div>"
    "</div>"
)

# بطاقة طريقة الاستخدام + الصورة التوضيحية (قسم البدائل الغذائية)
HOWTO_ALTS_HTML = (
    "<div class='howto'>"
    "<div class='howto-title'>طريقة الاستخدام</div>"
    f"<img class='howto-steps' src='{HOWTO_ALTS}' loading='lazy' decoding='async' "
    "alt='طريقة الاستخدام: اسم الطعام، الكمية المحددة، كمية الكربوهيدرات الموجودة فيه'>"
    "</div>"
)

# بطاقة طريقة الاستخدام (قسم الملصق الغذائي)
LAB_USAGE_HTML = (
    "<div class='howto-title'>طريقة الاستخدام</div>"
    "<div class='lab-usage'>"
    "<div class='u-step'><span class='u-ico'>📋</span><span>اقرأ بيانات الملصق الغذائي</span></div>"
    "<div class='u-step'><span class='u-ico'>➡️</span><span>أدخل الوزن الصافي وحجم الحصة وإجمالي الكربوهيدرات</span></div>"
    "<div class='u-step'><span class='u-ico'>➡️</span><span>اضغط «احسب»</span></div>"
    "<div class='u-step'><span class='u-ico'>➡️</span><span>تظهر النتيجة مباشرة</span></div>"
    "</div>"
)

# الشرح التعليمي لقسم الإنسولين (ICR + ISF) — نُقل من نوافذ ❓ إلى نافذة ⓘ الموحّدة
INS_ICR_INFO_HTML = (
    "<div class='info-sub'>معامل الكربوهيدرات (ICR)</div>"
    "<div class='howto-title'>ما هو؟</div>"
    "<p class='sec-desc'>عدد جرامات الكربوهيدرات التي تغطيها وحدة واحدة "
    "من الإنسولين.</p>"
    "<div class='ins-example'>مثال: إذا كان معامل الكربوهيدرات <b>1 : 15</b> "
    "وكانت الوجبة تحتوي على <b>45</b> جم كربوهيدرات:<br>"
    "45 ÷ 15 = <b>3</b> وحدات إنسولين.</div>"
    "<div class='howto-title'>معادلة حساب معامل الكربوهيدرات</div>"
    "<div class='howto-eq'>للبالغين: 500 ÷ الجرعة اليومية الكلية للإنسولين (TDD)<br>"
    "للأطفال: 350 ÷ الجرعة اليومية الكلية للإنسولين (TDD)</div>"
    "<div class='howto-title'>معادلة حساب جرعة التغطية</div>"
    "<div class='howto-eq'>جرعة الإنسولين = إجمالي الكربوهيدرات (جم) ÷ "
    "معامل الكربوهيدرات</div>"
    "<div class='howto-title'>ضبط معامل الكربوهيدرات</div>"
    "<p class='sec-desc'>بعد مراقبة قراءات سكر الدم بعد الوجبات لمدة 3–4 أيام:</p>"
    "<div class='ins-adjust'><span class='ia-ico'>⬆️</span><span>"
    "إذا تكرر <b>ارتفاع</b> السكر بعد الوجبات: اجعل المعامل <b>أقوى</b> "
    "بتقليل الرقم تدريجيًا (مثال: 1 : 15 → 1 : 14 → 1 : 13).</span></div>"
    "<div class='ins-adjust'><span class='ia-ico'>⬇️</span><span>"
    "إذا تكرر <b>انخفاض</b> السكر بعد الوجبات: اجعل المعامل <b>أضعف</b> "
    "بزيادة الرقم تدريجيًا (مثال: 1 : 15 → 1 : 16 → 1 : 17).</span></div>"
)

INS_ISF_INFO_HTML = (
    "<div class='info-sub'>معامل التصحيح (ISF)</div>"
    "<div class='howto-title'>ما هو؟</div>"
    "<p class='sec-desc'>هو مقدار الانخفاض المتوقع في مستوى سكر الدم بعد "
    "إعطاء وحدة واحدة من الإنسولين.</p>"
    "<div class='ins-example'>مثال: إذا كان السكر الحالي <b>250</b> mg/dL، "
    "والسكر المستهدف <b>150</b> mg/dL، ومعامل التصحيح <b>50</b>:<br>"
    "(250 − 150) ÷ 50 = <b>2</b> وحدتي إنسولين.<br>"
    "أي أن المريض يحتاج إلى <b>2</b> وحدتي إنسولين لتصحيح ارتفاع سكر الدم "
    "حتى يصل إلى المستوى المستهدف 150 mg/dL.</div>"
    "<div class='howto-title'>معادلة حساب معامل التصحيح</div>"
    "<div class='howto-eq'>للإنسولين سريع المفعول: 1800 ÷ الجرعة اليومية الكلية (TDD)<br>"
    "للإنسولين العادي (Regular): 1500 ÷ الجرعة اليومية الكلية (TDD)</div>"
    "<div class='howto-title'>معادلة الجرعة التصحيحية</div>"
    "<div class='howto-eq'>جرعة التصحيح = (سكر الدم الحالي − 150) ÷ "
    "معامل التصحيح</div>"
)


def _prod_example(uri: str, alt: str, rows: list) -> str:
    """صورة منتج حقيقية + بطاقة معلومات الحالة (حجم الحصة/عدد الحصص/الوزن الصافي)."""
    cap = "".join(
        f"<div class='ex-cap-row'><span class='ex-cap-l'>{html.escape(lbl)}</span>"
        f"<span class='ex-cap-v'>{html.escape(val)}</span></div>"
        for lbl, val in rows
    )
    img = (
        f"<img class='ex-photo' src='{uri}' alt='{html.escape(alt)}' loading='lazy'/>"
        if uri else ""
    )
    return f"{img}<div class='ex-cap'>{cap}</div>"


def _ex_case(title: str, text_html: str, uri: str, alt: str, rows: list) -> str:
    """بطاقة مثال ثابتة داخل نافذة المعلومات (بديل عن st.expander غير القابل للتضمين)."""
    return (
        f"<div class='ex-case'><div class='ex-case-title'>{html.escape(title)}</div>"
        f"<div class='ex-row'><div class='ex-text'>{text_html}</div>"
        f"<div class='ex-img'>{_prod_example(uri, alt, rows)}</div></div></div>"
    )


# بطاقات «أمثلة وتوضيحات» التعليمية (قسم الملصق الغذائي) — نُقلت من st.expander إلى نافذة ⓘ
LABEL_EXAMPLES_HTML = (
    "<div class='examples-head'>"
    "<span>أمثلة وتوضيحات</span></div>"
    "<p class='sec-desc'>هذه أمثلة توضّح طريقة إدخال البيانات في الحاسبة لكل حالة.</p>"
    + _ex_case(
        "الحالة الأولى: إذا كان الوزن الصافي يساوي حجم الحصة",
        "<b>مثال: لوح شوكولاتة.</b><br>"
        "الوزن الصافي للعبوة = <b>50 جم</b>.<br>"
        "حجم الحصة في الملصق = <b>50 جم</b>.<br>"
        "بما أن الوزن الصافي يساوي حجم الحصة، فهذا يعني أن العبوة تحتوي على "
        "حصة واحدة فقط، وبالتالي فإن كمية الكربوهيدرات المكتوبة في الملصق هي "
        "كمية الكربوهيدرات في كامل العبوة.",
        PROD_BAR, "لوح شوكولاتة",
        [("حجم الحصة الواحدة", "50 جم"), ("عدد الحصص في العبوة", "1"),
         ("الوزن الصافي", "50 جم")],
    )
    + _ex_case(
        "الحالة الثانية: إذا تناولت جزءًا من العبوة",
        "<b>مثال: بطاطس ليز.</b><br>"
        "إذا لم تتناول كامل العبوة، قم بوزن الكمية التي ستتناولها باستخدام "
        "ميزان الطعام، ثم أدخل الوزن في خانة <b>الوزن الصافي</b> في الحاسبة "
        "لحساب كمية الكربوهيدرات لهذه الكمية فقط.",
        PROD_LAYS, "بطاطس ليز",
        [("حجم الحصة الواحدة", "30 جم"), ("عدد الحصص في العبوة", "5"),
         ("الوزن الصافي", "زِن ما ستأكله")],
    )
    + _ex_case(
        "الحالة الثالثة: إذا كان المنتج يحتوي على عدة قطع",
        "<b>مثال: بسكويت شاي.</b><br>"
        "إذا أردت تناول جزء من الحصة فقط، قم بوزن الكمية التي ستتناولها "
        "بالميزان، ثم استخدم الحاسبة مباشرة لحساب الكربوهيدرات.",
        PROD_BISCUIT, "بسكويت شاي",
        [("حجم الحصة الواحدة", "30 جم"), ("عدد الحصص في العبوة", "10"),
         ("الكربوهيدرات الكلية للحصة", "15 جم")],
    )
    + _ex_case(
        "الحالة الرابعة: إذا لم يكن الوزن الصافي موجودًا",
        "<b>مثال: خبز برجر لوزين.</b><br>"
        "إذا لم يكن الوزن الصافي مكتوبًا على الملصق الغذائي، فيمكن حسابه "
        "بهذه المعادلة:"
        "<div class='howto-eq'>الوزن الصافي = حجم الحصة الواحدة × عدد الحصص في العبوة</div>"
        "وبعد معرفة الوزن الصافي، يتم استخدام الحاسبة بشكل طبيعي.",
        PROD_LUSINE, "خبز برجر لوزين",
        [("حجم الحصة الواحدة", "30 جم"), ("عدد الحصص في العبوة", "10"),
         ("الوزن الصافي", "30 × 10 = 300 جم")],
    )
)

# محتوى نافذة كل قسم = الشرح + المحتوى التعليمي الخاص به
INFO_BODY = {
    "info-per-gram": EQ_CARD_HTML,
    "info-alternatives": HOWTO_ALTS_HTML,
    "info-label-calc": LAB_USAGE_HTML + LABEL_EXAMPLES_HTML,
    "info-insulin-calc": INS_ICR_INFO_HTML + INS_ISF_INFO_HTML,
}
INFO_ORDER = [
    ("info-per-gram", "", "الكربوهيدرات لكل جرام"),
    ("info-alternatives", "", "البدائل الغذائية"),
    ("info-label-calc", "", "الملصق الغذائي"),
    ("info-insulin-calc", "", "حساب جرعة الإنسولين"),
]


def _info_modal_html(mid: str, icon: str, title: str) -> str:
    """نافذة معلومات (Modal) تُفتح عبر :target — بلا أي JavaScript."""
    return (
        f"<div id='{mid}' class='info-modal'>"
        f"<a href='#!' class='info-backdrop' aria-label='إغلاق'></a>"
        f"<div class='info-box'>"
        f"<a href='#!' class='info-close' aria-label='إغلاق'>&times;</a>"
        f"<div class='info-title'>{f'<span>{icon}</span>' if icon else ''}<span>{html.escape(title)}</span></div>"
        f"<p class='info-desc'>{html.escape(INFO_DESC[mid])}</p>"
        f"{INFO_BODY.get(mid, '')}"
        f"</div></div>"
    )


INFO_MODALS_HTML = "".join(_info_modal_html(*s) for s in INFO_ORDER)


def _info_icon(mid: str) -> str:
    """أيقونة ⓘ بجانب اسم القسم تفتح نافذة الشرح."""
    return f"<a href='#{mid}' class='sec-info' aria-label='شرح القسم'></a>"


# رسم توضيحي (SVG مضمّن) لأماكن حقن الإنسولين — بألوان الموقع، بلا صور خارجية
INJECT_SITES_SVG = (
    "<svg class='tip-figure' viewBox='0 0 320 360' "
    "xmlns='http://www.w3.org/2000/svg' role='img' "
    "aria-label='أماكن حقن الإنسولين في الجسم'>"
    "<g fill='#c7d9dd'>"
    "<circle cx='160' cy='42' r='26'/>"
    "<rect x='150' y='64' width='20' height='14'/>"
    "<rect x='116' y='76' width='88' height='122' rx='26'/>"
    "<rect x='90' y='84' width='24' height='108' rx='12'/>"
    "<rect x='206' y='84' width='24' height='108' rx='12'/>"
    "<rect x='118' y='188' width='84' height='40' rx='18'/>"
    "<rect x='122' y='220' width='34' height='128' rx='16'/>"
    "<rect x='164' y='220' width='34' height='128' rx='16'/>"
    "</g>"
    "<g fill='#3e6e7e' fill-opacity='0.30' stroke='#3e6e7e' "
    "stroke-width='2' stroke-dasharray='4 3'>"
    "<ellipse cx='160' cy='158' rx='30' ry='22'/>"
    "<ellipse cx='102' cy='108' rx='12' ry='18'/>"
    "<ellipse cx='218' cy='108' rx='12' ry='18'/>"
    "<ellipse cx='139' cy='256' rx='15' ry='26'/>"
    "<ellipse cx='181' cy='256' rx='15' ry='26'/>"
    "<ellipse cx='128' cy='202' rx='11' ry='14'/>"
    "<ellipse cx='192' cy='202' rx='11' ry='14'/>"
    "</g>"
    "<g font-family='inherit' font-size='15' font-weight='800' "
    "text-anchor='middle'>"
    "<circle cx='160' cy='158' r='13' fill='#3e6e7e'/>"
    "<text x='160' y='163' fill='#fff'>1</text>"
    "<circle cx='218' cy='108' r='13' fill='#3e6e7e'/>"
    "<text x='218' y='113' fill='#fff'>2</text>"
    "<circle cx='181' cy='256' r='13' fill='#3e6e7e'/>"
    "<text x='181' y='261' fill='#fff'>3</text>"
    "<circle cx='192' cy='202' r='13' fill='#3e6e7e'/>"
    "<text x='192' y='207' fill='#fff'>4</text>"
    "</g>"
    "</svg>"
)
INJECT_SITES_FIG = (
    "<div class='tip-figwrap'>"
    + INJECT_SITES_SVG
    + "<div class='tip-figcap'>"
    "<span class='fc'><b>1</b> البطن</span>"
    "<span class='fc'><b>2</b> أعلى الذراع</span>"
    "<span class='fc'><b>3</b> الفخذ</span>"
    "<span class='fc'><b>4</b> الأرداف</span>"
    "</div></div>"
)

# رسم توضيحي (SVG مضمّن) للطبق الصحي — بألوان الموقع، بلا صور خارجية
HEALTHY_PLATE_SVG = (
    "<svg class='tip-figure' viewBox='0 0 300 300' "
    "xmlns='http://www.w3.org/2000/svg' role='img' "
    "aria-label='تقسيم الطبق الصحي'>"
    "<circle cx='150' cy='150' r='116' fill='#ffffff' "
    "stroke='#cddfe2' stroke-width='6'/>"
    "<path d='M150,150 L150,44 A106,106 0 0 0 150,256 Z' fill='#4f7340'/>"
    "<path d='M150,150 L150,44 A106,106 0 0 1 256,150 Z' fill='#d98324'/>"
    "<path d='M150,150 L256,150 A106,106 0 0 1 150,256 Z' fill='#e6b53c'/>"
    "<g fill='#ffffff' font-family='inherit' font-weight='800' "
    "text-anchor='middle'>"
    "<text x='104' y='158' font-size='22'>50%</text>"
    "<text x='188' y='112' font-size='18'>25%</text>"
    "<text x='188' y='200' font-size='18'>25%</text>"
    "</g>"
    "</svg>"
)
HEALTHY_PLATE_FIG = (
    "<div class='tip-figwrap'>"
    + HEALTHY_PLATE_SVG
    + "<div class='plate-legend'>"
    "<span class='pl'><i class='pl-v'></i> خضروات (50%)</span>"
    "<span class='pl'><i class='pl-p'></i> بروتين (25%)</span>"
    "<span class='pl'><i class='pl-c'></i> كربوهيدرات (25%)</span>"
    "</div></div>"
)
# ملاحظة: pandas / openpyxl / requests / io ثقيلة الاستيراد (~٥.٧ ثانية)
# ولا تلزم عند أول رسم للصفحة ما دام الكاش موجوداً، لذا تُستورد بشكل كسول
# داخل الدوال التي تحتاجها (تعمل في الخلفية) لتسريع الإقلاع البارد.

# ─── مسارات الملفات ────────────────────────────────────────────────────────────
SHEETS_ID      = "1QirRmdv5LI9FsDjOeTAhQfIP5jH4vd2Y"
SHEETS_URL     = f"https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=xlsx"
LOCAL_BACKUP   = os.path.join(os.path.dirname(__file__), "foods.xlsx")
REFRESH_SEC    = 120  # مدة صلاحية الكاش: تُعاد قراءة الشيت كل دقيقتين كحد أقصى


# ══════════════════════════════════════════════════════════════════════════════
# تحميل البيانات — يُقرأ مباشرةً من Google Sheets وقت الطلب (بلا خيط خلفي)
# ملاحظة: النشر على Autoscale يُجمّد الحاوية بين الطلبات، لذا لا يعتمد الموقع
# على خيط تحديث خلفي (كان يتجمّد فلا تظهر التعديلات). بدلاً من ذلك تُجلب أحدث
# البيانات أثناء معالجة الطلب نفسه عبر st.cache_data(ttl=REFRESH_SEC).
# ══════════════════════════════════════════════════════════════════════════════
class DataManager:
    """أدوات تحليل ورقة Google Sheets فقط (بلا حالة). الجلب يتم في
    _load_food_data() المخزّنة مؤقتاً بـ ttl فتتحدّث أثناء معالجة الطلب."""

    # ── data loading ──────────────────────────────────────────────────────────
    @staticmethod
    def _parse(df):
        df.columns = df.columns.str.strip()
        cols = list(df.columns)
        # الاسم والكمية: أعمدة ثابتة معروفة بأسمائها
        name_col   = "النوع"  if "النوع"  in cols else (cols[0] if cols else None)
        amount_col = "الكمية" if "الكمية" in cols else None

        def _has(col, *subs):
            v = df[col].astype(str)
            return any(v.str.contains(s, na=False).any() for s in subs)

        others = [c for c in cols
                  if c not in (name_col, amount_col) and not str(c).startswith("Unnamed")]
        # عمود قيمة الكارب = العمود الذي تحتوي قيمه على «لكل جرام» أو «جرام كارب»،
        # وإلا فالعمود الذي يذكر عنوانه «كربوهيدرات»، وإلا أول عمود متبقٍّ.
        # هذا يجعل الكشف مستقلاً عن اسم عمود الفئة (الفئة/الطرق/…)،
        # ونأخذ *عنوانه* كما كتبه المستخدم ليظهر تلقائياً كتسمية في البطاقة.
        carb_col = next((c for c in others if _has(c, "لكل جرام", "جرام كارب")), None)
        if carb_col is None:
            carb_col = next((c for c in others if "كربوهيدرات" in str(c)), None)
        if carb_col is None:
            carb_col = others[0] if others else None
        # عمود القسم (اختياري) = أي عمود آخر تحتوي قيمه على «بدائل» — للرجوع إليه فقط
        sec_col = next((c for c in others
                        if c != carb_col and _has(c, "بدائل")), None)
        # عمود الفئة (اختياري) = عمود عنوانه «الفئة/فئة» أو تحتوي قيمه على «شعبي».
        # يُستخدم فقط للتصنيف الديناميكي لقسم «شعبي»: أي صنف قيمة فئته «شعبي»
        # يظهر تلقائياً داخل القسم دون أي تعديل في الكود. لا يؤثر على بقية المنطق،
        # ويعمل الموقع كالمعتاد سواء وُجد العمود أو لم يُضَف بعد.
        # نفضّل الكشف بعنوان العمود («الفئة/فئة/فئات» — نطابق المقطع المميّز «فئ»
        # على النص الخام قبل التطبيع لأن التطبيع يحوّل ئ→ي)، ثم نرجع للكشف بالمحتوى
        # (عمود تحتوي قيمه على «شعبي») فقط إن لم نجد عموداً بعنوان مناسب.
        cat_col = next((c for c in others
                        if c not in (carb_col, sec_col) and "فئ" in str(c)), None)
        if cat_col is None:
            cat_col = next((c for c in others
                            if c not in (carb_col, sec_col) and _has(c, "شعبي")), None)
        carb_label = carb_col.strip() if carb_col else "معامل الكارب"

        rename = {}
        if name_col:   rename[name_col]   = "name"
        if amount_col: rename[amount_col] = "amount"
        if carb_col:   rename[carb_col]   = "carbs_raw"
        if sec_col:    rename[sec_col]    = "section"
        if cat_col:    rename[cat_col]    = "cat_sheet"
        df = df.rename(columns=rename)
        if "name" not in df.columns:
            return [], []
        df = df.dropna(subset=["name"])
        # ملاحظة: أعمدة النص في pandas قد تكون من نوع Arrow حيث تبقى الخلايا الفارغة
        # قيمة NA (تظهر كـ float nan في apply)، لذا نستخدم fillna("") قبل astype(str)
        # حتى لا تُمرَّر nan إلى دوال تتوقّع نصاً (كان صفٌّ واحد بخانة قسم فارغة يوقف
        # التحليل كله ويجعل الموقع يرجع للنسخة المحلية الاحتياطية).
        df["name"]      = df["name"].fillna("").astype(str).str.strip().apply(_to_western)
        df["section"]   = df["section"].fillna("").astype(str).str.strip()   if "section"   in df.columns else ""
        df["amount"]    = df["amount"].fillna("").astype(str).str.strip().apply(_to_western) if "amount" in df.columns else ""
        df["carbs_raw"] = df["carbs_raw"].fillna("").astype(str).str.strip() if "carbs_raw" in df.columns else ""
        df["carb_label"] = carb_label
        df["section_ar"] = df["section"].apply(
            lambda s: "البدائل" if "بدائل" in s else ("الجرام" if "جرام" in s else s.strip())
        )
        df["carbs_clean"] = df["carbs_raw"].apply(_clean_carb)
        df["_norm_name"]  = df["name"].apply(_normalize)
        df["_norm_sec"]   = df["section_ar"].apply(_normalize)
        # قيمة عمود الفئة القادمة من Google Sheets (إن وُجد العمود)
        df["cat_sheet"] = (df["cat_sheet"].fillna("").astype(str).str.strip()
                           if "cat_sheet" in df.columns else "")
        # التصنيف: إذا كانت قيمة عمود الفئة «شعبي» يُصنَّف الصنف تلقائياً ضمن قسم
        # «شعبي»، وإلا نرجع للتصنيف حسب اسم الصنف (الكلمات المفتاحية) كما هو سابقاً.
        _cats = df.apply(_resolve_category, axis=1)
        df["_cat"]      = _cats.apply(lambda c: c[0])
        df["cat_label"] = _cats.apply(lambda c: c[1])
        # نوع القسم (جرام/بدائل) يُشتق من نص قيمة الكارب نفسه:
        #   «… لكل جرام» → قسم الجرام،  «… جرام كارب» → قسم البدائل.
        # نرجع لعمود «الفئة» (إن وُجد) فقط عند تعذّر التحديد من النص،
        # حتى يعمل الموقع سواء بقي عمود الفئة أو حُذف من Google Sheets.
        df["_sec_type"] = df.apply(
            lambda r: _section_type(r.get("carbs_clean", ""), r.get("section", "")),
            axis=1,
        )
        grams = df[df["_sec_type"] == "grams"].to_dict("records")
        alts  = df[df["_sec_type"] == "alts"].to_dict("records")
        # إزالة التكرار: لو جاء صنف بنفس (الاسم + الكمية + قيمة الكربوهيدرات)
        # أكثر من مرة (مثلاً مطابق لصنف موجود في «شعبي») يظهر مرة واحدة فقط.
        grams = _dedup_records(grams)
        alts  = _dedup_records(alts)
        grams.sort(key=lambda x: str(x.get("name", "")))
        alts.sort(key=lambda x:  str(x.get("name", "")))
        return grams, alts

    @staticmethod
    def _fetch_remote():
        try:
            import io
            import requests
            import pandas as pd
            # كاش-باستر + ترويسة no-cache يمنعان أي وسيط من إرجاع نسخة مخزّنة،
            # فنقرأ دائماً أحدث محتوى من Google Sheets.
            url = f"{SHEETS_URL}&_ts={int(time.time())}"
            r = requests.get(url, timeout=15,
                             headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl")
            return DataManager._parse(df)
        except Exception as e:
            import traceback
            logging.getLogger("carb-calc.data").warning(
                "خطأ أثناء جلب Google Sheets: %s\n%s", e, traceback.format_exc())
            return None, None

    @staticmethod
    def _fetch_local():
        try:
            import pandas as pd
            df = pd.read_excel(LOCAL_BACKUP, engine="openpyxl")
            return DataManager._parse(df)
        except Exception:
            return [], []

# ─── سجل عمليات جلب البيانات (يظهر في سجلات التشغيل/النشر) ──────────────────
_data_log = logging.getLogger("carb-calc.data")
if not _data_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [carb-calc] %(message)s"))
    _data_log.addHandler(_h)
    _data_log.setLevel(logging.INFO)


@st.cache_data(ttl=REFRESH_SEC, show_spinner=False)
def _load_food_data():
    """يُعيد (grams, alts, version) بأحدث بيانات من Google Sheets.
    مخزّن مؤقتاً بـ ttl=REFRESH_SEC ويُعاد تنفيذه أثناء معالجة الطلب، لذا يظهر
    أي تعديل في الشيت بعد تحديث الصفحة (خلال دقيقتين كحد أقصى) دون إعادة نشر."""
    grams, alts = DataManager._fetch_remote()
    if grams or alts:
        _data_log.info(
            "Google Sheets OK: تم جلب %d صنف جرام + %d بديل من الشيت %s",
            len(grams), len(alts), SHEETS_ID)
    else:
        # فشل الجلب من الشيت → نسخة محلية احتياطية فقط (foods.xlsx) كحل أخير
        grams, alts = DataManager._fetch_local()
        _data_log.warning(
            "تعذّر جلب البيانات من Google Sheets — استخدام النسخة المحلية "
            "الاحتياطية foods.xlsx (%d + %d). تحقّق من الاتصال أو صلاحية "
            "مشاركة الملف (يجب أن يكون قابلاً للقراءة عبر الرابط).",
            len(grams), len(alts))
    # الإصدار مشتق من محتوى البيانات نفسه: يتغيّر تلقائياً عند أي تعديل في
    # الشيت فتُبطَل كل كاشات بطاقات الـ HTML المُفتاحة بالإصدار وتُعاد بناؤها.
    try:
        blob = json.dumps([grams, alts], ensure_ascii=False, default=str,
                          sort_keys=True).encode("utf-8")
        version = zlib.crc32(blob) & 0xffffffff
    except Exception:
        version = len(grams) * 100003 + len(alts)
    return grams, alts, version


class _ManagerShim:
    """يحافظ على الواجهة القديمة get_manager().get() → (grams, alts, version)."""
    def get(self):
        return _load_food_data()


def get_manager() -> "_ManagerShim":
    return _ManagerShim()


# ══════════════════════════════════════════════════════════════════════════════
# دوال مساعدة (لا تعتمد على st)
# ══════════════════════════════════════════════════════════════════════════════
def _normalize(text: str) -> str:
    # توحيد صيغة يونيكود (NFKC) لتطابق أشكال العرض العربية مع الأشكال القياسية،
    # ثم إزالة الرموز غير المرئية (المسافات الصفرية/علامات الاتجاه/التطويل) حتى لا
    # يفشل البحث بسبب محارف خفية في نص البحث أو في بيانات الشيت.
    text = unicodedata.normalize("NFKC", str(text))
    text = _DEDUP_INVISIBLE.sub('', text)
    text = text.strip().lower()
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ؤ', 'و', text)
    text = re.sub(r'[ئى]', 'ي', text)
    return text


_CAT_SEP = re.compile(r'[|/،,()\\]+')

def _cat_match(kwn: str, full: str, tokens) -> bool:
    if ' ' in kwn:
        return kwn in full
    for t in tokens:
        if t == kwn or t == 'ال' + kwn:
            return True
        if len(kwn) >= 4:
            if t.startswith('ال' + kwn):
                return True
            if t.startswith(kwn) and len(t) <= len(kwn) + 2:
                return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
# أيقونة إيموجي ملوّنة لكل صنف بناءً على الاسم (تُحسب داخلياً، لا تُكتب في الجدول)
# الترتيب مهم: أول تطابق يفوز. تُستخدم كلمات بصيغة _normalize (ة→ه، أإآ→ا).
# عند عدم التعرّف على الصنف تُستخدم أيقونة افتراضية 🍽️.
# ══════════════════════════════════════════════════════════════════════════════
_EMOJI_DEFAULT = "🍽️"
_EMOJI_RULES = [
    # — مشروبات (قبل الحلويات حتى لا يلتقط "محلى/شوكولاته") —
    ("☕", ["قهوه", "لاتيه", "كابتشينو", "نسكافيه", "موكا", "هوت شوكليت", "هوت شوكلت",
            "شوكولاته ساخنه", "شوكلاته ساخنه"]),
    ("🍵", ["شاي", "شاهي"]),
    ("🧃", ["عصير"]),
    ("🥤", ["ميلك شيك", "ميلك تشيك", "ميلكشيك", "مشروبات", "مشروب", "كولا", "بيبسي",
            "سبرايت", "غازيه", "الطاقه", "بانش", "سموثي", "سموذي"]),
    ("🍺", ["بيره", "بيرك"]),
    # — حليب نباتي/منكّه (كلمات مركّبة دقيقة قبل قواعد الأرز/المكسرات) —
    ("🥛", ["حليب الصويا", "حليب اللوز", "حليب الرز", "حليب الارز",
            "حليب جوز الهند", "حليب بالشكولاته", "حليب بالشوكولاته"]),
    # — وجبات سريعة / أطباق محددة —
    ("🍕", ["بيتزا"]),
    ("🍔", ["برجر", "همبرجر", "همبر"]),
    ("🌯", ["شاورما", "تورتيلا", "رقائق", "مسحب"]),
    ("🍣", ["سوشي"]),
    ("🧆", ["فلافل"]),
    ("🥟", ["سمبوسه", "سبرنق رول", "منتو", "مطبق", "بف", "كبه"]),
    # — بطاطس مقلية —
    ("🍟", ["بطاطس مقلي", "فرايز", "فرنش فرايز"]),
    # — مكرونة / باستا —
    ("🍝", ["مكرونه", "معكرونه", "باستا", "سباغتي", "سباجتي", "لازانيا", "نودلز",
            "اندومي", "ماك اند", "سباغيتي"]),
    # — دقيق وحبوب الإفطار (قبل الأرز حتى يلتقط «دقيق الأرز/الذرة» إلخ) —
    ("🌾", ["دقيق", "قمح", "شعير", "جاودار", "دخن", "حنطه", "نشا"]),
    ("🥣", ["شوفان", "عصيده", "حبوب افطار", "حبوب", "كورن فلكس"]),
    # — أرز وأطباق الحبوب —
    ("🍚", ["ارز", "رز", "كبسه", "مندي", "برياني", "بخاري", "مقلوبه", "كشري", "صياديه",
            "فته", "كينوا", "جريش", "سليق", "هريس", "ثريد", "مطازيز", "مراصيع", "يغموش",
            "قرصان", "مرقوق", "صيادي"]),
    # — مخبوزات ومعجنات —
    ("🥐", ["فطيره", "فطاير", "فتاير", "مناقيش", "كرسون", "كروسون", "مطبق"]),
    ("🥞", ["بان كيك", "بانكيك", "وافل", "وأفل", "فرنش توست", "بانكيك"]),
    ("🍞", ["خبز", "توست", "صامولي", "تميس", "شابوره", "بقسماط", "جامبو", "شباتي",
            "نان", "نأن", "تورتيلا"]),
    # — حلويات —
    ("🍩", ["دونات", "بلح الشام", "لقيمات", "زلابيه"]),
    ("🍪", ["كوكيز", "بسكوت", "بسكويت", "بيتفور", "غريبه"]),
    ("🍫", ["شوكولاته", "شوكلاته", "نوتيلا", "كاكاو"]),
    ("🍦", ["ايس كريم", "ايسكريم", "بوظه"]),
    ("🍮", ["مهلبيه", "بودنج", "بودينج", "كريم كرميل", "كريم كراميل", "كرميل", "كراميل",
            "جلي", "جلو", "حلاوه جلي"]),
    ("🍰", ["كيك", "كيكه", "مافن", "كب كيك", "براونز", "براوني", "تشيز كيك", "بسبوسه",
            "كنافه", "قطايف", "بقلاوه", "ام علي", "تراميسو", "توفي", "حلاوه طحينيه",
            "بلح", "معمول", "كعك", "حلاوه", "حلوي", "حلى", "محلى", "مارشميلو"]),
    ("🍯", ["عسل", "شيره"]),
    ("🍓", ["مربى"]),
    ("🍬", ["سكر", "حلاوه مص"]),
    # — ألبان وأجبان —
    ("🧀", ["جبنه", "لبنه", "تشيدر", "اصابع جبن"]),
    ("🥜", ["زبده فول", "زبده لوز", "زبده كاجو", "زبده الفول", "زبده"]),
    ("🥛", ["حليب", "لبن", "زبادي", "قشطه", "كريمه", "كريم طبخ"]),
    # — بيض وبروتينات —
    ("🥚", ["بيض"]),
    ("🍗", ["دجاج"]),
    ("🦐", ["روبيان", "جمبري", "ربيان"]),
    ("🐟", ["سمك", "تونه"]),
    ("🍖", ["لحم", "تيكا", "باربيكيو", "مسقعه باللحم"]),
    # — بقوليات / مكسرات / بذور —
    ("🫘", ["فول", "عدس", "فاصوليا", "فاصولياء", "بقوليات", "حمص", "بليله"]),
    ("🥥", ["جوز الهند"]),
    ("🥜", ["لوز", "كاجو", "فستق", "بندق", "جوز", "عين الجمل", "صنوبر", "كستناء",
            "مكسرات", "سوداني", "بيكان", "حب القرع", "كستن"]),
    ("🌰", ["سمسم", "بذور", "لب ابيض", "لب اسمر", "لب احمر", "دوار الشمس", "شيا",
            "كتان", "حبه البركه", "حبه السوداء", "تباع الشمس"]),
    ("🍿", ["فشار"]),
    # — توابل —
    ("🌿", ["هيل", "زعفران", "قرنفل", "زنجبيل", "كمون", "الحلبه", "حبه البركه"]),
    # — خضروات —
    ("🥗", ["خضار", "خضروات", "سلطه", "تبوله", "فتوش", "ورق عنب", "محشي", "خس",
            "سبانخ", "متبل", "بابا غنوج", "بنجر", "شمندر"]),
    ("🍅", ["طماطم", "كاتشب", "كاتشاب", "معجون طماطم"]),
    ("🥫", ["مايونيز", "صوص", "صلصه", "رانش"]),
    ("🥔", ["بطاطس", "بطاطا"]),
    ("🥕", ["جزر"]),
    ("🌽", ["ذره", "كورن فلكس", "كورن"]),
    ("🥒", ["خيار", "كوسا"]),
    ("🍆", ["باذنجان", "مسقعه"]),
    ("🎃", ["قرع"]),
    ("🥦", ["زهره", "قرنبيط", "خرشوف", "بروكلي"]),
    ("🫛", ["بازلاء"]),
    ("🫑", ["فلفل"]),
    ("🍄", ["مشروم", "فطر"]),
    # — فواكه —
    ("🍎", ["تفاح"]),
    ("🍌", ["موز"]),
    ("🍊", ["برتقال", "يوسفي", "جريب فروت", "جريب"]),
    ("🍋", ["ليمون"]),
    ("🍉", ["بطيخ"]),
    ("🍇", ["عنب", "زبيب"]),
    ("🍓", ["فراوله"]),
    ("🍒", ["كرز"]),
    ("🍑", ["خوخ", "مشمش", "برقوق"]),
    ("🍐", ["كمثري"]),
    ("🍍", ["اناناس"]),
    ("🥭", ["مانجو"]),
    ("🍈", ["شمام"]),
    ("🥝", ["كيوي"]),
    ("🥑", ["افوكادو"]),
    ("🫐", ["توت"]),
    ("🌴", ["تمر"]),
    ("🍎", ["رمان", "جوافه", "بابايا", "تين", "بانش فروت"]),
    ("🍇", ["فواكه"]),
]


def _food_emoji(name: str) -> str:
    n = _normalize(name)
    full = _CAT_SEP.sub(' ', n)
    toks = [t for t in full.split() if t]
    if "بطاطس" in toks and any("مقلي" in t for t in toks):
        return "🍟"
    for emoji, kws in _EMOJI_RULES:
        for kw in kws:
            if _cat_match(_normalize(kw), full, toks):
                return emoji
    return _EMOJI_DEFAULT


# ══════════════════════════════════════════════════════════════════════════════
# تصنيف كل صنف إلى فئة عامة (تُحسب داخلياً من الاسم، لا تُكتب في الجدول).
# الترتيب مهم: أول تطابق يفوز — نفس منطق _cat_match المعتمد على الكلمات (tokens).
# كل عنصر: (مفتاح، إيموجي للشريط، اسم الفئة داخل البطاقة، كلمات مفتاحية).
# ══════════════════════════════════════════════════════════════════════════════
_CATEGORY_RULES = [
    # — شعبي: أصناف محددة فقط (يكتبها المستخدم يدوياً). يجب أن تبقى أولاً حتى تفوز —
    # — بأول تطابق قبل أي فئة أخرى (مثلاً "مغش لحم" يجب ألا تُصنّف بروتينات) —
    ("popular", "🥘", "شعبي", [
        "قوار", "مرسه", "حبحب مشوي", "قطن مكشن", "مغش لحم",
        "جريش", "سليق", "هريس", "قرصان", "مرقوق", "كنافه", "مصقع",
        "مسقعه", "تميس", "مطبق",
    ]),
    ("drinks", "🥤", "مشروبات", [
        "قهوه", "لاتيه", "كابتشينو", "نسكافيه", "موكا", "هوت شوكليت", "هوت شوكلت",
        "شوكولاته ساخنه", "شوكلاته ساخنه", "شاي", "شاهي", "عصير", "ميلك شيك",
        "ميلك تشيك", "ميلكشيك", "مشروبات", "مشروب", "كولا", "بيبسي", "سبرايت",
        "غازيه", "الطاقه", "بانش", "سموثي", "سموذي", "بيره", "بيرك",
    ]),
    ("dairy", "🥛", "ألبان وأجبان", [
        "حليب الصويا", "حليب اللوز", "حليب الرز", "حليب الارز", "حليب جوز الهند",
        "حليب بالشكولاته", "حليب بالشوكولاته", "جبنه", "لبنه", "تشيدر", "اصابع جبن",
        "حليب", "لبن", "زبادي", "قشطه", "كريمه", "كريم طبخ",
    ]),
    ("fastfood", "🍔", "وجبات سريعة", [
        "بيتزا", "برجر", "همبرجر", "همبر", "شاورما", "تورتيلا", "رقائق", "مسحب",
        "سوشي", "فلافل", "سمبوسه", "سبرنق رول", "منتو", "بف", "كبه", "بطاطس مقلي",
        "فرايز", "فرنش فرايز",
    ]),
    ("pasta", "🍝", "معكرونة", [
        "مكرونه", "معكرونه", "باستا", "سباغتي", "سباجتي", "لازانيا", "نودلز",
        "اندومي", "ماك اند", "سباغيتي",
    ]),
    ("grains", "🍚", "أرز وحبوب", [
        "دقيق", "قمح", "شعير", "جاودار", "دخن", "حنطه", "نشا", "شوفان", "عصيده",
        "حبوب افطار", "حبوب", "كورن فلكس", "ارز", "رز", "كبسه", "مندي", "برياني",
        "بخاري", "مقلوبه", "كشري", "صياديه", "فته", "كينوا", "جريش", "سليق",
        "هريس", "ثريد", "مطازيز", "مراصيع", "يغموش", "قرصان", "مرقوق", "صيادي",
        "برغل", "فريك",
    ]),
    ("bakery", "🍞", "خبز ومخبوزات", [
        "فطيره", "فطاير", "فتاير", "مناقيش", "كرسون", "كروسون", "مطبق", "بان كيك",
        "بانكيك", "وافل", "وأفل", "فرنش توست", "خبز", "توست", "صامولي", "تميس",
        "شابوره", "بقسماط", "جامبو", "شباتي", "نان", "نأن", "معجنات",
    ]),
    ("sweets", "🍫", "حلويات", [
        "دونات", "بلح الشام", "لقيمات", "زلابيه", "كوكيز", "بسكوت", "بسكويت",
        "بيتفور", "غريبه", "شوكولاته", "شوكلاته", "نوتيلا", "كاكاو", "ايس كريم",
        "ايسكريم", "بوظه", "مهلبيه", "بودنج", "بودينج", "كريم كرميل", "كريم كراميل",
        "كرميل", "كراميل", "جلي", "جلو", "حلاوه جلي", "كيك", "كيكه", "مافن",
        "كب كيك", "براونز", "براوني", "تشيز كيك", "بسبوسه", "كنافه", "قطايف",
        "بقلاوه", "ام علي", "تراميسو", "توفي", "حلاوه طحينيه", "بلح", "معمول",
        "كعك", "حلاوه", "حلوي", "حلى", "محلى", "مارشميلو", "عسل", "شيره", "مربى",
        "سكر", "حلاوه مص",
    ]),
    ("protein", "🍗", "بروتينات", [
        "بيض", "دجاج", "روبيان", "جمبري", "ربيان", "سمك", "تونه", "لحم", "تيكا",
        "باربيكيو", "مسقعه باللحم",
    ]),
    ("legumes", "🫘", "بقوليات", [
        "فول", "عدس", "فاصوليا", "فاصولياء", "بقوليات", "حمص", "بليله",
    ]),
    ("nuts", "🥜", "مكسرات", [
        "زبده فول", "زبده لوز", "زبده كاجو", "زبده الفول", "زبده", "جوز الهند",
        "لوز", "كاجو", "فستق", "بندق", "جوز", "عين الجمل", "صنوبر", "كستناء",
        "مكسرات", "سوداني", "بيكان", "حب القرع", "كستن", "سمسم", "بذور", "لب ابيض",
        "لب اسمر", "لب احمر", "دوار الشمس", "شيا", "كتان", "تباع الشمس", "فشار",
    ]),
    ("veg", "🥦", "خضروات", [
        "خضار", "خضروات", "سلطه", "تبوله", "فتوش", "ورق عنب", "محشي", "خس",
        "سبانخ", "متبل", "بابا غنوج", "بنجر", "شمندر", "طماطم", "كاتشب", "كاتشاب",
        "معجون طماطم", "مايونيز", "صوص", "صلصه", "رانش", "بطاطس", "بطاطا", "جزر",
        "ذره", "كورن", "خيار", "كوسا", "باذنجان", "مسقعه", "قرع", "زهره",
        "قرنبيط", "خرشوف", "بروكلي", "بازلاء", "فلفل", "مشروم", "فطر",
    ]),
    ("fruit", "🍎", "فواكه", [
        "تفاح", "موز", "برتقال", "يوسفي", "جريب فروت", "جريب", "ليمون", "بطيخ",
        "عنب", "زبيب", "فراوله", "كرز", "خوخ", "مشمش", "برقوق", "كمثري", "اناناس",
        "مانجو", "شمام", "كيوي", "افوكادو", "توت", "تمر", "رمان", "جوافه",
        "بابايا", "تين", "بانش فروت", "فواكه",
    ]),
]


_POPULAR_LABEL = next(
    (lbl for key, _e, lbl, _k in _CATEGORY_RULES if key == "popular"), "شعبي"
)


def _food_category(name: str):
    """إرجاع (مفتاح الفئة، اسم الفئة) لصنف من اسمه، أو ('other','أخرى') عند عدم التطابق."""
    n = _normalize(name)
    full = _CAT_SEP.sub(' ', n)
    toks = [t for t in full.split() if t]
    if "بطاطس" in toks and any("مقلي" in t for t in toks):
        return ("fastfood", "وجبات سريعة")
    for key, _emoji, label, kws in _CATEGORY_RULES:
        for kw in kws:
            if _cat_match(_normalize(kw), full, toks):
                return (key, label)
    return ("other", "أخرى")


def _resolve_category(row):
    """تصنيف الصنف من عمود الفئة في Google Sheets: أي قيمة فئة مكتوبة في الجدول
    تُعتمد تلقائياً وتظهر كشريحة في الشريط دون أي تعديل في الكود. «شعبي» تبقى
    مرتبطة بقسم «شعبي»، وأي قيمة تطابق اسم فئة معروفة تندمج معها، وإلا تُنشأ فئة
    جديدة باسمها كما هو. عند خلوّ خانة الفئة نرجع للتصنيف حسب اسم الصنف."""
    raw = str(row.get("cat_sheet", "")).strip()
    if raw and raw.lower() not in ("nan", "none"):
        norm = _normalize(raw)
        if "شعبي" in norm:
            return ("popular", _POPULAR_LABEL)
        known = _SHEET_LABEL_TO_CAT.get(norm)
        if known:
            return known
        return ("sheet:" + norm, _to_western(raw))
    return _food_category(str(row.get("name", "")))


_DEDUP_INVISIBLE = re.compile(r'[\u200b-\u200f\u202a-\u202e\u0640\ufeff]')
_DEDUP_WS = re.compile(r'\s+')

# خريطة: اسم فئة مكتوب في الجدول (مطبَّع) → (مفتاح، تسمية) لإحدى القواعد الثابتة،
# حتى لو كتب المستخدم في الجدول «حلويات» تندمج مع فئة الحلويات بدل إنشاء فئة مكررة.
# تُعرَّف بعد _DEDUP_INVISIBLE لأن _normalize يستخدمه عند بناء هذه الخريطة وقت الاستيراد.
_SHEET_LABEL_TO_CAT = {
    _normalize(lbl): (key, lbl) for key, _e, lbl, _kw in _CATEGORY_RULES
}

def _dedup_norm(s):
    """مفتاح مقارنة موحّد: إزالة الرموز غير المرئية (المسافات الصفرية/علامات الاتجاه/
    التطويل ـ) ودمج المسافات المتكررة في مسافة واحدة، حتى تُعتبر القيم المتطابقة
    بصرياً متطابقة. لا يغيّر النص المعروض — يُستخدم للمقارنة فقط."""
    s = _DEDUP_INVISIBLE.sub('', str(s))
    return _DEDUP_WS.sub(' ', s).strip()

def _dedup_records(records):
    """إزالة التكرار داخل القسم الواحد: لا يُحذف سجل إلا إذا تطابقت جميع بياناته
    الأساسية (الاسم + الكمية + قيمة الكربوهيدرات)، ويُبقى أول ظهور فقط. تُهمَل فروق
    المسافات/الرموز غير المرئية وحدها؛ أي اختلاف حقيقي في الاسم أو الكمية أو قيمة
    الكربوهيدرات يبقى سجلاً منفصلاً. لا يُحذف أي صف من Google Sheets نفسه."""
    seen = set()
    out = []
    for r in records:
        key = (_dedup_norm(r.get("name", "")),
               _dedup_norm(r.get("amount", "")),
               _dedup_norm(r.get("carbs_clean", "")))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

def _to_western(s) -> str:
    """تحويل الأرقام العربية/الفارسية إلى إنجليزية فقط (دون تغيير الحروف العربية)."""
    return str(s).translate(_DIGIT_MAP).replace('٫', '.').replace('٬', ',')

def _clean_carb(val) -> str:
    # عرض محتوى الخلية كما هو، مع تحويل الأرقام العربية إلى إنجليزية فقط.
    # لا نحذف أي نص ولا نضيف أي شيء — النص الذي تكتبه يظهر كما هو.
    if val is None:
        return "—"
    t = str(val).strip()
    if t in ("", "nan", "None"):
        return "—"
    return _to_western(t)

def _section_type(carbs_clean, section) -> str:
    """تحديد قسم الطعام (جرام/بدائل) من نص قيمة الكارب، مع الرجوع لعمود الفئة."""
    cl = str(carbs_clean)
    if "لكل جرام" in cl:
        return "grams"
    if "جرام كارب" in cl:
        return "alts"
    s = str(section)
    if "جرام" in s:
        return "grams"
    if "بدائل" in s:
        return "alts"
    return ""

def _matches(q_norm: str, food: dict) -> bool:
    return q_norm in food.get("_norm_name", "") or q_norm in food.get("_norm_sec", "")

def _parse_num(val):
    """استخراج أول قيمة رقمية من النص (يدعم الأرقام العربية والإنجليزية)."""
    t = _to_western(val).replace(',', '.')
    m = re.search(r'[-+]?\d+(?:\.\d+)?', t)
    return float(m.group()) if m else None

def _fmt_num(x: float) -> str:
    """تنسيق ناتج الحساب: إزالة الأصفار الزائدة وعرضه بأرقام إنجليزية."""
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}".rstrip('0').rstrip('.')


# ══════════════════════════════════════════════════════════════════════════════
# HTML builders (نبني HTML مرة واحدة ونُخزّنه في session_state)
# ══════════════════════════════════════════════════════════════════════════════
def _build_gram_card_html(food: dict) -> str:
    name  = html.escape(str(food.get("name", "")))
    carbs = html.escape(str(food.get("carbs_clean", "—")))
    emoji = _food_emoji(str(food.get("name", "")))
    cat   = html.escape(str(food.get("cat_label", "")))
    cat_html = f"<span class='cg-cat'>{cat}</span>" if cat else ""
    return (
        f"<div class='card-gram'>"
        f"<div class='cg-left'>"
        f"<span class='cg-emoji'>{emoji}</span>"
        f"<div class='cg-info'><span class='cg-name'>{name}</span>{cat_html}</div>"
        f"</div>"
        f"<span class='cg-badge'>{carbs}</span>"
        f"</div>"
    )

def _build_gram_card_interactive(food: dict) -> str:
    """بطاقة «لكل جرام» قابلة للضغط: تتحوّل في مكانها إلى وضع الحساب داخل iframe."""
    name  = html.escape(str(food.get("name", "")))
    carbs = html.escape(str(food.get("carbs_clean", "—")))
    emoji = _food_emoji(str(food.get("name", "")))
    cat   = html.escape(str(food.get("cat_label", "")))
    cat_html = f"<span class='cg-cat'>{cat}</span>" if cat else ""
    per_gram = _parse_num(food.get("carbs_clean", ""))
    head = (
        f"<div class='cg-left'>"
        f"<span class='cg-emoji'>{emoji}</span>"
        f"<div class='cg-info'><span class='cg-name'>{name}</span>{cat_html}</div>"
        f"</div>"
        f"<span class='cg-badge'>{carbs}</span>"
    )
    if per_gram is None:
        # لا قيمة رقمية للحساب — تبقى بطاقة عادية غير قابلة للضغط
        return f"<div class='card-gram'>{head}</div>"
    pg = f"{per_gram:.6f}".rstrip('0').rstrip('.')
    calc = (
        "<div class='cg-calc'>"
        "<div class='cg-calc-label'>أدخل الوزن (جم)</div>"
        "<input class='cg-w' type='text' inputmode='decimal' "
        "placeholder='مثال: 100'>"
        "<button class='cg-btn' type='button'>احسب</button>"
        "<div class='cg-msg'>الرجاء إدخال الوزن أولاً.</div>"
        "<div class='cg-result'>"
        "<div class='cg-res-label'>إجمالي الكربوهيدرات</div>"
        "<div class='cg-res-num'><span class='cg-res'>—</span> "
        "<span class='cg-res-unit'>جم كربوهيدرات</span></div>"
        "<button class='cg-add' type='button'>➕ إضافة إلى وجبتي</button>"
        "</div></div>"
    )
    return f"<div class='card-gram' data-pg='{pg}' role='button' tabindex='0'>{head}{calc}</div>"

def _build_gram_cards_doc(foods: list) -> str:
    """مستند HTML كامل (CSS + JS) لشبكة بطاقات «لكل جرام» التفاعلية داخل iframe.
    الحساب يتم في المتصفح عند الضغط على زر «احسب» (دون إعادة تحميل): الوزن × لكل جرام."""
    cards = "".join(_build_gram_card_interactive(f) for f in foods)
    return (
        "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap' rel='stylesheet' media='print' onload=\"this.media='all'\">"
        "<style>"
        "*{box-sizing:border-box;font-family:'Cairo','Segoe UI',Tahoma,Arial,sans-serif;}"
        "html,body{margin:0;padding:0;background:transparent;}"
        ".pg-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:start;}"
        "@media(max-width:640px){.pg-grid{grid-template-columns:1fr;}}"
        ".card-gram{background:#ffffff;border:1px solid #e6ebf5;border-radius:14px;"
        "padding:13px 16px;box-shadow:0 1px 4px rgba(20,40,90,0.05);"
        "display:flex;align-items:center;justify-content:space-between;gap:10px;}"
        ".card-gram[data-pg]{cursor:pointer;}"
        ".card-gram[data-pg]:hover{border-color:#cddfe2;}"
        ".cg-info{display:flex;flex-direction:column;gap:2px;min-width:0;}"
        ".cg-left{display:flex;align-items:center;gap:11px;min-width:0;}"
        ".cg-emoji{font-size:1.35rem;line-height:1;width:42px;height:42px;flex-shrink:0;"
        "display:inline-flex;align-items:center;justify-content:center;"
        "background:#ecf4f5;border:1px solid #e6ebf5;border-radius:12px;}"
        ".cg-name{font-size:0.98rem;font-weight:800;color:#23434c;line-height:1.3;"
        "overflow:hidden;text-overflow:ellipsis;}"
        ".cg-cat{font-size:0.78rem;font-weight:700;color:#6f8893;line-height:1.2;}"
        ".cg-badge{background:#e3eef1;color:#3e6e7e;font-weight:900;font-size:1rem;"
        "border-radius:10px;padding:6px 13px;white-space:nowrap;flex-shrink:0;}"
        ".cg-calc{display:none;flex-basis:100%;width:100%;margin-top:12px;padding-top:12px;"
        "border-top:1px dashed #d6e3e6;}"
        ".card-gram.calc-open{flex-wrap:wrap;cursor:default;}"
        ".card-gram.calc-open .cg-calc{display:block;}"
        ".cg-calc-label{font-size:0.8rem;color:#5c7682;font-weight:700;margin-bottom:6px;text-align:right;}"
        ".cg-w{width:100%;font-family:inherit;font-size:1rem;font-weight:800;color:#23434c;"
        "text-align:right;direction:rtl;padding:9px 12px;border:1.5px solid #d6e3e6;"
        "border-radius:10px;background:#fff;}"
        ".cg-w:focus{outline:none;border-color:#3e6e7e;}"
        ".cg-btn{display:block;width:100%;margin-top:10px;background:#3e6e7e;color:#fff;"
        "border:none;border-radius:12px;font-family:inherit;font-weight:800;font-size:0.98rem;"
        "padding:10px 26px;cursor:pointer;}"
        ".cg-btn:hover{background:#2f5965;}"
        ".cg-msg{display:none;margin-top:10px;text-align:center;color:#b26a00;"
        "background:#fff3e0;border:1px solid #ffe0b2;border-radius:10px;padding:8px 12px;"
        "font-size:0.85rem;font-weight:700;}"
        ".cg-result{display:none;margin-top:12px;text-align:center;background:#eaf3f4;"
        "border:1px solid #cfe2e5;border-radius:12px;padding:12px;}"
        ".cg-res-label{font-size:0.82rem;color:#5c7682;margin-bottom:4px;font-weight:700;}"
        ".cg-res-num{font-size:1.6rem;font-weight:900;color:#3e6e7e;}"
        ".cg-res-num .cg-res-unit{font-size:0.85rem;font-weight:700;color:#5c7682;}"
        ".cg-add{display:block;width:100%;margin-top:10px;background:#4f7340;color:#fff;"
        "border:none;border-radius:12px;font-family:inherit;font-weight:800;font-size:0.95rem;"
        "padding:9px 20px;cursor:pointer;}"
        ".cg-add:hover{background:#3f5d33;}"
        ".cg-add.added{background:#2f5965;}"
        ".meal-cart,.meal-insulin{background:#fff;border:1px solid #e6ebf5;border-radius:14px;"
        "padding:16px 18px;margin-top:16px;box-shadow:0 1px 4px rgba(20,40,90,0.05);}"
        ".mc-head,.mi-head{font-size:1.05rem;font-weight:900;color:#23434c;margin-bottom:12px;}"
        ".mc-empty{color:#6f8893;font-size:0.9rem;font-weight:700;text-align:center;padding:8px 0 4px;}"
        ".mc-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border:1px solid #eef2f7;"
        "border-radius:10px;margin-bottom:8px;background:#fbfcfe;}"
        ".mc-item-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px;}"
        ".mc-item-name{font-weight:800;color:#23434c;font-size:0.95rem;}"
        ".mc-item-sub{font-size:0.76rem;color:#6f8893;font-weight:700;}"
        ".mc-item-carb{font-weight:900;color:#3e6e7e;background:#e3eef1;border-radius:9px;"
        "padding:5px 11px;white-space:nowrap;font-size:0.92rem;}"
        ".mc-del{background:#fff;border:1px solid #f0d2d2;color:#c0392b;border-radius:9px;"
        "width:32px;height:32px;cursor:pointer;font-size:0.85rem;flex-shrink:0;line-height:1;}"
        ".mc-del:hover{background:#fdecec;}"
        ".mc-total{margin-top:12px;padding-top:12px;border-top:1px dashed #d6e3e6;"
        "text-align:left;font-weight:900;color:#23434c;font-size:1rem;}"
        ".mc-total-val{color:#3e6e7e;}"
        ".mc-add-manual{display:block;width:100%;margin-top:12px;background:#fff;color:#4f7340;"
        "border:1.5px dashed #b6cfa8;border-radius:12px;font-family:inherit;font-weight:800;"
        "font-size:0.92rem;padding:10px 18px;cursor:pointer;}"
        ".mc-add-manual:hover{background:#f2f7ee;border-color:#4f7340;}"
        ".mi-note{font-size:0.85rem;color:#5c7682;font-weight:700;background:#eaf3f4;"
        "border:1px solid #cfe2e5;border-radius:10px;padding:8px 12px;margin-bottom:12px;}"
        ".mi-carbs{font-weight:900;color:#3e6e7e;}"
        ".mi-label{display:block;font-size:0.82rem;color:#5c7682;font-weight:800;margin:8px 0 5px;}"
        ".mi-in{width:100%;font-family:inherit;font-size:1rem;font-weight:800;color:#23434c;"
        "text-align:right;direction:rtl;padding:9px 12px;border:1.5px solid #d6e3e6;"
        "border-radius:10px;background:#fff;}"
        ".mi-in:focus{outline:none;border-color:#3e6e7e;}"
        ".mi-btn{display:block;width:100%;margin-top:14px;background:#3e6e7e;color:#fff;"
        "border:none;border-radius:12px;font-family:inherit;font-weight:800;font-size:1rem;"
        "padding:11px 26px;cursor:pointer;}"
        ".mi-btn:hover{background:#2f5965;}"
        ".mi-msg{display:none;margin-top:12px;text-align:center;color:#b26a00;background:#fff3e0;"
        "border:1px solid #ffe0b2;border-radius:10px;padding:8px 12px;font-size:0.85rem;font-weight:700;}"
        ".mi-result{display:none;margin-top:14px;background:#eaf3f4;border:1px solid #cfe2e5;"
        "border-radius:12px;padding:6px 14px;}"
        ".mi-row{display:flex;justify-content:space-between;align-items:center;gap:10px;"
        "padding:10px 0;border-bottom:1px solid #d9e7ea;}"
        ".mi-row:last-child{border-bottom:none;}"
        ".mi-row-l{color:#5c7682;font-weight:700;font-size:0.9rem;}"
        ".mi-row-v{color:#3e6e7e;font-weight:900;font-size:1.05rem;}"
        ".mi-row-total .mi-row-l{color:#23434c;font-weight:900;font-size:0.98rem;}"
        ".mi-row-total .mi-row-v{font-size:1.3rem;}"
        ".mi-approx{font-size:0.8rem;font-weight:700;color:#5c7682;}"
        "</style></head><body>"
        f"<div class='pg-root'><div class='pg-grid'>{cards}</div>"
        "<div class='meal-cart'>"
        "<div class='mc-head'>وجبتي</div>"
        "<div class='mc-list'></div>"
        "<div class='mc-empty'>لم تتم إضافة أي صنف بعد.</div>"
        "<div class='mc-total'>إجمالي الكربوهيدرات = <span class='mc-total-val'>0</span> جم</div>"
        "<button class='mc-add-manual' type='button'>➕ إضافة منتج يدوي</button>"
        "</div>"
        "<div class='meal-insulin'>"
        "<div class='mi-head'>حساب جرعة الإنسولين</div>"
        "<div class='mi-note'>يُحسب تلقائياً من إجمالي كربوهيدرات وجبتي "
        "(<span class='mi-carbs'>0</span> جم).</div>"
        "<label class='mi-label'>معامل الكربوهيدرات (ICR)</label>"
        "<input class='mi-in' id='mi_icr' type='text' inputmode='decimal' placeholder='مثال: 15'>"
        "<label class='mi-label'>السكر الحالي (mg/dL)</label>"
        "<input class='mi-in' id='mi_bg' type='text' inputmode='decimal' placeholder='مثال: 200'>"
        "<label class='mi-label'>معامل التصحيح (ISF)</label>"
        "<input class='mi-in' id='mi_isf' type='text' inputmode='decimal' placeholder='مثال: 50'>"
        "<button class='mi-btn' type='button'>احسب جرعة الإنسولين</button>"
        "<div class='mi-msg'></div>"
        "<div class='mi-result'>"
        "<div class='mi-row'><span class='mi-row-l'>جرعة تغطية الكربوهيدرات</span>"
        "<span class='mi-row-v' id='mi_cov'>—</span></div>"
        "<div class='mi-row'><span class='mi-row-l'>جرعة التصحيح (الهدف 150)</span>"
        "<span class='mi-row-v' id='mi_corr'>—</span></div>"
        "<div class='mi-row mi-row-total'><span class='mi-row-l'>إجمالي الجرعة المطلوبة</span>"
        "<span class='mi-row-v' id='mi_tot'>—</span></div>"
        "</div>"
        "</div>"
        "</div>"
        "<script>"
        "function fmt(x){var r=Math.round(x*100)/100;"
        "if(Math.abs(r-Math.round(r))<1e-9)return String(Math.round(r));return String(r);}"
        "function toWestern(s){var a='٠١٢٣٤٥٦٧٨٩',p='۰۱۲۳۴۵۶۷۸۹';"
        "return String(s).replace(/[٠-٩]/g,function(d){return a.indexOf(d);})"
        ".replace(/[۰-۹]/g,function(d){return p.indexOf(d);})"
        ".replace('٫','.').replace('٬',',');}"
        "function openReset(card){var b=card.querySelector('.cg-result');"
        "if(b)b.style.display='none';var m=card.querySelector('.cg-msg');"
        "if(m)m.style.display='none';}"
        "function compute(card){var pg=parseFloat(card.getAttribute('data-pg'))||0;"
        "var inp=card.querySelector('.cg-w');var res=card.querySelector('.cg-res');"
        "var box=card.querySelector('.cg-result');var msg=card.querySelector('.cg-msg');"
        "if(!inp||!res)return;"
        "var raw=toWestern((inp.value||'')).trim().replace(',','.');"
        "var w=parseFloat(raw);"
        "if(raw===''||isNaN(w)||w<=0){if(box)box.style.display='none';"
        "if(msg)msg.style.display='block';resize();return;}"
        "if(msg)msg.style.display='none';res.textContent=fmt(pg*w);"
        "if(box)box.style.display='block';resize();}"
        "function resize(){try{var root=document.querySelector('.pg-root');"
        "var target=Math.ceil((root?root.offsetHeight:document.body.scrollHeight)+8);"
        "var cur=parseFloat(window.frameElement.style.height)||0;"
        "if(Math.abs(cur-target)>2)window.frameElement.style.height=target+'px';}catch(e){}}"
        "function g(id){return document.getElementById(id);}"
        "function q(s){return document.querySelector(s);}"
        "var MK='carbcalc_meal_v1',IK='carbcalc_ins_v1';"
        "function loadCart(){try{return JSON.parse(localStorage.getItem(MK))||[];}catch(e){return[];}}"
        "function saveCart(){try{localStorage.setItem(MK,JSON.stringify(cart));}catch(e){}}"
        "var cart=loadCart();"
        "function cartTotal(){var t=0;for(var i=0;i<cart.length;i++)t+=(+cart[i].carbs||0);return t;}"
        "function saveInputs(){try{localStorage.setItem(IK,JSON.stringify("
        "{icr:g('mi_icr').value,bg:g('mi_bg').value,isf:g('mi_isf').value}));}catch(e){}}"
        "function loadInputs(){try{var o=JSON.parse(localStorage.getItem(IK))||{};"
        "if(g('mi_icr'))g('mi_icr').value=o.icr||'';if(g('mi_bg'))g('mi_bg').value=o.bg||'';"
        "if(g('mi_isf'))g('mi_isf').value=o.isf||'';}catch(e){}}"
        "function units(n){n=Math.round(n);if(n===1)return 'وحدة واحدة';if(n===2)return 'وحدتان';"
        "if(n>=3&&n<=10)return n+' وحدات';return n+' وحدة';}"
        "function renderCart(){var list=q('.mc-list');if(!list)return;list.innerHTML='';"
        "for(var i=0;i<cart.length;i++){(function(it,idx){"
        "var row=document.createElement('div');row.className='mc-item';"
        "var del=document.createElement('button');del.className='mc-del';"
        "del.setAttribute('data-i',idx);del.textContent='✕';"
        "var main=document.createElement('div');main.className='mc-item-main';"
        "var nm=document.createElement('span');nm.className='mc-item-name';nm.textContent=it.name;"
        "var sub=document.createElement('span');sub.className='mc-item-sub';"
        "sub.textContent=it.manual?'مُدخل يدوياً':(it.qty?('الكمية: '+it.qty):('الوزن: '+fmt(it.weight)+' جم'));"
        "main.appendChild(nm);main.appendChild(sub);"
        "var cb=document.createElement('span');cb.className='mc-item-carb';"
        "cb.textContent=fmt(it.carbs)+' جم';"
        "row.appendChild(del);row.appendChild(main);row.appendChild(cb);list.appendChild(row);"
        "})(cart[i],i);}"
        "var emp=q('.mc-empty'),tt=q('.mc-total');"
        "if(cart.length===0){if(emp)emp.style.display='block';if(tt)tt.style.display='none';}"
        "else{if(emp)emp.style.display='none';if(tt)tt.style.display='block';}"
        "var tv=q('.mc-total-val');if(tv)tv.textContent=fmt(cartTotal());"
        "var mc=q('.mi-carbs');if(mc)mc.textContent=fmt(cartTotal());"
        "updateBadge();"
        "var rb=q('.mi-result');if(rb&&rb.style.display==='block')insulin();else resize();}"
        "function addToMeal(btn){var card=btn.closest('.card-gram');if(!card)return;"
        "var pg=parseFloat(card.getAttribute('data-pg'))||0;var inp=card.querySelector('.cg-w');"
        "var w=parseFloat(toWestern((inp&&inp.value)||'').replace(',','.'));"
        "if(isNaN(w)||w<=0)return;var nmel=card.querySelector('.cg-name');"
        "var nm=nmel?nmel.textContent.trim():'';"
        "cart.push({name:nm,weight:w,carbs:pg*w});saveCart();renderCart();"
        "btn.textContent='✓ تمت الإضافة';btn.classList.add('added');"
        "setTimeout(function(){btn.textContent='➕ إضافة إلى وجبتي';"
        "btn.classList.remove('added');},1300);}"
        "function insulin(){"
        "var icr=parseFloat(toWestern((g('mi_icr').value)||'').replace(',','.'));"
        "var bg=parseFloat(toWestern((g('mi_bg').value)||'').replace(',','.'));"
        "var isf=parseFloat(toWestern((g('mi_isf').value)||'').replace(',','.'));"
        "var total=cartTotal();var errs=[];"
        "if(isNaN(icr)||icr<=0)errs.push('أدخل معامل الكربوهيدرات بشكل صحيح.');"
        "if(isNaN(bg)||bg<0)errs.push('أدخل السكر الحالي بشكل صحيح.');"
        "if(isNaN(isf)||isf<=0)errs.push('أدخل معامل التصحيح بشكل صحيح.');"
        "var msg=q('.mi-msg'),res=q('.mi-result');"
        "if(errs.length){if(msg){msg.innerHTML=errs.join('<br>');msg.style.display='block';}"
        "if(res)res.style.display='none';resize();return;}"
        "if(msg)msg.style.display='none';"
        "var cov=total/icr;var corr=bg>150?(bg-150)/isf:0;var tot=cov+corr;"
        "g('mi_cov').textContent=fmt(cov)+' وحدة';"
        "g('mi_corr').textContent=fmt(corr)+' وحدة';"
        "var tx=fmt(tot)+' وحدة';"
        "if(Math.abs(tot-Math.round(tot))>1e-9)"
        "tx=fmt(tot)+\" وحدة <span class='mi-approx'>(تقريباً \"+units(tot)+\")</span>\";"
        "g('mi_tot').innerHTML=tx;if(res)res.style.display='block';saveInputs();resize();}"
        "function manualStyle(){try{var pd=window.parent.document;"
        "if(pd.getElementById('mm-style'))return;"
        "var s=pd.createElement('style');s.id='mm-style';s.textContent="
        "'#mm-overlay{position:fixed;inset:0;z-index:100000;background:rgba(20,40,60,0.45);'"
        "+'display:none;align-items:center;justify-content:center;padding:18px;direction:rtl;}'"
        "+'#mm-overlay.open{display:flex;}'"
        "+'#mm-overlay .mm-box{background:#fff;border-radius:16px;padding:20px 20px 18px;width:100%;'"
        "+'max-width:340px;box-shadow:0 12px 40px rgba(20,40,90,0.25);direction:rtl;text-align:right;'"
        "+'font-family:inherit;box-sizing:border-box;}'"
        "+'#mm-overlay .mm-title{font-size:1.05rem;font-weight:900;color:#23434c;margin-bottom:4px;}'"
        "+'#mm-overlay .mm-sub{font-size:0.8rem;color:#6f8893;font-weight:700;margin-bottom:14px;}'"
        "+'#mm-overlay .mm-label{display:block;font-size:0.82rem;color:#5c7682;font-weight:800;margin:10px 0 5px;}'"
        "+'#mm-overlay .mm-in{width:100%;box-sizing:border-box;font-family:inherit;font-size:1rem;'"
        "+'font-weight:800;color:#23434c;text-align:right;direction:rtl;padding:9px 12px;'"
        "+'border:1.5px solid #d6e3e6;border-radius:10px;background:#fff;}'"
        "+'#mm-overlay .mm-in:focus{outline:none;border-color:#3e6e7e;}'"
        "+'#mm-overlay .mm-msg{display:none;margin-top:12px;text-align:center;color:#b26a00;'"
        "+'background:#fff3e0;border:1px solid #ffe0b2;border-radius:10px;padding:8px 12px;'"
        "+'font-size:0.85rem;font-weight:700;}'"
        "+'#mm-overlay .mm-actions{display:flex;gap:10px;margin-top:16px;}'"
        "+'#mm-overlay .mm-btn{flex:1;background:#4f7340;color:#fff;border:none;border-radius:12px;'"
        "+'font-family:inherit;font-weight:800;font-size:0.95rem;padding:10px 18px;cursor:pointer;}'"
        "+'#mm-overlay .mm-btn:hover{background:#3f5d33;}'"
        "+'#mm-overlay .mm-cancel{flex:1;background:#fff;color:#5c7682;border:1.5px solid #d6e3e6;'"
        "+'border-radius:12px;font-family:inherit;font-weight:800;font-size:0.95rem;padding:10px 18px;cursor:pointer;}'"
        "+'#mm-overlay .mm-cancel:hover{background:#f4f7f9;}';"
        "pd.head.appendChild(s);}catch(e){}}"
        "function mmEl(id){try{return window.parent.document.getElementById(id);}catch(e){return null;}}"
        "function ensureManual(){try{manualStyle();var pd=window.parent.document;"
        "var old=pd.getElementById('mm-overlay');if(old)old.remove();"
        "var ov=pd.createElement('div');ov.id='mm-overlay';"
        "var box=pd.createElement('div');box.className='mm-box';"
        "var bx=\"<div class='mm-title'>\\u2795 \\u0625\\u0636\\u0627\\u0641\\u0629 \\u0645\\u0646\\u062a\\u062c \\u064a\\u062f\\u0648\\u064a</div>\";"
        "bx+=\"<div class='mm-sub'>\\u064a\\u064f\\u0636\\u0627\\u0641 \\u0644\\u0647\\u0630\\u0647 \\u0627\\u0644\\u0648\\u062c\\u0628\\u0629 \\u0641\\u0642\\u0637 \\u0648\\u0644\\u0627 \\u064a\\u064f\\u062d\\u0641\\u0638 \\u0641\\u064a \\u0642\\u0627\\u0639\\u062f\\u0629 \\u0627\\u0644\\u0628\\u064a\\u0627\\u0646\\u0627\\u062a.</div>\";"
        "bx+=\"<label class='mm-label'>\\u0627\\u0633\\u0645 \\u0627\\u0644\\u0645\\u0646\\u062a\\u062c (\\u0627\\u062e\\u062a\\u064a\\u0627\\u0631\\u064a)</label>\";"
        "bx+=\"<input class='mm-in' id='mm_name' type='text' placeholder='\\u0645\\u062b\\u0627\\u0644: \\u0642\\u0637\\u0639\\u0629 \\u0643\\u064a\\u0643'>\";"
        "bx+=\"<label class='mm-label'>\\u0643\\u0645\\u064a\\u0629 \\u0627\\u0644\\u0643\\u0631\\u0628\\u0648\\u0647\\u064a\\u062f\\u0631\\u0627\\u062a (\\u062c\\u0645)</label>\";"
        "bx+=\"<input class='mm-in' id='mm_carbs' type='text' inputmode='decimal' placeholder='\\u0645\\u062b\\u0627\\u0644: 30'>\";"
        "bx+=\"<div class='mm-msg' id='mm_msg'></div>\";"
        "bx+=\"<div class='mm-actions'>\";"
        "bx+=\"<button class='mm-btn' id='mm_add' type='button'>\\u0625\\u0636\\u0627\\u0641\\u0629</button>\";"
        "bx+=\"<button class='mm-cancel' id='mm_cancel' type='button'>\\u0625\\u0644\\u063a\\u0627\\u0621</button>\";"
        "bx+=\"</div>\";"
        "box.innerHTML=bx;ov.appendChild(box);pd.body.appendChild(ov);"
        "ov.addEventListener('click',function(e){if(e.target===ov)closeManual();});"
        "box.querySelector('#mm_add').addEventListener('click',addManual);"
        "box.querySelector('#mm_cancel').addEventListener('click',closeManual);"
        "box.querySelector('#mm_carbs').addEventListener('keydown',function(e){"
        "if(e.key==='Enter'){e.preventDefault();addManual();}});"
        "box.querySelector('#mm_name').addEventListener('keydown',function(e){"
        "if(e.key==='Enter'){e.preventDefault();var c=mmEl('mm_carbs');if(c)c.focus();}});"
        "}catch(e){}}"
        "function openManual(){ensureManual();var o=mmEl('mm-overlay');if(!o)return;"
        "var n=mmEl('mm_name'),c=mmEl('mm_carbs'),m=mmEl('mm_msg');"
        "if(n)n.value='';if(c)c.value='';if(m)m.style.display='none';"
        "o.classList.add('open');setTimeout(function(){if(c)c.focus();},60);}"
        "function closeManual(){var o=mmEl('mm-overlay');if(o)o.classList.remove('open');}"
        "function addManual(){var n=mmEl('mm_name'),c=mmEl('mm_carbs'),m=mmEl('mm_msg');"
        "var nm=((n&&n.value)||'').trim();"
        "var raw=toWestern((c&&c.value)||'').trim().replace(',','.');"
        "var v=parseFloat(raw);"
        "if(raw===''||isNaN(v)||v<=0){if(m){"
        "m.textContent='\\u0627\\u0644\\u0631\\u062c\\u0627\\u0621 \\u0625\\u062f\\u062e\\u0627\\u0644 \\u0643\\u0645\\u064a\\u0629 \\u0643\\u0631\\u0628\\u0648\\u0647\\u064a\\u062f\\u0631\\u0627\\u062a \\u0635\\u062d\\u064a\\u062d\\u0629.';"
        "m.style.display='block';}return;}"
        "if(!nm)nm='\\u0645\\u0646\\u062a\\u062c \\u064a\\u062f\\u0648\\u064a';"
        "cart.push({name:nm,carbs:v,manual:true});saveCart();renderCart();closeManual();}"
        "document.addEventListener('click',function(e){"
        "if(e.target.closest('.mc-add-manual')){openManual();return;}"
        "var addb=e.target.closest('.cg-add');if(addb){addToMeal(addb);return;}"
        "var del=e.target.closest('.mc-del');if(del){var i=parseInt(del.getAttribute('data-i'),10);"
        "if(i>=0){cart.splice(i,1);saveCart();renderCart();}return;}"
        "var mib=e.target.closest('.mi-btn');if(mib){insulin();return;}"
        "var btn=e.target.closest('.cg-btn');"
        "if(btn){var c=btn.closest('.card-gram');if(c)compute(c);return;}"
        "var card=e.target.closest('.card-gram[data-pg]');if(!card)return;"
        "if(e.target.closest('.cg-w'))return;"
        "card.classList.toggle('calc-open');"
        "if(card.classList.contains('calc-open'))openReset(card);resize();});"
        "document.addEventListener('keydown',function(e){"
        "if(e.target.classList.contains('mi-in')){if(e.key==='Enter'){e.preventDefault();insulin();}return;}"
        "if(e.target.classList.contains('cg-w')){if(e.key==='Enter'){e.preventDefault();"
        "var c=e.target.closest('.card-gram');if(c)compute(c);}return;}"
        "if(e.target.closest('.cg-btn'))return;"
        "if(e.key!=='Enter'&&e.key!==' ')return;"
        "var card=e.target.closest('.card-gram[data-pg]');"
        "if(!card)return;e.preventDefault();"
        "card.classList.toggle('calc-open');"
        "if(card.classList.contains('calc-open'))openReset(card);resize();});"
        "document.addEventListener('input',function(e){"
        "if(e.target.classList.contains('mi-in'))saveInputs();});"
        "function fabStyle(){try{var pd=window.parent.document;"
        "if(pd.getElementById('pg-fab-style'))return;"
        "var s=pd.createElement('style');s.id='pg-fab-style';"
        "s.textContent='#pg-fabcol{position:fixed;left:16px;bottom:16px;z-index:99999;"
        "display:flex;flex-direction:column;align-items:flex-start;gap:10px;pointer-events:none;}"
        "#pg-fabcol>*{pointer-events:auto;}"
        "#pg-top{display:none;align-items:center;justify-content:center;"
        "width:46px;height:46px;padding:0;background:#3e6e7e;color:#fff;border:none;"
        "border-radius:30px;font-family:inherit;font-weight:800;font-size:1.35rem;"
        "cursor:pointer;line-height:1;box-shadow:0 6px 18px rgba(20,40,90,0.28);}"
        "#pg-top:hover{background:#2f5965;}"
        "#pg-top:active{transform:translateY(1px);}"
        "#pg-fab{"
        "display:none;align-items:center;gap:8px;background:#3e6e7e;color:#fff;"
        "border:none;border-radius:30px;font-family:inherit;font-weight:800;"
        "font-size:0.95rem;padding:12px 18px;cursor:pointer;direction:rtl;"
        "box-shadow:0 6px 18px rgba(20,40,90,0.28);}"
        "#pg-fab:hover{background:#2f5965;}"
        "#pg-fab:active{transform:translateY(1px);}"
        "#pg-fab .pf-ico{font-size:1.15rem;line-height:1;}"
        "#pg-fab .pf-badge{display:none;min-width:20px;height:20px;padding:0 5px;"
        "box-sizing:border-box;background:#e03131;color:#fff;border-radius:11px;"
        "font-size:0.78rem;font-weight:900;align-items:center;justify-content:center;"
        "line-height:1;}';"
        "pd.head.appendChild(s);}catch(e){}}"
        "function pscrollEl(){try{var pd=window.parent.document;"
        "var c=[pd.scrollingElement,pd.documentElement,pd.body,"
        "pd.querySelector('section.main'),pd.querySelector('[data-testid=\"stMain\"]'),"
        "pd.querySelector('[data-testid=\"stAppViewContainer\"]')];"
        "for(var i=0;i<c.length;i++){if(c[i]&&c[i].scrollHeight-c[i].clientHeight>4)return c[i];}"
        "return pd.scrollingElement||pd.documentElement;}catch(e){return null;}}"
        "function scrollToCart(){try{var ifr=window.frameElement;if(!ifr)return;"
        "var cart=q('.meal-cart');var off=cart?cart.offsetTop:0;"
        "var delta=ifr.getBoundingClientRect().top+off-70;"
        "var sc=pscrollEl();"
        "if(sc&&sc.scrollBy)sc.scrollBy({top:delta,behavior:'smooth'});"
        "else window.parent.scrollBy({top:delta,behavior:'smooth'});}catch(e){}}"
        "function goTop(){try{var sc=pscrollEl();"
        "if(sc&&sc.scrollTo)sc.scrollTo({top:0,behavior:'smooth'});"
        "else window.parent.scrollTo({top:0,behavior:'smooth'});}catch(e){}}"
        "function fabApply(){try{var pd=window.parent.document;"
        "var fab=pd.getElementById('pg-fab');if(!fab)return;"
        "fab.style.display='flex';}catch(e){}}"
        "function topApply(){try{var pd=window.parent.document;"
        "var t=pd.getElementById('pg-top');if(!t)return;"
        "t.style.display='flex';}catch(e){}}"
        "var __fabRaf=0;function toggleFab(){if(__fabRaf)return;"
        "var raf=window.requestAnimationFrame||function(f){return setTimeout(f,16);};"
        "__fabRaf=raf(function(){__fabRaf=0;fabApply();topApply();});}"
        "function updateBadge(){try{var fab=window.parent.document.getElementById('pg-fab');"
        "if(!fab)return;var b=fab.querySelector('.pf-badge');if(!b)return;"
        "if(cart.length>0){b.textContent=cart.length;b.style.display='flex';}"
        "else b.style.display='none';}catch(e){}}"
        "function ensureFab(){try{fabStyle();var pd=window.parent.document,pw=window.parent;"
        "var col=pd.getElementById('pg-fabcol');"
        "if(!col){col=pd.createElement('div');col.id='pg-fabcol';pd.body.appendChild(col);}"
        "var oldT=pd.getElementById('pg-top');if(oldT)oldT.remove();"
        "var top=pd.createElement('button');top.id='pg-top';top.type='button';"
        "top.setAttribute('aria-label','العودة إلى أعلى الصفحة');top.innerHTML='&#8593;';"
        "top.addEventListener('click',goTop);col.appendChild(top);"
        "var old=pd.getElementById('pg-fab');if(old)old.remove();"
        "var fab=pd.createElement('button');fab.id='pg-fab';fab.type='button';"
        "fab.setAttribute('aria-label','وجبتي');"
        "var ico=pd.createElement('span');ico.className='pf-ico';ico.textContent='🍽️';"
        "var txt=pd.createElement('span');txt.className='pf-txt';txt.textContent='وجبتي';"
        "var bdg=pd.createElement('span');bdg.className='pf-badge';"
        "fab.appendChild(ico);fab.appendChild(txt);fab.appendChild(bdg);"
        "fab.addEventListener('click',scrollToCart);col.appendChild(fab);"
        "if(pw.__pgFabT){pw.removeEventListener('scroll',pw.__pgFabT,true);"
        "pw.removeEventListener('resize',pw.__pgFabT);}"
        "pw.__pgFabT=toggleFab;pw.addEventListener('scroll',toggleFab,true);"
        "pw.addEventListener('resize',toggleFab);"
        "updateBadge();toggleFab();"
        "setTimeout(toggleFab,150);setTimeout(toggleFab,600);"
        "setTimeout(toggleFab,1200);}catch(e){}}"
        "window.addEventListener('storage',function(e){if(e.key===MK){cart=loadCart();renderCart();}});"
        "ensureFab();ensureManual();renderCart();loadInputs();"
        "window.addEventListener('load',function(){ensureFab();ensureManual();renderCart();loadInputs();resize();});"
        "if(document.fonts&&document.fonts.ready)document.fonts.ready.then(resize);"
        "setTimeout(resize,60);setTimeout(resize,300);setTimeout(resize,800);"
        "</script></body></html>"
    )

def _render_gram_cards_interactive(foods: list, version: int, search: str, cat: str):
    """رسم بطاقات «لكل جرام» التفاعلية عبر iframe، مع تخزين المستند مؤقتاً للسرعة.
    الارتفاع تلقائي ('content') ويُضبط أيضاً عبر JS عند فتح/إغلاق وضع الحساب."""
    cache_key = f"_gramdoc_{version}_{search}_{cat}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _build_gram_cards_doc(foods)
    st.iframe(st.session_state[cache_key], height="content")

def _build_alt_card_html(food: dict) -> str:
    name   = html.escape(str(food.get("name", "")))
    amount = food.get("amount", "")
    carbs  = html.escape(str(food.get("carbs_clean", "—")))
    amt_ok = amount and amount not in ("nan", "None", "")
    pill_amount = (
        f"<div class='ca-pill'><span class='ca-pill-label'>الكمية</span>"
        f"<span class='ca-pill-value'>{html.escape(str(amount))}</span></div>"
        if amt_ok else ""
    )
    emoji = _food_emoji(str(food.get("name", "")))
    cat   = html.escape(str(food.get("cat_label", "")))
    cat_html = f"<div class='ca-cat'>{cat}</div>" if cat else ""
    return (
        f"<div class='card-alt'>"
        f"<div class='ca-head'>"
        f"<span class='ca-emoji'>{emoji}</span>"
        f"<div class='ca-name'>{name}</div>"
        f"</div>"
        f"{cat_html}"
        f"<div class='ca-body'>{pill_amount}"
        f"<div class='ca-pill'><span class='ca-pill-label'>الكربوهيدرات</span>"
        f"<span class='ca-pill-value'>{carbs}</span></div>"
        f"</div></div>"
    )

def _build_alt_card_interactive(food: dict) -> str:
    """بطاقة «البدائل» قابلة للضغط: تفتح نافذة بدائل بنفس كمية الكربوهيدرات داخل iframe."""
    name   = str(food.get("name", ""))
    amount = food.get("amount", "")
    carbs_disp = str(food.get("carbs_clean", "—"))
    emoji = _food_emoji(name)
    cat   = str(food.get("cat_label", ""))
    amt_ok = bool(amount) and str(amount) not in ("nan", "None", "")
    name_e  = html.escape(name)
    cat_e   = html.escape(cat)
    carbs_e = html.escape(carbs_disp)
    amount_e = html.escape(str(amount)) if amt_ok else ""
    cat_html = f"<div class='ca-cat'>{cat_e}</div>" if cat_e else ""
    pill_amount = (
        f"<div class='ca-pill'><span class='ca-pill-label'>الكمية</span>"
        f"<span class='ca-pill-value'>{amount_e}</span></div>"
        if amt_ok else ""
    )
    body = (
        f"<div class='ca-head'><span class='ca-emoji'>{emoji}</span>"
        f"<div class='ca-name'>{name_e}</div></div>"
        f"{cat_html}"
        f"<div class='ca-body'>{pill_amount}"
        f"<div class='ca-pill'><span class='ca-pill-label'>الكربوهيدرات</span>"
        f"<span class='ca-pill-value'>{carbs_e}</span></div></div>"
    )
    carb_num = _parse_num(carbs_disp)
    if carb_num is None or carb_num <= 0:
        # لا قيمة رقمية للكربوهيدرات — بطاقة عادية غير قابلة للضغط
        return f"<div class='card-alt'>{body}</div>"
    cn = f"{carb_num:.4f}".rstrip('0').rstrip('.')
    macro = _macro_group(cat)
    return (
        f"<div class='card-alt' role='button' tabindex='0' data-ac='{cn}' "
        f"data-ag='{html.escape(macro, quote=True)}' "
        f"data-an=\"{html.escape(name, quote=True)}\" "
        f"data-am=\"{html.escape(str(amount) if amt_ok else '', quote=True)}\" "
        f"data-act=\"{html.escape(carbs_disp, quote=True)}\">{body}</div>"
    )


_MACRO_BY_LABEL = {
    "أرز وحبوب": "starch", "معكرونة": "starch", "خبز ومخبوزات": "starch",
    "فواكه": "fruit", "ألبان وأجبان": "dairy", "مشروبات": "drinks",
    "حلويات": "sweets", "بروتينات": "protein", "بقوليات": "legumes",
    "مكسرات": "nuts", "خضروات": "veg", "وجبات سريعة": "fastfood",
    "شعبي": "popular",
}


def _macro_group(label) -> str:
    """المجموعة الغذائية الكبرى لاسم الفئة (تُستخدم لتقييد البدائل).
    النشويات (أرز/معكرونة/خبز) تُجمَّع في مجموعة واحدة 'starch'."""
    return _MACRO_BY_LABEL.get(str(label).strip(), "other")


# قائمة بدائل داخلية احتياطية لكل مجموعة غذائية (اسم، نسبة كربوهيدرات لكل جرام)
# تُستخدم فقط عند عدم وجود بدائل مناسبة في بيانات Google Sheets — ومن نفس المجموعة فقط.
_ALT_FALLBACK = {
    "starch": [["خبز توست", 0.50], ["خبز عربي", 0.52], ["خبز بر", 0.43],
               ["مكرونة مطبوخة", 0.25], ["أرز مطبوخ", 0.28], ["برغل مطبوخ", 0.19],
               ["شوفان مطبوخ", 0.12], ["بطاطس مسلوقة", 0.17], ["ذرة مسلوقة", 0.19]],
    "fruit": [["موز", 0.23], ["تفاح", 0.14], ["برتقال", 0.12], ["كمثرى", 0.15],
              ["عنب", 0.18], ["خوخ", 0.10], ["مانجو", 0.15], ["فراولة", 0.08]],
    "dairy": [["حليب", 0.05], ["لبن", 0.05], ["زبادي", 0.06],
              ["حليب قليل الدسم", 0.05], ["حليب خالي الدسم", 0.05]],
    "drinks": [["عصير برتقال", 0.10], ["عصير تفاح", 0.11], ["عصير مانجو", 0.13],
               ["مشروب غازي", 0.10]],
    "sweets": [["كيك", 0.55], ["بسكويت", 0.70], ["شوكولاتة", 0.58],
               ["آيس كريم", 0.24], ["دونات", 0.50]],
    "legumes": [["فول مطبوخ", 0.12], ["عدس مطبوخ", 0.20], ["حمص مطبوخ", 0.27],
                ["فاصوليا مطبوخة", 0.21]],
    "veg": [["بطاطس مسلوقة", 0.17], ["ذرة مسلوقة", 0.19], ["جزر", 0.10],
            ["بازلاء", 0.14]],
}


def _alt_candidates(grams: list, alts: list) -> list:
    """قائمة المرشحين لعرض البدائل — كلها من بيانات Google Sheets الحالية فقط.
    نوعان من المرشحين:
      • مرجعي (ref): من قسم «البدائل» — له كمية مرجعية نصية (q) مثل «نصف كوب»
        وكمية كربوهيدرات لتلك الحصة (cc). تُعرض الكمية كما هي دون حساب يدوي.
      • محسوب (calc): من قسم «لكل جرام» — له نسبة كربوهيدرات لكل جرام (r)،
        وتُحسب الكمية التقديرية بالجرام عند الحاجة (الهدف ÷ r).
    تُعالَج «البدائل» أولاً كي تفوز الكمية المرجعية على المحسوبة لنفس الطعام."""
    out, seen = [], set()
    for f in alts:
        nm = str(f.get("name", "")).strip()
        if not nm or nm in seen:
            continue
        q = str(f.get("amount", "")).strip()
        cc = _parse_num(f.get("carbs_clean", ""))
        if q and q not in ("nan", "None", "") and cc and cc > 0:
            seen.add(nm)
            out.append({"n": nm, "q": q, "cc": cc, "e": _food_emoji(nm),
                        "c": str(f.get("cat_label", "")),
                        "g": _macro_group(f.get("cat_label", ""))})
    for f in grams:
        nm = str(f.get("name", "")).strip()
        if not nm or nm in seen:
            continue
        r = _parse_num(f.get("carbs_clean", ""))
        if r and r > 0:
            seen.add(nm)
            out.append({"n": nm, "r": r, "e": _food_emoji(nm),
                        "c": str(f.get("cat_label", "")),
                        "g": _macro_group(f.get("cat_label", ""))})
    return out


# CSS نافذة البدائل (تُحقن في مستند الصفحة الأم لأن iframe بارتفاع المحتوى
# لا يمكنه تثبيت عنصر فوق الشاشة) — نفس هوية الموقع (تركوازي + أخضر مريمي).
_ALT_MODAL_CSS = (
    "#amo-ov{position:fixed;inset:0;z-index:100000;background:rgba(15,30,40,0.45);"
    "display:flex;align-items:center;justify-content:center;padding:16px;"
    "font-family:'Cairo','Segoe UI',Tahoma,Arial,sans-serif;direction:rtl;}"
    ".amo-sheet{background:#fff;border-radius:18px;width:100%;max-width:430px;"
    "max-height:86vh;overflow:auto;box-shadow:0 18px 50px rgba(10,25,40,0.35);"
    "animation:amoUp .22s ease;}"
    "@keyframes amoUp{from{opacity:0;transform:translateY(16px);}to{opacity:1;transform:none;}}"
    ".amo-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:18px 18px 10px;}"
    ".amo-title{font-size:1.15rem;font-weight:900;color:#23434c;line-height:1.35;}"
    ".amo-x{flex-shrink:0;background:#f0f4f7;border:none;color:#5c7682;width:32px;height:32px;"
    "border-radius:50%;font-size:1rem;cursor:pointer;line-height:1;}"
    ".amo-x:hover{background:#e1e9ee;}"
    ".amo-meta{display:flex;gap:8px;padding:0 18px 4px;flex-wrap:wrap;}"
    ".amo-chip{display:flex;flex-direction:column;gap:2px;background:#eef5f6;border:1px solid #d8e7ea;"
    "border-radius:11px;padding:7px 14px;flex:1;min-width:120px;}"
    ".amo-chip-l{font-size:0.72rem;color:#6f8893;font-weight:700;}"
    ".amo-chip-v{font-size:0.98rem;color:#3e6e7e;font-weight:900;}"
    ".amo-sub{padding:12px 18px 6px;font-size:0.92rem;font-weight:800;color:#23434c;}"
    ".amo-list{padding:0 18px;display:flex;flex-direction:column;gap:8px;}"
    ".amo-item{display:flex;flex-direction:row;align-items:center;gap:10px;"
    "border:1.5px solid #e6ebf5;border-radius:12px;padding:11px 14px;"
    "background:#fbfcfe;transition:border-color .15s,background .15s;}"
    ".amo-item:hover{border-color:#cddfe2;}"
    ".amo-item.amo-base{border-color:#3e6e7e;background:#eaf3f4;}"
    ".amo-ibody{flex:1;display:flex;flex-direction:column;gap:2px;min-width:0;}"
    ".amo-iadd{flex-shrink:0;background:#3e6e7e;color:#fff;border:none;border-radius:10px;"
    "font-family:inherit;font-weight:800;font-size:0.76rem;line-height:1.3;padding:8px 10px;"
    "cursor:pointer;white-space:nowrap;}"
    ".amo-iadd:hover{background:#2f5965;}"
    ".amo-iadd.done{background:#4f7340;}"
    ".amo-iname{font-weight:800;color:#23434c;font-size:0.97rem;}"
    ".amo-icat{font-size:0.76rem;color:#74866a;font-weight:700;}"
    ".amo-iqty{font-weight:900;color:#3e6e7e;font-size:1.02rem;margin-top:3px;}"
    ".amo-icarb{font-size:0.82rem;color:#6f8893;font-weight:700;margin-top:1px;}"
    ".amo-empty{padding:6px 18px 4px;color:#6f8893;font-weight:700;font-size:0.9rem;}"
    ".amo-note{padding:9px 18px 2px;color:#6f8893;font-weight:700;font-size:0.8rem;line-height:1.5;}"
    ".amo-foot{display:flex;gap:10px;padding:14px 18px 18px;position:sticky;bottom:0;background:#fff;}"
    ".amo-btn{flex:1;border:none;border-radius:12px;font-family:inherit;font-weight:800;"
    "font-size:0.98rem;padding:11px 16px;cursor:pointer;}"
    ".amo-close{background:#eef2f5;color:#3e5560;}"
    ".amo-close:hover{background:#e1e9ee;}"
    "#amo-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:100001;"
    "background:#23434c;color:#fff;font-family:'Cairo',sans-serif;font-weight:800;font-size:0.9rem;"
    "padding:11px 18px;border-radius:30px;box-shadow:0 8px 24px rgba(10,25,40,0.3);direction:rtl;"
    "animation:amoUp .2s ease;}"
    "@media(max-width:560px){#amo-ov{align-items:flex-end;padding:0;}"
    ".amo-sheet{max-width:none;border-radius:18px 18px 0 0;max-height:90vh;}}"
)


def _build_alt_cards_doc(foods: list, cands: list) -> str:
    """مستند HTML كامل (CSS + JS) لشبكة بطاقات «البدائل» التفاعلية داخل iframe.
    الضغط على بطاقة يفتح نافذة فوق الصفحة فيها بدائل بنفس كمية الكربوهيدرات
    (نفس الفئة أولاً ثم بقية الفئات؛ الكمية المرجعية تُعرض كما هي، وإلا تُحسب
    تقديراً بالجرام). القسم للتثقيف والمقارنة فقط — لا يضيف إلى «وجبتي» ولا
    يرتبط بحاسبة الإنسولين."""
    cards = "".join(_build_alt_card_interactive(f) for f in foods)
    cands_json = json.dumps(cands, ensure_ascii=False).replace("</", "<\\/")
    fb_json = json.dumps(_ALT_FALLBACK, ensure_ascii=False).replace("</", "<\\/")
    return (
        "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap' rel='stylesheet' media='print' onload=\"this.media='all'\">"
        "<style>"
        "*{box-sizing:border-box;font-family:'Cairo','Segoe UI',Tahoma,Arial,sans-serif;}"
        "html,body{margin:0;padding:0;background:transparent;}"
        ".alt-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:start;}"
        "@media(max-width:640px){.alt-grid{grid-template-columns:1fr;}}"
        ".card-alt{background:#ffffff;border:1px solid #e6efe0;border-radius:14px;"
        "padding:13px 16px;margin-bottom:0;box-shadow:0 1px 4px rgba(27,94,32,0.05);}"
        ".card-alt[data-ac]{cursor:pointer;}"
        ".card-alt[data-ac]:hover{border-color:#bcd3aa;}"
        ".ca-head{display:flex;align-items:center;gap:11px;}"
        ".ca-emoji{font-size:1.35rem;line-height:1;width:42px;height:42px;flex-shrink:0;"
        "display:inline-flex;align-items:center;justify-content:center;"
        "background:#f1f6ec;border:1px solid #e6efe0;border-radius:12px;}"
        ".ca-name{font-size:0.98rem;font-weight:800;color:#2b3f25;}"
        ".ca-cat{font-size:0.78rem;font-weight:700;color:#74866a;margin-bottom:10px;margin-top:2px;}"
        ".ca-body{display:flex;gap:10px;flex-wrap:wrap;}"
        ".ca-pill{display:flex;flex-direction:column;align-items:center;"
        "background:#f4f8ee;border:1px solid #e6efe0;border-radius:11px;"
        "padding:7px 14px;flex:1;min-width:90px;}"
        ".ca-pill-label{font-size:0.7rem;color:#8a957f;margin-bottom:3px;}"
        ".ca-pill-value{font-size:0.98rem;font-weight:800;color:#4f7340;}"
        "</style></head><body>"
        f"<div class='alt-root'><div class='alt-grid'>{cards}</div></div>"
        "<script>"
        f"var CANDS={cands_json};"
        f"var FB={fb_json};"
        "function fmt(x){var r=Math.round(x*100)/100;"
        "if(Math.abs(r-Math.round(r))<1e-9)return String(Math.round(r));return String(r);}"
        "function toWestern(s){var a='٠١٢٣٤٥٦٧٨٩',p='۰۱۲۳۴۵۶۷۸۹';"
        "return String(s).replace(/[٠-٩]/g,function(d){return a.indexOf(d);})"
        ".replace(/[۰-۹]/g,function(d){return p.indexOf(d);})"
        ".replace('٫','.').replace('٬',',');}"
        "function q(s){return document.querySelector(s);}"
        "function resize(){try{var root=q('.alt-root');"
        "var target=Math.ceil((root?root.offsetHeight:document.body.scrollHeight)+8);"
        "var cur=parseFloat(window.frameElement.style.height)||0;"
        "if(Math.abs(cur-target)>2)window.frameElement.style.height=target+'px';}catch(e){}}"
        "function altsFor(name,T,MAC){var out=[];"
        "for(var i=0;i<CANDS.length;i++){var c=CANDS[i];if(c.n===name)continue;"
        "var qty,carb,calc,w=0;"
        "if(c.q){qty=c.q;carb=c.cc;calc=false;}"
        "else if(c.r>0){w=T/c.r;if(w<15||w>600)continue;"
        "qty='≈ '+fmt(w)+' جم';carb=T;calc=true;}else continue;"
        "out.push({n:c.n,e:c.e||'',c:c.c||'',g:c.g||'',qty:qty,carb:carb,calc:calc,w:w});}"
        "if(!out.length){var L=(FB&&FB[MAC])||[];"
        "for(var j=0;j<L.length;j++){var nm=L[j][0],r=L[j][1];"
        "if(nm===name||!(r>0))continue;var w2=T/r;if(w2<15||w2>600)continue;"
        "out.push({n:nm,e:'',c:'',g:MAC,qty:'≈ '+fmt(w2)+' جم',carb:T,calc:true,w:w2});}}"
        "out.sort(function(a,b){var ca=(a.calc?1:0)-(b.calc?1:0);if(ca)return ca;"
        "var ga=(a.g===MAC?0:1)-(b.g===MAC?0:1);if(ga)return ga;"
        "return Math.abs(a.carb-T)-Math.abs(b.carb-T);});"
        "return {list:out.slice(0,10)};}"
        f"function modalStyle(){{try{{var pd=window.parent.document;if(pd.getElementById('amo-style'))return;"
        f"var s=pd.createElement('style');s.id='amo-style';s.textContent={json.dumps(_ALT_MODAL_CSS)};"
        f"pd.head.appendChild(s);}}catch(e){{}}}}"
        "var __amoEsc=null;"
        "function closeModal(){try{var pd=window.parent.document;var o=pd.getElementById('amo-ov');if(o)o.remove();"
        "if(__amoEsc){pd.removeEventListener('keydown',__amoEsc);__amoEsc=null;}}catch(e){}}"
        "function openModal(card){modalStyle();closeModal();var pd=window.parent.document;"
        "var name=card.getAttribute('data-an')||'';var T=parseFloat(card.getAttribute('data-ac'))||0;"
        "var amt=card.getAttribute('data-am')||'';var ctext=card.getAttribute('data-act')||'';"
        "var MAC=card.getAttribute('data-ag')||'';"
        "var R=altsFor(name,T,MAC);var alts=R.list;"
        "var ov=pd.createElement('div');ov.id='amo-ov';"
        "var sheet=pd.createElement('div');sheet.className='amo-sheet';"
        "var head=pd.createElement('div');head.className='amo-head';"
        "var ttl=pd.createElement('div');ttl.className='amo-title';ttl.textContent=name;"
        "var x=pd.createElement('button');x.className='amo-x';x.type='button';x.textContent='✕';"
        "x.addEventListener('click',closeModal);head.appendChild(ttl);head.appendChild(x);"
        "var meta=pd.createElement('div');meta.className='amo-meta';"
        "function chip(l,v){var c=pd.createElement('div');c.className='amo-chip';"
        "var cl=pd.createElement('span');cl.className='amo-chip-l';cl.textContent=l;"
        "var cv=pd.createElement('span');cv.className='amo-chip-v';cv.textContent=v;"
        "c.appendChild(cl);c.appendChild(cv);return c;}"
        "if(amt)meta.appendChild(chip('الكمية',amt));"
        "meta.appendChild(chip('الكربوهيدرات',ctext));"
        "function toast(msg){try{var t=pd.getElementById('amo-toast');if(t)t.remove();"
        "t=pd.createElement('div');t.id='amo-toast';t.textContent=msg;pd.body.appendChild(t);"
        "setTimeout(function(){try{t.remove();}catch(e){}},1800);}catch(e){}}"
        "function pushCart(item){try{var MK='carbcalc_meal_v1';var cart=[];"
        "try{cart=JSON.parse(window.localStorage.getItem(MK))||[];}catch(e){cart=[];}"
        "cart.push(item);window.localStorage.setItem(MK,JSON.stringify(cart));}catch(e){}}"
        "function addBtn(item,msg){var b=pd.createElement('button');b.className='amo-iadd';b.type='button';"
        "b.textContent='➕ إلى وجبتي';"
        "b.addEventListener('click',function(e){e.stopPropagation();pushCart(item);toast(msg);"
        "b.classList.add('done');b.textContent='✓ أُضيف';"
        "setTimeout(function(){try{b.classList.remove('done');b.textContent='➕ إلى وجبتي';}catch(e){}},1600);});"
        "return b;}"
        "var subB=pd.createElement('div');subB.className='amo-sub';"
        "subB.textContent='المنتج الأساسي';"
        "var baseList=pd.createElement('div');baseList.className='amo-list';"
        "var bit=pd.createElement('div');bit.className='amo-item amo-base';"
        "var bb=pd.createElement('div');bb.className='amo-ibody';"
        "var bn=pd.createElement('div');bn.className='amo-iname';bn.textContent=name;bb.appendChild(bn);"
        "if(amt){var bq=pd.createElement('div');bq.className='amo-iqty';bq.textContent='الكمية: '+amt;bb.appendChild(bq);}"
        "var bc=pd.createElement('div');bc.className='amo-icarb';bc.textContent=ctext;bb.appendChild(bc);"
        "bit.appendChild(bb);"
        "bit.appendChild(addBtn({name:name,qty:amt||'',carbs:T},'✓ تمت إضافة المنتج إلى وجبتي'));"
        "baseList.appendChild(bit);"
        "var sub=pd.createElement('div');sub.className='amo-sub';"
        "sub.textContent='يمكن استبداله بـ (نفس كمية الكربوهيدرات)';"
        "var list=pd.createElement('div');list.className='amo-list';"
        "if(!alts.length){var em=pd.createElement('div');em.className='amo-empty';"
        "em.textContent='لا توجد بدائل مناسبة حالياً.';list.appendChild(em);}"
        "else{for(var i=0;i<alts.length;i++){(function(a){"
        "var it=pd.createElement('div');it.className='amo-item';"
        "var ib=pd.createElement('div');ib.className='amo-ibody';"
        "var nmw=pd.createElement('div');nmw.className='amo-iname';"
        "nmw.textContent=(a.e?a.e+' ':'')+a.n;ib.appendChild(nmw);"
        "if(a.c){var cc=pd.createElement('div');cc.className='amo-icat';cc.textContent=a.c;ib.appendChild(cc);}"
        "var qt=pd.createElement('div');qt.className='amo-iqty';qt.textContent='الكمية: '+a.qty;"
        "ib.appendChild(qt);"
        "var cw=pd.createElement('div');cw.className='amo-icarb';"
        "cw.textContent='≈ '+fmt(a.carb)+' جم كربوهيدرات';ib.appendChild(cw);"
        "it.appendChild(ib);"
        "it.appendChild(addBtn({name:a.n,qty:a.qty,carbs:a.carb},'✓ تمت إضافة البديل إلى وجبتي'));"
        "list.appendChild(it);})(alts[i]);}}"
        "var note=pd.createElement('div');note.className='amo-note';"
        "note.textContent='البدائل مرتبة من الأقرب لكمية الكربوهيدرات، نفس الفئة أولاً ثم بقية الفئات. يمكنك إضافة المنتج الأساسي أو أي بديل إلى «وجبتي» بالضغط على زر الإضافة بجانبه.';"
        "if(!alts.length)note.style.display='none';"
        "var foot=pd.createElement('div');foot.className='amo-foot';"
        "var cb=pd.createElement('button');cb.className='amo-btn amo-close';cb.type='button';cb.textContent='إغلاق';"
        "cb.addEventListener('click',closeModal);"
        "foot.appendChild(cb);"
        "sheet.appendChild(head);sheet.appendChild(meta);sheet.appendChild(subB);sheet.appendChild(baseList);"
        "sheet.appendChild(sub);sheet.appendChild(list);"
        "sheet.appendChild(note);sheet.appendChild(foot);ov.appendChild(sheet);"
        "ov.addEventListener('click',function(e){if(e.target===ov)closeModal();});"
        "pd.body.appendChild(ov);"
        "__amoEsc=function(e){if(e.key==='Escape')closeModal();};pd.addEventListener('keydown',__amoEsc);}"
        "(function(){try{var pd=window.parent.document;var o=pd.getElementById('amo-ov');if(o)o.remove();"
        "var t=pd.getElementById('amo-toast');if(t)t.remove();}catch(e){}})();"
        "document.addEventListener('click',function(e){var card=e.target.closest('.card-alt[data-ac]');"
        "if(card)openModal(card);});"
        "document.addEventListener('keydown',function(e){if(e.key!=='Enter'&&e.key!==' ')return;"
        "var card=e.target.closest('.card-alt[data-ac]');if(!card)return;e.preventDefault();openModal(card);});"
        "if(document.fonts&&document.fonts.ready)document.fonts.ready.then(resize);"
        "setTimeout(resize,60);setTimeout(resize,300);setTimeout(resize,800);"
        "window.addEventListener('load',resize);"
        "</script></body></html>"
    )


def _render_alt_cards_interactive(foods: list, all_grams: list, all_alts: list,
                                  version: int, search: str, cat: str):
    """رسم بطاقات «البدائل» التفاعلية عبر iframe مع تخزين المستند مؤقتاً للسرعة."""
    cache_key = f"_altdoc_{version}_{search}_{cat}"
    if cache_key not in st.session_state:
        cands = _alt_candidates(all_grams, all_alts)
        st.session_state[cache_key] = _build_alt_cards_doc(foods, cands)
    st.iframe(st.session_state[cache_key], height="content")


def _get_card_html_cache(section: str, foods: list, version: int, search: str, cat: str) -> list[str]:
    """إعادة HTML المُخزَّن للبطاقات، أو بناؤه إذا تغيّرت البيانات/البحث/الفئة."""
    cache_key = f"_html_{section}_{version}_{search}_{cat}"
    if cache_key not in st.session_state:
        builder = _build_gram_card_html if section == "gram" else _build_alt_card_html
        st.session_state[cache_key] = [builder(f) for f in foods]
    return st.session_state[cache_key]

# ══════════════════════════════════════════════════════════════════════════════
# إعداد الصفحة
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="كارب الأطعمة",
    page_icon="🥗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Preconnect لـ Google Fonts لتسريع تحميل الخط
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

st.markdown("""
<style>
*, html, body, [class*="css"] {
    font-family: 'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif !important;
}
/* لا تمرير تلقائي: نمنع التمرير المتحرك (يبدو وكأن الصفحة معلّقة) ونعطّل
   تثبيت التمرير في المتصفح حتى لا تقفز الصفحة عند تغيّر ارتفاع المحتوى
   بعد البحث/الفلترة/فتح البطاقات. الصفحة لا تتحرك إلا بتمرير المستخدم. */
html { scroll-behavior: auto; overflow-anchor: none; }
*, body, .stApp, .main, [data-testid="stAppViewContainer"],
.block-container, section.main { overflow-anchor: none; }
.stApp { direction: rtl; background: #EEF2F7; }
h1,h2,h3,h4,h5,h6,p,label,span,div { direction: rtl; text-align: right; }

#MainMenu, header[data-testid="stHeader"], .stDeployButton { display: none !important; }

.block-container {
    padding-top: 3.7rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 880px !important;
}

/* ═══ الشريط العلوي الثابت ═══ */
.topbar {
    position: fixed; top: 0; right: 0; left: 0;
    height: 56px; z-index: 999;
    background: #ffffff;
    box-shadow: 0 2px 10px rgba(20,40,90,0.06);
    display: flex; align-items: center; justify-content: flex-start;
    padding: 0 128px 0 18px;
}
.topbar-title { font-size: 1.12rem; font-weight: 900; color: #3e6e7e; }
.topbar-logo {
    display: inline-flex; align-items: center; justify-content: center;
    width: 38px; height: 38px; margin-right: 8px;
}
.topbar-logo img { width: 100%; height: 100%; object-fit: contain; }

/* إخفاء القائمة الجانبية الأصلية (تتعارض مع RTL) واستبدالها بقائمة مخصصة */
section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }

/* ═══ زر القائمة أعلى اليمين (الموقع الطبيعي للمستخدم العربي) ═══ */
.nav-burger {
    position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
    height: 40px; border-radius: 11px; padding: 0 13px;
    background: #3e6e7e; color: #ffffff !important;
    display: flex; align-items: center; justify-content: center; gap: 8px;
    line-height: 1; text-decoration: none;
    box-shadow: 0 2px 8px rgba(62,110,126,0.25);
}
.nav-burger .nb-ico { font-size: 1.25rem; }
.nav-burger .nb-lbl { font-size: 0.92rem; font-weight: 800; }
.nav-burger:hover { background: #2f5965; }

/* ═══ الدُرج الجانبي (CSS فقط عبر :target) ═══ */
.nav-drawer {
    position: fixed; top: 0; right: -320px; width: 282px; height: 100%;
    background: #ffffff; z-index: 1002; padding: 18px 16px;
    box-shadow: -6px 0 28px rgba(15,23,42,0.18);
    transition: right 0.28s ease; overflow-y: auto;
}
#menu:target { right: 0; }
.nav-overlay {
    position: fixed; inset: 0; background: rgba(15,23,42,0.42);
    opacity: 0; visibility: hidden; transition: 0.28s; z-index: 1001;
    text-decoration: none;
}
#menu:target ~ .nav-overlay { opacity: 1; visibility: visible; }
.nav-link {
    display: block; text-decoration: none;
    padding: 12px 14px; margin-bottom: 8px;
    border-radius: 12px; font-weight: 700; font-size: 0.98rem;
    color: #334155 !important; background: #f7f9fc; border: 1px solid #eef2f7;
}
.nav-link:hover { background: #e3eef1; color: #3e6e7e !important; }

.anchor { position: relative; visibility: hidden; height: 0; scroll-margin-top: 72px; }

/* لوح القسم */
.sec-head {
    display: flex; align-items: center; gap: 8px;
    margin: 22px 2px 12px;
}
.sec-head .ico { font-size: 1.15rem; }
.sec-head .txt { font-size: 1.05rem; font-weight: 900; color: #3e6e7e; }
.sec-desc {
    margin: 2px 2px 14px; color: #5b6b72; font-size: 0.95rem;
    line-height: 1.7; font-weight: 600; max-width: 660px;
}
/* أيقونة ⓘ بجانب اسم القسم */
.sec-info {
    display: inline-flex; align-items: center; justify-content: center;
    width: 19px; height: 19px; border-radius: 50%; flex: 0 0 auto;
    border: 1.5px solid #3e6e7e; color: #3e6e7e;
    font-family: Georgia, 'Times New Roman', serif;
    font-style: italic; font-weight: 700; font-size: 0.72rem; line-height: 1;
    text-decoration: none; margin-inline-start: 2px;
    transition: background 0.15s, color 0.15s;
}
.sec-info::before { content: 'i'; }
.sec-info:hover { background: #3e6e7e; color: #ffffff; }
/* نافذة المعلومات (Modal) — CSS فقط عبر :target */
.info-modal {
    position: fixed; inset: 0; z-index: 1400;
    display: flex; align-items: center; justify-content: center;
    padding: 22px; background: rgba(15,23,42,0.45);
    opacity: 0; visibility: hidden; transition: opacity 0.2s ease;
}
.info-modal:target { opacity: 1; visibility: visible; }
.info-backdrop { position: absolute; inset: 0; }
.info-box {
    position: relative; z-index: 1; background: #ffffff;
    width: 100%; max-width: 460px; max-height: 84vh; overflow-y: auto;
    border-radius: 16px;
    border: 1px solid #e6ebf5; box-shadow: 0 12px 40px rgba(15,23,42,0.25);
    padding: 20px 20px 22px; direction: rtl; text-align: right;
}
.info-box .info-title {
    display: flex; align-items: center; gap: 8px;
    color: #3e6e7e; font-weight: 900; font-size: 1rem; margin-bottom: 8px;
    position: sticky; top: -20px; background: #ffffff;
    padding-top: 4px; padding-bottom: 6px; z-index: 2;
}
.info-box p {
    margin: 0; color: #5b6b72; font-size: 0.95rem;
    line-height: 1.8; font-weight: 600;
}
.info-box .info-desc { margin-bottom: 4px; }
.info-box img { max-width: 100%; height: auto; }
/* عنوان فرعي داخل النافذة (يفصل شرح ICR عن ISF) */
.info-box .info-sub {
    color: #3e6e7e; font-weight: 900; font-size: 1rem;
    margin: 18px 0 8px; padding-top: 14px; border-top: 1px solid #eef2f7;
}
/* بطاقات الأمثلة داخل النافذة (بديل عن st.expander) */
.info-box .ex-case {
    margin-top: 16px; padding-top: 14px; border-top: 1px solid #eef2f7;
}
.info-box .ex-case-title {
    color: #3e6e7e; font-weight: 800; font-size: 0.95rem; margin-bottom: 10px;
}
.info-box .ex-row { flex-direction: column; gap: 12px; }
.info-close {
    position: absolute; top: 8px; left: 12px;
    color: #94a3b8; font-size: 1.5rem; line-height: 1;
    text-decoration: none; font-weight: 700; z-index: 3;
}
.info-close:hover { color: #3e6e7e; }
.howto { margin: 0 2px 20px; }
.howto-title {
    font-size: 0.9rem; font-weight: 800; color: #3e6e7e; margin-bottom: 10px;
}
.howto-steps {
    display: block; width: 100%; max-width: 820px; height: auto;
    border-radius: 12px; margin-top: 2px;
}
.howto-eq {
    margin-top: 12px; max-width: 820px; padding: 11px 16px;
    background: #eef5f1; border: 1px solid #dcebe2; border-radius: 10px;
    color: #4f7340; font-weight: 800; font-size: 0.95rem;
    line-height: 1.7; text-align: center;
}
.eq-card {
    margin: 4px 2px 22px; max-width: 820px; padding: 22px 22px;
    background: linear-gradient(135deg, #eaf4fb 0%, #f4fafd 100%);
    border: 1.5px solid #bcdcef; border-radius: 16px;
    box-shadow: 0 2px 12px rgba(62,110,126,0.08); text-align: center;
}
.eq-card .eq-badge {
    display: inline-block; margin-bottom: 14px; padding: 4px 14px;
    background: #fff; border: 1px solid #cfe6f2; border-radius: 999px;
    color: #3e6e7e; font-size: 0.85rem; font-weight: 800;
}
.eq-card .eq-line {
    display: flex; flex-wrap: wrap; align-items: center;
    justify-content: center; gap: 10px 14px; line-height: 1.5;
}
.eq-card .eq-term {
    font-size: 1.1rem; font-weight: 800; color: #2b4d59;
}
.eq-card .eq-op {
    font-size: 1.75rem; font-weight: 900; color: #d98324; line-height: 1;
}
.eq-card .eq-total {
    font-size: 1.15rem; font-weight: 900; color: #3e6e7e;
    background: #fff; padding: 5px 16px; border-radius: 999px;
    border: 1px solid #cfe6f2;
}
.lab-usage { margin: 2px 2px 6px; }
.lab-usage .u-step {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 13px; margin-bottom: 8px;
    background: #f4f8fa; border: 1px solid #e3eef2; border-radius: 10px;
    font-size: 0.95rem; color: #2b3a40; font-weight: 700;
}
.lab-usage .u-ico { font-size: 1.05rem; }
.case-block { margin-top: 26px; padding-top: 20px; border-top: 2px solid #e3eef2; }
.case-head {
    display: flex; align-items: center; gap: 10px;
    flex-wrap: wrap; margin-bottom: 8px;
}
.case-num {
    background: #3e6e7e; color: #fff; font-weight: 800; font-size: 0.82rem;
    padding: 4px 13px; border-radius: 999px; white-space: nowrap;
}
.case-name { font-size: 1.05rem; font-weight: 800; color: #3e6e7e; }
.case-img {
    display: block; width: 100%; max-width: 460px; height: auto;
    margin: 12px auto 6px; border-radius: 14px; border: 1px solid #e6ebf0;
}

.panel {
    background: #F7F9FC; border: 1px solid #e6ebf5; border-radius: 18px;
    padding: 14px; box-shadow: 0 2px 10px rgba(20,40,90,0.05);
}

/* ─── بحث ─── */
.stTextInput > div > div > input {
    direction: rtl !important; text-align: right !important;
    font-size: 1rem !important; border-radius: 14px !important;
    border: 1.5px solid #cddfe2 !important; padding: 12px 18px !important;
    background: #ffffff !important; box-shadow: 0 1px 5px rgba(62,110,126,0.05) !important;
}
.stTextInput > div > div > input:focus {
    border-color: #3e6e7e !important; box-shadow: 0 2px 12px rgba(62,110,126,0.14) !important;
}
.stTextInput > div { border: none !important; box-shadow: none !important; }
div[data-testid="InputInstructions"] { display: none !important; }

.search-summary {
    background: #e3eef1; border-right: 4px solid #3e6e7e; border-radius: 10px;
    padding: 9px 16px; margin-top: 12px; font-size: 0.85rem; font-weight: 700;
    color: #3e6e7e; direction: rtl; display: flex; gap: 16px; flex-wrap: wrap; align-items: center;
}

/* ═══ شريط الفئات القابل للتمرير أفقياً (أسفل البحث مباشرة) ═══ */
.st-key-cat_filter div[role="radiogroup"] {
    flex-wrap: nowrap !important;
    overflow-x: auto;
    gap: 8px;
    padding: 2px 2px 8px;
    margin-top: 10px;
    -webkit-overflow-scrolling: touch;
}
.st-key-cat_filter div[role="radiogroup"]::-webkit-scrollbar { height: 6px; }
.st-key-cat_filter div[role="radiogroup"]::-webkit-scrollbar-track { background: transparent; }
.st-key-cat_filter div[role="radiogroup"]::-webkit-scrollbar-thumb {
    background: #cddfe2; border-radius: 999px;
}
.st-key-cat_filter label {
    flex: 0 0 auto !important;
    margin: 0 !important;
    background: #ffffff;
    border: 1.5px solid #d6e3e6;
    border-radius: 999px;
    padding: 6px 15px;
    cursor: pointer;
    transition: background .15s ease, border-color .15s ease, color .15s ease;
    white-space: nowrap;
}
.st-key-cat_filter label > div:first-child { display: none !important; }
.st-key-cat_filter label p {
    font-size: 0.9rem !important; font-weight: 700 !important;
    color: #3e6e7e !important; margin: 0 !important; white-space: nowrap;
}
.st-key-cat_filter label:hover { border-color: #3e6e7e; }
.st-key-cat_filter label:has(input:checked) {
    background: #3e6e7e; border-color: #3e6e7e;
}
.st-key-cat_filter label:has(input:checked) p { color: #ffffff !important; }

/* ═══ بطاقة الجرام ═══ */
.card-gram {
    background: #ffffff; border: 1px solid #e6ebf5; border-radius: 14px;
    padding: 13px 16px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(20,40,90,0.05);
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
}
.cg-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.cg-left { display: flex; align-items: center; gap: 11px; min-width: 0; }
.cg-emoji {
    font-size: 1.35rem; line-height: 1; width: 42px; height: 42px; flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    background: #ecf4f5; border: 1px solid #e6ebf5; border-radius: 12px;
}
.cg-name { font-size: 0.98rem; font-weight: 800; color: #23434c; line-height: 1.3;
    overflow: hidden; text-overflow: ellipsis; }
.cg-cat { font-size: 0.78rem; font-weight: 700; color: #6f8893; line-height: 1.2; }
.cg-badge {
    background: #e3eef1; color: #3e6e7e; font-weight: 900; font-size: 1rem;
    border-radius: 10px; padding: 6px 13px; white-space: nowrap; flex-shrink: 0;
}

/* ═══ بطاقة البدائل ═══ */
.card-alt {
    background: #ffffff; border: 1px solid #e6efe0; border-radius: 14px;
    padding: 13px 16px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(27,94,32,0.05);
}
.ca-head { display: flex; align-items: center; gap: 11px; }
.ca-emoji {
    font-size: 1.35rem; line-height: 1; width: 42px; height: 42px; flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    background: #f1f6ec; border: 1px solid #e6efe0; border-radius: 12px;
}
.ca-name { font-size: 0.98rem; font-weight: 800; color: #2b3f25; }
.ca-cat { font-size: 0.78rem; font-weight: 700; color: #74866a; margin-bottom: 10px; margin-top: 2px; }
.ca-body { display: flex; gap: 10px; flex-wrap: wrap; }
.ca-pill {
    display: flex; flex-direction: column; align-items: center;
    background: #f4f8ee; border: 1px solid #e6efe0; border-radius: 11px;
    padding: 7px 14px; flex: 1; min-width: 90px;
}
.ca-pill-label { font-size: 0.7rem; color: #8a957f; margin-bottom: 3px; }
.ca-pill-value { font-size: 0.98rem; font-weight: 800; color: #4f7340; }

/* ═══ نماذج (Forms) ═══ */
div[data-testid="stForm"] {
    background: #F7F9FC; border: 1px solid #e6ebf5 !important; border-radius: 18px;
    padding: 16px !important; box-shadow: 0 2px 10px rgba(20,40,90,0.05);
}
div[data-testid="stForm"] button[kind="secondaryFormSubmit"],
div[data-testid="stForm"] button {
    background: #3e6e7e !important; color: #ffffff !important;
    border: none !important; border-radius: 12px !important;
    font-weight: 800 !important; padding: 9px 26px !important;
}

/* ═══ قسم البحث بالذكاء الاصطناعي (بنفس هوية خانة البحث عن الطعام) ═══ */
.ai-note{background:#eaf3f4;border:1px solid #cfe2e5;border-radius:14px;padding:15px 18px;
  color:#3e6e7e;font-weight:700;font-size:0.95rem;line-height:1.7;direction:rtl;text-align:right;
  margin:6px 2px 20px;}
/* صندوق الإدخال — يطابق تماماً خانة البحث عن الطعام (عرض/حواف/ألوان/ظل) */
.st-key-ai_box{background:#fff;border:1.5px solid #cddfe2;border-radius:14px;padding:5px 8px;
  box-shadow:0 1px 5px rgba(62,110,126,0.05);margin:2px 0 8px;}
.st-key-ai_box:focus-within{border-color:#3e6e7e;box-shadow:0 2px 12px rgba(62,110,126,0.14);}
.st-key-ai_box [data-testid="stVerticalBlock"]{gap:0.45rem !important;}
.st-key-ai_box [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:8px !important;
  align-items:center;justify-content:space-between !important;}
.st-key-ai_box [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]{min-width:0 !important;
  flex:0 0 auto !important;width:auto !important;}
/* عمود حقل النص يتمدد ليملأ السطر (الأزرار تبقى بعرضها الطبيعي) */
.st-key-ai_box [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(.stTextInput){
  flex:1 1 auto !important;}
/* حقل النص يندمج داخل الصندوق (بلا حدود أو ظل خاص به) ويتقلّص بحرية */
.st-key-ai_box .stTextInput,
.st-key-ai_box [data-baseweb="input"],
.st-key-ai_box [data-baseweb="base-input"]{min-width:0 !important;width:100% !important;}
.st-key-ai_box .stTextInput > div > div > input{border:none !important;box-shadow:none !important;
  background:transparent !important;padding:10px 10px !important;font-size:1rem !important;
  min-width:0 !important;direction:rtl !important;text-align:right !important;}
.st-key-ai_box .stTextInput > div > div > input:focus{border:none !important;box-shadow:none !important;}
.st-key-ai_box .stTextInput > div{border:none !important;box-shadow:none !important;}
/* زر الكاميرا داخل صندوق البحث نفسه — أيقونة 📷 عبر file_uploader تفتح نافذة النظام الأصلية
   (كاميرا/معرض/ملفات) مباشرة، بلا بطاقة أو قائمة منفصلة */
.st-key-ai_cam_row [data-testid="stFileUploader"]{margin:0 !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"]{background:transparent !important;
  border:none !important;padding:0 !important;min-height:0 !important;display:block !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzoneInstructions"],
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] svg,
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] small{display:none !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"]::before{content:"" !important;display:none !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] button{width:44px !important;
  min-width:44px !important;height:44px !important;justify-content:center !important;
  background:transparent !important;color:#3e6e7e !important;
  border:none !important;border-radius:12px !important;
  font-size:0 !important;padding:0 !important;box-shadow:none !important;
  display:flex !important;align-items:center !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] button > *{display:none !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] button:hover{background:#f3f8f9 !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderDropzone"] button::before{content:"📷";
  font-size:1.35rem !important;line-height:1 !important;}
.st-key-ai_cam_row [data-testid="stFileUploaderFile"],
.st-key-ai_cam_row [data-testid="stFileUploaderFileData"],
.st-key-ai_cam_row [data-testid="stFileUploaderDeleteBtn"]{display:none !important;}
/* زر الإرسال — بلون العلامة التجارية كأيقونة بحث */
.st-key-ai_box .stButton button{width:44px !important;min-width:44px !important;height:44px !important;
  background:#3e6e7e !important;color:#fff !important;
  border:1.5px solid #3e6e7e !important;border-radius:12px !important;font-size:1.25rem !important;
  font-weight:800 !important;padding:0 !important;box-shadow:0 3px 10px rgba(62,110,126,0.22);
  display:flex !important;align-items:center !important;justify-content:center !important;}
.st-key-ai_box .stButton button:hover{background:#2f5965 !important;border-color:#2f5965 !important;}
.ai-attached{color:#4f7340;font-weight:800;font-size:0.9rem;direction:rtl;text-align:right;margin:2px 4px 6px;}
/* مؤشر التحميل الأنيق */
.ai-loading{background:linear-gradient(135deg,#eaf4fb 0%,#f4fafd 100%);border:1.5px solid #bcdcef;
  border-radius:16px;padding:16px 20px;color:#2b4d59;font-weight:800;font-size:1rem;direction:rtl;
  text-align:right;margin:10px 2px 6px;display:flex;align-items:center;gap:10px;}
.ai-load-ico{display:inline-block;animation:aiPulse 1.1s ease-in-out infinite;font-size:1.3rem;}
@keyframes aiPulse{0%,100%{opacity:.4;transform:scale(.9);}50%{opacity:1;transform:scale(1.15);}}
/* بطاقة الإجابة — بنفس تصميم بطاقات الموقع */
.st-key-ai_answer{background:#fff;border:1px solid #e6ebf5;border-radius:16px;padding:16px 20px 12px;
  box-shadow:0 2px 10px rgba(20,40,90,0.05);margin:12px 0 6px;animation:aiFade .35s ease;}
@keyframes aiFade{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
.st-key-ai_answer [data-testid="stMarkdownContainer"]{direction:rtl;text-align:right;}
.st-key-ai_answer [data-testid="stMarkdownContainer"] p,
.st-key-ai_answer [data-testid="stMarkdownContainer"] li{font-size:1rem;line-height:1.95;color:#2b3a40;}
.st-key-ai_answer [data-testid="stMarkdownContainer"] h1,
.st-key-ai_answer [data-testid="stMarkdownContainer"] h2,
.st-key-ai_answer [data-testid="stMarkdownContainer"] h3,
.st-key-ai_answer [data-testid="stMarkdownContainer"] strong{color:#3e6e7e;}
.ai-thumb-wrap{direction:rtl;text-align:right;margin:0 0 12px;}
.ai-thumb{max-width:170px;max-height:170px;border-radius:14px;border:1.5px solid #cddfe2;
  object-fit:cover;box-shadow:0 3px 10px rgba(20,50,60,0.10);}
.st-key-ai_newq button{width:100% !important;background:#fff !important;color:#3e6e7e !important;
  border:1.5px solid #cddfe2 !important;border-radius:12px !important;font-weight:800 !important;
  padding:9px !important;margin-top:2px;}
.st-key-ai_newq button:hover{background:#eaf3f4 !important;border-color:#3e6e7e !important;}
[data-testid="stFileUploaderDropzoneInstructions"]{display:none !important;}

/* ═══ نتيجة حساب الملصق الغذائي ═══ */
.lab-result {
    border-radius: 16px; padding: 16px 18px; margin-top: 14px;
    border: 1px solid #cfe2e5; background: #eaf3f4; text-align: center;
}
.lab-final { font-size: 0.95rem; color: #5c7682; font-weight: 700; margin-bottom: 6px; }
.lab-final-val { font-size: 2rem; font-weight: 900; color: #3e6e7e; white-space: nowrap; }
.lab-final-val span { font-size: 1rem; font-weight: 700; color: #5c7682; }

/* ═══ أمثلة وتوضيحات الملصق الغذائي ═══ */
.examples-head {
    display: flex; align-items: center; gap: 9px;
    margin: 30px 0 4px; font-size: 1.12rem; font-weight: 900; color: #3e6e7e;
}
.examples-head .ico { font-size: 1.2rem; }

/* بطاقات الأمثلة (st.expander) — نفس هوية صندوق النصائح (.tip-card) */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e6ebf5 !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(20,40,90,0.05) !important;
    margin-bottom: 10px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] details {
    border: none !important; background: transparent !important;
    box-shadow: none !important; border-radius: 14px !important;
}
[data-testid="stExpander"] summary {
    display: flex !important; align-items: center !important;
    direction: rtl !important; text-align: right !important;
    padding: 13px 16px !important; cursor: pointer; list-style: none;
    font-size: 0.98rem !important; font-weight: 800 !important; color: #3e6e7e !important;
    transition: background .2s ease;
}
[data-testid="stExpander"] summary:hover { background: #f4f8fa !important; }
[data-testid="stExpander"] summary::-webkit-details-marker { display: none; }
/* إخفاء أيقونة Streamlit المعطوبة (نص keyboard_arrow_*) واستبدالها بسهم نظيف */
[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] summary [data-testid="stIconMaterial"],
[data-testid="stExpander"] summary span.material-symbols-rounded,
[data-testid="stExpander"] summary i.material-icons { display: none !important; }
[data-testid="stExpander"] summary::after {
    content: ""; width: 9px; height: 9px; margin-inline-start: auto; flex: 0 0 auto;
    border-right: 2.5px solid #3e6e7e; border-bottom: 2.5px solid #3e6e7e;
    transform: rotate(45deg); transition: transform .25s ease;
}
[data-testid="stExpander"] details[open] > summary::after,
[data-testid="stExpander"][open] summary::after { transform: rotate(-135deg); }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 2px 16px 14px !important; animation: exFade .25s ease;
}
@keyframes exFade {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: none; }
}

.ex-row {
    display: flex; gap: 18px; align-items: center; flex-wrap: wrap;
    justify-content: space-between;
}
.ex-text {
    flex: 1 1 240px; min-width: 210px;
    font-size: 0.95rem; color: #2b3a40; line-height: 2; font-weight: 600;
    text-align: right;
}
.ex-text b { color: #3e6e7e; }
.ex-text .howto-eq { margin: 10px 0; }
.ex-img { flex: 0 0 auto; margin: 4px auto; width: 200px; }
/* صورة المنتج الحقيقية + بطاقة معلومات الحالة (بألوان الموقع) */
.ex-photo {
    display: block; width: 100%; height: 165px; object-fit: contain;
    background: #fff; border: 1.5px solid #cddfe2; border-radius: 12px;
    padding: 10px; box-shadow: 0 2px 10px rgba(62,110,126,0.10);
}
.ex-cap {
    margin-top: 10px; background: #fff; border: 1.5px solid #cddfe2;
    border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(62,110,126,0.10);
}
.ex-cap-row {
    display: flex; justify-content: space-between; align-items: center; gap: 10px;
    padding: 7px 12px; border-top: 1px solid #eef3f5; direction: rtl; text-align: right;
    color: #3a4a52; font-weight: 700; font-size: 0.82rem;
}
.ex-cap-row:first-child { border-top: none; }
.ex-cap-row .ex-cap-v { font-weight: 800; white-space: nowrap; color: #3e6e7e; }

/* ═══ حساب جرعة الإنسولين ═══ */
.ins-example {
    margin: 4px 2px 14px; max-width: 660px; padding: 11px 16px;
    background: #eef4f7; border: 1px solid #d7e6ea; border-right: 4px solid #3e6e7e;
    border-radius: 10px; color: #2b3a40; font-size: 0.92rem; line-height: 1.8; font-weight: 600;
}
.ins-example b { color: #3e6e7e; }
.ins-adjust {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 11px 14px; margin-bottom: 10px; max-width: 660px;
    background: #f4f8fa; border: 1px solid #e3eef2; border-radius: 12px;
    font-size: 0.92rem; color: #2b3a40; font-weight: 600; line-height: 1.8;
}
.ins-adjust .ia-ico { font-size: 1.2rem; line-height: 1.5; }
.ins-adjust b { color: #3e6e7e; }
.ins-hint {
    text-align: center; color: #5c7682; font-size: 0.85rem; font-weight: 700;
    margin: 12px 0 2px;
}

/* ═══ معلومات ونصائح ═══ */
.tip-card {
    background: #ffffff; border: 1px solid #e6ebf5; border-radius: 14px;
    padding: 12px 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(20,40,90,0.05);
    display: flex; gap: 10px; align-items: flex-start;
}
.tip-ico { font-size: 1.1rem; flex-shrink: 0; }
.tip-txt { font-size: 0.92rem; color: #334155; line-height: 1.6; font-weight: 600; }

/* محتوى بطاقات النصائح القابلة للفتح (داخل st.expander) */
.tip-sub {
    color: #3e6e7e; font-weight: 800; font-size: 1.08rem;
    margin: 14px 0 5px; line-height: 1.6;
    direction: rtl; text-align: right;
}
.tip-sub:first-child { margin-top: 2px; }
.tip-sub2 {
    color: #4f7340; font-weight: 800; font-size: 1rem;
    margin: 11px 0 4px; line-height: 1.6;
    direction: rtl; text-align: right;
}
.tip-p {
    color: #2b3a40; font-size: 0.94rem; font-weight: 600; line-height: 1.8;
    margin: 0 0 4px; direction: rtl; text-align: right;
    overflow-wrap: break-word; word-break: normal;
}
.tip-list {
    margin: 2px 0 8px !important; padding: 0 !important;
    padding-inline-start: 0 !important; list-style: none !important;
    direction: rtl !important; text-align: right !important;
}
.tip-list li {
    padding: 0 !important; padding-inline-start: 0 !important;
    margin: 0 0 4px !important; list-style: none !important;
    direction: rtl !important; text-align: right !important;
    color: #2b3a40; font-size: 0.94rem; font-weight: 600; line-height: 1.8;
    overflow-wrap: break-word; word-break: normal;
}
.tip-list li::marker { content: "" !important; }
.tip-note {
    margin: 12px 0 4px; padding: 11px 13px; border-radius: 10px;
    background: #eaf4fb; border: 1px solid #bcdcef;
    color: #2b3a40; font-size: 0.9rem; font-weight: 700; line-height: 1.85;
    direction: rtl; text-align: right; overflow-wrap: break-word; word-break: normal;
}
.tip-note b { color: #3e6e7e; }
.tip-figwrap { margin: 8px 0 12px; }
.tip-figure { display: block; width: 100%; max-width: 270px; height: auto; margin: 4px 0 6px auto; }
.tip-figcap {
    display: flex; flex-wrap: wrap; direction: rtl; justify-content: flex-start;
    gap: 6px 16px; margin-top: 2px;
}
.tip-figcap .fc {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.85rem; font-weight: 700; color: #2b3a40;
}
.tip-figcap .fc b {
    display: inline-flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; border-radius: 50%;
    background: #3e6e7e; color: #fff; font-size: 0.78rem;
}
.tip-check {
    margin: 12px 0 4px; padding: 11px 13px; border-radius: 10px;
    background: #eef6ee; border: 1px solid #cfe3c9;
    color: #2b3a40; font-size: 0.9rem; font-weight: 700; line-height: 1.85;
    direction: rtl; text-align: right; overflow-wrap: break-word; word-break: normal;
}
.plate-legend {
    display: flex; flex-wrap: wrap; direction: rtl; justify-content: flex-start;
    gap: 6px 16px; margin-top: 2px;
}
.plate-legend .pl {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.85rem; font-weight: 700; color: #2b3a40;
}
.plate-legend .pl i { width: 14px; height: 14px; border-radius: 4px; display: inline-block; }
.pl-v { background: #4f7340; }
.pl-p { background: #d98324; }
.pl-c { background: #e6b53c; }

/* تذييل اعتماد المحتوى (Footer) */
.site-footer {
    border-top: 1px solid #e6ebf5;
    margin-top: 14px; padding: 16px 10px 4px;
    direction: rtl; text-align: right;
}
.sf-logo { margin-bottom: 10px; }
.sf-logo img { height: 46px; width: auto; }
.sf-org { color: #334155; font-size: 0.9rem; font-weight: 700; line-height: 2; }
.sf-block { margin-top: 12px; }
.sf-role { color: #3e6e7e; font-size: 0.85rem; font-weight: 700; }
.sf-name { color: #334155; font-size: 0.9rem; font-weight: 600; line-height: 1.9; }

.foot-note {
    text-align: center; color: #94a3b8; font-size: 0.8rem;
    margin: 28px 0 6px; line-height: 1.7;
}
.empty-msg { text-align: center; color: #b8c0cf; padding: 26px 0; font-size: 0.92rem; }

@media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        width: 100% !important; min-width: 100% !important; flex: 0 0 100% !important;
    }
    .block-container { padding: 3.7rem 0.75rem 1rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ─── الشريط العلوي + القائمة الجانبية المخصصة (CSS فقط) ─────────────────────────
st.markdown(f"""
<div class="topbar">
  <a href="#menu" class="nav-burger"><span class="nb-ico">☰</span><span class="nb-lbl">القائمة</span></a>
  <span class="topbar-title">كارب الأطعمة</span>
  <span class="topbar-logo"><img src="{LOGO_MARK}" alt="كارب الأطعمة"></span>
</div>
<div id="menu" class="nav-drawer">
  <a class="nav-link" href="#search">البحث عن الأطعمة</a>
  <a class="nav-link" href="#ai-search">البحث بالذكاء الاصطناعي</a>
  <a class="nav-link" href="#alternatives">البدائل الغذائية</a>
  <a class="nav-link" href="#per-gram">الكربوهيدرات لكل جرام</a>
  <a class="nav-link" href="#label-calc">الملصق الغذائي</a>
  <a class="nav-link" href="#insulin-calc">حساب جرعة الإنسولين</a>
  <a class="nav-link" href="#tips">معلومات ونصائح</a>
  <div class="site-footer">{SITE_FOOTER_HTML}</div>
</div>
<a href="#" class="nav-overlay"></a>
{INFO_MODALS_HTML}
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# جلب البيانات (فوري من الذاكرة)
# ══════════════════════════════════════════════════════════════════════════════
GRAMS_FOODS, ALT_FOODS, DATA_VERSION = get_manager().get()
total_all = len(GRAMS_FOODS) + len(ALT_FOODS)

# ─── خيارات شريط الفئات: تُبنى من الأصناف الموجودة فعلاً، بالترتيب المعرّف ───
# القواعد الثابتة أولاً، ثم أي فئة جديدة قادمة من عمود الفئة في الجدول (مفاتيح
# «sheet:…») تظهر تلقائياً كشريحة دون أي تعديل في الكود.
_ALL_CATS = _CATEGORY_RULES + [("other", "🍽️", "أخرى", [])]
_known_keys = {k for (k, _e, _lab, _kw) in _ALL_CATS}
_present_cats = {f.get("_cat") for f in GRAMS_FOODS} | {f.get("_cat") for f in ALT_FOODS}
# تسميات الفئات الديناميكية القادمة من الجدول (تُؤخذ كما كتبها المستخدم)
_sheet_cat_labels: dict = {}
for _f in GRAMS_FOODS + ALT_FOODS:
    _k = _f.get("_cat")
    if _k and _k not in _known_keys and _k not in _sheet_cat_labels:
        _sheet_cat_labels[_k] = _f.get("cat_label", _k)
_chip_defs = [(k, e, lab) for (k, e, lab, _kw) in _ALL_CATS if k in _present_cats]
_chip_defs += [(k, "🏷️", _sheet_cat_labels[k]) for k in sorted(_sheet_cat_labels)]
CAT_OPTIONS = ["الكل"] + [f"{e} {lab}" for (k, e, lab) in _chip_defs]
CHIP_TO_KEY = {f"{e} {lab}": k for (k, e, lab) in _chip_defs}
CHIP_TO_KEY["الكل"] = None


# ─── دوال رسم البطاقات ────────────────────────────────────────────────────────
def _render_card_grid(cards: list):
    for i in range(0, len(cards), 2):
        cols = st.columns(2, gap="small")
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(cards):
                break
            with col:
                st.markdown(cards[idx], unsafe_allow_html=True)


def render_cards(section: str, foods: list, version: int, search: str, cat: str):
    """رسم بطاقات الأطعمة في شبكة مسطّحة (دون تجميع حسب الفئة)."""
    html_list = _get_card_html_cache(section, foods, version, search, cat)
    _render_card_grid(html_list)


# ══════════════════════════════════════════════════════════════════════════════
# قسم البحث عن الأطعمة
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div id='search' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>البحث عن الأطعمة</span></div>",
    unsafe_allow_html=True,
)

global_search = st.text_input(
    label="بحث", placeholder="ابحث عن طعام…",
    label_visibility="collapsed", key="gs",
)

# ─── شريط الفئات (أسفل البحث مباشرة) — يفلتر القسمين معاً ويبقى ثابتاً بينهما ───
if st.session_state.get("cat_filter") not in CAT_OPTIONS:
    st.session_state["cat_filter"] = "الكل"
cat_chip = st.radio(
    "الفئات", CAT_OPTIONS, horizontal=True,
    key="cat_filter", label_visibility="collapsed",
)
cat_key = CHIP_TO_KEY.get(cat_chip)

if global_search:
    # كاش نتائج البحث مشفر بـ (version + مصطلح البحث) — يُبطل عند أي تحديث للبيانات
    search_key = f"_search_{DATA_VERSION}_{global_search}"
    if search_key not in st.session_state:
        q = _normalize(_to_western(global_search))
        st.session_state[search_key] = (
            [f for f in GRAMS_FOODS if _matches(q, f)],
            [f for f in ALT_FOODS   if _matches(q, f)],
        )
    fg, fa = st.session_state[search_key]
else:
    fg = GRAMS_FOODS
    fa = ALT_FOODS

# تطبيق فلتر الفئة المختارة على القسمين معاً (يبقى ثابتاً بين «لكل جرام» و«البدائل»)
if cat_key:
    fg = [f for f in fg if f.get("_cat") == cat_key]
    fa = [f for f in fa if f.get("_cat") == cat_key]

if global_search:
    st.markdown(f"""
<div class='search-summary'>
    <span>🔎 «{html.escape(_to_western(global_search))}»</span>
    <span>⚖️ الجرام: {len(fg)}</span>
    <span>🔄 البدائل: {len(fa)}</span>
    <span>الإجمالي: {len(fg)+len(fa)}</span>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# قسم البحث بالذكاء الاصطناعي (معزول تماماً: أي خطأ فيه لا يؤثر على بقية الموقع)
# ══════════════════════════════════════════════════════════════════════════════
# ── Feature Flag: تفعيل/تعطيل ميزة البحث بالذكاء الاصطناعي ──
# غيّر القيمة إلى True لإعادة تفعيل الميزة بالكامل (لا حاجة لأي تعديل آخر).
# عند False: تبقى البطاقة ظاهرة بنفس التصميم لكن الحقول والأزرار معطلة،
# وتظهر رسالة «هذه الميزة غير مفعلة حاليًا». لا يُحذف أي كود أو إعداد أو مفتاح.
AI_SEARCH_ENABLED = False
def _ai_actions_doc(text: str) -> str:
    """مستند iframe صغير لزرّي «نسخ» و«مشاركة» — يعملان بنقرة مباشرة من المستخدم."""
    import json as _json
    payload = _json.dumps(text).replace("<", "\\u003c")
    doc = """<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@700;800&display=swap');
*{box-sizing:border-box;margin:0;padding:0;font-family:'Cairo',-apple-system,'Segoe UI',sans-serif;}
body{background:transparent;display:flex;gap:10px;justify-content:flex-start;padding:2px;}
button{flex:1;max-width:190px;cursor:pointer;border-radius:12px;padding:10px 12px;font-weight:800;
  font-size:0.9rem;border:1.5px solid #cddfe2;background:#fff;color:#3e6e7e;transition:all .15s;}
button:hover{background:#eaf3f4;border-color:#3e6e7e;}
button:active{transform:translateY(1px);}
.done{background:#e7f4ec !important;border-color:#4f7340 !important;color:#3f6a33 !important;}
</style></head><body>
<button id='cp'>\uD83D\uDCCB \u0646\u0633\u062E</button>
<button id='sh'>\uD83D\uDD17 \u0645\u0634\u0627\u0631\u0643\u0629</button>
<script>
var T=__PAYLOAD__;
function copy(){
  try{ if(navigator.clipboard&&navigator.clipboard.writeText){return navigator.clipboard.writeText(T);} }catch(e){}
  return new Promise(function(res){var ta=document.createElement('textarea');ta.value=T;
    ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.focus();ta.select();
    try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);res();});
}
var cp=document.getElementById('cp'), sh=document.getElementById('sh');
cp.addEventListener('click',function(){copy().then(function(){cp.textContent='\u2713 \u062A\u0645 \u0627\u0644\u0646\u0633\u062E';
  cp.classList.add('done');setTimeout(function(){cp.textContent='\uD83D\uDCCB \u0646\u0633\u062E';cp.classList.remove('done');},1600);});});
sh.addEventListener('click',function(){
  if(navigator.share){navigator.share({text:T}).catch(function(){});}
  else{copy().then(function(){sh.textContent='\u2713 \u062A\u0645 \u0627\u0644\u0646\u0633\u062E \u0644\u0644\u0645\u0634\u0627\u0631\u0643\u0629';
    sh.classList.add('done');setTimeout(function(){sh.textContent='\uD83D\uDD17 \u0645\u0634\u0627\u0631\u0643\u0629';sh.classList.remove('done');},1600);});}
});
</script></body></html>"""
    return doc.replace("__PAYLOAD__", payload)


def render_ai_section():
    """قسم البحث بالذكاء الاصطناعي (Gemini) — امتداد لخانة البحث عن الطعام.

    تصميم بسيط: صندوق إدخال مطابق لخانة البحث + أيقونتي كاميرا/رفع صورة + زر إرسال،
    ثم تظهر الإجابة في بطاقة أنيقة أسفله مباشرة. لا محادثات ولا سجل ولا فقاعات دردشة.
    كل الاستيرادات كسولة (lazy) للحفاظ على سرعة الإقلاع، والقسم معزول تماماً: أي فشل
    في المفتاح/قاعدة البيانات/الشبكة يُظهر رسالة لطيفة فقط ويبقى باقي الموقع يعمل.
    """
    # ── الميزة معطلة مؤقتاً (Feature Flag): نفس البطاقة لكن كل العناصر Disabled ──
    if not AI_SEARCH_ENABLED:
        with st.container(key="ai_box"):
            c_q, c_cam, c_send = st.columns(3, vertical_alignment="center")
            with c_q:
                st.text_input(
                    "سؤالك", placeholder="اسأل عن أي طعام...",
                    label_visibility="collapsed", key="ai_q_off", disabled=True)
            with c_cam:
                with st.container(key="ai_cam_row"):
                    st.file_uploader(
                        "إضافة صورة",
                        type=["png", "jpg", "jpeg", "webp"],
                        label_visibility="collapsed", key="ai_cam_off", disabled=True)
            with c_send:
                st.button("➤", key="ai_send_off", disabled=True)
        st.markdown(
            "<div class='ai-note'>هذه الميزة غير مفعلة حاليًا، وستتوفر قريبًا.</div>",
            unsafe_allow_html=True)
        return

    import uuid as _uuid
    import base64 as _b64
    from datetime import datetime as _dt, timedelta as _td, date as _date

    try:
        from services import config as _cfg
        from services import db_service as _db
        from services import ai_service as _ai
        from services.ai_service import AIError as _AIError
    except Exception:
        logging.exception("AI services import failed")
        st.markdown(
            "<div class='ai-note'>قسم الذكاء الاصطناعي غير متاح حالياً. باقي الموقع يعمل بشكل طبيعي.</div>",
            unsafe_allow_html=True)
        return

    if not _ai.is_available():
        st.markdown(
            "<div class='ai-note'>ميزة الذكاء الاصطناعي غير مُهيّأة حالياً. باقي الموقع يعمل بشكل طبيعي.</div>",
            unsafe_allow_html=True)
        return

    # قاعدة البيانات اختيارية — تُستخدم فقط لتطبيق الحدود اليومية لكل مستخدم.
    if "ai_db_ok" not in st.session_state:
        st.session_state["ai_db_ok"] = _db.db_available()
    db_ok = st.session_state["ai_db_ok"]

    MSG_LIMIT = _cfg.DAILY_MSG_LIMIT
    IMG_LIMIT = _cfg.DAILY_IMG_LIMIT
    today = _date.today()

    # ── هوية مجهولة عبر كوكي (لحدود الاستخدام فقط) — لا تُعطّل الواجهة إن لم تجهز بعد ──
    def _resolve_uid():
        if not db_ok:
            return None
        u = st.session_state.get("ai_uid")
        if u:
            return u
        try:
            import extra_streamlit_components as stx
            cm = stx.CookieManager(key="carbai_cm")
            found = (cm.get_all() or {}).get("carbai_uid")
            if found:
                st.session_state["ai_uid"] = found
                return found
            if st.session_state.get("_ai_cookie_ready"):
                nu = "u_" + _uuid.uuid4().hex
                cm.set("carbai_uid", nu, expires_at=_dt.now() + _td(days=365))
                st.session_state["ai_uid"] = nu
                return nu
            st.session_state["_ai_cookie_ready"] = True
        except Exception:
            pass
        # مؤقتاً (لهذه الجلسة) حتى تجهز الكوكي — تبقى الحدود فعّالة
        return st.session_state.setdefault("ai_uid_tmp", "s_" + _uuid.uuid4().hex)

    uid = _resolve_uid()
    n = st.session_state.get("ai_nonce", 0)

    # ── صندوق الإدخال (مطابق لخانة البحث عن الطعام): سطر واحد = حقل النص + زر الكاميرا يساره + زر الإرسال ──
    cam_val = None
    up_val = None
    with st.container(key="ai_box"):
        c_q, c_cam, c_send = st.columns(3, vertical_alignment="center")
        with c_q:
            q = st.text_input(
                "سؤالك", placeholder="اسأل عن أي طعام...",
                label_visibility="collapsed", key=f"ai_q_{n}",
            )
        with c_cam:
            with st.container(key="ai_cam_row"):
                cam_val = st.file_uploader(
                    "إضافة صورة",
                    type=["png", "jpg", "jpeg", "webp"],
                    label_visibility="collapsed", key=f"ai_cam_{n}")
        with c_send:
            sent = st.button("➤", key=f"ai_send_{n}")

    img_up = cam_val or up_val
    if img_up is not None:
        st.markdown(
            "<div class='ai-attached'>✓ تم إرفاق صورة — اضغط زر الإرسال لتحليلها.</div>",
            unsafe_allow_html=True)

    if sent:
        text = (q or "").strip()
        has_img = img_up is not None
        if not text and not has_img:
            st.warning("اكتب سؤالاً أو ارفع صورة أولاً.")
        else:
            blocked = False
            # قراءة الاستهلاك اليومي: قاعدة البيانات إن توفّرت، وإلا عدّاد الجلسة
            # (تبقى الحدود فعّالة دائماً حتى عند تعطّل قاعدة البيانات).
            used_msg, used_img = 0, 0
            got_from_db = False
            if db_ok and uid:
                try:
                    used_msg, used_img = _db.get_usage(uid, today)
                    got_from_db = True
                except Exception:
                    got_from_db = False
            if not got_from_db:
                _sess_usage = st.session_state.get(
                    f"ai_usage_{today}", {"msg": 0, "img": 0})
                used_msg, used_img = _sess_usage["msg"], _sess_usage["img"]
            if used_msg >= MSG_LIMIT:
                st.warning(f"لقد وصلت إلى الحد اليومي المسموح به من الأسئلة ({MSG_LIMIT}). يمكنك المتابعة غداً. 🌙")
                blocked = True
            elif has_img and used_img >= IMG_LIMIT:
                st.warning(f"لقد وصلت إلى الحد اليومي المسموح به من الصور ({IMG_LIMIT}). يمكنك المتابعة غداً. 🌙")
                blocked = True

            if not blocked:
                # تجهيز الصورة (تصغير للأداء) + معاينة مصغّرة
                img_bytes = None
                img_mime = None
                preview_uri = None
                if has_img:
                    try:
                        from PIL import Image
                        import io
                        raw = img_up.getvalue()
                        im = Image.open(io.BytesIO(raw)).convert("RGB")
                        w, h = im.size
                        mx = max(w, h)
                        if mx > 1024:
                            s = 1024 / mx
                            im = im.resize((int(w * s), int(h * s)))
                        buf = io.BytesIO()
                        im.save(buf, format="JPEG", quality=85)
                        img_bytes = buf.getvalue()
                        img_mime = "image/jpeg"
                        pim = im.copy()
                        pw, ph2 = pim.size
                        pmx = max(pw, ph2)
                        if pmx > 360:
                            ps = 360 / pmx
                            pim = pim.resize((int(pw * ps), int(ph2 * ps)))
                        pbuf = io.BytesIO()
                        pim.save(pbuf, format="JPEG", quality=80)
                        preview_uri = "data:image/jpeg;base64," + _b64.b64encode(pbuf.getvalue()).decode()
                    except Exception:
                        img_bytes = img_up.getvalue()
                        img_mime = getattr(img_up, "type", None) or "image/jpeg"

                # مؤشر تحميل أنيق أثناء التحليل
                ph = st.empty()
                ph.markdown(
                    "<div class='ai-loading'><span class='ai-load-ico'>🔍</span> "
                    + ("جارٍ تحليل الصورة…" if has_img else "جارٍ البحث عن إجابتك…")
                    + "</div>",
                    unsafe_allow_html=True,
                )
                reply = None
                err = None
                try:
                    reply = _ai.generate_reply([], text, img_bytes, img_mime)
                except _AIError as e:
                    err = str(e)
                finally:
                    ph.empty()

                if err:
                    st.error(err)
                else:
                    inc_in_db = False
                    if db_ok and uid:
                        try:
                            _db.increment_usage(uid, today, messages=1, images=1 if has_img else 0)
                            inc_in_db = True
                        except Exception:
                            inc_in_db = False
                    if not inc_in_db:
                        _su = st.session_state.get(
                            f"ai_usage_{today}", {"msg": 0, "img": 0})
                        _su["msg"] += 1
                        if has_img:
                            _su["img"] += 1
                        st.session_state[f"ai_usage_{today}"] = _su
                    st.session_state["ai_last_answer"] = reply
                    st.session_state["ai_last_img"] = preview_uri
                    st.session_state["ai_nonce"] = n + 1
                    st.rerun()

    # ── بطاقة الإجابة (أسفل الصندوق مباشرة) ──
    ans = st.session_state.get("ai_last_answer")
    if ans:
        ans = _ai._sanitize_text(ans)
        with st.container(key="ai_answer"):
            prev = st.session_state.get("ai_last_img")
            if prev:
                st.markdown(
                    f"<div class='ai-thumb-wrap'><img class='ai-thumb' src='{prev}' alt='صورة الطعام'/></div>",
                    unsafe_allow_html=True)
            st.markdown(ans)
            try:
                st.iframe(_ai_actions_doc(ans), height=62)
            except Exception:
                logging.exception("AI actions bar failed")
        if st.button("➕ سؤال جديد", key="ai_newq"):
            st.session_state.pop("ai_last_answer", None)
            st.session_state.pop("ai_last_img", None)
            st.session_state["ai_nonce"] = st.session_state.get("ai_nonce", 0) + 1
            st.rerun()


st.markdown("<div id='ai-search' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>البحث بالذكاء الاصطناعي</span></div>",
    unsafe_allow_html=True,
)
try:
    render_ai_section()
except Exception:
    logging.exception("AI section crashed")
    st.markdown(
        "<div class='ai-note'>قسم الذكاء الاصطناعي غير متاح حالياً. باقي الموقع يعمل بشكل طبيعي.</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# قسم البدائل الغذائية (أول قسم محتوى بعد الذكاء الاصطناعي — بطلب المستخدم)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div id='alternatives' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>البدائل الغذائية</span>"
    + _info_icon("info-alternatives") + "</div>",
    unsafe_allow_html=True,
)
if total_all == 0:
    st.info("لا توجد بيانات بعد.")
elif not fa:
    st.markdown("<div class='empty-msg'>لا توجد نتائج مطابقة</div>", unsafe_allow_html=True)
else:
    _render_alt_cards_interactive(
        fa, GRAMS_FOODS, ALT_FOODS, DATA_VERSION, global_search, cat_key or "all"
    )


# ══════════════════════════════════════════════════════════════════════════════
# قسم الكربوهيدرات بالجرام (بعد البدائل)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div id='per-gram' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>الكربوهيدرات لكل جرام</span>"
    + _info_icon("info-per-gram") + "</div>",
    unsafe_allow_html=True,
)
if total_all == 0:
    st.info("لا توجد بيانات بعد.")
elif not fg:
    st.markdown("<div class='empty-msg'>لا توجد نتائج مطابقة</div>", unsafe_allow_html=True)
else:
    _render_gram_cards_interactive(fg, DATA_VERSION, global_search, cat_key or "all")


# ══════════════════════════════════════════════════════════════════════════════
# قسم الملصق الغذائي — حاسبة واحدة (٣ خانات) + أمثلة وتوضيحات قابلة للفتح
# ══════════════════════════════════════════════════════════════════════════════
def _label_result_html(main_val: float) -> str:
    """بطاقة نتيجة الملصق الغذائي: الناتج النهائي بالجرام فقط."""
    return f"""
<div class='lab-result'>
  <div class='lab-final'>الناتج النهائي</div>
  <div class='lab-final-val'>{_fmt_num(main_val)} <span>جم كربوهيدرات</span></div>
</div>"""


st.markdown("<div id='label-calc' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>الملصق الغذائي</span>"
    + _info_icon("info-label-calc") + "</div>",
    unsafe_allow_html=True,
)

# ── حاسبة واحدة: (الوزن الصافي ÷ حجم الحصة) × إجمالي الكربوهيدرات ──────────────
with st.form("lf_label"):
    l_net = st.text_input("الوزن الصافي (جم)", placeholder="مثال: 180", key="lbl_net")
    l_serv = st.text_input("حجم الحصة (جم)", placeholder="مثال: 30", key="lbl_serv")
    l_carbs = st.text_input("إجمالي الكربوهيدرات (جم)", placeholder="مثال: 22", key="lbl_carbs")
    s_lbl = st.form_submit_button("احسب")
if s_lbl:
    net = _parse_num(l_net)
    serv = _parse_num(l_serv)
    carbs = _parse_num(l_carbs)
    errs = []
    if net is None or net <= 0:
        errs.append("أدخل الوزن الصافي بشكل صحيح.")
    if serv is None or serv <= 0:
        errs.append("أدخل حجم الحصة بشكل صحيح.")
    if carbs is None or carbs < 0:
        errs.append("أدخل إجمالي الكربوهيدرات بشكل صحيح.")
    if errs:
        st.markdown(
            "<div class='empty-msg'>" + "<br>".join(errs) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            _label_result_html((net / serv) * carbs),
            unsafe_allow_html=True,
        )

# ملاحظة: بطاقات «أمثلة وتوضيحات» + «طريقة الاستخدام» انتقلت إلى نافذة ⓘ التعريفية.


# ══════════════════════════════════════════════════════════════════════════════
# قسم حساب جرعة الإنسولين — معامل الكربوهيدرات (ICR) + معامل التصحيح (ISF)
# ══════════════════════════════════════════════════════════════════════════════
def _insulin_result_html(label: str, value_html: str) -> str:
    """بطاقة نتيجة موحّدة لحاسبات جرعة الإنسولين."""
    return f"""
<div class='lab-result'>
  <div class='lab-final'>{label}</div>
  <div class='lab-final-val'>{value_html}</div>
</div>"""


st.markdown("<div id='insulin-calc' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>حساب جرعة الإنسولين</span>"
    + _info_icon("info-insulin-calc") + "</div>",
    unsafe_allow_html=True,
)

# ── معامل الكربوهيدرات (ICR) ─────────────────────────────────────────────────
st.markdown(
    "<div class='case-block'>"
    "<div class='case-head'><span class='case-num'>ICR</span>"
    "<span class='case-name'>معامل الكربوهيدرات</span></div>"
    "</div>",
    unsafe_allow_html=True,
)
ICR_BASES = {"بالغ (قاعدة 500)": 500, "طفل (قاعدة 350)": 350}
with st.form("ins_icr"):
    icr_cat = st.radio(
        "اختر الفئة",
        list(ICR_BASES.keys()),
        key="icr_cat",
    )
    icr_tdd = st.text_input(
        "الجرعة اليومية الكلية للإنسولين (TDD)",
        placeholder="مثال: 40", key="icr_tdd",
    )
    s_icr = st.form_submit_button("احسب")
if s_icr:
    tdd_icr = _parse_num(icr_tdd)
    if tdd_icr is None or tdd_icr <= 0:
        st.markdown(
            "<div class='empty-msg'>أدخل الجرعة اليومية الكلية (TDD) بشكل صحيح.</div>",
            unsafe_allow_html=True,
        )
    else:
        base_icr = ICR_BASES[icr_cat]
        icr_val = round(base_icr / tdd_icr)
        st.markdown(
            _insulin_result_html("معامل الكربوهيدرات", f"1 : {_fmt_num(icr_val)}"),
            unsafe_allow_html=True,
        )

# ── معامل التصحيح (ISF) ──────────────────────────────────────────────────────
st.markdown(
    "<div class='case-block'>"
    "<div class='case-head'><span class='case-num'>ISF</span>"
    "<span class='case-name'>معامل التصحيح</span></div>"
    "</div>",
    unsafe_allow_html=True,
)
ISF_BASES = {"💉 سريع المفعول (قاعدة 1800)": 1800, "💉 الإنسولين العادي Regular (قاعدة 1500)": 1500}
with st.form("ins_isf"):
    isf_type = st.radio(
        "نوع الإنسولين",
        list(ISF_BASES.keys()),
        key="isf_type",
    )
    isf_tdd = st.text_input(
        "الجرعة اليومية الكلية للإنسولين (TDD)",
        placeholder="مثال: 40", key="isf_tdd",
    )
    s_isf = st.form_submit_button("احسب")
if s_isf:
    tdd_isf = _parse_num(isf_tdd)
    if tdd_isf is None or tdd_isf <= 0:
        st.markdown(
            "<div class='empty-msg'>أدخل الجرعة اليومية الكلية (TDD) بشكل صحيح.</div>",
            unsafe_allow_html=True,
        )
    else:
        base_isf = ISF_BASES[isf_type]
        isf_val = round(base_isf / tdd_isf)
        st.markdown(
            _insulin_result_html("معامل التصحيح", f"{_fmt_num(isf_val)} <span>mg/dL</span>"),
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# قسم معلومات ونصائح
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div id='tips' class='anchor'></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-head'>"
    "<span class='txt'>معلومات ونصائح</span></div>",
    unsafe_allow_html=True,
)
with st.expander("نبذة عن السكري من النوع الأول"):
    st.markdown(
        "<div class='tip-sub'>ما هو السكري من النوع الأول؟</div>"
        "<p class='tip-p'>السكري من النوع الأول هو مرض مناعي ذاتي يتوقف فيه "
        "البنكرياس عن إنتاج الإنسولين، لذلك يحتاج المصاب إلى الإنسولين يوميًا "
        "للمحافظة على مستوى السكر في الدم.</p>"

        "<div class='tip-sub'>سبب الإصابة</div>"
        "<p class='tip-p'>السبب الدقيق غير معروف، ويُعتقد أنه ينتج عن تفاعل "
        "عوامل وراثية وبيئية تؤثر في جهاز المناعة.</p>"

        "<div class='tip-sub'>فترة شهر العسل</div>"
        "<p class='tip-p'>قد يمر بعض المرضى بعد التشخيص بمرحلة مؤقتة تُسمى فترة "
        "شهر العسل، حيث يستمر البنكرياس في إنتاج كمية قليلة من الإنسولين، مما "
        "يقلل الحاجة إلى جرعات الإنسولين لفترة من الوقت.</p>"
        "<div class='tip-note'><b>مهم:</b> لا تعني هذه المرحلة الشفاء من السكري، "
        "لذلك يجب عدم إيقاف الإنسولين إلا بتوجيه من الفريق الطبي.</div>"

        "<div class='tip-sub'>هل يمكن الشفاء منه؟</div>"
        "<p class='tip-p'>لا يوجد علاج شافٍ حاليًا، لكن يمكن التحكم بالسكري من "
        "النوع الأول من خلال:</p>"
        "<ul class='tip-list'>"
        "<li>الالتزام بالإنسولين.</li>"
        "<li>حساب الكربوهيدرات.</li>"
        "<li>قياس السكر بانتظام.</li>"
        "<li>التغذية الصحية.</li>"
        "<li>ممارسة النشاط البدني.</li>"
        "</ul>"

        "<div class='tip-sub'>الهدف من العلاج</div>"
        "<ul class='tip-list'>"
        "<li>المحافظة على مستوى السكر ضمن المعدل المستهدف.</li>"
        "<li>تقليل خطر المضاعفات.</li>"
        "<li>العيش حياة صحية وطبيعية.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

with st.expander("استخدام الإنسولين"):
    st.markdown(
        "<div class='tip-sub'>ما هو الإنسولين؟</div>"
        "<p class='tip-p'>الإنسولين هو هرمون يساعد على انتقال الجلوكوز من الدم إلى "
        "خلايا الجسم لاستخدامه كمصدر للطاقة.</p>"
        "<p class='tip-p'>في السكري من النوع الأول لا ينتج الجسم الإنسولين، لذلك "
        "يحتاج المريض إلى استخدامه يوميًا للمحافظة على مستوى السكر في الدم.</p>"

        "<div class='tip-sub'>لماذا يجب استخدام الإنسولين؟</div>"
        "<p class='tip-p'>يساعد الإنسولين على:</p>"
        "<ul class='tip-list'>"
        "<li>المحافظة على مستوى السكر ضمن المعدل المستهدف.</li>"
        "<li>تقليل خطر ارتفاع أو هبوط السكر.</li>"
        "<li>الوقاية من المضاعفات.</li>"
        "<li>مساعدة الجسم على استخدام الغذاء بصورة صحيحة.</li>"
        "</ul>"

        "<div class='tip-sub'>أماكن حقن الإنسولين</div>"
        "<p class='tip-p'>يمكن حقن الإنسولين في:</p>"
        + INJECT_SITES_FIG +
        "<p class='tip-p'>سرعة الامتصاص تختلف حسب مكان الحقن:</p>"
        "<ul class='tip-list'>"
        "<li>البطن: الأسرع امتصاصًا.</li>"
        "<li>أعلى الذراع: امتصاص متوسط.</li>"
        "<li>الفخذ والأرداف: أبطأ امتصاصًا.</li>"
        "</ul>"

        "<div class='tip-sub'>تغيير أماكن الحقن</div>"
        "<p class='tip-p'>يُنصح بعدم الحقن في نفس الموضع كل مرة.</p>"
        "<div class='tip-check'>✔ غيّر مكان الحقن مع كل جرعة، واترك مسافة 2–3 سم "
        "تقريبًا بين موضع الحقنة السابقة والجديدة.</div>"
        "<p class='tip-p'>يساعد ذلك على:</p>"
        "<ul class='tip-list'>"
        "<li>تحسين امتصاص الإنسولين.</li>"
        "<li>تقليل حدوث التكتلات أو سماكة الجلد.</li>"
        "<li>المحافظة على فعالية الإنسولين.</li>"
        "</ul>"

        "<div class='tip-sub'>حفظ الإنسولين</div>"
        "<ul class='tip-list'>"
        "<li>يُحفظ الإنسولين غير المفتوح في الثلاجة.</li>"
        "<li>يُحفظ القلم المستخدم حسب تعليمات الشركة المصنعة.</li>"
        "<li>لا يُجمّد الإنسولين.</li>"
        "<li>تجنب تعريضه للشمس أو الحرارة المرتفعة.</li>"
        "<li>إذا تغير اللون أو ظهرت شوائب فلا تستخدمه.</li>"
        "</ul>"

        "<div class='tip-sub'>تذكير</div>"
        "<ul class='tip-list'>"
        "<li>استخدم إبرة جديدة مع كل حقنة.</li>"
        "<li>تأكد من الجرعة قبل الحقن.</li>"
        "<li>لا تشارك قلم الإنسولين مع أي شخص.</li>"
        "<li>راقب تاريخ انتهاء الصلاحية.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

with st.expander("التعامل مع انخفاض وارتفاع السكر"):
    st.markdown(
        "<div class='tip-sub'>انخفاض سكر الدم</div>"
        "<p class='tip-p'>يحدث انخفاض السكر عندما يكون مستوى السكر في الدم أقل من "
        "<b>70 mg/dL</b>.</p>"

        "<div class='tip-sub2'>الأسباب</div>"
        "<ul class='tip-list'>"
        "<li>زيادة جرعة الإنسولين.</li>"
        "<li>تأخير أو تخطي الوجبة.</li>"
        "<li>عدم تناول كمية كافية من الكربوهيدرات.</li>"
        "<li>ممارسة نشاط بدني دون تعويض بالكربوهيدرات.</li>"
        "<li>شرب الكحول (للبالغين).</li>"
        "</ul>"

        "<div class='tip-sub2'>الأعراض</div>"
        "<ul class='tip-list'>"
        "<li>التعرق.</li>"
        "<li>الرجفة.</li>"
        "<li>الجوع.</li>"
        "<li>الدوخة.</li>"
        "<li>تسارع نبضات القلب.</li>"
        "<li>صعوبة التركيز.</li>"
        "<li>تشوش الرؤية.</li>"
        "</ul>"

        "<div class='tip-sub2'>العلاج (قاعدة 15/15)</div>"
        "<div class='tip-note'><b>قاعدة 15/15:</b> تناول 15 جم من الكربوهيدرات "
        "سريعة الامتصاص، ثم انتظر 15 دقيقة، ثم أعد قياس السكر.</div>"
        "<ul class='tip-list'>"
        "<li>تناول 15 جم من الكربوهيدرات سريعة الامتصاص.</li>"
        "<li>انتظر 15 دقيقة.</li>"
        "<li>أعد قياس السكر.</li>"
        "<li>إذا بقي أقل من <b>70 mg/dL</b> كرر العلاج.</li>"
        "<li>بعد تحسن السكر، تناول وجبة أو سناك إذا كانت الوجبة التالية ليست "
        "قريبة.</li>"
        "</ul>"

        "<div class='tip-sub'>ارتفاع سكر الدم</div>"
        "<p class='tip-p'>يحدث ارتفاع السكر عندما يكون مستوى السكر أعلى من المعدل "
        "المستهدف.</p>"

        "<div class='tip-sub2'>الأسباب</div>"
        "<ul class='tip-list'>"
        "<li>نسيان أو تأخير جرعة الإنسولين.</li>"
        "<li>تناول كمية كبيرة من الكربوهيدرات دون تغطيتها بالإنسولين.</li>"
        "<li>المرض أو العدوى.</li>"
        "<li>التوتر والضغوط النفسية.</li>"
        "<li>تلف الإنسولين أو انتهاء صلاحيته.</li>"
        "<li>انسداد أو انفصال مضخة الإنسولين (لمستخدمي المضخة).</li>"
        "</ul>"

        "<div class='tip-sub2'>الأعراض</div>"
        "<ul class='tip-list'>"
        "<li>العطش الشديد.</li>"
        "<li>كثرة التبول.</li>"
        "<li>جفاف الفم.</li>"
        "<li>التعب.</li>"
        "<li>تشوش الرؤية.</li>"
        "</ul>"

        "<div class='tip-sub2'>ماذا أفعل عند ارتفاع السكر؟</div>"
        "<ul class='tip-list'>"
        "<li>اشرب كمية كافية من الماء.</li>"
        "<li>استخدم جرعة التصحيح حسب الخطة العلاجية.</li>"
        "<li>أعد قياس السكر بعد ساعتين.</li>"
        "<li>إذا كان السكر أكثر من <b>300 mg/dL</b> أو استمر مرتفعًا، افحص الكيتون "
        "حسب تعليمات الفريق الطبي.</li>"
        "</ul>"

        "<div class='tip-sub'>أخطاء شائعة</div>"
        "<ul class='tip-list'>"
        "<li>نسيان جرعة الإنسولين.</li>"
        "<li>تأخير جرعة الإنسولين.</li>"
        "<li>حساب الكربوهيدرات بشكل غير صحيح.</li>"
        "<li>عدم قياس السكر بانتظام.</li>"
        "<li>علاج هبوط السكر بكمية كبيرة من السكريات.</li>"
        "<li>تجاهل ارتفاع السكر أو تأخير جرعة التصحيح.</li>"
        "<li>عدم حمل مصدر سريع للكربوهيدرات لعلاج الهبوط.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

with st.expander("التغذية ونمط الحياة الصحي"):
    st.markdown(
        "<div class='tip-sub'>الطبق الصحي</div>"
        + HEALTHY_PLATE_FIG +
        "<p class='tip-p'>يقسم الطبق إلى:</p>"

        "<div class='tip-sub2'>🟢 نصف الطبق (50%) — خضروات غير نشوية</div>"
        "<p class='tip-p'>مثل:</p>"
        "<ul class='tip-list'>"
        "<li>الخس</li>"
        "<li>الخيار</li>"
        "<li>الطماطم</li>"
        "<li>البروكلي</li>"
        "<li>الكوسة</li>"
        "</ul>"

        "<div class='tip-sub2'>🟠 ربع الطبق (25%) — بروتين صحي</div>"
        "<p class='tip-p'>مثل:</p>"
        "<ul class='tip-list'>"
        "<li>الدجاج</li>"
        "<li>السمك</li>"
        "<li>اللحم قليل الدهن</li>"
        "<li>البيض</li>"
        "<li>البقوليات</li>"
        "</ul>"

        "<div class='tip-sub2'>🟡 ربع الطبق (25%) — كربوهيدرات</div>"
        "<p class='tip-p'>مثل:</p>"
        "<ul class='tip-list'>"
        "<li>الأرز</li>"
        "<li>الخبز</li>"
        "<li>المكرونة</li>"
        "<li>البطاطس</li>"
        "<li>الشوفان</li>"
        "<li>الحبوب الكاملة</li>"
        "</ul>"

        "<div class='tip-sub2'>🥛 بجانب الطبق</div>"
        "<ul class='tip-list'>"
        "<li>كوب حليب أو لبن قليل الدسم.</li>"
        "<li>ثمرة فاكهة مناسبة.</li>"
        "</ul>"
        "<div class='tip-note'><b>نصيحة:</b> احسب كمية الكربوهيدرات في وجبتك "
        "باستخدام أدوات الموقع.</div>"

        "<div class='tip-sub'>نصائح غذائية</div>"
        "<ul class='tip-list'>"
        "<li>يُفضل توزيع الكربوهيدرات على الوجبات وعدم تناول كمية كبيرة في وجبة "
        "واحدة.</li>"
        "<li>الأطفال: غالبًا تحتوي الوجبة الرئيسية على 30–50 جم من الكربوهيدرات "
        "حسب العمر والخطة العلاجية.</li>"
        "<li>المراهقون والبالغون: غالبًا تحتوي الوجبة الرئيسية على 45–70 جم من "
        "الكربوهيدرات حسب الاحتياج.</li>"
        "<li>الوجبة الخفيفة (السناك): غالبًا 15–30 جم من الكربوهيدرات عند "
        "الحاجة.</li>"
        "<li>احسب الكربوهيدرات بدقة قبل كل وجبة.</li>"
        "<li>اشرب كمية كافية من الماء.</li>"
        "<li>قلل من المشروبات المحلاة والسكريات.</li>"
        "</ul>"

        "<div class='tip-sub'>النشاط البدني</div>"
        "<p class='tip-p'>يساعد النشاط البدني على تحسين التحكم بمستوى السكر "
        "وزيادة حساسية الجسم للإنسولين.</p>"
        "<ul class='tip-list'>"
        "<li>مارس نشاطًا بدنيًا بانتظام.</li>"
        "<li>افحص السكر قبل وبعد التمرين عند الحاجة.</li>"
        "<li>احمل معك مصدرًا سريعًا للكربوهيدرات لعلاج هبوط السكر.</li>"
        "<li>تجنب ممارسة الرياضة إذا كان مستوى السكر منخفضًا أو مرتفعًا بشكل "
        "شديد.</li>"
        "</ul>"

        "<div class='tip-sub'>النوم والصحة النفسية</div>"
        "<p class='tip-p'>يساعد النوم الجيد وتقليل التوتر على تحسين التحكم "
        "بالسكري.</p>"
        "<ul class='tip-list'>"
        "<li>احرص على النوم لمدة 7–9 ساعات يوميًا.</li>"
        "<li>حاول التقليل من التوتر والضغوط النفسية.</li>"
        "<li>اطلب الدعم من الأسرة أو الفريق الطبي عند الحاجة.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

with st.expander("السكري أثناء المرض والحماض الكيتوني"):
    st.markdown(
        "<div class='tip-sub'>السكري أثناء المرض</div>"
        "<p class='tip-p'>عند الإصابة بالحمى أو الإنفلونزا أو القيء أو أي عدوى، "
        "قد يرتفع مستوى السكر في الدم ويزداد خطر الإصابة بالحماض الكيتوني، لذلك "
        "يحتاج المريض إلى متابعة السكر والإنسولين بشكل أكبر.</p>"

        "<div class='tip-sub'>ماذا أفعل أثناء المرض؟</div>"
        "<ul class='tip-list'>"
        "<li>لا توقف الإنسولين حتى إذا كنت لا تستطيع تناول الطعام، إلا إذا أوصى "
        "الطبيب بذلك.</li>"
        "<li>افحص مستوى السكر كل 2–4 ساعات أو حسب الخطة العلاجية.</li>"
        "<li>اشرب كميات كافية من السوائل لتجنب الجفاف.</li>"
        "<li>إذا لم تستطع تناول الوجبات المعتادة، حاول تناول سوائل أو أطعمة تحتوي "
        "على الكربوهيدرات حسب قدرتك.</li>"
        "<li>اتبع تعليمات الفريق الطبي عند استمرار القيء أو ارتفاع السكر.</li>"
        "</ul>"

        "<div class='tip-sub'>متى أفحص الكيتون؟</div>"
        "<p class='tip-p'>افحص الكيتون إذا:</p>"
        "<ul class='tip-list'>"
        "<li>كان مستوى السكر <b>250 mg/dL</b> أو أكثر في قياسين متتاليين.</li>"
        "<li>كنت تعاني من الحمى أو العدوى.</li>"
        "<li>كان لديك غثيان أو قيء.</li>"
        "<li>شعرت بتعب شديد أو ألم في البطن.</li>"
        "</ul>"

        "<div class='tip-sub'>ما هو الحماض الكيتوني؟</div>"
        "<p class='tip-p'>الحماض الكيتوني السكري هو مضاعفة خطيرة تحدث عندما لا "
        "يحصل الجسم على كمية كافية من الإنسولين، فيبدأ بحرق الدهون للحصول على "
        "الطاقة، مما يؤدي إلى تراكم الكيتونات في الدم وارتفاع حموضته.</p>"

        "<div class='tip-sub'>أعراض الحماض الكيتوني</div>"
        "<ul class='tip-list'>"
        "<li>ارتفاع شديد في مستوى السكر.</li>"
        "<li>وجود كيتون في البول أو الدم.</li>"
        "<li>غثيان أو قيء.</li>"
        "<li>ألم في البطن.</li>"
        "<li>عطش شديد وجفاف.</li>"
        "<li>تنفس سريع أو عميق.</li>"
        "<li>رائحة الفم تشبه الفاكهة.</li>"
        "<li>تعب شديد أو نعاس.</li>"
        "</ul>"

        "<div class='tip-sub'>كيف أقي نفسي من الحماض الكيتوني؟</div>"
        "<ul class='tip-list'>"
        "<li>لا توقف الإنسولين أبدًا دون استشارة الطبيب.</li>"
        "<li>افحص السكر بانتظام.</li>"
        "<li>افحص الكيتون عند ارتفاع السكر أو أثناء المرض.</li>"
        "<li>اشرب كمية كافية من السوائل.</li>"
        "<li>استخدم جرعات التصحيح حسب الخطة العلاجية.</li>"
        "<li>تأكد من سلامة قلم أو مضخة الإنسولين وصلاحية الإنسولين.</li>"
        "<li>راجع الطبيب عند استمرار ارتفاع السكر أو وجود كيتون.</li>"
        "</ul>"

        "<div class='tip-sub'>متى أراجع الطوارئ؟</div>"
        "<p class='tip-p'>توجه إلى الطوارئ فورًا إذا:</p>"
        "<ul class='tip-list'>"
        "<li>كان الكيتون مرتفعًا ولم ينخفض.</li>"
        "<li>استمر القيء أو لم تستطع الاحتفاظ بالسوائل.</li>"
        "<li>كان لديك صعوبة في التنفس.</li>"
        "<li>استمر السكر مرتفعًا رغم جرعات التصحيح.</li>"
        "<li>شعرت بنعاس شديد أو انخفاض في مستوى الوعي.</li>"
        "</ul>"

        "<div class='tip-sub'>نصيحة مهمة</div>"
        "<div class='tip-note'>المرض لا يعني إيقاف الإنسولين، بل غالبًا يحتاج "
        "الجسم إلى متابعة أدق وجرعات مناسبة حسب الخطة العلاجية، لذلك احرص على "
        "قياس السكر والكيتون بانتظام أثناء المرض.</div>",
        unsafe_allow_html=True,
    )

with st.expander("الحياة اليومية مع السكري"):
    st.markdown(
        "<div class='tip-sub'>المدرسة</div>"
        "<ul class='tip-list'>"
        "<li>أخبر المعلمين أو المشرفين بإصابتك بالسكري.</li>"
        "<li>احمل جهاز قياس السكر، والإنسولين، ومصدرًا سريعًا للكربوهيدرات.</li>"
        "<li>لا تؤجل علاج هبوط السكر أثناء اليوم الدراسي.</li>"
        "<li>احرص على تناول الوجبات في مواعيدها.</li>"
        "</ul>"

        "<div class='tip-sub'>السفر</div>"
        "<ul class='tip-list'>"
        "<li>احمل كمية كافية من الإنسولين ومستلزمات السكري.</li>"
        "<li>ضع الإنسولين في حقيبة اليد ولا تشحنه مع الأمتعة.</li>"
        "<li>احمل وجبات خفيفة ومصدرًا سريعًا للكربوهيدرات.</li>"
        "<li>راقب مستوى السكر أثناء السفر، خاصة مع اختلاف الوقت أو زيادة "
        "الحركة.</li>"
        "<li>احتفظ بوصفة طبية أو تقرير مختصر عند السفر لمسافات طويلة.</li>"
        "</ul>"

        "<div class='tip-sub'>رمضان</div>"
        "<ul class='tip-list'>"
        "<li>استشر طبيبك قبل الصيام.</li>"
        "<li>لا تصم إذا أوصى الطبيب بعدم الصيام.</li>"
        "<li>افحص السكر بانتظام، وقياس السكر لا يفطر.</li>"
        "<li>أفطر فورًا إذا انخفض السكر إلى أقل من 70 mg/dL أو ارتفع بشكل "
        "شديد.</li>"
        "<li>لا توقف الإنسولين أو تغير جرعاته دون استشارة الطبيب.</li>"
        "</ul>"

        "<div class='tip-sub'>الأعياد والمناسبات</div>"
        "<ul class='tip-list'>"
        "<li>استمتع بالطعام باعتدال.</li>"
        "<li>احسب الكربوهيدرات قبل تناول الحلويات.</li>"
        "<li>لا تتجاوز جرعة الإنسولين المقررة.</li>"
        "<li>راقب مستوى السكر بعد الوجبات.</li>"
        "</ul>"

        "<div class='tip-sub'>المطاعم</div>"
        "<ul class='tip-list'>"
        "<li>اختر الوجبات المشوية أو المطهية بطريقة صحية.</li>"
        "<li>اطلب الصلصات بشكل منفصل إن أمكن.</li>"
        "<li>احسب كمية الكربوهيدرات قبل تناول الوجبة.</li>"
        "<li>انتبه لحجم الحصص، فقد تكون أكبر من المعتاد.</li>"
        "</ul>"

        "<div class='tip-sub'>الحفلات</div>"
        "<ul class='tip-list'>"
        "<li>لا تذهب وأنت جائع جدًا.</li>"
        "<li>ابدأ بالخضروات أو البروتين ثم تناول الكربوهيدرات باعتدال.</li>"
        "<li>احسب الكربوهيدرات قبل تناول الحلويات أو المشروبات.</li>"
        "<li>احتفظ دائمًا بمصدر سريع للكربوهيدرات تحسبًا لهبوط السكر.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

with st.expander("المتابعة الدورية"):
    st.markdown(
        "<p class='tip-p'>المتابعة المنتظمة تساعد على التحكم في مستوى السكر، "
        "والوقاية من المضاعفات، والحفاظ على صحة الجسم.</p>"

        "<div class='tip-sub'>HbA1c (السكر التراكمي)</div>"
        "<ul class='tip-list'>"
        "<li>يُجرى كل 3 أشهر أو حسب توصية الطبيب.</li>"
        "<li>يوضح متوسط مستوى السكر خلال آخر 2–3 أشهر.</li>"
        "<li>يساعد على تقييم فعالية الخطة العلاجية.</li>"
        "</ul>"

        "<div class='tip-sub'>فحص العين</div>"
        "<ul class='tip-list'>"
        "<li>يُجرى مرة واحدة سنويًا أو حسب توصية طبيب العيون.</li>"
        "<li>للكشف المبكر عن اعتلال الشبكية السكري.</li>"
        "</ul>"

        "<div class='tip-sub'>فحص الكلى</div>"
        "<ul class='tip-list'>"
        "<li>متابعة وظائف الكلى وتحليل البول بشكل دوري.</li>"
        "<li>للكشف المبكر عن أي تغيرات قد تؤثر على الكلى.</li>"
        "</ul>"

        "<div class='tip-sub'>فحص القدمين</div>"
        "<ul class='tip-list'>"
        "<li>افحص قدميك يوميًا.</li>"
        "<li>راجع الطبيب عند وجود جرح أو احمرار أو تورم أو تغير في لون "
        "الجلد.</li>"
        "<li>ارتدِ حذاءً مناسبًا وتجنب المشي حافي القدمين.</li>"
        "</ul>"

        "<div class='tip-sub'>اللقاحات</div>"
        "<ul class='tip-list'>"
        "<li>لقاح الإنفلونزا الموسمية.</li>"
        "<li>اللقاحات الأخرى حسب توصية الطبيب.</li>"
        "</ul>"

        "<div class='tip-sub'>المواعيد الدورية</div>"
        "<p class='tip-p'>احرص على مراجعة فريق السكري بانتظام لمتابعة:</p>"
        "<ul class='tip-list'>"
        "<li>مستوى السكر.</li>"
        "<li>جرعات الإنسولين.</li>"
        "<li>النمو (للأطفال والمراهقين).</li>"
        "<li>التغذية.</li>"
        "<li>النشاط البدني.</li>"
        "</ul>"

        "<div class='tip-sub'>سجل قراءات السكر</div>"
        "<p class='tip-p'>احرص على تسجيل:</p>"
        "<ul class='tip-list'>"
        "<li>قراءات السكر اليومية.</li>"
        "<li>جرعات الإنسولين.</li>"
        "<li>حالات انخفاض أو ارتفاع السكر.</li>"
        "<li>أي ملاحظات مثل المرض أو النشاط البدني أو تغيير الجرعات.</li>"
        "</ul>"
        "<p class='tip-p'>يساعد ذلك الطبيب وأخصائي التغذية على تقييم حالتك وتعديل "
        "الخطة العلاجية بدقة.</p>"

        "<div class='tip-sub'>تذكير</div>"
        "<p class='tip-p'>الالتزام بالمتابعة الدورية يساعد على:</p>"
        "<ul class='tip-list'>"
        "<li>تحسين التحكم بمستوى السكر.</li>"
        "<li>تقليل خطر المضاعفات.</li>"
        "<li>المحافظة على صحة العينين والكلى والأعصاب والقدمين.</li>"
        "<li>العيش بصحة أفضل وجودة حياة أفضل.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )


st.markdown(
    "<div class='foot-note'>المعلومات لأغراض إرشادية ولا تغني عن استشارة الطبيب "
    "أو أخصائي التغذية.</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f"<div class='site-footer'>{SITE_FOOTER_HTML}</div>",
    unsafe_allow_html=True,
)
