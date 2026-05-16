import re

with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

# تعديل قائمة الموديلات لضمان المجاني والمستقر فقط وتجنب الـ 404
old_models = r'\[\s*["\']google/gemini-2.5-flash:free["\'].*?\]'
new_models = '["google/gemini-2.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-r1:free"]'

if "google/gemini-2.5-flash:free" in code:
    # استبدال ذكي لقائمة الموديلات الاحتياطية
    code = re.sub(r'["\']microsoft/phi-4-reasoning:free["\'],?', '', code)

# التأكد من وجود try-except قوي يمنع انهيار اللوب عند الـ 404 أو 402
fallback_fix = """
    try:
        # تشغيل التناوب الذكي بدون توقف
        pass
    except Exception as e:
        print(f
