import sqlite3

DB_NAME = 'bot.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول کاربران با username
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            name TEXT,
            role TEXT,                   -- 'admin', 'manager', 'member'
            supervisor_id INTEGER        -- For member: manager.id, For manager: admin.id
        )
    ''')
    # جدول تسک‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            assigned_by INTEGER,
            assigned_to INTEGER,
            deadline TEXT,
            reminder_type TEXT DEFAULT 'none',
            reminder_value INTEGER DEFAULT NULL,
            is_done INTEGER DEFAULT 0,
            is_urgent INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    # جدول گزارش‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            content TEXT,
            timestamp TEXT,
            score INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# --- USERS ---
def get_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    if not username:
        return None
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(telegram_id, username, name, role='member', supervisor_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO users (telegram_id, username, name, role, supervisor_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (telegram_id, username, name, role, supervisor_id))
    # اگر کاربر فقط با username ثبت شده بود و حالا با telegram_id اومده، آپدیت کن
    if telegram_id:
        c.execute('''
            UPDATE users SET telegram_id = ?, name = ?, role = ?, supervisor_id = ?
            WHERE username = ? OR telegram_id = ?
        ''', (telegram_id, name, role, supervisor_id, username, telegram_id))
    conn.commit()
    conn.close()

def delete_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

def get_all_users_by_role(role):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE role = ?", (role,))
    users = c.fetchall()
    conn.close()
    return users

def get_team_users(manager_id):
    """لیست اعضای تیم یک مدیر میانی"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE supervisor_id = ? AND role = 'member'", (manager_id,))
    users = c.fetchall()
    conn.close()
    return users

def get_managers_for_admin(admin_id):
    """لیست همه مدیرهای میانی یک مدیر اصلی"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE supervisor_id = ? AND role = 'manager'", (admin_id,))
    managers = c.fetchall()
    conn.close()
    return managers

# --- TASKS ---
def get_tasks_for_user(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT t.id, t.title, t.description, t.deadline, t.reminder_type, t.reminder_value
        FROM tasks t
        JOIN users u ON u.id = t.assigned_to
        WHERE u.telegram_id = ? AND t.is_done = 0
    ''', (telegram_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

def create_task(title, description, assigned_by, assigned_to, deadline, reminder_type, reminder_value, is_urgent, created_at):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO tasks (title, description, assigned_by, assigned_to, deadline, reminder_type, reminder_value, is_urgent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, assigned_by, assigned_to, deadline, reminder_type, reminder_value, is_urgent, created_at))
    conn.commit()
    conn.close()

def get_all_active_tasks():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT t.*, u.telegram_id as user_telegram_id, u.name as user_name
        FROM tasks t
        JOIN users u ON t.assigned_to = u.id
        WHERE t.is_done = 0
    ''')
    tasks = c.fetchall()
    conn.close()
    return tasks

def mark_task_done(task_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE tasks SET is_done = 1 WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

# --- REPORTS ---
def create_report(task_id, user_id, content, timestamp):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO reports (task_id, user_id, content, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (task_id, user_id, content, timestamp))
    conn.commit()
    conn.close()

def rate_report(report_id, score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE reports SET score = ? WHERE id = ?', (score, report_id))
    conn.commit()
    conn.close()

def get_reports_for_supervisor(supervisor_id, all_admin=False):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if all_admin:
        # مدیر اصلی: تمام گزارش‌های کاربران و مدیرها را می‌بیند (غیراز خودش)
        c.execute('''
            SELECT r.id, r.content, r.timestamp, r.score, u.name
            FROM reports r
            JOIN users u ON r.user_id = u.id
            WHERE u.role IN ('manager', 'member')
            ORDER BY r.timestamp DESC
            LIMIT 20
        ''')
    else:
        # مدیر میانی: فقط گزارش اعضای تیم خودش
        c.execute('''
            SELECT r.id, r.content, r.timestamp, r.score, u.name
            FROM reports r
            JOIN users u ON r.user_id = u.id
            WHERE u.supervisor_id = ? AND u.role = 'member'
            ORDER BY r.timestamp DESC
            LIMIT 20
        ''', (supervisor_id,))
    result = c.fetchall()
    conn.close()
    return result

def get_reports_for_user(user_id):
    """نمایش گزارش‌های ثبت شده توسط خود کاربر"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT content, timestamp, score FROM reports
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 20
    ''', (user_id,))
    result = c.fetchall()
    conn.close()
    return result

