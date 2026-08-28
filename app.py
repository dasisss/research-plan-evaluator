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

# CSS

# ============================================================

st.markdown(
""" <style>
.block-container {
direction: rtl;
max-width: 1450px;
padding-top: 1rem;
}

```
.hero {
    padding: 28px 32px;
    border-radius: 20px;
    background: linear-gradient(135deg, #173b63, #2f7f8f);
    color: white;
    margin-bottom: 22px;
}

.hero h1 {
    margin: 0;
    font-size: 2.2rem;
}

.hero p {
    margin-top: 10px;
    line-height: 1.9;
    font-size: 1.05rem;
}

.result-card {
    padding: 20px;
    border-radius: 16px;
    border: 1px solid #dce5e9;
    background: white;
    margin-bottom: 15px;
    line-height: 1.9;
}

.criterion-card {
    padding: 15px;
    border-radius: 12px;
    background: #f8fafb;
    border-right: 5px solid #2f7f8f;
    margin-bottom: 10px;
}

.small-note {
    color: #667781;
    font-size: 0.9rem;
}
</style>
""",
unsafe_allow_html=True,
```

)

# ============================================================

# العنوان

# ============================================================

st.markdown(
""" <div class="hero"> <h1>📚 مقيّم خطة البحث العلمي</h1> <p>
نظام ذكي لتقييم خطة البحث وفق المعايير المعتمدة
من 12 إلى 51 ومن 68 إلى 71 فقط، مع تقديم
درجة رقمية وتحليل أكاديمي مكتوب ودليل وتوصيات. </p> </div>
""",
unsafe_allow_html=True,
)

# ============================================================

# أدوات مساعدة

# ============================================================

def get_secret(name, default=""):
try:
if name in st.secrets:
return str(st.secrets[name])
except Exception:
pass

```
return os.getenv(name, default)
```

def clean_text(text):
text = text.replace("\u200f", " ")
text = text.replace("\u200e", " ")
text = text.replace("\ufeff", " ")

```
text = re.sub(r"[ \t]+", " ", text)
text = re.sub(r"\n{3,}", "\n\n", text)

return text.strip()
```

# ============================================================

# استخراج Word

# ============================================================

@st.cache_data(show_spinner=False)
def extract_docx(data):

```
from docx import Document

document = Document(
    io.BytesIO(data)
)

parts = []

for paragraph in document.paragraphs:
    if paragraph.text.strip():
        parts.append(
            paragraph.text.strip()
        )

for table in document.tables:

    for row in table.rows:

        cells = [
            cell.text.strip()
            for cell in row.cells
        ]

        if any(cells):
            parts.append(
                " | ".join(cells)
            )

return clean_text(
    "\n".join(parts)
)
```

# ============================================================

# استخراج PDF

# ============================================================

@st.cache_data(show_spinner=False)
def extract_pdf(data):

```
import fitz

document = fitz.open(
    stream=data,
    filetype="pdf"
)

pages = []

for page in document:
    pages.append(
        page.get_text("text")
    )

return clean_text(
    "\n".join(pages)
)
```

# ============================================================

# OCR للصورة

# ============================================================

@st.cache_data(show_spinner=False)
def extract_image(data):

```
from PIL import Image
import pytesseract

image = Image.open(
    io.BytesIO(data)
)

try:
    languages = pytesseract.get_languages(
        config=""
    )

    language = (
        "ara+eng"
        if "ara" in languages
        else "eng"
    )

except Exception:
    language = "eng"

text = pytesseract.image_to_string(
    image,
    lang=language,
    config="--psm 6"
)

return clean_text(text)
```

# ============================================================

# OCR للـ PDF المصور

# ============================================================

@st.cache_data(show_spinner=False)
def extract_pdf_ocr(data):

```
import fitz
from PIL import Image
import pytesseract

document = fitz.open(
    stream=data,
    filetype="pdf"
)

try:
    languages = pytesseract.get_languages(
        config=""
    )

    language = (
        "ara+eng"
        if "ara" in languages
        else "eng"
    )

except Exception:
    language = "eng"

pages = []

for page in document:

    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(2, 2),
        alpha=False
    )

    image = Image.open(
        io.BytesIO(
            pixmap.tobytes("png")
        )
    )

    pages.append(
        pytesseract.image_to_string(
            image,
            lang=language,
            config="--psm 6"
        )
    )

return clean_text(
    "\n".join(pages)
)
```

# ============================================================

# اختيار طريقة الاستخراج

# ============================================================

def extract_file(uploaded_file):

```
data = uploaded_file.getvalue()
filename = uploaded_file.name.lower()

if filename.endswith(".docx"):

    return (
        extract_docx(data),
        "Word"
    )

if filename.endswith(".pdf"):

    text = extract_pdf(data)

    compact = re.sub(
        r"\s",
        "",
        text
    )

    if len(compact) < 300:

        return (
            extract_pdf_ocr(data),
            "PDF مصور + OCR"
        )

    return (
        text,
        "PDF"
    )

return (
    extract_image(data),
    "صورة + OCR"
)
```

# ============================================================

# عنوان البحث

# ============================================================

def find_title(text):

```
lines = [
    line.strip()
    for line in text.splitlines()
    if line.strip()
]

patterns = [
    r"^عنوان البحث",
    r"^عنوان الدراسة",
    r"^عنوان",
    r"^title"
]

for index, line in enumerate(lines[:100]):

    for pattern in patterns:

        if re.search(
            pattern,
            line,
            re.IGNORECASE
        ):

            if index + 1 < len(lines):
                return lines[index + 1]

if lines:
    return lines[0]

return "غير محدد"
```

# ============================================================

# استخراج المقدمة

# ============================================================

def get_introduction(text):

```
lines = [
    line.strip()
    for line in text.splitlines()
    if line.strip()
]

start = None

headings = [
    "المقدمة",
    "مقدمة",
    "تمهيد"
]

for i, line in enumerate(lines):

    if any(
        line.startswith(h)
        for h in headings
    ):

        start = i + 1
        break

if start is None:
    return ""

result = []

stop_words = [
    "مشكلة الدراسة",
    "إشكالية الدراسة",
    "تساؤلات الدراسة",
    "أسئلة الدراسة",
    "فرضيات الدراسة",
    "فروض الدراسة",
    "أهمية الدراسة",
    "أهداف الدراسة",
    "مصطلحات الدراسة",
    "حدود الدراسة",
    "منهج الدراسة"
]

for line in lines[start:]:

    if any(
        line.startswith(stop)
        for stop in stop_words
    ):
        break

    result.append(line)

    if len(
        " ".join(result)
    ) >= 9000:
        break

return " ".join(result)[:9000]
```

# ============================================================

# بناء قائمة المعايير

# ============================================================

def criteria_for_prompt():

```
result = []

for number, category, criterion in CRITERIA:

    result.append(
        f"{number}. {category}: {criterion}"
    )

return "\n".join(result)
```

# ============================================================

# Prompt

# ============================================================

def build_prompt(text):

```
title = find_title(text)
introduction = get_introduction(text)

return f"""
```

أنت أستاذ جامعي ومحكّم متخصص في مناهج البحث العلمي.

مهمتك تقييم خطة البحث المرفوعة وفق المعايير
المعتمدة في النظام.

هام جداً:

يجب تقييم المعايير التالية فقط:

12 إلى 51
و
68 إلى 71

ولا تستخدم أي معيار آخر.

عدد المعايير:
{len(CRITERIA)}

الدرجة لكل معيار:

0 = غير متحقق
1 = متحقق جزئياً
2 = متحقق بوضوح

لا تمنح درجة اعتماداً على وجود كلمة مفتاحية فقط.
يجب قراءة السياق وفهم المعنى.

لا تخترع معلومات.

إذا لم تجد دليلاً واضحاً في النص، قل:
"لا يوجد دليل كافٍ في النص."

لكل معيار أعد:

id
score
status
evidence
explanation
suggestion

حيث:

status:

* غير متحقق
* متحقق جزئياً
* متحقق

evidence:
دليل مختصر وحقيقي من خطة البحث.

explanation:
تحليل أكاديمي يبرر الدرجة.

suggestion:
اقتراح عملي لتحسين المعيار إذا كانت الدرجة أقل من 2.

==================================================
التحليل الأكاديمي العام
=======================

اكتب تحليلاً أكاديمياً متكاملاً في الحقل:

overall_analysis

ويجب أن يتناول:

1. جودة عنوان البحث.
2. المقدمة.
3. مشكلة الدراسة.
4. تساؤلات الدراسة.
5. فروض الدراسة.
6. أهمية الدراسة.
7. أهداف الدراسة.
8. المصطلحات.
9. حدود الدراسة.
10. منهج البحث.
11. الترابط بين عناصر الخطة.
12. شخصية الباحث.
13. اللغة والأسلوب.
14. نقاط القوة.
15. نقاط الضعف.
16. أهم التعديلات المقترحة.

لا تكتف بتلخيص الدرجات.

==================================================
عنوان البحث
===========

{title}

==================================================
المقدمة
=======

{introduction}

==================================================
المعايير
========

{criteria_for_prompt()}

==================================================
خطة البحث
=========

{text[:70000]}

==================================================
صيغة الإجابة
============

أعد JSON صالحاً فقط بالشكل التالي:

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

يجب أن يحتوي results على جميع المعايير الـ {len(CRITERIA)}
دون إضافة أي معيار آخر.
"""

# ============================================================

# قراءة JSON

# ============================================================

def parse_json(text):

````
text = text.strip()

text = re.sub(
    r"^```json\s*",
    "",
    text,
    flags=re.IGNORECASE
)

text = re.sub(
    r"^```\s*",
    "",
    text
)

text = re.sub(
    r"\s*```$",
    "",
    text
)

try:
    return json.loads(text)

except Exception:

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "لم يتم العثور على JSON صالح في استجابة النموذج."
        )

    return json.loads(
        text[start:end + 1]
    )
````

# ============================================================

# توحيد النتائج

# ============================================================

def normalize_results(data):

```
allowed = {
    item[0]: item
    for item in CRITERIA
}

received = {}

for item in data.get(
    "results",
    []
):

    try:
        number = int(
            item.get("id")
        )
    except Exception:
        continue

    if number not in allowed:
        continue

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

    category = allowed[number][1]
    criterion = allowed[number][2]

    status = item.get(
        "status"
    )

    if not status:

        status = [
            "غير متحقق",
            "متحقق جزئياً",
            "متحقق"
        ][score]

    received[number] = {
        "id": number,
        "category": category,
        "criterion": criterion,
        "score": score,
        "status": status,
        "evidence": item.get(
            "evidence",
            "لا يوجد دليل كافٍ في النص."
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

results = []

for number, category, criterion in CRITERIA:

    if number in received:

        results.append(
            received[number]
        )

    else:

        results.append(
            {
                "id": number,
                "category": category,
                "criterion": criterion,
                "score": 0,
                "status": "غير متحقق",
                "evidence":
                    "لم يقدم النموذج دليلاً لهذا المعيار.",
                "explanation":
                    "لم يتم الحصول على نتيجة كافية.",
                "suggestion":
                    "يرجى مراجعة هذا المعيار في خطة البحث."
            }
        )

return (
    results,
    data.get(
        "overall_analysis",
        "لم يتم توفير تحليل عام."
    )
)
```

# ============================================================

# OpenAI

# ============================================================

def call_openai(
text,
api_key,
model
):

```
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
                    "أنت محكّم أكاديمي. "
                    "أجب بالعربية وأعد JSON فقط."
            },
            {
                "role": "user",
                "content":
                    build_prompt(text)
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
    ["message"]
    ["content"]
)

return normalize_results(
    parse_json(content)
)
```

# ============================================================

# Gemini

# ============================================================

def call_gemini(
text,
api_key,
model
):

```
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
                        "أنت محكّم أكاديمي. "
                        "أجب بالعربية وأعد JSON فقط."
                }
            ]
        },

        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text":
                            build_prompt(text)
                    }
                ]
            }
        ],

        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType":
                "application/json"
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

return normalize_results(
    parse_json(content)
)
```

# ============================================================

# Claude

# ============================================================

def call_claude(
text,
api_key,
model
):

```
import requests

response = requests.post(

    "https://api.anthropic.com/v1/messages",

    headers={
        "x-api-key":
            api_key,
        "anthropic-version":
            "2023-06-01",
        "content-type":
            "application/json"
    },

    json={
        "model": model,
        "max_tokens": 16000,

        "system":
            "أنت محكّم أكاديمي. "
            "أجب بالعربية وأعد JSON فقط.",

        "messages": [
            {
                "role": "user",
                "content":
                    build_prompt(text)
            }
        ]
    },

    timeout=300
)

response.raise_for_status()

data = response.json()

parts = []

for block in data.get(
    "content",
    []
):

    if block.get("type") == "text":
        parts.append(
            block.get(
                "text",
                ""
            )
        )

content = "\n".join(parts)

return normalize_results(
    parse_json(content)
)
```

# ============================================================

# API مخصص متوافق مع OpenAI

# ============================================================

def call_custom(
text,
api_key,
model,
base_url
):

```
import requests

if not base_url:
    raise ValueError(
        "أدخل عنوان API المخصص."
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
                    "أجب بالعربية وأعد JSON فقط."
            },
            {
                "role": "user",
                "content":
                    build_prompt(text)
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
    ["message"]
    ["content"]
)

return normalize_results(
    parse_json(content)
)
```

# ============================================================

# تنفيذ API

# ============================================================

def evaluate(
text,
provider,
api_key,
model,
base_url=""
):

```
if not api_key:
    raise ValueError(
        "لم يتم إدخال مفتاح API."
    )

if provider == "OpenAI":

    return call_openai(
        text,
        api_key,
        model
    )

if provider == "Gemini":

    return call_gemini(
        text,
        api_key,
        model
    )

if provider == "Claude":

    return call_claude(
        text,
        api_key,
        model
    )

if provider == "API مخصص":

    return call_custom(
        text,
        api_key,
        model,
        base_url
    )

raise ValueError(
    "مزود API غير معروف."
)
```

# ============================================================

# الحساب

# ============================================================

def calculate(results):

```
total = sum(
    item["score"]
    for item in results
)

maximum = MAX_SCORE

percentage = (
    total / maximum * 100
    if maximum
    else 0
)

if percentage >= 85:
    level = "ممتاز"

elif percentage >= 70:
    level = "جيد جداً"

elif percentage >= 55:
    level = "جيد"

elif percentage >= 40:
    level = "مقبول"

else:
    level = "يحتاج إلى تحسين"

return (
    total,
    maximum,
    percentage,
    level
)
```

# ============================================================

# التقرير

# ============================================================

def build_markdown_report(
filename,
provider,
results,
analysis
):

```
total, maximum, percentage, level = (
    calculate(results)
)

lines = [

    "# تقرير تقييم خطة البحث العلمي",

    "",

    f"**الملف:** {filename}",

    f"**مزود الذكاء الاصطناعي:** {provider}",

    f"**التاريخ:** "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",

    "",

    "## نطاق التقييم",

    "المعايير 12–51 و68–71 فقط.",

    "",

    "## النتيجة العامة",

    f"**{percentage:.1f}% — "
    f"{total}/{maximum} — {level}**",

    "",

    "## التحليل الأكاديمي",

    analysis,

    "",

    "## التقييم التفصيلي"
]

current_category = None

for item in results:

    category = item["category"]

    if category != current_category:

        lines.extend(
            [
                "",
                f"### {category}",
                ""
            ]
        )

        current_category = category

    lines.extend(
        [
            f"#### المعيار {item['id']}",
            "",
            f"**المعيار:** {item['criterion']}",
            "",
            f"**الدرجة:** {item['score']}/2",
            "",
            f"**الحكم:** {item['status']}",
            "",
            f"**الدليل:** {item['evidence']}",
            "",
            f"**التحليل:** {item['explanation']}",
            "",
            f"**التوصية:** {item['suggestion']}",
            ""
        ]
    )

return "\n".join(lines)
```

# ============================================================

# الشريط الجانبي

# ============================================================

with st.sidebar:

```
st.header(
    "⚙️ إعدادات النظام"
)

mode = st.radio(
    "طريقة التقييم",
    [
        "🤖 تقييم بالذكاء الاصطناعي",
        "🔎 فحص أولي"
    ]
)

st.divider()

st.markdown(
    "### 📌 نطاق التقييم"
)

st.info(
    "المعايير 12–51 و68–71 فقط"
)

st.write(
    f"عدد المعايير: **{len(CRITERIA)}**"
)

st.write(
    f"الدرجة القصوى: **{MAX_SCORE}**"
)
```

# ============================================================

# اختيار API

# ============================================================

if mode == "🤖 تقييم بالذكاء الاصطناعي":

```
provider = st.selectbox(
    "اختر مزود الذكاء الاصطناعي",
    [
        "OpenAI",
        "Gemini",
        "Claude",
        "API مخصص"
    ]
)

if provider == "OpenAI":

    api_key = st.text_input(
        "OpenAI API Key",
        value=get_secret(
            "OPENAI_API_KEY"
        ),
        type="password"
    )

    model = st.selectbox(
        "النموذج",
        [
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-5"
        ]
    )

    base_url = ""

elif provider == "Gemini":

    api_key = st.text_input(
        "Gemini API Key",
        value=get_secret(
            "GEMINI_API_KEY"
        ),
        type="password"
    )

    model = st.selectbox(
        "النموذج",
        [
            "gemini-2.5-flash",
            "gemini-2.5-pro"
        ]
    )

    base_url = ""

elif provider == "Claude":

    api_key = st.text_input(
        "Claude API Key",
        value=get_secret(
            "ANTHROPIC_API_KEY"
        ),
        type="password"
    )

    model = st.selectbox(
        "النموذج",
        [
            "claude-sonnet-4-5",
            "claude-opus-4-1"
        ]
    )

    base_url = ""

else:

    api_key = st.text_input(
        "API Key",
        value=get_secret(
            "CUSTOM_API_KEY"
        ),
        type="password"
    )

    model = st.text_input(
        "اسم النموذج",
        value=get_secret(
            "CUSTOM_API_MODEL"
        )
    )

    base_url = st.text_input(
        "عنوان API",
        value=get_secret(
            "CUSTOM_API_BASE_URL"
        )
    )
```

else:

```
provider = "فحص أولي"
api_key = ""
model = ""
base_url = ""
```

# ============================================================

# رفع الملف

# ============================================================

uploaded_file = st.file_uploader(
"📤 ارفع خطة البحث",
type=[
"pdf",
"docx",
"png",
"jpg",
"jpeg",
"webp"
]
)

# ============================================================

# معالجة الملف

# ============================================================

if uploaded_file:

```
with st.spinner(
    "جارٍ استخراج النص من الملف..."
):

    try:

        extracted_text, extraction_method = (
            extract_file(uploaded_file)
        )

    except Exception as error:

        st.error(
            f"حدث خطأ أثناء قراءة الملف: {error}"
        )

        st.stop()

if not extracted_text:

    st.error(
        "لم يتم استخراج أي نص من الملف."
    )

    st.stop()

st.success(
    f"تم استخراج النص بنجاح "
    f"({extraction_method}) — "
    f"{len(extracted_text):,} حرف."
)

with st.expander(
    "👁️ معاينة النص المستخرج"
):

    st.text_area(
        "النص",
        extracted_text,
        height=300,
        label_visibility="collapsed"
    )


# ========================================================
# زر التقييم
# ========================================================

if st.button(
    "🚀 ابدأ تقييم خطة البحث",
    type="primary",
    use_container_width=True
):

    try:

        if mode == "🤖 تقييم بالذكاء الاصطناعي":

            with st.spinner(
                f"جارٍ التقييم باستخدام {provider}..."
            ):

                results, analysis = evaluate(
                    extracted_text,
                    provider,
                    api_key,
                    model,
                    base_url
                )

        else:

            # --------------------------------------------
            # الفحص الأولي
            # --------------------------------------------

            results = []

            text_lower = extracted_text.lower()

            for number, category, criterion in CRITERIA:

                score = 0

                keywords = [
                    "عنوان",
                    "مقدمة",
                    "مشكلة",
                    "سؤال",
                    "تساؤل",
                    "فرض",
                    "أهمية",
                    "هدف",
                    "مصطلح",
                    "حدود",
                    "منهج",
                    "دراسة",
                    "بحث",
                    "لغة"
                ]

                hits = sum(
                    1
                    for keyword in keywords
                    if keyword in text_lower
                )

                if hits >= 6:
                    score = 2

                elif hits >= 2:
                    score = 1

                results.append(
                    {
                        "id": number,
                        "category": category,
                        "criterion": criterion,
                        "score": score,
                        "status": [
                            "غير متحقق",
                            "متحقق جزئياً",
                            "متحقق"
                        ][score],
                        "evidence":
                            "نتيجة فحص أولي آلي.",
                        "explanation":
                            "الفحص الأولي يعتمد "
                            "على مؤشرات لغوية ولا "
                            "يمثل تحليلاً دلالياً كاملاً.",
                        "suggestion":
                            "ينصح باستخدام التقييم "
                            "بالذكاء الاصطناعي للحصول "
                            "على تحليل أكاديمي أدق."
                    }
                )

            analysis = (
                "هذه نتيجة فحص أولي آلي. "
                "لا ينبغي اعتمادها كتقييم أكاديمي "
                "نهائي، لأن التقييم الدلالي يحتاج "
                "إلى قراءة السياق والعلاقات بين "
                "عناصر خطة البحث."
            )


        # --------------------------------------------
        # حفظ النتائج
        # --------------------------------------------

        st.session_state["results"] = results
        st.session_state["analysis"] = analysis
        st.session_state["filename"] = uploaded_file.name
        st.session_state["provider"] = provider

        st.success(
            "✅ اكتمل تقييم خطة البحث."
        )

    except Exception as error:

        st.error(
            f"حدث خطأ أثناء التقييم: {error}"
        )

        with st.expander(
            "تفاصيل الخطأ"
        ):

            st.exception(error)
```

# ============================================================

# عرض النتائج

# ============================================================

if "results" in st.session_state:

```
results = st.session_state["results"]
analysis = st.session_state["analysis"]

total, maximum, percentage, level = calculate(
    results
)

st.divider()

# ========================================================
# النتائج الأساسية
# ========================================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "النتيجة",
    f"{percentage:.1f}%"
)

col2.metric(
    "النقاط",
    f"{total}/{maximum}"
)

col3.metric(
    "التقدير",
    level
)

col4.metric(
    "المعايير",
    len(results)
)

st.progress(
    percentage / 100
)


# ========================================================
# التحليل العام
# ========================================================

st.subheader(
    "📝 التحليل الأكاديمي العام"
)

st.markdown(
    f"""
    <div class="result-card">
    {analysis.replace(chr(10), "<br>")}
    </div>
    """,
    unsafe_allow_html=True
)


# ========================================================
# النتائج حسب المحاور
# ========================================================

st.subheader(
    "📊 النتائج حسب المحاور"
)

summary = []

for category, category_items in CATEGORIES.items():

    category_results = [
        result
        for result in results
        if result["category"] == category
    ]

    score = sum(
        result["score"]
        for result in category_results
    )

    maximum_category = (
        len(category_items) * 2
    )

    percentage_category = (
        score / maximum_category * 100
        if maximum_category
        else 0
    )

    summary.append(
        {
            "المحور":
                category,

            "عدد المعايير":
                len(category_items),

            "النقاط":
                f"{score}/{maximum_category}",

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

    category_results = [
        result
        for result in results
        if result["category"] == category
    ]

    for result in category_results:

        score = result["score"]

        icon = [
            "🔴",
            "🟠",
            "🟢"
        ][score]

        with st.expander(
            f"{icon} المعيار {result['id']} — "
            f"{result['criterion']} "
            f"— {result['score']}/2"
        ):

            st.write(
                f"**الحكم:** {result['status']}"
            )

            st.markdown(
                "**📌 الدليل من الخطة:**"
            )

            st.info(
                result["evidence"]
            )

            st.markdown(
                "**🔎 التحليل الأكاديمي:**"
            )

            st.write(
                result["explanation"]
            )

            st.markdown(
                "**💡 التوصية:**"
            )

            if result["suggestion"]:

                st.warning(
                    result["suggestion"]
                )

            else:

                st.success(
                    "لا توجد توصية إضافية؛ "
                    "المعيار متحقق."
                )


# ========================================================
# المعايير التي تحتاج إلى تحسين
# ========================================================

st.subheader(
    "🎯 المعايير التي تحتاج إلى تحسين"
)

weak_results = [
    result
    for result in results
    if result["score"] < 2
]

if weak_results:

    for result in weak_results:

        st.markdown(
            f"**{result['id']}. "
            f"{result['criterion']}** — "
            f"{result['suggestion']}"
        )

else:

    st.success(
        "🎉 جميع المعايير حصلت على الدرجة الكاملة."
    )


# ========================================================
# إعداد التقرير
# ========================================================

markdown_report = build_markdown_report(
    st.session_state["filename"],
    st.session_state["provider"],
    results,
    analysis
)

json_report = {
    "filename":
        st.session_state["filename"],

    "provider":
        st.session_state["provider"],

    "evaluation_scope":
        "12–51 و68–71 فقط",

    "criteria_count":
        len(results),

    "total_score":
        total,

    "maximum_score":
        maximum,

    "percentage":
        percentage,

    "level":
        level,

    "overall_analysis":
        analysis,

    "results":
        results
}


# ========================================================
# التحميل
# ========================================================

st.subheader(
    "📥 حفظ التقرير"
)

col1, col2 = st.columns(2)

with col1:

    st.download_button(
        "⬇️ تنزيل JSON",

        data=json.dumps(
            json_report,
            ensure_ascii=False,
            indent=2
        ),

        file_name=
            "تقرير_تقييم_خطة_البحث.json",

        mime="application/json",

        use_container_width=True
    )

with col2:

    st.download_button(
        "⬇️ تنزيل Markdown",

        data=markdown_report,

        file_name=
            "تقرير_تقييم_خطة_البحث.md",

        mime="text/markdown",

        use_container_width=True
    )
```

else:

```
st.info(
    "📤 ارفع خطة البحث للبدء في التقييم."
)
```
