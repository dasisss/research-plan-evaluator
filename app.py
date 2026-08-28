import io
import json
import os
import re
from datetime import datetime

import streamlit as st
from criteria import CRITERIA, CATEGORIES, MAX_SCORE

st.set_page_config(
    page_title="مقيّم خطة البحث العلمي",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
html, body, [class*="css"] { font-family: Tahoma, Arial, sans-serif; }
.block-container { direction: rtl; max-width: 1450px; padding-top: 1rem; }
.hero { padding: 28px 30px; border-radius: 22px; background: linear-gradient(135deg,#173b63,#2f7f8f); color: white; margin-bottom: 18px; }
.hero h1 { font-size: 2.15rem; margin: 0 0 8px; }
.hero p { font-size: 1.03rem; margin: 0; opacity: .96; line-height: 1.8; }
.card { padding: 18px; border: 1px solid #dfe7eb; border-radius: 16px; background: #fff; margin-bottom: 12px; line-height: 1.9; }
.good { border-right: 5px solid #2e7d32; }
.warn { border-right: 5px solid #c78b22; }
.bad { border-right: 5px solid #b23a48; }
.muted { color: #65747e; font-size: .92rem; }
.small-title { font-weight: 700; font-size: 1.08rem; }
.stProgress > div > div > div > div { background-color: #2f7f8f; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>📚 مقيّم خطة البحث العلمي</h1>
  <p>تقييم دلالي وكتابي لخطة البحث وفق المعايير 12–51 و68–71 فقط، مع تفسير أكاديمي ودليل من النص وتوصيات عملية.</p>
</div>
""",
    unsafe_allow_html=True,
)


def get_secret(name, default=""):
    """Read a Streamlit secret first, then an environment variable."""
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value:
                return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


def clean_text(text):
    text = text.replace("\u200f", " ").replace("\u200e", " ").replace("\ufeff", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@st.cache_data(show_spinner=False)
def extract_docx(data):
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return clean_text("\n".join(parts))


@st.cache_data(show_spinner=False)
def extract_pdf(data):
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    return clean_text("\n".join(page.get_text("text") for page in doc))


@st.cache_data(show_spinner=False)
def ocr_image(data):
    from PIL import Image
    import pytesseract

    im = Image.open(io.BytesIO(data))
    try:
        lang = "ara+eng"
        available = pytesseract.get_languages(config="")
        if "ara" not in available:
            lang = "eng"
    except Exception:
        lang = "eng"
    return clean_text(pytesseract.image_to_string(im, lang=lang, config="--psm 6"))


@st.cache_data(show_spinner=False)
def ocr_pdf(data):
    import fitz
    from PIL import Image
    import pytesseract

    doc = fitz.open(stream=data, filetype="pdf")
    out = []
    try:
        lang = "ara+eng" if "ara" in pytesseract.get_languages(config="") else "eng"
    except Exception:
        lang = "eng"
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        out.append(pytesseract.image_to_string(im, lang=lang, config="--psm 6"))
    return clean_text("\n".join(out))


def extract_upload(upload):
    data = upload.getvalue()
    name = upload.name.lower()
    if name.endswith(".docx"):
        return extract_docx(data), "Word"
    if name.endswith(".pdf"):
        text = extract_pdf(data)
        if len(re.sub(r"\s", "", text)) < 300:
            return ocr_pdf(data), "PDF + OCR"
        return text, "PDF نصي"
    return ocr_image(data), "صورة + OCR"


def section_excerpt(text, headings, limit=9000):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    start = None
    for i, line in enumerate(lines):
        norm = re.sub(r"[\s:：]+$", "", line).lower()
        if any(norm.startswith(h.lower()) for h in headings):
            start = i + 1
            break
    if start is None:
        return ""
    chunks = []
    for line in lines[start:]:
        if len(chunks) and re.match(r"^(مشكلة الدراسة|تساؤلات الدراسة|فروض الدراسة|أهمية الدراسة|أهداف الدراسة|مصطلحات الدراسة|حدود الدراسة|منهج الدراسة|المنهج|الخاتمة)\b", line):
            break
        chunks.append(line)
        if len(" ".join(chunks)) >= limit:
            break
    return " ".join(chunks)[:limit]


def find_title(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    for i, line in enumerate(lines[:100]):
        if re.search(r"^(عنوان|عنوان البحث|عنوان الدراسة|title)\b", line, re.I):
            if i + 1 < len(lines):
                return lines[i + 1]
        if "موضوع البحث" in line and i + 1 < len(lines):
            return lines[i + 1]
    for line in lines[:35]:
        if 4 <= len(line.split()) <= 30 and not re.search(r"جامعة|كلية|قسم|الجمهورية|وزارة|السنة", line):
            return line
    return lines[0] if lines else ""


def heuristic_score(text, criterion):
    """فحص أولي فقط؛ لا يُقدَّم على أنه تحكيم دلالي."""
    n, _, _ = criterion
    alltext = text.lower()
    title = find_title(text)
    intro = section_excerpt(text, ["المقدمة", "مقدمة", "تمهيد"], 7000)
    words = len(intro.split())
    if n == 12:
        w = len(title.split())
        return 2 if 5 <= w <= 18 else (1 if title else 0)
    if n == 13:
        return 2 if title else 0
    if n == 14:
        markers = ["أثر", "دور", "علاقة", "تأثير", "استخدام", "مساهمة", "فاعلية", "مستوى"]
        return 2 if sum(x in title for x in markers) >= 2 else (1 if any(x in title for x in markers) else 0)
    if n == 15:
        ambiguous = ["هذا", "ذلك", "بعض", "عدة", "مختلفة", "متنوعة", "حديثة"]
        return 0 if any(x in title for x in ambiguous) else (2 if title else 0)
    if n in (16, 17, 18, 19):
        if n == 16:
            return 2 if words >= 100 else (1 if words >= 40 else 0)
        if n == 17:
            keys = ["البحث", "الدراسة", "الموضوع", "المتغير", "العوامل", "ظاهرة"]
            h = sum(k in intro for k in keys)
            return 2 if h >= 4 else (1 if h >= 2 else 0)
        if n == 18:
            return 2 if 120 <= words <= 1800 else (1 if words >= 50 else 0)
        return 2 if words >= 200 else (1 if words >= 80 else 0)
    # باقي المعايير: فحص كلمات مفتاحية عام، مع تنبيه المستخدم أنه ليس حكماً نهائياً.
    groups = {
        range(20, 24): ["مشكلة", "مبررات", "مصادر", "سؤال", "الإشكالية"],
        range(24, 28): ["سؤال", "تساؤل", "؟"],
        range(28, 32): ["فرض", "فرضية", "الفروض"],
        range(32, 36): ["أهمية", "علمية", "نظرية", "تطبيقية"],
        range(36, 40): ["أهداف", "هدف", "يهدف", "تهدف"],
        range(40, 44): ["مصطلحات", "التعريف", "اللغوي", "الاصطلاحي", "الإجرائي"],
        range(44, 48): ["حدود", "الموضوعية", "المكانية", "الزمانية", "البشرية"],
        range(48, 52): ["المنهج", "منهج الدراسة", "الوصفي", "التحليلي", "المقارن"],
        range(68, 72): ["الدراسة", "البحث"],
    }
    for rg, keys in groups.items():
        if n in rg:
            h = sum(k in alltext for k in keys)
            return 2 if h >= max(2, len(keys) // 2) else (1 if h else 0)
    return 0


def evaluate_heuristic(text):
    rows = []
    for cr in CRITERIA:
        s = heuristic_score(text, cr)
        rows.append({
            "id": cr[0], "category": cr[1], "criterion": cr[2], "score": s,
            "status": ["غير متحقق", "متحقق جزئياً", "متحقق"][s],
            "evidence": "فحص آلي أولي؛ لا يُعد تحكيماً دلالياً.",
            "explanation": "هذه النتيجة مؤشر أولي مبني على بنية النص ومؤشرات لغوية، وليست بديلاً عن التحليل الدلالي.",
            "suggestion": "استخدم وضع الذكاء الاصطناعي الدلالي للحصول على تفسير أكاديمي ودليل وتوصية."
        })
    return rows


def get_provider_config(provider):
    if provider == "OpenAI":
        return (
            get_secret("OPENAI_API_KEY"),
            get_secret("OPENAI_MODEL", "gpt-4.1-mini"),
            "https://api.openai.com/v1"
        )

    if provider == "Gemini":
        return (
            get_secret("GEMINI_API_KEY"),
            get_secret("GEMINI_MODEL", "gemini-3.7-flash"),
            ""
        )

    if provider == "Claude":
        return (
            get_secret("ANTHROPIC_API_KEY"),
            get_secret("ANTHROPIC_MODEL", "claude-sonnet-5"),
            ""
        )

    return (
        get_secret("CUSTOM_API_KEY"),
        get_secret("CUSTOM_API_MODEL", ""),
        get_secret("CUSTOM_API_BASE_URL", "")
    )


def parse_json_response(content):
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start:end + 1])
        raise


def build_evaluation_prompt(text):
    criteria_text = "\n".join(
        f"{n}. [{cat}] {c}" for n, cat, c in CRITERIA
    )

    title = find_title(text)
    intro = section_excerpt(
        text,
        ["المقدمة", "مقدمة", "تمهيد"],
        10000
    )

    full_text = text[:65000]

    return f"""
أنت محكّم أكاديمي متخصص في مناهج البحث العلمي،
وتعمل على تقييم خطة بحث عربية.

مهمتك الأساسية ليست إعطاء أرقام فقط، بل كتابة تحليل
أكاديمي تفسيري واضح يمكن للباحث الاستفادة منه في
إعادة صياغة خطته.

قيّم الخطة حصراً وفق المعايير 12–51 و68–71 المدرجة أدناه.
ممنوع تقييم أو احتساب أي معيار خارج هذه القائمة.

مقياس كل معيار:

0 = غير متحقق
1 = متحقق جزئياً
2 = متحقق بوضوح

لكل معيار أعد:

- score: 0 أو 1 أو 2
- status: غير متحقق / متحقق جزئياً / متحقق
- evidence: دليل موجز من النص المرفوع نفسه، أو
  "لا يوجد دليل كافٍ في النص"
- explanation: تحليل يشرح لماذا استحق النص هذه الدرجة،
  وليس مجرد إعادة صياغة المعيار
- suggestion: اقتراح عملي ومحدد للتحسين إذا كانت الدرجة أقل من 2

ثم اكتب overall_analysis في فقرات عربية مترابطة،
ويجب أن يتضمن:

1. الحكم العام على مستوى الخطة ضمن المعايير المحددة.
2. تحليلاً مستقلاً للعنوان: الوضوح، الاختصار، التحديد،
   الموضوع الرئيس، المتغيرات، والغموض.
3. تحليلاً مستقلاً للمقدمة: الانتقال من العام إلى الخاص،
   عرض فكرة البحث والموضوع والعوامل المرتبطة، والتوازن
   بين الإسهاب والإيجاز، ووضوح شخصية الباحث.
4. تحليلاً لمشكلة الدراسة ومبرراتها ومصادر الوصول إليها
   وصياغة نهايتها.
5. تحليلاً للتساؤلات والفروض ومدى ترابطها.
6. تحليلاً للأهمية والأهداف ومدى الاتساق بينها وبين
   مشكلة الدراسة.
7. تحليلاً للمصطلحات والحدود والمنهج.
8. تحليلاً للترابط العام، والتنسيق، وشخصية الباحث،
   والسلامة الإملائية والنحوية.
9. نقاط القوة.
10. نقاط الضعف.
11. توصيات عملية مرتبة من الأكثر أهمية إلى الأقل أهمية.

قواعد صارمة:

- لا تحكم من وجود كلمة واحدة فقط؛ افهم السياق والمعنى والترابط.
- لا تخترع معلومات غير موجودة في الخطة.
- لا تنسب للباحث فكرة لا تظهر في النص.
- لا تعط درجة 2 لمجرد وجود عنوان فرعي؛ يجب أن يكون
  المضمون مستوفياً للمعيار.
- عند غياب الدليل، قل صراحة إنه غير ظاهر في النص.
- لا تجعل التحليل الكتابي مجرد تلخيص للدرجات.
- لا تستخدم عبارات عامة مثل "الخطة جيدة" دون تفسير.
- اكتب بالعربية الأكاديمية الواضحة.

العنوان المستخرج آلياً:
{title}

المقدمة المستخرجة آلياً إن أمكن:
{intro}

المعايير المسموح بها فقط:
{criteria_text}

نص خطة البحث:
{full_text}

أعد JSON فقط بهذا الشكل:

{{
  "overall_analysis": "تحليل أكاديمي متعدد الفقرات، غني بالتفسير، وليس قائمة درجات فقط.",
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
"""


def normalize_ai_result(parsed):
    by_id = {
        int(x["id"]): x
        for x in parsed.get("results", [])
        if str(x.get("id", "")).isdigit()
    }

    rows = []

    for n, cat, criterion in CRITERIA:
        item = by_id.get(n, {})

        try:
            score = int(item.get("score", 0))
        except Exception:
            score = 0

        score = max(0, min(2, score))

        rows.append({
            "id": n,
            "category": cat,
            "criterion": criterion,
            "score": score,
            "status": item.get(
                "status",
                ["غير متحقق", "متحقق جزئياً", "متحقق"][score]
            ),
            "evidence": item.get(
                "evidence",
                "لا يوجد دليل كافٍ في النص"
            ),
            "explanation": item.get("explanation", ""),
            "suggestion": item.get("suggestion", ""),
        })

    return rows, parsed.get("overall_analysis", "").strip()


def evaluate_openai(text, api_key, model):
    import requests

    prompt = build_evaluation_prompt(text)

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "أجب بالعربية وبموضوعية. "
                    "أعد JSON صالحاً فقط دون Markdown."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    return normalize_ai_result(
        parse_json_response(content)
    )


def evaluate_gemini(text, api_key, model):
    import requests

    prompt = build_evaluation_prompt(text)

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )

    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "أجب بالعربية وبموضوعية. "
                        "أعد JSON صالحاً فقط دون Markdown."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
        },
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json"
        },
        json=body,
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()

    content = (
        data["candidates"][0]["content"]["parts"][0]["text"]
    )

    return normalize_ai_result(
        parse_json_response(content)
    )


def evaluate_claude(text, api_key, model):
    import requests

    prompt = build_evaluation_prompt(text)

    url = "https://api.anthropic.com/v1/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "max_tokens": 16000,
        "system": (
            "أجب بالعربية وبموضوعية. "
            "أعد JSON صالحاً فقط دون Markdown."
        ),
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()

    content = ""

    for block in data.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")

    return normalize_ai_result(
        parse_json_response(content)
    )


def evaluate_custom_api(text, api_key, model, base_url):
    import requests

    if not base_url:
        raise ValueError(
            "يجب إدخال عنوان API للخدمة المخصصة."
        )

    prompt = build_evaluation_prompt(text)

    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "أجب بالعربية وبموضوعية. "
                    "أعد JSON صالحاً فقط دون Markdown."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    return normalize_ai_result(
        parse_json_response(content)
    )


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
        f"مزود غير معروف: {provider}"
    )

def report(rows):
    total = sum(x["score"] for x in rows)
    pct = total / MAX_SCORE * 100
    level = "ممتاز" if pct >= 85 else "جيد جداً" if pct >= 70 else "جيد" if pct >= 55 else "يحتاج إلى تحسين"
    return total, pct, level


def markdown_report(plan_name, mode, rows, analysis):
    total, pct, level = report(rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [
        "# تقرير تقييم خطة البحث العلمي",
        f"**الملف:** {plan_name}",
        f"**الوضع:** {mode}",
        f"**تاريخ التقرير:** {now}",
        "**نطاق التقييم:** المعايير 12–51 و68–71 فقط (44 معياراً).",
        "",
        f"## النتيجة العامة: {pct:.1f}% — {total}/{MAX_SCORE} — {level}",
        "",
        "## التحليل الأكاديمي المكتوب",
        analysis,
        "",
        "## التقييم التفصيلي",
    ]
    for cat in CATEGORIES:
        out.append(f"\n### {cat}")
        for r in [x for x in rows if x["category"] == cat]:
            out += [
                f"**المعيار {r['id']}: {r['criterion']}**",
                f"- الحكم: {r['status']} ({r['score']}/2)",
                f"- الدليل: {r.get('evidence','')}",
                f"- التفسير: {r.get('explanation','')}",
                f"- التوصية: {r.get('suggestion','')}",
                "",
            ]
    return "\n".join(out)


with st.sidebar:
    st.header("⚙️ إعدادات التقييم")
    mode = st.radio("وضع التقييم", ["ذكاء اصطناعي دلالي", "فحص آلي أولي"], index=0)
    st.divider()
    st.markdown("**المعايير المعتمدة**")
    st.write("12–51 و68–71 فقط")
    st.caption(f"44 معياراً — الحد الأقصى {MAX_SCORE} نقطة")
    st.divider()
if mode == "ذكاء اصطناعي دلالي":

    provider = st.selectbox(
        "🤖 مزود الذكاء الاصطناعي",
        [
            "OpenAI",
            "Gemini",
            "Claude",
            "API متوافق مخصص",
        ],
        index=0,
    )

    if provider == "OpenAI":

        api_key = st.text_input(
            "🔑 مفتاح OpenAI API",
            value=get_secret("OPENAI_API_KEY"),
            type="password",
            help="ضع المفتاح في Streamlit Secrets باسم OPENAI_API_KEY."
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
                value=get_secret("OPENAI_MODEL", "")
            )
        else:
            model = model_choice

        base_url = "https://api.openai.com/v1"

        st.caption(
            "سيتم استخدام OpenAI مباشرة."
        )

    elif provider == "Gemini":

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            value=get_secret("GEMINI_API_KEY"),
            type="password",
            help="ضع المفتاح في Streamlit Secrets باسم GEMINI_API_KEY."
        )

        model_options = [
            "gemini-3.7-flash",
            "gemini-3.7-pro",
            "نموذج آخر"
        ]

        model_choice = st.selectbox(
            "🧠 نموذج Gemini",
            model_options
        )

        if model_choice == "نموذج آخر":
            model = st.text_input(
                "اسم نموذج Gemini",
                value=get_secret("GEMINI_MODEL", "")
            )
        else:
            model = model_choice

        base_url = ""

        st.caption(
            "سيتم الاتصال بواجهة Gemini الرسمية مباشرة."
        )

    elif provider == "Claude":

        api_key = st.text_input(
            "🔑 مفتاح Claude API",
            value=get_secret("ANTHROPIC_API_KEY"),
            type="password",
            help="ضع المفتاح في Streamlit Secrets باسم ANTHROPIC_API_KEY."
        )

        model_options = [
            "claude-sonnet-5",
            "claude-opus-5",
            "نموذج آخر"
        ]

        model_choice = st.selectbox(
            "🧠 نموذج Claude",
            model_options
        )

        if model_choice == "نموذج آخر":
            model = st.text_input(
                "اسم نموذج Claude",
                value=get_secret("ANTHROPIC_MODEL", "")
            )
        else:
            model = model_choice

        base_url = ""

        st.caption(
            "سيتم الاتصال بواجهة Claude الرسمية مباشرة."
        )

    else:

        api_key = st.text_input(
            "🔑 مفتاح API",
            value=get_secret("CUSTOM_API_KEY"),
            type="password"
        )

        model = st.text_input(
            "🧠 النموذج",
            value=get_secret("CUSTOM_API_MODEL", "")
        )

        base_url = st.text_input(
            "🌐 عنوان API",
            value=get_secret("CUSTOM_API_BASE_URL", "")
        )

        st.caption(
            "يجب أن تكون الخدمة متوافقة مع OpenAI Chat Completions."
        )

upload = st.file_uploader(
    "📤 حمّل خطة البحث",
    type=["pdf", "docx", "png", "jpg", "jpeg", "webp"],
    help="PDF نصي أو ممسوح ضوئياً، Word، أو صورة.",
)

if upload:
    with st.spinner("جارٍ استخراج النص من الملف..."):
        try:
            text, extraction_mode = extract_upload(upload)
        except Exception as exc:
            st.error(f"تعذر استخراج النص: {exc}")
            st.stop()

    if not text.strip():
        st.error("لم يتم العثور على نص قابل للتحليل. جرّب ملفاً أوضح أو صورة بدقة أعلى.")
        st.stop()

    st.success(f"تمت المعالجة: {upload.name} — {extraction_mode} — {len(text):,} حرف")
    with st.expander("🔎 معاينة النص المستخرج"):
        st.text_area("النص", text, height=300, label_visibility="collapsed")

    if st.button("🚀 ابدأ التقييم الأكاديمي", type="primary", use_container_width=True):
        try:
            if mode == "ذكاء اصطناعي دلالي":
                if not api_key:
                    st.error("أدخل مفتاح API في الشريط الجانبي أو ضعه في Streamlit Secrets.")
                    st.stop()
                with st.spinner("يجري الآن تحليل الخطة معياراً معياراً وكتابة التقرير الأكاديمي..."):
rows, analysis = evaluate_ai(
    text,
    provider,
    api_key,
    model,
    base_url
)            else:
                with st.spinner("جارٍ إجراء الفحص الآلي الأولي..."):
                    rows = evaluate_heuristic(text)
                    total, pct, level = report(rows)
                    analysis = (
                        f"هذا تقرير فحص أولي وليس تحكيماً دلالياً. حصلت الخطة على {pct:.1f}% ({total}/{MAX_SCORE}). "
                        "للحكم الأكاديمي الحقيقي، يُنصح بتفعيل وضع الذكاء الاصطناعي الدلالي، لأنه يقرأ المعنى والسياق ويكتب تفسيراً ودليلاً وتوصيات لكل معيار."
                    )
            st.session_state.update(
                rows=rows,
                analysis=analysis,
                plan_name=upload.name,
                text=text,
                mode=mode,
            )
            st.success("اكتمل التقييم.")
        except Exception as exc:
            st.error(f"تعذر إكمال التقييم: {exc}")
            st.exception(exc)


if "rows" in st.session_state:
    rows = st.session_state["rows"]
    analysis = st.session_state.get("analysis", "")
    total, pct, level = report(rows)

    a, b, c, d = st.columns(4)
    a.metric("النتيجة", f"{pct:.1f}%")
    b.metric("النقاط", f"{total}/{MAX_SCORE}")
    c.metric("التقدير", level)
    d.metric("المعايير", len(CRITERIA))
    st.progress(pct / 100)

    st.subheader("📝 التحليل الأكاديمي المكتوب")
    st.markdown(f'<div class="card">{analysis.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    st.subheader("📊 النتيجة حسب المحور")
    summary = []
    for cat, items in CATEGORIES.items():
        rr = [r for r in rows if r["category"] == cat]
        sc = sum(r["score"] for r in rr)
        mx = len(rr) * 2
        summary.append({"المحور": cat, "عدد المعايير": len(rr), "النقاط": f"{sc}/{mx}", "النسبة": f"{sc/mx*100:.1f}%"})
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("🧾 التقييم التفصيلي")
    for cat in CATEGORIES:
        st.markdown(f"### {cat}")
        for r in [x for x in rows if x["category"] == cat]:
            icon = ["🔴", "🟠", "🟢"][r["score"]]
            with st.expander(f"{icon} المعيار {r['id']}: {r['criterion']} — {r['status']}"):
                st.write("**الدرجة:**", f"{r['score']}/2")
                st.write("**الدليل من الخطة:**", r.get("evidence", "لا يوجد"))
                st.write("**التحليل:**", r.get("explanation", ""))
                if r.get("suggestion"):
                    st.write("**التوصية:**", r["suggestion"])

    st.subheader("🎯 الأولويات التي تحتاج إلى تحسين")
    weak = [r for r in rows if r["score"] < 2]
    if weak:
        for r in weak:
            st.markdown(f"- **المعيار {r['id']} — {r['criterion']}:** {r.get('suggestion') or 'يحتاج إلى مراجعة.'}")
    else:
        st.success("لم تظهر معايير بحاجة إلى تحسين ضمن النطاق المحدد.")

    md = markdown_report(st.session_state.get("plan_name", "خطة البحث"), st.session_state.get("mode", ""), rows, analysis)
    payload = {
        "plan": st.session_state.get("plan_name"),
        "mode": st.session_state.get("mode"),
        "criteria_scope": "12–51 و68–71 فقط",
        "criteria_count": len(CRITERIA),
        "total": total,
        "max_score": MAX_SCORE,
        "percentage": pct,
        "level": level,
        "overall_analysis": analysis,
        "results": rows,
    }

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ تنزيل التقرير JSON",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "تقرير_تقييم_خطة_البحث.json",
            "application/json",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "⬇️ تنزيل التقرير المكتوب Markdown",
            md,
            "تقرير_تقييم_خطة_البحث.md",
            "text/markdown",
            use_container_width=True,
        )
else:
    st.info("حمّل خطة البحث ثم اضغط «ابدأ التقييم الأكاديمي». في الوضع الدلالي سيُكتب تحليل أكاديمي، وليس مجرد درجات.")
