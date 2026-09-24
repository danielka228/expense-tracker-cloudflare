import os
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from pyodide.ffi import run_sync
from workers import wsgi, env

from templates import TEMPLATES

app = Flask(__name__)
app.jinja_loader = DictLoader(TEMPLATES)

app.config["SECRET_KEY"] = env.SECRET_KEY
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

CATEGORIES = ['Еда', 'Транспорт', 'Жильё', 'Развлечения', 'Здоровье', 'Одежда', 'Прочее']


def db():
    return env.DB


def d1_run(sql, *params):
    result = run_sync(db().prepare(sql).bind(*params).run())
    return result.results.to_py()


def d1_first(sql, *params):
    result = run_sync(db().prepare(sql).bind(*params).first())
    if result is None:
        return None
    return result.to_py() if hasattr(result, "to_py") else result


def d1_write(sql, *params):
    run_sync(db().prepare(sql).bind(*params).run())


def initialize_database():
    schema = """
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS expense (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        note TEXT,
        expense_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);
    CREATE INDEX IF NOT EXISTS idx_expense_user_date ON expense(user_id, expense_date);
    """
    run_sync(db().exec(schema))


try:
    initialize_database()
except Exception:
    pass


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


@app.route('/ping')
def ping():
    return 'OK', 200


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Заполните все поля', 'error')
            return render_template('register.html')

        if len(password) < 4:
            flash('Пароль должен быть не короче 4 символов', 'error')
            return render_template('register.html')

        existing = d1_first('SELECT id FROM user WHERE username = ? LIMIT 1', username)
        if existing:
            flash('Такой пользователь уже существует', 'error')
            return render_template('register.html')

        now = datetime.utcnow().isoformat(timespec='seconds')
        password_hash = generate_password_hash(password)

        d1_write(
            'INSERT INTO user (username, password_hash, created_at) VALUES (?, ?, ?)',
            username, password_hash, now
        )

        user = d1_first(
            'SELECT id, username FROM user WHERE username = ? LIMIT 1',
            username
        )

        session['user_id'] = int(user['id'])
        session['username'] = user['username']
        flash('Регистрация прошла успешно!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = d1_first(
            'SELECT id, username, password_hash FROM user WHERE username = ? LIMIT 1',
            username
        )

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = int(user['id'])
            session['username'] = user['username']
            return redirect(url_for('dashboard'))

        flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    user_id = int(session['user_id'])

    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', '').replace(',', '.'))
        except (ValueError, TypeError):
            flash('Введите корректную сумму', 'error')
            return redirect(url_for('dashboard'))

        if amount < 0:
            flash('Сумма не может быть отрицательной', 'error')
            return redirect(url_for('dashboard'))

        category = request.form.get('category', 'Прочее')
        if category not in CATEGORIES:
            category = 'Прочее'

        note = request.form.get('note', '').strip()
        expense_date_str = request.form.get('expense_date')

        try:
            expense_date = (
                datetime.strptime(expense_date_str, '%Y-%m-%d').date()
                if expense_date_str else date.today()
            )
        except ValueError:
            flash('Некорректная дата', 'error')
            return redirect(url_for('dashboard'))

        now = datetime.utcnow().isoformat(timespec='seconds')
        d1_write(
            """INSERT INTO expense
               (user_id, amount, category, note, expense_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            user_id, amount, category, note, expense_date.isoformat(), now
        )

        flash('Трата добавлена', 'success')
        return redirect(url_for('dashboard'))

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    rows = d1_run(
        """SELECT id, amount, category, note, expense_date, created_at
           FROM expense
           WHERE user_id = ?
           ORDER BY expense_date DESC, created_at DESC""",
        user_id
    )

    class ExpenseView:
        def __init__(self, row):
            self.id = int(row['id'])
            self.amount = float(row['amount'])
            self.category = row['category']
            self.note = row['note']
            self.expense_date = datetime.strptime(
                row['expense_date'], '%Y-%m-%d'
            ).date()
            self.created_at = row['created_at']

    all_expenses = [ExpenseView(row) for row in rows]

    today_total = sum(e.amount for e in all_expenses if e.expense_date == today)
    week_total = sum(e.amount for e in all_expenses if e.expense_date >= week_start)
    month_total = sum(e.amount for e in all_expenses if e.expense_date >= month_start)

    by_category = {}
    for e in all_expenses:
        if e.expense_date >= month_start:
            by_category[e.category] = by_category.get(e.category, 0) + e.amount

    recent = all_expenses[:15]

    return render_template(
        'dashboard.html',
        categories=CATEGORIES,
        today=today.isoformat(),
        today_total=today_total,
        week_total=week_total,
        month_total=month_total,
        by_category=by_category,
        recent=recent,
        username=session.get('username')
    )


@app.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    user_id = int(session['user_id'])

    d1_write(
        'DELETE FROM expense WHERE id = ? AND user_id = ?',
        expense_id, user_id
    )

    flash('Запись удалена', 'success')
    return redirect(url_for('dashboard'))


Default = wsgi.entrypoint(app)
