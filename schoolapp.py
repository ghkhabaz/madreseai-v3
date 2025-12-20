import os
import json
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# مسیر فایل داده مدارس و کتاب‌ها
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "schools.json")
BOOKS_DIR = os.path.join(BASE_DIR, "data", "books")


def load_schools_data():
    """خواندن داده مدارس از فایل JSON."""
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("schools", [])
    except Exception:
        return []


def find_school_by_id(schools, school_id: str):
    """پیدا کردن مدرسه بر اساس id ساده."""
    for s in schools:
        if s.get("id") == school_id:
            return s
    return None


def simple_faq_match(faqs, question: str):
    """
    جست‌وجوی کمی هوشمندتر:
    - از روی keywords و tags برای هر FAQ امتیاز حساب می‌کند.
    - هر کلمه‌کلیدی که در سوال باشد: +1
    - هر تگی که در سوال باشد: +2 (چون خاص‌تر است)
    - FAQ با بیشترین امتیاز انتخاب می‌شود؛ اگر امتیاز=0 باشد، None برمی‌گردد.
    """
    question = (question or "").strip()
    if not question:
        return None

    normalized_q = question.replace("?", "").replace("؟", "").lower()

    best_faq = None
    best_score = 0

    for faq in faqs:
        keywords = faq.get("keywords", [])
        tags = faq.get("tags", [])

        score = 0

        # امتیاز برای کلمات کلیدی
        for kw in keywords:
            kw_norm = (kw or "").strip().lower()
            if kw_norm and kw_norm in normalized_q:
                score += 1

        # امتیاز برای تگ‌ها (وزن بیشتر)
        for tag in tags:
            tag_norm = (tag or "").strip().lower()
            if tag_norm and tag_norm in normalized_q:
                score += 2

        if score > best_score:
            best_score = score
            best_faq = faq

    if best_score == 0:
        return None

    return best_faq


@app.route("/")
def home():
    """صفحه لندینگ MadreseAI."""
    return render_template("index.html")


@app.route("/api/<school_id>/ask", methods=["POST"])
def ask_school_bot(school_id):
    """
    API ساده چت‌بات مدرسه.
    ورودی JSON: { "question": "متن سوال والد/دانش‌آموز" }
    خروجی JSON: { "answer": "...", "matched_question": "..." }
    """
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")

    if not question.strip():
        return jsonify({"error": "سوال خالی است."}), 400

    schools = load_schools_data()
    school = find_school_by_id(schools, school_id)

    if not school:
        return jsonify({"error": "مدرسه‌ای با این شناسه پیدا نشد."}), 404

    faqs = school.get("faqs", [])
    matched = simple_faq_match(faqs, question)

    if not matched:
        return jsonify({
            "answer": "در اطلاعات فعلی این مدرسه پاسخی برای این سوال پیدا نشد. لطفاً با دفتر مدرسه تماس بگیرید.",
            "matched_question": None
        })

    return jsonify({
        "answer": matched.get("answer", ""),
        "matched_question": matched.get("question", "")
    })


# ---------- ماژول دمو طراحی سؤال از کتاب ----------

def load_book_text(grade: str, subject: str, chapter: str) -> str:
    """
    خواندن متن فصل از فایل.
    در نسخه دمو، فقط برای «پایه ۶، علوم تجربی، فصل ۴» فایل داریم.
    بقیه ترکیب‌ها فعلاً خالی است تا بعداً اضافه شوند.
    """
    # نرمال‌سازی ساده نام درس
    subject = (subject or "").strip()
    subject_norm = subject.replace(" ", "")
    is_science_grade6 = (
        grade == "6" and
        ("علوم" in subject or "science" in subject_norm) and
        chapter == "4"
    )

    if is_science_grade6:
        filename = "science_grade6_f4.txt"
    else:
        return ""

    path = os.path.join(BOOKS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def generate_demo_questions_from_text(text: str, qtype: str, count: int = 3):
    """
    تولید چند سوال دمو از روی متن، با تنوع بیشتر در قالب سوال‌ها.
    هنوز هوش مصنوعی واقعی نیست، فقط تنوع نمایشی برای مدیران.
    """
    text = (text or "").strip()
    if not text:
        return []

    # تکه‌های کوتاه از متن برای استفاده در سوال
    t_short = (text[:120] + "…") if len(text) > 120 else text
    mid_start = max(0, len(text) // 3)
    t_mid = (text[mid_start: mid_start + 120] + "…") if len(text) > mid_start + 40 else text

    questions = []

    for i in range(1, count + 1):
        if qtype == "mcq":
            templates = [
                f"بر اساس متن زیر، کدام گزینه درست است؟\n«{t_short}»",
                f"از متن زیر، بهترین توصیف برای مفهوم اصلی کدام است؟\n«{t_mid}»",
                f"بر اساس توضیحات فصل، کدام گزینه مثال بهتری از مفهوم گفته‌شده است؟"
            ]
            q_text = random.choice(templates)

            option_templates = [
                ["مثال درست از مفهوم اصلی متن", "مثال کم‌ربط", "گزینه نادرست", "گزینه نامرتبط"],
                ["توضیح کامل و صحیح", "توضیح ناقص", "توضیح اشتباه", "توضیح بی‌ربط"],
                ["تعریف دقیق", "تعریف ناقص", "تعریف اشتباه", "تعریف غیرعلمی"]
            ]
            opts = random.choice(option_templates)

            questions.append({
                "type": "mcq",
                "question": f"سوال تستی شماره {i}: {q_text}",
                "options": opts,
                "answer": opts[0]
            })

        elif qtype == "tf":
            templates = [
                "در این فصل درباره حالت‌های مختلف مواد صحبت شده است.",
                "در این فصل، دانش‌آموز فقط باید نام مواد را حفظ کند و نیازی به مثال زدن ندارد.",
                "در این فصل، دانش‌آموز با مفاهیم تبخیر و میعان آشنا می‌شود."
            ]
            base = random.choice(templates)
            q_text = f"جمله زیر بر اساس متن فصل صحیح است؟\n«{base}»"
            # جمله دوم عمداً غلط در نظر گرفته می‌شود
            answer = "غلط" if "فقط باید نام مواد را حفظ کند" in base else "درست"

            questions.append({
                "type": "tf",
                "question": f"سوال درست/غلط شماره {i}: {q_text}",
                "answer": answer
            })

        else:  # short
            templates = [
                "با توجه به فصل، توضیح دهید چه تفاوتی بین جامد، مایع و گاز وجود دارد.",
                "یک مثال از هر کدام از حالت‌های ماده (جامد، مایع، گاز) بنویسید.",
                "بر اساس آنچه در این فصل خوانده‌اید، یک پاراگراف کوتاه درباره تغییر حالت‌های ماده بنویسید."
            ]
            q_text = random.choice(templates)

            questions.append({
                "type": "short",
                "question": f"سوال تشریحی شماره {i}: {q_text}",
                "answer": ""
            })

    return questions


@app.route("/api/demo/quiz", methods=["POST"])
def demo_quiz():
    """
    دمو طراحی سوال:
    ورودی JSON مثل:
    {
      "grade": "6",
      "subject": "علوم تجربی",
      "chapter": "4",
      "qtype": "mcq",
      "count": 3,
      "track": "math" | null
    }
    در نسخه دمو، فقط ترکیب پایه ۶، علوم، فصل ۴ پشتیبانی واقعی می‌شود.
    """
    data = request.get_json(silent=True) or {}
    grade = str(data.get("grade", "6"))
    subject = data.get("subject", "علوم تجربی")
    chapter = str(data.get("chapter", "4"))
    qtype = data.get("qtype", "mcq")
    count = int(data.get("count", 3) or 3)

    # خواندن متن فصل (فقط برای ترکیب دمو)
    text = load_book_text(grade, subject, chapter)
    if not text:
        return jsonify({
            "error": "برای این پایه/درس/فصل در نسخه نمایشی فعلی محتوایی ثبت نشده است. "
                     "در این دمو فقط «علوم پایه ششم، فصل ۴» فعال است.",
            "questions": []
        }), 400

    questions = generate_demo_questions_from_text(text, qtype, count)
    return jsonify({
        "grade": grade,
        "subject": subject,
        "chapter": chapter,
        "qtype": qtype,
        "count": len(questions),
        "questions": questions
    })


# ---------- ماژول دمو کارنامه / گزارش ----------

def build_demo_report(name: str, grade: str, scores: dict, attendance_percent: int) -> str:
    """
    تولید یک متن گزارش ساده بر اساس نمرات.
    بعداً این بخش را می‌توان با مدل هوش مصنوعی جایگزین کرد.
    """
    name = name or "دانش‌آموز"
    grade = grade or ""
    scores = scores or {}

    strong_subjects = [s for s, v in scores.items() if v >= 18]
    mid_subjects = [s for s, v in scores.items() if 14 <= v < 18]
    weak_subjects = [s for s, v in scores.items() if v < 14]

    lines = []

    lines.append(f"ولی محترم {name}،")
    lines.append(f"این گزارش بر اساس عملکرد {name} در پایه {grade} تنظیم شده است.\n")

    if strong_subjects:
        strong_list = "، ".join(strong_subjects)
        lines.append(f"- در درس‌های {strong_list} عملکرد بسیار خوبی داشته و نشان می‌دهد مفاهیم را به خوبی درک کرده است.")
    if mid_subjects:
        mid_list = "، ".join(mid_subjects)
        lines.append(f"- در درس‌های {mid_list} سطح عملکرد خوب است، اما با کمی تمرین بیشتر می‌تواند به سطح عالی برسد.")
    if weak_subjects:
        weak_list = "، ".join(weak_subjects)
        lines.append(f"- در درس‌های {weak_list} نیاز به توجه و همراهی بیشتری وجود دارد. پیشنهاد می‌شود با معلم مربوطه برای برنامه جبرانی هماهنگ کنید.")

    lines.append(f"- حضور {name} در کلاس‌ها حدود {attendance_percent}٪ بوده است. حضور منظم تاثیر مستقیم در پیشرفت درسی دارد.")

    lines.append("\nبه طور کلی، روند پیشرفت {0} مثبت ارزیابی می‌شود و با ادامه همراهی شما و تلاش دانش‌آموز، می‌توان انتظار نتایج بهتر در ماه‌های آینده را داشت.".format(name))

    return "\n".join(lines)


@app.route("/api/demo/report", methods=["POST"])
def demo_report():
    """
    دمو تولید گزارش/کارنامه.
    ورودی JSON مثل:
    {
      "name": "علی نمونه",
      "grade": "۶ ابتدایی",
      "scores": {"ریاضی": 18, ...},
      "attendance_percent": 95
    }
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    grade = data.get("grade", "")
    scores = data.get("scores", {})
    attendance_percent = int(data.get("attendance_percent", 0) or 0)

    if not name:
        return jsonify({"error": "نام دانش‌آموز مشخص نشده است."}), 400

    report_text = build_demo_report(name, grade, scores, attendance_percent)

    return jsonify({
        "name": name,
        "grade": grade,
        "scores": scores,
        "attendance_percent": attendance_percent,
        "report": report_text
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
