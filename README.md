# 📚 مقيّم خطة البحث العلمي

تطبيق Streamlit عربي لتقييم خطط البحث العلمي بالاعتماد **حصراً** على المعايير **12–51 و68–71** الواردة في جدول التحكيم الذي حدده المستخدم.

- عدد المعايير: **44**
- الدرجة القصوى: **88 نقطة**
- كل معيار: 0 أو 1 أو 2
- التقييم لا يكتفي بالرقم: في الوضع الدلالي ينتج **تحليلاً أكاديمياً مكتوباً، دليلاً من النص، تفسيراً، وتوصية عملية** لكل معيار.

## الملفات المدعومة
- PDF نصي
- PDF ممسوح ضوئياً عبر OCR
- Word DOCX
- PNG / JPG / JPEG / WEBP

## وضع الذكاء الاصطناعي الدلالي
التطبيق يستخدم واجهة Chat Completions متوافقة مع OpenAI. يمكن استخدام OpenAI أو خدمة أخرى متوافقة مع نفس الواجهة.

### أسرار Streamlit Cloud
لا تضع مفتاح API داخل GitHub أو داخل `app.py`.

في Streamlit Community Cloud افتح **Advanced settings → Secrets** وأضف:

```toml
OPENAI_API_KEY = "ضع_المفتاح_هنا"
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"
```

يمكن تغيير `OPENAI_MODEL` و`OPENAI_BASE_URL` إذا كنت تستخدم مزوداً متوافقاً مع OpenAI.

## تشغيل محلي

```bash
pip install -r requirements.txt
streamlit run app.py
```

يلزم وجود Tesseract مع اللغة العربية عند استخدام OCR. في Streamlit Community Cloud يتكفل `packages.txt` بتثبيت:

- `tesseract-ocr`
- `tesseract-ocr-ara`

## النشر على Streamlit Community Cloud

1. أنشئ مستودعاً على GitHub.
2. ارفع **محتويات هذا المجلد** إلى جذر المستودع، بحيث يكون `app.py` و`requirements.txt` في الجذر.
3. افتح https://share.streamlit.io وسجّل الدخول بحساب GitHub.
4. اختر **Create app**.
5. اختر المستودع والفرع `main` والملف `app.py`.
6. افتح **Advanced settings** وأضف أسرار API كما هو موضح أعلاه.
7. اضغط **Deploy**.

بعد النشر تحصل على رابط من نوع `https://اسم-التطبيق.streamlit.app/`.

## ملاحظات
- الفحص الآلي الأولي متاح بدون API، لكنه **ليس تحكيماً دلالياً**.
- الوضع الدلالي هو الوضع الموصى به للمشروع لأنه يقرأ المعنى والسياق ولا يكتفي بوجود الكلمات المفتاحية.
- التقرير النهائي يتضمن النتيجة الرقمية، والتحليل المكتوب، والتقييم التفصيلي لكل معيار، والأدلة والتوصيات.
