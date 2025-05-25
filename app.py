from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import sqlite3

app = Flask(__name__)
DATABASE = 'test_results.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Позволяет получать результаты как словари
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_text TEXT NOT NULL,
                options TEXT NOT NULL, -- JSON string
                correct_answer TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                level TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        # Загрузка вопросов из JSON файла при инициализации, если их нет
        try:
            cursor.execute("SELECT COUNT(*) FROM questions")
            if cursor.fetchone()[0] == 0:
                with open("questions.json", 'r', encoding='utf-8') as f:
                    questions_data = json.load(f)
                for q in questions_data:
                    cursor.execute("INSERT INTO questions (question_text, options, correct_answer) VALUES (?, ?, ?)",
                                   (q['question'], json.dumps(q['options']), q['correct_answer']))
                db.commit()
                print("Вопросы загружены в базу данных.")
        except FileNotFoundError:
            print("questions.json не найден. Вопросы не будут загружены автоматически.")
        db.close()

def assign_level(score, total_questions):
    """Определяет уровень студента."""
    percentage = (score / total_questions) * 100
    if percentage >= 90:
        return "Продвинутый (Advanced)"
    elif percentage >= 70:
        return "Средний (Intermediate)"
    elif percentage >= 50:
        return "Начальный (Beginner)"
    else:
        return "Нуждается в улучшении (Needs Improvement)"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test', methods=['GET', 'POST'])
def test():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, question_text, options FROM questions")
    questions = []
    for row in cursor.fetchall():
        q = dict(row)
        q['options'] = json.loads(q['options']) # Десериализация JSON-строки в список
        questions.append(q)
    db.close()

    if request.method == 'POST':
        student_name = request.form['student_name']
        submitted_answers = {}
        for q_id, answer_index_str in request.form.items():
            if q_id.startswith('question_'):
                try:
                    q_id_num = int(q_id.split('_')[1])
                    submitted_answers[q_id_num] = int(answer_index_str) - 1 # Индекс с 0
                except (ValueError, IndexError):
                    pass # Пропустить неверные данные

        score = 0
        total_questions = len(questions)
        correct_answers_map = {} # Для проверки

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, correct_answer, options FROM questions")
        db_questions = cursor.fetchall()
        db.close()

        for q_row in db_questions:
            correct_answers_map[q_row['id']] = {
                "correct_text": q_row['correct_answer'],
                "options": json.loads(q_row['options'])
            }

        for q_id, student_answer_index in submitted_answers.items():
            if q_id in correct_answers_map:
                question_info = correct_answers_map[q_id]
                if student_answer_index >= 0 and student_answer_index < len(question_info['options']):
                    if question_info['options'][student_answer_index] == question_info['correct_text']:
                        score += 1

        percentage = (score / total_questions) * 100
        level = assign_level(score, total_questions)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO results (student_name, score, total_questions, percentage, level) VALUES (?, ?, ?, ?, ?)",
                       (student_name, score, total_questions, percentage, level))
        db.commit()
        db.close()

        return render_template('result.html', student_name=student_name, score=score,
                               total_questions=total_questions, percentage=percentage, level=level)

    return render_template('test.html', questions=questions)

@app.route('/statistics')
def statistics():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT level, COUNT(*) as count FROM results GROUP BY level")
    level_counts = {row['level']: row['count'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT COUNT(*) FROM results")
    total_students = cursor.fetchone()[0]
    db.close()

    level_stats = {}
    for level, count in level_counts.items():
        percentage = (count / total_students) * 100 if total_students > 0 else 0
        level_stats[level] = {"count": count, "percentage": f"{percentage:.2f}%"}

    # Добавляем все ожидаемые уровни, даже если по ним 0 студентов
    all_levels = ["Продвинутый (Advanced)", "Средний (Intermediate)", "Начальный (Beginner)", "Нуждается в улучшении (Needs Improvement)"]
    for level in all_levels:
        if level not in level_stats:
            level_stats[level] = {"count": 0, "percentage": "0.00%"}

    return render_template('statistics.html', level_stats=level_stats, total_students=total_students)

@app.route('/api/results')
def api_results():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT student_name, score, total_questions, percentage, level, timestamp FROM results ORDER BY timestamp DESC")
    results = [dict(row) for row in cursor.fetchall()]
    db.close()
    return jsonify(results)

if __name__ == '__main__':
    init_db()
else:
    init_db # Инициализируем базу данных и загружаем вопросы
   # debug=True только для разработки
