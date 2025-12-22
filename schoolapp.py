import os
import json
import random
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader  # در requirements.txt: flask==3.0.3, gunicorn==22.0.0, pypdf>=3.12.0

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "schools.json")
BOOKS_DIR = os.path.join(BASE_DIR, "data", "books")
BOOK_INDEX_PATH = os.path.join(BOOKS_DIR, "book_index.json")


# ---------- ابزارهای مشترک ----------

def load_schools_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("schools", [])
    except Exception:
        return []


def find_school_by_id(schools, school_id: str):
    for s in schools:
        if s.get("id") == school_id:
            return s
    return None


def simple_faq_match(faqs, question: str):
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

        for kw in keywords:
            kw_norm = (kw or "").strip().lower()
            if kw_norm and kw_norm in normalized_q:
                score += 1

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


# ---------- روت‌های اصلی ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/<school_id>/ask", methods=["POST"])
def ask_school_bot(school_id):
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


# ---------- طراحی سؤال از کتاب ----------

def load_book_index() -> dict:
    """خواندن book_index.json که بازه صفحات هر فصل را نگه می‌دارد."""
    try:
        with open(BOOK_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def extract_text_from_pdf_range(pdf_path: str, start_page: int, end_page: int) -> str:
    """
    استخراج متن از یک بازه صفحه در PDF با pypdf.
    شماره صفحات بر اساس فایل است (۱، ۲، ۳، ...) و به نمایه ۰ تبدیل می‌شود.
    اگر خطا رخ دهد، متن خلاصه fallback برمی‌گردد تا سرور کرش نکند.
    """
    try:
        reader = PdfReader(pdf_path)
        n_pages = len(reader.pages)
        # اطمینان از حدود
        start = max(1, start_page)
        end = min(end_page, n_pages)
        parts = []
        for page_no in range(start, end + 1):
            try:
                page = reader.pages[page_no - 1]  # تبدیل به ایندکس صفرمبتنی
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            parts.append(txt)
        text = "\n".join(parts).strip()
        if text:
            return text
    except Exception:
        pass

    # اگر PDF مشکل داشت، متن fallback برای فیزیک دهم
    return (
        "در این کتاب فیزیک پایه دهم، مفاهیم اصلی مانند کمیت‌های فیزیکی، اندازه‌گیری، "
        "حرکت‌شناسی و دینامیک بررسی می‌شوند. دانش‌آموز با بردار و نرده‌ای، سرعت، شتاب، "
        "نیرو و قوانین نیوتن آشنا می‌شود و می‌آموزد چگونه مسائل حرکت و تعادل اجسام را حل کند."
    )


def load_book_text(grade: str, subject: str, chapter: str, track: str | None = None) -> str:
    """
    منبع متن:
    - علوم پایه ششم، فصل ۴ → فایل data/books/science_grade6_f4.txt
    - فیزیک پایه دهم ریاضی → بازه صفحات هر فصل از book_index.json روی PDF physics_grade10_math.pdf
    """
    subject = (subject or "").strip()
    subject_norm = subject.replace(" ", "").lower()
    grade = str(grade)
    chapter = str(chapter)

    # علوم ششم فصل ۴
    is_science_grade6_f4 = (
        grade == "6"
        and ("علوم" in subject or "science" in subject_norm)
        and chapter == "4"
    )
    if is_science_grade6_f4:
        path = os.path.join(BOOKS_DIR, "science_grade6_f4.txt")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    # فیزیک دهم (کلید: physics_grade10_math)
    is_physics_grade10 = (
        grade == "10"
        and ("فیزیک" in subject or "physics" in subject_norm)
    )
    if is_physics_grade10:
        index_data = load_book_index()
        book_key = "physics_grade10_math"
        book_info = index_data.get(book_key, {})
        page_range = book_info.get(chapter)

        pdf_path = os.path.join(BOOKS_DIR, "physics_grade10_math.pdf")

        if page_range and isinstance(page_range, list) and len(page_range) == 2:
            start_page, end_page = page_range
            return extract_text_from_pdf_range(pdf_path, int(start_page), int(end_page))
        else:
            # اگر برای این فصل بازه تعریف نشده باشد، فعلاً کل PDF/ fallback
            return extract_text_from_pdf_range(pdf_path, 1, 20)

    return ""


def generate_demo_questions_from_text(text: str, qtype: str, count: int = 3):
    text = (text or "").strip()
    if not text:
        return []

    # کمی خلاصه ابتدای متن و وسط متن برای استفاده در سوال‌ها
    t_short = (text[:300] + "…") if len(text) > 300 else text
    mid_start = max(0, len(text) // 3)
    t_mid = (text[mid_start: mid_start + 300] + "…") if len(text) > mid_start + 100 else text

    questions = []

    for i in range(1, count + 1):
        if qtype == "mcq":
            templates = [
                f"بر اساس متن زیر، کدام گزینه درست است؟\n«{t_short}»",
                f"با توجه به متن زیر، کدام گزینه بهترین توصیف برای مفهوم اصلی است؟\n«{t_mid}»"
            ]
            q_text = random.choice(templates)
            opts = ["گزینه صحیح", "نزدیک به صحیح", "نادرست", "کاملاً نادرست"]
            questions.append({
                "type": "mcq",
                "question": f"سوال تستی {i}: {q_text}",
                "options": opts,
                "answer": opts[0]
            })

        elif qtype == "tf":
            base = "عبارت زیر را بر اساس متن کتاب، درست یا نادرست تشخیص دهید."
            q_text = f"{base}\n«در این بخش کتاب، تنها یک نوع حرکت بررسی شده است.»"
            answer = random.choice(["درست", "نادرست"])
            questions.append({
                "type": "tf",
                "question": f"سوال درست/غلط {i}: {q_text}",
                "answer": answer
            })

        else:  # short
            base = "با توجه به متن کتاب، تفاوت دو مفهوم اصلی این فصل را توضیح دهید."
            questions.append({
                "type": "short",
                "question": f"سوال تشریحی {i}: {base}",
                "answer": ""
            })

    return questions


@app.route("/api/demo/quiz", methods=["POST"])
def demo_quiz():
    data = request.get_json(silent=True) or {}
    grade = str(data.get("grade", "6"))
    subject = data.get("subject", "علوم تجربی")
    chapter = str(data.get("chapter", "4"))
    qtype = data.get("qtype", "mcq")
    count = int(data.get("count", 3) or 3)
    track = data.get("track")

    text = load_book_text(grade, subject, chapter, track)

    if not text:
        return jsonify({
            "error": "در نسخه دمو فعلاً «علوم پایه ششم، فصل ۴» و «فیزیک پایه دهم (فصول تعریف‌شده در book_index)» فعال است.",
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


# ---------- دمو کارنامه (گزارش متنی) ----------

def build_demo_report(name: str, grade: str, scores: dict, attendance_percent: int) -> str:
    name = name or "دانش‌آموز"
    grade = grade or ""
    scores = scores or {}

    strong_subjects = [s for s, v in scores.items() if v >= 18]
    mid_subjects = [s for s, v in scores.items() if 14 <= v < 18]
    weak_subjects = [s for s, v in scores.items() if v < 14]

    lines = []

    lines.append(f"ولی محترم {name}،")
    lines.append(
        f"این گزارش بر اساس عملکرد {name} در پایه {grade} در دبستان غیرانتفاعی پویا تنظیم شده است.\n"
    )

    if strong_subjects:
        strong_list = "، ".join(strong_subjects)
        lines.append(
            f"- در درس‌های {strong_list} عملکرد بسیار خوبی داشته و نشان می‌دهد مفاهیم را به خوبی درک کرده است."
        )
    if mid_subjects:
        mid_list = "، ".join(mid_subjects)
        lines.append(
            f"- در درس‌های {mid_list} سطح عملکرد خوب است، اما با کمی تمرین بیشتر می‌تواند به سطح عالی برسد."
        )
    if weak_subjects:
        weak_list = "، ".join(weak_subjects)
        lines.append(
            f"- در درس‌های {weak_list} نیاز به توجه و همراهی بیشتری وجود دارد. پیشنهاد می‌شود با معلم مربوطه برای برنامه جبرانی هماهنگ کنید."
        )

    lines.append(
        f"- حضور {name} در کلاس‌ها حدود {attendance_percent}٪ بوده است. حضور منظم تاثیر مستقیم در پیشرفت درسی دارد."
    )

    lines.append(
        "\nبه طور کلی، روند پیشرفت {0} مثبت ارزیابی می‌شود و با ادامه همراهی شما و تلاش دانش‌آموز، می‌توان انتظار نتایج بهتر در ماه‌های آینده را داشت.".format(
            name
        )
    )

    return "\n".join(lines)


@app.route("/api/demo/report", methods=["POST"])
def demo_report():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    grade = data.get("grade", "")
    scores = data.get("scores", {})
    attendance_percent = int(data.get("attendance_percent", 0) or 0)

    if not name:
        return jsonify({"error": "نام دانش‌آموز لازم است."}), 400

    report_text = build_demo_report(name, grade, scores, attendance_percent)

    return jsonify({
        "name": name,
        "grade": grade,
        "scores": scores,
        "attendance_percent": attendance_percent,
        "report": report_text
    })


# ---------- کارنامه رسمی HTML ----------

@app.route("/demo/report-card")
def demo_report_card():
    sample_data = {
        "student_name": "علی نمونه",
        "student_code": "۱۲۳۴۵۶۷",
        "grade_title": "پایه ششم ابتدایی",
        "school_name": "دبستان غیرانتفاعی پویا",
        "year_title": "سال تحصیلی ۱۴۰۳-۱۴۰۴",
        "total_units": 23,
        "total_score": 460,
        "avg_score": 20,
        "attendance_percent": 95,
        "courses": [
            {"name": "ریاضی", "unit": 3, "score": 20},
            {"name": "علوم تجربی", "unit": 3, "score": 20},
            {"name": "فارسی", "unit": 3, "score": 20},
            {"name": "قرآن و هدیه‌ها", "unit": 2, "score": 20},
            {"name": "مطالعات اجتماعی", "unit": 2, "score": 20},
            {"name": "زبان انگلیسی", "unit": 2, "score": 20},
            {"name": "هنر", "unit": 1, "score": 20},
            {"name": "ورزش", "unit": 1, "score": 20}
        ]
    }
    return render_template("report_card.html", **sample_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
