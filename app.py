````python
import io
import json
import os
import re
from datetime import datetime

import streamlit as st
from criteria import CRITERIA, CATEGORIES, MAX_SCORE


# ============================================================
# إعداد الصفحة
# ============================================================

st.set_page_config(
    page_title="مقيّم خطة البحث العلمي",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# تنسيق الواجهة
# ============================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: Tahoma, Arial, sans-serif;
    }

    .block-container {
        direction: rtl;
        max-width: 1450px;
        padding-top: 1rem;
    }

    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(135deg,#173b63,#2f7f8f);
        color: white;
        margin-bottom: 18px;
    }

    .hero h1 {
        font-size: 2.15rem;
        margin: 0 0 8px;
    }

    .hero p {
        font-size: 1.03rem;
        margin: 0;
        opacity: .96;
        line-height: 1.8;
    }

    .card {
        padding: 18px;
        border: 1px solid #dfe7eb;
        border-radius: 16px;
        background: #fff;
        margin-bottom: 12px;
        line-height: 1.9;
    }

    .good {
        border-right: 5px solid #2e7d32;
    }

    .warn {
        border-right: 5px solid #c78b22;
    }

    .bad {
        border-right: 5px solid #b23a48;
    }

    .muted {
        color: #65747e;
        font-size: .92rem;
    }

    .stProgress > div > div > div > div {
        background-color: #2f7f8f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
        <h1>📚 مقيّم خطة البحث العلمي</h1>
        <p>
        تقييم أكاديمي دلالي لخطة البحث وفق المعايير
        12–51 و68–71 فقط، مع الدرجة الرقمية والتحليل
        الكتابي والأدلة والتوصيات.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# قراءة المفاتيح من Streamlit Secrets
# ============================================================

def get_secret(name, default=""):
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value:
                return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


# ============================================================
# تنظيف النص
# ============================================================

def clean_text(text):
    text = text.replace("\u200f", " ")
    text = text.replace("\u200e", " ")
    text = text.replace("\ufeff", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ============================================================
# قراءة Word
# ============================================================

@st.cache_data(show_spinner=False)
def extract_docx(data):

    from docx import Document

    doc = Document(io.BytesIO(data))

    parts = []

    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text.strip())

    for table in doc.tables:
        for row in table.rows:
            parts.append(
                " | ".join(
                    cell.text.strip()
                    for cell in row.cells
                )
            )

    return clean_text("\n".join(parts))


# ============================================================
# قراءة PDF
# ============================================================

@st.cache_data(show_spinner=False)
def extract_pdf(data):

    import fitz

    doc = fitz.open(
        stream=data,
        filetype="pdf"
    )

    text = []

    for page in doc:
        text.append(
            page.get_text("text")
        )

    return clean_text(
        "\n".join(text)
    )


# ============================================================
# OCR للصورة
# ============================================================

@st.cache_data(show_spinner=False)
def ocr_image(data):

    from PIL import Image
    import pytesseract

    image = Image.open(
        io.BytesIO(data)
    )

    try:
        available = pytesseract.get_languages(
            config=""
        )

        lang = (
            "ara+eng"
            if "ara" in available
            else "eng"
        )

    except Exception:
        lang = "eng"

    return clean_text(
        pytesseract.image_to_string(
            image,
            lang=lang,
            config="--psm 6"
        )
    )


# ============================================================
# OCR للـ PDF
# ============================================================

@st.cache_data(show_spinner=False)
def ocr_pdf(data):

    import fitz
    from PIL import Image
    import pytesseract

    doc = fitz.open(
        stream=data,
        filetype="pdf"
    )

    output = []

    try:
        available = pytesseract.get_languages(
            config=""
        )

        lang = (
            "ara+eng"
            if "ara" in available
            else "eng"
        )

    except Exception:
        lang = "eng"

    for page in doc:

        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        image = Image.open(
            io.BytesIO(
                pix.tobytes("png")
            )
        )

        output.append(
            pytesseract.image_to_string(
                image,
                lang=lang,
                config="--psm 6"
            )
        )

    return clean_text(
        "\n".join(output)
    )


# ============================================================
# استخراج النص من الملف
# ============================================================

def extract_upload(upload):

    data = upload.getvalue()
    name = upload.name.lower()

    if name.endswith(".docx"):
        return extract_docx(data), "Word"

    if name.endswith(".pdf"):

        text = extract_pdf(data)

        if len(
            re.sub(r"\s", "", text)
        ) < 300:

            return (
                ocr_pdf(data),
                "PDF + OCR"
            )

        return text, "PDF نصي"

    return (
        ocr_image(data),
        "صورة + OCR"
    )


# ============================================================
# استخراج عنوان البحث
# ============================================================

def find_title(text):

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    for i, line in enumerate(lines[:100]):

        if re.search(
            r"^(عنوان|عنوان البحث|عنوان الدراسة|title)\b",
            line,
            re.I
        ):

            if i + 1 < len(lines):
                return lines[i + 1]

        if (
            "موضوع البحث" in line
            and i + 1 < len(lines)
        ):
            return lines[i + 1]

    for line in lines[:35]:

        if (
            4 <= len(line.split()) <= 30
            and not re.search(
                r"جامعة|كلية|قسم|الجمهورية|وزارة|السنة",
                line
            )
        ):
            return line

    return (
        lines[0]
        if lines
        else ""
    )


# ============================================================
# استخراج المقدمة أو قسم معين
# ============================================================

def section_excerpt(
    text,
    headings,
    limit=9000
):

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    start = None

    for i, line in enumerate(lines):

        normalized = re.sub(
            r"[\s:：]+$",
            "",
            line
        ).lower()

        if any(
            normalized.startswith(
                h.lower()
            )
            for h in headings
        ):
            start = i + 1
            break

    if start is None:
        return ""

    chunks = []

    for line in lines[start:]:

        if (
            chunks
            and re.match(
                r"^(مشكلة الدراسة|"
                r"تساؤلات الدراسة|"
                r"فروض الدراسة|"
                r"أهمية الدراسة|"
                r"أهداف الدراسة|"
                r"مصطلحات الدراسة|"
                r"حدود الدراسة|"
                r"منهج الدراسة|"
                r"المنهج|"
                r"الخاتمة)\b",
                line
            )
        ):
            break

        chunks.append(line)

        if len(
            " ".join(chunks)
        ) >= limit:
            break

    return " ".join(chunks)[:limit]


# ============================================================
# بناء Prompt التقييم
# ============================================================

def build_evaluation_prompt(text):

    criteria_text = "\n".join(
        f"{n}. [{cat}] {criterion}"
        for n, cat, criterion in CRITERIA
    )

    title = find_title(text)

    introduction = section_excerpt(
        text,
        [
            "المقدمة",
            "مقدمة",
            "تمهيد"
        ],
        10000
    )

    # الحد الأقصى للنص المرسل إلى API
    full_text = text[:65000]

    return f"""
أنت محكّم أكاديمي متخصص في مناهج البحث العلمي.

مهمتك تقييم خطة بحث عربية تقييماً أكاديمياً
دقيقاً ودلالياً.

مهم جداً:

قيّم فقط المعايير التالية:

12–51
68–71

ولا تقيم أو تحتسب أي معيار آخر.

عدد المعايير المعتمدة هو:
44 معياراً.

---------------------------------------
مقياس التقييم
---------------------------------------

0 = غير متحقق

1 = متحقق جزئياً

2 = متحقق بوضوح

---------------------------------------
لكل معيار
---------------------------------------

أعد:

score:
0 أو 1 أو 2

status:
غير متحقق
أو
متحقق جزئياً
أو
متحقق

evidence:
دليل حقيقي ومختصر من النص المرفوع.

إذا لم يوجد دليل:
"لا يوجد دليل كافٍ في النص"

explanation:
تحليل أكاديمي يشرح سبب الدرجة.

يجب ألا يكون مجرد إعادة صياغة للمعيار.

suggestion:
توصية عملية محددة لتحسين المعيار إذا كانت
الدرجة أقل من 2.

---------------------------------------
التحليل الأكاديمي العام
---------------------------------------

اكتب تحليلاً أكاديمياً مترابطاً في:

overall_analysis

ويجب أن يتضمن:

1. الحكم العام على الخطة.

2. تحليل عنوان البحث من حيث:
- الوضوح
- الاختصار
- التحديد
- الموضوع الرئيس
- المتغيرات
- الغموض

3. تحليل المقدمة من حيث:
- الانتقال من العام إلى الخاص
- عرض موضوع البحث
- تحديد المشكلة
- عرض العوامل والمتغيرات
- التوازن بين الإسهاب والإيجاز
- وضوح شخصية الباحث

4. تحليل مشكلة الدراسة ومبرراتها.

5. تحليل التساؤلات والفروض.

6. تحليل الأهمية والأهداف.

7. تحليل المصطلحات.

8. تحليل الحدود.

9. تحليل المنهج.

10. تحليل الترابط العام بين عناصر الخطة.

11. تحليل شخصية الباحث.

12. تحليل السلامة اللغوية والإملائية.

13. نقاط القوة.

14. نقاط الضعف.

15. توصيات عملية مرتبة حسب الأولوية.

---------------------------------------
قواعد مهمة
---------------------------------------

لا تحكم بناءً على وجود كلمة واحدة فقط.

افهم السياق والمعنى والترابط.

لا تخترع معلومات غير موجودة.

لا تنسب للباحث فكرة غير موجودة في النص.

لا تمنح 2 لمجرد وجود عنوان فرعي.

عند غياب الدليل اذكر ذلك صراحة.

لا تجعل التحليل مجرد تلخيص للدرجات.

لا تستخدم عبارات عامة مثل:
"الخطة جيدة"
دون تفسير.

اكتب بالعربية الأكاديمية الواضحة.

---------------------------------------
عنوان البحث
---------------------------------------

{title}

---------------------------------------
المقدمة
---------------------------------------

{introduction}

---------------------------------------
المعايير المسموح بها
---------------------------------------

{criteria_text}

---------------------------------------
نص خطة البحث
---------------------------------------

{full_text}

---------------------------------------
صيغة JSON المطلوبة
---------------------------------------

أعد JSON فقط:

{{
    "overall_analysis": "...",
    "results": [
        {{
            "id": 12,
            "score": 2,
            "status": "متحقق",
            "evidence": "...",
            "explanation": "...",
            "suggestion": "..."
        }}
    ]
}}

يجب أن تحتوي results على المعايير
المسموح بها فقط.
"""


# ============================================================
# تنظيف JSON
# ============================================================

def parse_json_response(content):

    content = content.strip()

    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.I
    )

    content = re.sub(
        r"\s*```$",
        "",
        content
    )

    try:
        return json.loads(content)

    except json.JSONDecodeError:

        start = content.find("{")
        end = content.rfind("}")

        if (
            start >= 0
            and end > start
        ):

            return json.loads(
                content[
                    start:end + 1
                ]
            )

        raise


# ============================================================
# توحيد نتيجة الذكاء الاصطناعي
# ============================================================

def normalize_ai_result(parsed):

    allowed_ids = {
        int(x[0])
        for x in CRITERIA
    }

    by_id = {}

    for item in parsed.get(
        "results",
        []
    ):

        try:
            item_id = int(
                item.get("id")
            )
        except Exception:
            continue

        if item_id in allowed_ids:
            by_id[item_id] = item

    rows = []

    for n, category, criterion in CRITERIA:

        item = by_id.get(
            n,
            {}
        )

        try:
            score = int(
                item.get(
                    "score",
                    0
                )
            )
        except Exception:
            score = 0

        score = max(
            0,
            min(2, score)
        )

        status = item.get(
            "status",
            [
                "غير متحقق",
                "متحقق جزئياً",
                "متحقق"
            ][score]
        )

        rows.append(
            {
                "id": n,
                "category": category,
                "criterion": criterion,
                "score": score,
                "status": status,
                "evidence": item.get(
                    "evidence",
                    "لا يوجد دليل كافٍ في النص"
                ),
                "explanation": item.get(
                    "explanation",
                    ""
                ),
                "suggestion": item.get(
                    "suggestion",
                    ""
                )
            }
        )

    return (
        rows,
        parsed.get(
            "overall_analysis",
            ""
        ).strip()
    )


# ============================================================
# OpenAI
# ============================================================

def evaluate_openai(
    text,
    api_key,
    model
):

    import requests

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",

        headers={
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json"
        },

        json={
            "model": model,

            "messages": [
                {
                    "role": "system",
                    "content":
                        "أجب بالعربية. "
                        "أعد JSON صالحاً فقط."
                },
                {
                    "role": "user",
                    "content":
                        build_evaluation_prompt(
                            text
                        )
                }
            ],

            "temperature": 0.1
        },

        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    content = (
        data["choices"][0]
        ["message"]["content"]
    )

    return normalize_ai_result(
        parse_json_response(content)
    )


# ============================================================
# Gemini
# ============================================================

def evaluate_gemini(
    text,
    api_key,
    model
):

    import requests

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )

    response = requests.post(
        url,

        headers={
            "Content-Type":
                "application/json"
        },

        json={
            "systemInstruction": {
                "parts": [
                    {
                        "text":
                            "أجب بالعربية "
                            "وبموضوعية. "
                            "أعد JSON فقط."
                    }
                ]
            },

            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text":
                                build_evaluation_prompt(
                                    text
                                )
                        }
                    ]
                }
            ],

            "generationConfig": {
                "temperature": 0.1
            }
        },

        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    content = (
        data["candidates"][0]
        ["content"]["parts"][0]
        ["text"]
    )

    return normalize_ai_result(
        parse_json_response(content)
    )


# ============================================================
# Claude
# ============================================================

def evaluate_claude(
    text,
    api_key,
    model
):

    import requests

    response = requests.post(
        "https://api.anthropic.com/v1/messages",

        headers={
            "x-api-key":
                api_key,
            "anthropic-version":
                "2023-06-01",
            "Content-Type":
                "application/json"
        },

        json={
            "model": model,

            "max_tokens": 16000,

            "system":
                "أجب بالعربية "
                "وبموضوعية. "
                "أعد JSON فقط.",

            "messages": [
                {
                    "role": "user",
                    "content":
                        build_evaluation_prompt(
                            text
                        )
                }
            ]
        },

        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    content = ""

    for block in data.get(
        "content",
        []
    ):

        if block.get(
            "type"
        ) == "text":

            content += block.get(
                "text",
                ""
            )

    return normalize_ai_result(
        parse_json_response(content)
    )


# ============================================================
# API متوافق مع OpenAI
# ============================================================

def evaluate_custom_api(
    text,
    api_key,
    model,
    base_url
):

    import requests

    if not base_url:
        raise ValueError(
            "يجب إدخال عنوان API."
        )

    url = (
        base_url.rstrip("/")
        + "/chat/completions"
    )

    response = requests.post(
        url,

        headers={
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json"
        },

        json={
            "model": model,

            "messages": [
                {
                    "role": "system",
                    "content":
                        "أجب بالعربية "
                        "وأعد JSON فقط."
                },
                {
                    "role": "user",
                    "content":
                        build_evaluation_prompt(
                            text
                        )
                }
            ],

            "temperature": 0.1
        },

        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    content = (
        data["choices"][0]
        ["message"]["content"]
    )

    return normalize_ai_result(
        parse_json_response(content)
    )


# ============================================================
# اختيار API
# ============================================================

def evaluate_ai(
    text,
    provider,
    api_key,
    model,
    base_url=""
):

    if not api_key:
        raise ValueError(
            f"لم يتم إدخال مفتاح API الخاص بـ {provider}."
        )

    if provider == "OpenAI":
        return evaluate_openai(
            text,
            api_key,
            model
        )

    if provider == "Gemini":
        return evaluate_gemini(
            text,
            api_key,
            model
        )

    if provider == "Claude":
        return evaluate_claude(
            text,
            api_key,
            model
        )

    if provider == "API متوافق مخصص":
        return evaluate_custom_api(
            text,
            api_key,
            model,
            base_url
        )

    raise ValueError(
        "مزود API غير معروف."
    )


# ============================================================
# حساب النتيجة
# ============================================================

def report(rows):

    total = sum(
        x["score"]
        for x in rows
    )

    maximum = len(rows) * 2

    if maximum == 0:
        return 0, 0, "لا توجد معايير"

    percentage = (
        total / maximum
    ) * 100

    if percentage >= 85:
        level = "ممتاز"

    elif percentage >= 70:
        level = "جيد جداً"

    elif percentage >= 55:
        level = "جيد"

    else:
        level = "يحتاج إلى تحسين"

    return (
        total,
        percentage,
        level
    )


# ============================================================
# التقرير Markdown
# ============================================================

def markdown_report(
    plan_name,
    mode,
    rows,
    analysis
):

    total, percentage, level = report(
        rows
    )

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    output = [
        "# تقرير تقييم خطة البحث العلمي",

        f"**الملف:** {plan_name}",

        f"**الوضع:** {mode}",

        f"**التاريخ:** {now}",

        "**نطاق التقييم:** "
        "المعايير 12–51 و68–71 فقط.",

        "",

        f"## النتيجة العامة: "
        f"{percentage:.1f}% — "
        f"{total}/{len(rows)*2} — "
        f"{level}",

        "",

        "## التحليل الأكاديمي",

        analysis,

        "",

        "## التقييم التفصيلي"
    ]

    for category in CATEGORIES:

        output.append(
            f"\n### {category}"
        )

        for row in rows:

            if row["category"] != category:
                continue

            output.extend(
                [
                    f"**المعيار {row['id']}: "
                    f"{row['criterion']}**",

                    f"- الدرجة: "
                    f"{row['score']}/2",

                    f"- الحكم: "
                    f"{row['status']}",

                    f"- الدليل: "
                    f"{row['evidence']}",

                    f"- التحليل: "
                    f"{row['explanation']}",

                    f"- التوصية: "
                    f"{row['suggestion']}",

                    ""
                ]
            )

    return "\n".join(output)


# ============================================================
# الشريط الجانبي
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ إعدادات التقييم"
    )

    mode = st.radio(
        "وضع التقييم",

        [
            "ذكاء اصطناعي دلالي",
            "فحص آلي أولي"
        ],

        index=0
    )

    st.divider()

    st.markdown(
        "**المعايير المعتمدة**"
    )

    st.write(
        "12–51 و68–71 فقط"
    )

    st.caption(
        f"{len(CRITERIA)} معياراً"
    )

    st.divider()


# ============================================================
# اختيار مزود API
# ============================================================

if mode == "ذكاء اصطناعي دلالي":

    provider = st.selectbox(
        "🤖 اختر مزود الذكاء الاصطناعي",

        [
            "OpenAI",
            "Gemini",
            "Claude",
            "API متوافق مخصص"
        ]
    )

    # --------------------------------------------------------
    # OpenAI
    # --------------------------------------------------------

    if provider == "OpenAI":

        api_key = st.text_input(
            "🔑 مفتاح OpenAI API",

            value=get_secret(
                "OPENAI_API_KEY"
            ),

            type="password"
        )

        model_options = [
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-5",
            "نموذج آخر"
        ]

        model_choice = st.selectbox(
            "🧠 نموذج OpenAI",
            model_options
        )

        if model_choice == "نموذج آخر":

            model = st.text_input(
                "اسم النموذج",
                value=get_secret(
                    "OPENAI_MODEL",
                    ""
                )
            )

        else:
            model = model_choice

        base_url = (
            "https://api.openai.com/v1"
        )

    # --------------------------------------------------------
    # Gemini
    # --------------------------------------------------------

    elif provider == "Gemini":

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",

            value=get_secret(
                "GEMINI_API_KEY"
            ),

            type="password"
        )

        model_options = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "نموذج آخر"
        ]

        model_choice = st.selectbox(
            "🧠 نموذج Gemini",
            model_options
        )

        if model_choice == "نموذج آخر":

            model = st.text_input(
                "اسم نموذج Gemini",
                value=get_secret(
                    "GEMINI_MODEL",
                    ""
                )
            )

        else:
            model = model_choice

        base_url = ""

    # --------------------------------------------------------
    # Claude
    # --------------------------------------------------------

    elif provider == "Claude":

        api_key = st.text_input(
            "🔑 مفتاح Claude API",

            value=get_secret(
                "ANTHROPIC_API_KEY"
            ),

            type="password"
        )

        model_options = [
            "claude-sonnet-4-5",
            "claude-opus-4-1",
            "نموذج آخر"
        ]

        model_choice = st.selectbox(
            "🧠 نموذج Claude",
            model_options
        )

        if model_choice == "نموذج آخر":

            model = st.text_input(
                "اسم نموذج Claude",
                value=get_secret(
                    "ANTHROPIC_MODEL",
                    ""
                )
            )

        else:
            model = model_choice

        base_url = ""

    # --------------------------------------------------------
    # API مخصص
    # --------------------------------------------------------

    else:

        api_key = st.text_input(
            "🔑 مفتاح API",

            value=get_secret(
                "CUSTOM_API_KEY"
            ),

            type="password"
        )

        model = st.text_input(
            "🧠 اسم النموذج",

            value=get_secret(
                "CUSTOM_API_MODEL"
            )
        )

        base_url = st.text_input(
            "🌐 عنوان API",

            value=get_secret(
                "CUSTOM_API_BASE_URL"
            )
        )

        st.caption(
            "يجب أن تكون الخدمة متوافقة "
            "مع OpenAI Chat Completions."
        )


# ============================================================
# رفع خطة البحث
# ============================================================

upload = st.file_uploader(

    "📤 حمّل خطة البحث",

    type=[
        "pdf",
        "docx",
        "png",
        "jpg",
        "jpeg",
        "webp"
    ],

    help=(
        "يمكن رفع ملف Word أو PDF "
        "أو صورة."
    )
)


# ============================================================
# معالجة الملف
# ============================================================

if upload:

    with st.spinner(
        "جارٍ استخراج النص..."
    ):

        try:

            text, extraction_mode = (
                extract_upload(upload)
            )

        except Exception as exc:

            st.error(
                f"تعذر استخراج النص: {exc}"
            )

            st.stop()

    if not text.strip():

        st.error(
            "لم يتم العثور على نص قابل للتحليل."
        )

        st.stop()

    st.success(
        f"تمت المعالجة: {upload.name} — "
        f"{extraction_mode} — "
        f"{len(text):,} حرف"
    )

    with st.expander(
        "🔎 معاينة النص المستخرج"
    ):

        st.text_area(
            "النص",
            text,
            height=300,
            label_visibility="collapsed"
        )


    # ========================================================
    # زر التقييم
    # ========================================================

    if st.button(
        "🚀 ابدأ التقييم الأكاديمي",
        type="primary",
        use_container_width=True
    ):

        try:

            # ------------------------------------------------
            # الذكاء الاصطناعي
            # ------------------------------------------------

            if mode == "ذكاء اصطناعي دلالي":

                if not api_key:

                    st.error(
                        "أدخل مفتاح API."
                    )

                    st.stop()

                with st.spinner(
                    "يجري تحليل خطة البحث "
                    "معياراً معياراً..."
                ):

                    rows, analysis = evaluate_ai(
                        text,
                        provider,
                        api_key,
                        model,
                        base_url
                    )

            # ------------------------------------------------
            # الفحص الأولي
            # ------------------------------------------------

            else:

                st.warning(
                    "الفحص الآلي الأولي "
                    "ليس بديلاً عن التحليل الدلالي."
                )

                rows = []

                for n, category, criterion in CRITERIA:

                    all_text = text.lower()

                    score = 0

                    keywords = {
                        12: [
                            "عنوان",
                            "موضوع"
                        ],

                        13: [
                            "عنوان"
                        ],

                        14: [
                            "أثر",
                            "دور",
                            "علاقة",
                            "تأثير"
                        ],

                        20: [
                            "مشكلة",
                            "إشكالية"
                        ],

                        24: [
                            "سؤال",
                            "تساؤل"
                        ],

                        28: [
                            "فرض",
                            "فرضية"
                        ],

                        32: [
                            "أهمية"
                        ],

                        36: [
                            "هدف",
                            "أهداف"
                        ],

                        40: [
                            "مصطلحات",
                            "تعريف"
                        ],

                        44: [
                            "حدود"
                        ],

                        48: [
                            "منهج"
                        ],

                        68: [
                            "دراسة",
                            "بحث"
                        ],

                        69: [
                            "دراسة",
                            "بحث"
                        ],

                        70: [
                            "دراسة",
                            "بحث"
                        ],

                        71: [
                            "دراسة",
                            "بحث"
                        ]
                    }

                    keys = keywords.get(
                        n,
                        []
                    )

                    hits = sum(
                        1
                        for key in keys
                        if key in all_text
                    )

                    if hits >= 2:
                        score = 2

                    elif hits == 1:
                        score = 1

                    rows.append(
                        {
                            "id": n,
                            "category": category,
                            "criterion": criterion,
                            "score": score,
                            "status": [
                                "غير متحقق",
                                "متحقق جزئياً",
                                "متحقق"
                            ][score],

                            "evidence":
                                "فحص آلي أولي "
                                "بالاعتماد على "
                                "مؤشرات لغوية.",

                            "explanation":
                                "هذه نتيجة أولية "
                                "ولا تمثل تحكيماً "
                                "أكاديمياً دلالياً.",

                            "suggestion":
                                "استخدم الذكاء "
                                "الاصطناعي الدلالي "
                                "لتحليل المعيار "
                                "بشكل أعمق."
                        }
                    )

                total, percentage, level = report(
                    rows
                )

                analysis = (
                    f"أظهر الفحص الأولي "
                    f"نتيجة قدرها "
                    f"{percentage:.1f}% "
                    f"({total}/{len(rows)*2}). "
                    "هذه النتيجة إرشادية فقط، "
                    "ولا تغني عن التحليل الدلالي "
                    "للنص."
                )


            # =================================================
            # حفظ النتيجة
            # =================================================

            st.session_state["rows"] = rows

            st.session_state[
                "analysis"
            ] = analysis

            st.session_state[
                "plan_name"
            ] = upload.name

            st.session_state[
                "text"
            ] = text

            st.session_state[
                "mode"
            ] = mode

            st.session_state[
                "provider"
            ] = provider if mode == (
                "ذكاء اصطناعي دلالي"
            ) else ""

            st.success(
                "✅ اكتمل التقييم بنجاح."
            )

        except Exception as exc:

            st.error(
                f"تعذر إكمال التقييم: {exc}"
            )

            with st.expander(
                "تفاصيل الخطأ"
            ):
                st.exception(exc)


# ============================================================
# عرض النتائج
# ============================================================

if "rows" in st.session_state:

    rows = st.session_state[
        "rows"
    ]

    analysis = st.session_state.get(
        "analysis",
        ""
    )

    total, percentage, level = report(
        rows
    )


    # ========================================================
    # النتائج الرئيسية
    # ========================================================

    st.divider()

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    col1.metric(
        "النتيجة",
        f"{percentage:.1f}%"
    )

    col2.metric(
        "النقاط",
        f"{total}/{len(rows)*2}"
    )

    col3.metric(
        "التقدير",
        level
    )

    col4.metric(
        "عدد المعايير",
        len(rows)
    )

    st.progress(
        percentage / 100
    )


    # ========================================================
    # التحليل الأكاديمي
    # ========================================================

    st.subheader(
        "📝 التحليل الأكاديمي المكتوب"
    )

    st.markdown(
        f"""
        <div class="card">
        {analysis.replace(chr(10), "<br>")}
        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # النتائج حسب المحور
    # ========================================================

    st.subheader(
        "📊 النتيجة حسب المحور"
    )

    summary = []

    for category in CATEGORIES:

        category_rows = [
            row
            for row in rows
            if row["category"] == category
        ]

        score = sum(
            row["score"]
            for row in category_rows
        )

        maximum = (
            len(category_rows) * 2
        )

        percentage_category = (
            score / maximum * 100
            if maximum
            else 0
        )

        summary.append(
            {
                "المحور":
                    category,

                "عدد المعايير":
                    len(category_rows),

                "النقاط":
                    f"{score}/{maximum}",

                "النسبة":
                    f"{percentage_category:.1f}%"
            }
        )

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # التقييم التفصيلي
    # ========================================================

    st.subheader(
        "🧾 التقييم التفصيلي"
    )

    for category in CATEGORIES:

        st.markdown(
            f"### {category}"
        )

        category_rows = [
            row
            for row in rows
            if row["category"] == category
        ]

        for row in category_rows:

            icon = [
                "🔴",
                "🟠",
                "🟢"
            ][row["score"]]

            with st.expander(
                f"{icon} المعيار "
                f"{row['id']}: "
                f"{row['criterion']} "
                f"— {row['status']}"
            ):

                st.write(
                    "**الدرجة:**",
                    f"{row['score']}/2"
                )

                st.write(
                    "**الدليل من الخطة:**"
                )

                st.info(
                    row.get(
                        "evidence",
                        "لا يوجد دليل"
                    )
                )

                st.write(
                    "**التحليل الأكاديمي:**"
                )

                st.write(
                    row.get(
                        "explanation",
                        ""
                    )
                )

                if row.get(
                    "suggestion"
                ):

                    st.write(
                        "**التوصية:**"
                    )

                    st.warning(
                        row["suggestion"]
                    )


    # ========================================================
    # الأولويات
    # ========================================================

    st.subheader(
        "🎯 الأولويات التي تحتاج إلى تحسين"
    )

    weak = [
        row
        for row in rows
        if row["score"] < 2
    ]

    if weak:

        for row in weak:

            st.markdown(
                f"""
                - **المعيار {row['id']} — "
                f"{row['criterion']}**: "
                f"{row.get('suggestion', 'يحتاج إلى مراجعة.')}"
                """
            )

    else:

        st.success(
            "🎉 لم تظهر معايير بحاجة إلى تحسين "
            "ضمن نطاق التقييم المحدد."
        )


    # ========================================================
    # إنشاء الملفات
    # ========================================================

    markdown = markdown_report(
        st.session_state.get(
            "plan_name",
            "خطة البحث"
        ),

        st.session_state.get(
            "mode",
            ""
        ),

        rows,

        analysis
    )

    json_report = {

        "plan":
            st.session_state.get(
                "plan_name"
            ),

        "mode":
            st.session_state.get(
                "mode"
            ),

        "provider":
            st.session_state.get(
                "provider",
                ""
            ),

        "criteria_scope":
            "12–51 و68–71 فقط",

        "criteria_count":
            len(rows),

        "total":
            total,

        "max_score":
            len(rows) * 2,

        "percentage":
            percentage,

        "level":
            level,

        "overall_analysis":
            analysis,

        "results":
            rows
    }


    # ========================================================
    # أزرار التحميل
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        st.download_button(
            "⬇️ تنزيل التقرير JSON",

            json.dumps(
                json_report,
                ensure_ascii=False,
                indent=2
            ),

            "تقرير_تقييم_خطة_البحث.json",

            "application/json",

            use_container_width=True
        )

    with col2:

        st.download_button(
            "⬇️ تنزيل التقرير Markdown",

            markdown,

            "تقرير_تقييم_خطة_البحث.md",

            "text/markdown",

            use_container_width=True
        )

else:

    st.info(
        "📤 حمّل خطة البحث ثم اضغط "
        "«ابدأ التقييم الأكاديمي»."
    )
````
