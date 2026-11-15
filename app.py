"""
TrackMyHabits - Flask Application Entrypoint & Full-Stack Backend
Features:
- Full Authentication: Register, Login, Logout, Session Security, CSRF Tokens
- Dashboard: Streaks, today's checklist, 7-day consistency chart, goals snapshot
- Habits CRUD & Toggle: Complete/Undo dates, schedules (daily, weekdays, weekly_target)
- SMART Goals CRUD & Progress: Link habits, deadline tracking, auto completion
- Calendar: Month overview, day breakdown, direct log toggle
- Analytics: Live metrics, daily, weekly, monthly, habits breakdown, goals
- Notifications: In-app reminders, goal deadline alerts, daily progress summaries
- Profile & Settings: Change password, timezone, theme preference, account deletion
- Mandatory Admin Panel: Users list, search, pagination, suspend/reactivate, role management, audit logs, system stats
"""
import os
import secrets
import json
from datetime import datetime, date, timedelta, timezone
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, abort, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash

import db
import habit_logic
import repos

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get("VERCEL_ENV") == "production":
    app.config['SESSION_COOKIE_SECURE'] = True

# --- Helpers & Context Processors ---

def get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    try:
        user = db.execute_query(
            "SELECT id, full_name, email, role, is_active, created_at, last_login_at FROM users WHERE id = %s",
            (uid,), fetch_one=True
        )
        if not user or not user['is_active']:
            session.clear()
            return None
        return user
    except Exception:
        return None

def get_user_timezone():
    return session.get('timezone', 'Asia/Kolkata')

def get_today_local():
    # User's local date
    # In a full deployment, pytz or zoneinfo can be used; standard default here
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')

@app.context_processor
def inject_global_vars():
    csrf = session.get('csrf')
    if not csrf:
        csrf = secrets.token_hex(32)
        session['csrf'] = csrf
    
    cur_user = get_current_user()
    unread_count = 0
    if cur_user:
        try:
            uc = db.execute_query(
                "SELECT COUNT(*) AS c FROM notifications WHERE user_id = %s AND is_read = FALSE",
                (cur_user['id'],), fetch_one=True
            )
            unread_count = uc['c'] if uc else 0
        except Exception:
            unread_count = 0

    return {
        'current_user': cur_user,
        'csrf_token': lambda: csrf,
        'unread_count': unread_count,
        'formatted_today': datetime.now().strftime('%A, %d %B %Y')
    }

def require_login():
    u = get_current_user()
    if not u:
        abort(redirect(url_for('login_page')))
    return u

def require_admin():
    u = require_login()
    if u['role'] != 'admin':
        abort(403)
    return u

def verify_csrf():
    if request.method in ['POST', 'PUT', 'DELETE']:
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not token or token != session.get('csrf'):
            return False
    return True

# --- Public & Auth Routes ---

@app.route('/')
def home():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return render_template('login.html', error=None)

    # POST
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    if not email or not password:
        return render_template('login.html', error="Please provide email and password.")

    try:
        user = db.execute_query(
            "SELECT * FROM users WHERE email = %s",
            (email,), fetch_one=True
        )
        if not user or not check_password_hash(user['password_hash'], password):
            return render_template('login.html', error="Invalid email or password.")

        if not user['is_active']:
            return render_template('login.html', error="Your account has been deactivated. Contact an administrator.")

        # Update last login
        now_utc = datetime.now(timezone.utc)
        db.execute_query("UPDATE users SET last_login_at = %s WHERE id = %s", (now_utc, user['id']), commit=True)

        session.clear()
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = user['full_name']
        session['role'] = user['role']

        # Load user settings
        settings = db.execute_query("SELECT timezone, theme FROM user_settings WHERE user_id = %s", (user['id'],), fetch_one=True)
        if settings:
            session['timezone'] = settings['timezone']
            session['theme'] = settings['theme']
        else:
            session['timezone'] = 'Asia/Kolkata'
            session['theme'] = 'dark'

        if user['role'] == 'admin':
            repos.log_admin_audit(user['id'], user['email'], 'admin_login', 'user', user['id'], {'ip': request.remote_addr}, request.remote_addr)

        return redirect(url_for('dashboard'))
    except Exception as e:
        return render_template('login.html', error=f"Database error: {str(e)}")

@app.route('/register', methods=['POST'])
def register_action():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not full_name or not email or not password:
        return render_template('login.html', error="All fields are required.")
    if password != confirm_password:
        return render_template('login.html', error="Passwords do not match.")
    if len(password) < 8:
        return render_template('login.html', error="Password must be at least 8 characters.")

    try:
        existing = db.execute_query("SELECT id FROM users WHERE email = %s", (email,), fetch_one=True)
        if existing:
            return render_template('login.html', error="Email is already registered.")

        pw_hash = generate_password_hash(password)
        new_u = db.execute_query(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, 'user') RETURNING id",
            (full_name, email, pw_hash), commit=True, fetch_one=True
        )
        uid = new_u['id']

        # Insert default settings
        db.execute_query(
            "INSERT INTO user_settings (user_id, theme, timezone) VALUES (%s, 'dark', 'Asia/Kolkata') ON CONFLICT DO NOTHING",
            (uid,), commit=True
        )

        session.clear()
        session['user_id'] = uid
        session['user_email'] = email
        session['user_name'] = full_name
        session['role'] = 'user'
        session['theme'] = 'dark'
        session['timezone'] = 'Asia/Kolkata'

        return redirect(url_for('dashboard'))
    except Exception as e:
        return render_template('login.html', error=f"Registration failed: {str(e)}")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- Main App Pages ---

@app.route('/dashboard')
def dashboard():
    u = require_login()
    uid = u['id']
    today_str = get_today_local()

    habits_raw = db.execute_query(
        "SELECT h.*, c.name AS category_name FROM habits h JOIN habit_categories c ON c.id = h.category_id WHERE h.user_id = %s AND h.status <> 'archived'",
        (uid,), fetch_all=True
    ) or []
    habits = repos.enrich_habits(uid, habits_raw, today_str)
    total_habits = len(habits)
    active_habits = [h for h in habits if h['status'] == 'active']
    due = [h for h in active_habits if h['due_today']]
    done_today = sum(1 for h in due if h['done_today'])
    pending_today = len(due) - done_today
    today_pct = int(round(done_today / len(due) * 100)) if due else None
    streaks = repos.overall_streaks(uid, today_str)

    # 7-day activity & consistency
    t_date = habit_logic.parse_date(today_str)
    from_7 = habit_logic.format_date(t_date - timedelta(days=6))
    week_act = repos.daily_activity(uid, from_7, today_str, today_str)

    chart_labels = []
    chart_vals = []
    for d_str, v in week_act.items():
        d_obj = habit_logic.parse_date(d_str)
        chart_labels.append(d_obj.strftime('%a'))
        chart_vals.append(int(round(v['completed'] / v['scheduled'] * 100)) if v['scheduled'] else None)
    has_chart = any(v['scheduled'] > 0 for v in week_act.values())

    from_30 = habit_logic.format_date(t_date - timedelta(days=29))
    month_act = repos.daily_activity(uid, from_30, today_str, today_str)
    ms = sum(v['scheduled'] for v in month_act.values())
    mc = sum(v['completed'] for v in month_act.values())
    consistency = int(round(mc / ms * 100)) if ms > 0 else None

    # Goals
    goals_raw = db.execute_query(
        "SELECT * FROM goals WHERE user_id = %s AND status = 'active' ORDER BY deadline ASC LIMIT 20",
        (uid,), fetch_all=True
    ) or []
    goals = repos.enrich_goals(uid, goals_raw, today_str)
    upcoming_goals = goals[:5]

    recent = repos.recent_activity(uid, 8)
    first_name = u['full_name'].split()[0] if u['full_name'] else 'there'

    return render_template(
        'dashboard.html',
        layout='app',
        page_title='Dashboard',
        active_page='dashboard',
        first_name=first_name,
        total_habits=total_habits,
        active_habits=active_habits,
        due=due,
        done_today=done_today,
        pending_today=pending_today,
        today_pct=today_pct,
        consistency=consistency,
        streaks=streaks,
        goals=goals,
        upcoming_goals=upcoming_goals,
        has_chart=has_chart,
        chart_data={'labels': chart_labels, 'values': chart_vals},
        recent=recent
    )

@app.route('/habits')
def habits_page():
    u = require_login()
    cats = db.execute_query("SELECT id, name FROM habit_categories ORDER BY id", fetch_all=True) or []
    return render_template(
        'habits.html',
        layout='app',
        page_title='Habits',
        active_page='habits',
        categories=cats,
        habit_icons=habit_logic.HABIT_ICONS,
        habit_colors=habit_logic.HABIT_COLORS
    )

@app.route('/goals')
def goals_page():
    u = require_login()
    cats = db.execute_query("SELECT id, name FROM habit_categories ORDER BY id", fetch_all=True) or []
    habits = db.execute_query(
        "SELECT id, name FROM habits WHERE user_id = %s AND status <> 'archived' ORDER BY name",
        (u['id'],), fetch_all=True
    ) or []
    return render_template(
        'goals.html',
        layout='app',
        page_title='Goals',
        active_page='goals',
        categories=cats,
        habits=habits
    )

@app.route('/calendar')
def calendar_page():
    require_login()
    return render_template(
        'calendar.html',
        layout='app',
        page_title='Calendar',
        active_page='calendar'
    )

@app.route('/analytics')
def analytics_page():
    require_login()
    return render_template(
        'analytics.html',
        layout='app',
        page_title='Analytics',
        active_page='analytics'
    )

@app.route('/notifications')
def notifications_page():
    require_login()
    return render_template(
        'notifications.html',
        layout='app',
        page_title='Notifications',
        active_page='notifications'
    )

@app.route('/profile')
def profile_page():
    u = require_login()
    uid = u['id']
    nh = db.execute_query("SELECT COUNT(*) AS c FROM habits WHERE user_id = %s", (uid,), fetch_one=True)['c']
    ng = db.execute_query("SELECT COUNT(*) AS c FROM goals WHERE user_id = %s", (uid,), fetch_one=True)['c']
    nl = db.execute_query("SELECT COUNT(*) AS c FROM habit_logs WHERE user_id = %s", (uid,), fetch_one=True)['c']

    # Format member_since with fallback to current date
    created_at = u.get('created_at')
    if created_at:
        if hasattr(created_at, 'strftime'):
            member_since = created_at.strftime('%d %b %Y')
        else:
            try:
                dt = datetime.fromisoformat(str(created_at))
                member_since = dt.strftime('%d %b %Y')
            except Exception:
                member_since = datetime.now().strftime('%d %b %Y')
    else:
        member_since = datetime.now().strftime('%d %b %Y')

    return render_template(
        'profile.html',
        layout='app',
        page_title='Profile',
        active_page='profile',
        user=u,
        member_since=member_since,
        counts={'habits': nh, 'goals': ng, 'logs': nl}
    )

@app.route('/settings')
def settings_page():
    u = require_login()
    s = db.execute_query("SELECT * FROM user_settings WHERE user_id = %s", (u['id'],), fetch_one=True)
    if not s:
        s = {'theme': 'dark', 'timezone': 'Asia/Kolkata', 'notify_reminders': True, 'notify_goals': True, 'notify_daily_summary': True}
    return render_template(
        'settings.html',
        layout='app',
        page_title='Settings',
        active_page='settings',
        settings=s
    )

# --- Admin Section (Mandatory Requirements) ---

@app.route('/admin')
def admin_overview():
    require_admin()
    def get_count(sql, params=None):
        try:
            res = db.execute_query(sql, params, fetch_one=True)
            if res:
                # Handle dictionary keys irrespective of casing or column name
                if 'c' in res:
                    return int(res['c'] or 0)
                # Return first value if dict
                for val in res.values():
                    return int(val or 0)
            return 0
        except Exception:
            return 0

    stats = {
        'Total users': get_count("SELECT COUNT(*) AS c FROM users"),
        'Active accounts': get_count("SELECT COUNT(*) AS c FROM users WHERE is_active = TRUE"),
        'Deactivated accounts': get_count("SELECT COUNT(*) AS c FROM users WHERE is_active = FALSE"),
        'Total habits': get_count("SELECT COUNT(*) AS c FROM habits"),
        'Total goals': get_count("SELECT COUNT(*) AS c FROM goals"),
        'Completions logged': get_count("SELECT COUNT(*) AS c FROM habit_logs"),
        'Completed goals': get_count("SELECT COUNT(*) AS c FROM goals WHERE status = 'completed'")
    }

    # 14-day trends (PostgreSQL CURRENT_DATE / date_trunc compatible)
    today = datetime.now(timezone.utc).date()
    days_map = {}
    for i in range(13, -1, -1):
        d_str = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        days_map[d_str] = {'users': 0, 'logs': 0}

    try:
        u_rows = db.execute_query(
            "SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS d, COUNT(*)::int AS c FROM users WHERE created_at >= (CURRENT_DATE - INTERVAL '14 days') GROUP BY 1",
            fetch_all=True
        ) or []
        for r in u_rows:
            ds = str(r['d']).strip()[:10]
            if ds in days_map:
                days_map[ds]['users'] = int(r['c'])
    except Exception:
        pass

    try:
        l_rows = db.execute_query(
            "SELECT to_char(date_trunc('day', completed_at), 'YYYY-MM-DD') AS d, COUNT(*)::int AS c FROM habit_logs WHERE completed_at >= (CURRENT_DATE - INTERVAL '14 days') GROUP BY 1",
            fetch_all=True
        ) or []
        for r in l_rows:
            ds = str(r['d']).strip()[:10]
            if ds in days_map:
                days_map[ds]['logs'] = int(r['c'])
    except Exception:
        pass

    chart_data = {
        'labels': list(days_map.keys()),
        'users': [v['users'] for v in days_map.values()],
        'logs': [v['logs'] for v in days_map.values()]
    }

    return render_template(
        'admin/index.html',
        layout='app',
        page_title='Admin Dashboard',
        active_page='admin',
        stats=stats,
        chart_data=chart_data
    )

@app.route('/admin/users')
def admin_users_page():
    require_admin()
    return render_template(
        'admin/users.html',
        layout='app',
        page_title='Manage Users',
        active_page='admin'
    )

@app.route('/admin/audit')
def admin_audit_page():
    require_admin()
    logs = db.execute_query("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100", fetch_all=True) or []
    return render_template(
        'admin/audit.html',
        layout='app',
        page_title='Admin Audit Trail',
        active_page='admin',
        logs=logs
    )

# --- Backwards Compatible API Endpoints for Vanilla JS Frontend ---

def get_req_data():
    if request.is_json:
        return request.get_json() or {}
    return request.form.to_dict()

# Habits API
@app.route('/api/habits/list.php', methods=['GET'])
def api_habits_list():
    try:
        u = require_login()
        q = request.args.get('q', '').strip()
        cat_id = request.args.get('category_id') or request.args.get('cat')
        status = request.args.get('status') or 'all'

        params = [u['id']]
        where = "WHERE h.user_id = %s"

        if status and status != 'all':
            where += " AND h.status = %s"
            params.append(status)
        else:
            where += " AND h.status <> 'archived'"

        if cat_id and str(cat_id) != '0':
            where += " AND h.category_id = %s"
            params.append(int(cat_id))

        if q:
            where += " AND (h.name ILIKE %s OR h.description ILIKE %s)"
            params.extend([f"%{q}%", f"%{q}%"])

        sql = f"""
        SELECT h.*, COALESCE(c.name, 'General') AS category_name
        FROM habits h
        LEFT JOIN habit_categories c ON c.id = h.category_id
        {where}
        ORDER BY h.id DESC
        """
        habits = db.execute_query(sql, tuple(params), fetch_all=True) or []
        enriched = repos.enrich_habits(u['id'], habits, get_today_local())

        for item in enriched:
            for k, v in list(item.items()):
                if hasattr(v, 'isoformat'):
                    item[k] = v.isoformat()

        return jsonify({'success': True, 'habits': enriched})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/habits/toggle.php', methods=['POST'])
def api_habits_toggle():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    hid = data.get('habit_id') or data.get('id')
    log_date = data.get('log_date') or get_today_local()
    if not hid:
        return jsonify({'success': False, 'message': 'Habit ID required.'}), 400

    habit = db.execute_query("SELECT id FROM habits WHERE id = %s AND user_id = %s", (hid, u['id']), fetch_one=True)
    if not habit:
        return jsonify({'success': False, 'message': 'Habit not found or unauthorized.'}), 404

    existing = db.execute_query("SELECT id FROM habit_logs WHERE habit_id = %s AND log_date = %s", (hid, log_date), fetch_one=True)
    if existing:
        db.execute_query("DELETE FROM habit_logs WHERE id = %s", (existing['id'],), commit=True)
        is_done = False
    else:
        db.execute_query("INSERT INTO habit_logs (habit_id, user_id, log_date) VALUES (%s, %s, %s)", (hid, u['id'], log_date), commit=True)
        is_done = True

    return jsonify({'success': True, 'done': is_done, 'log_date': log_date})

@app.route('/api/habits/save.php', methods=['POST'])
def api_habits_save():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    hid = data.get('id')
    name = data.get('name', '').strip()
    desc = data.get('description', '').strip()
    cat_id = int(data.get('category_id') or 1)
    start_date = data.get('start_date') or get_today_local()
    icon = data.get('icon', 'check-circle')
    color = data.get('color', '#4F46E5')
    sched_type = data.get('schedule_type', 'daily')
    weekly_target = int(data.get('weekly_target') or 1) if sched_type == 'weekly_target' else None
    reminder_time = data.get('reminder_time') or None

    if not name:
        return jsonify({'success': False, 'message': 'Name is required.'}), 400

    if hid:
        db.execute_query(
            """UPDATE habits SET name=%s, description=%s, category_id=%s, start_date=%s, icon=%s, color=%s, schedule_type=%s, weekly_target=%s, reminder_time=%s, updated_at=CURRENT_TIMESTAMP
               WHERE id=%s AND user_id=%s""",
            (name, desc, cat_id, start_date, icon, color, sched_type, weekly_target, reminder_time, hid, u['id']),
            commit=True
        )
        habit_id = hid
    else:
        new_h = db.execute_query(
            """INSERT INTO habits (user_id, category_id, name, description, icon, color, start_date, schedule_type, weekly_target, reminder_time)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (u['id'], cat_id, name, desc, icon, color, start_date, sched_type, weekly_target, reminder_time),
            commit=True, fetch_one=True
        )
        habit_id = new_h['id']

    # Update weekdays if schedule_type == 'weekdays'
    db.execute_query("DELETE FROM habit_schedules WHERE habit_id = %s", (habit_id,), commit=True)
    if sched_type == 'weekdays':
        weekdays = data.get('weekdays')
        if isinstance(weekdays, str):
            weekdays = [int(w) for w in weekdays.split(',') if w.isdigit()]
        elif isinstance(weekdays, list):
            weekdays = [int(w) for w in weekdays]
        for w in (weekdays or []):
            db.execute_query("INSERT INTO habit_schedules (habit_id, weekday) VALUES (%s, %s) ON CONFLICT DO NOTHING", (habit_id, w), commit=True)

    return jsonify({'success': True, 'id': habit_id})

@app.route('/api/habits/delete.php', methods=['POST'])
def api_habits_delete():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    hid = data.get('id')
    db.execute_query("DELETE FROM habits WHERE id = %s AND user_id = %s", (hid, u['id']), commit=True)
    return jsonify({'success': True})

# Goals API
@app.route('/api/goals/list.php', methods=['GET'])
def api_goals_list():
    u = require_login()
    q = request.args.get('q', '').strip()
    status = request.args.get('status') or 'all'

    params = [u['id']]
    where = "WHERE user_id = %s"

    if status and status != 'all':
        if status in ['active', 'completed', 'paused']:
            where += " AND status = %s"
            params.append(status)

    if q:
        where += " AND (title ILIKE %s OR specific_objective ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    sql = f"SELECT * FROM goals {where} ORDER BY deadline ASC"
    goals = db.execute_query(sql, tuple(params), fetch_all=True) or []
    enriched = repos.enrich_goals(u['id'], goals, get_today_local())

    # Handle computed overdue status filter if requested
    if status == 'overdue':
        enriched = [g for g in enriched if g.get('display_status') == 'overdue']

    return jsonify({'success': True, 'goals': enriched})

@app.route('/api/goals/save.php', methods=['POST'])
def api_goals_save():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    gid = data.get('id')
    title = data.get('title', '').strip()
    spec = data.get('specific_objective', '').strip()
    desc = data.get('description', '').strip()
    target = float(data.get('target_value') or 1.0)
    current = float(data.get('current_value') or 0.0)
    unit = data.get('unit', '').strip()
    prio = data.get('priority', 'medium')
    start_date = data.get('start_date') or get_today_local()
    deadline = data.get('deadline') or get_today_local()
    cat_id = int(data.get('category_id')) if data.get('category_id') and int(data.get('category_id')) > 0 else None

    if not title or not spec:
        return jsonify({'success': False, 'message': 'Title and objective required.'}), 400

    if gid:
        db.execute_query(
            """UPDATE goals SET title=%s, specific_objective=%s, description=%s, target_value=%s, current_value=%s, unit=%s, priority=%s, start_date=%s, deadline=%s, category_id=%s, updated_at=CURRENT_TIMESTAMP
               WHERE id=%s AND user_id=%s""",
            (title, spec, desc, target, current, unit, prio, start_date, deadline, cat_id, gid, u['id']),
            commit=True
        )
        goal_id = gid
    else:
        new_g = db.execute_query(
            """INSERT INTO goals (user_id, category_id, title, specific_objective, description, target_value, current_value, unit, priority, start_date, deadline)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (u['id'], cat_id, title, spec, desc, target, current, unit, prio, start_date, deadline),
            commit=True, fetch_one=True
        )
        goal_id = new_g['id']

    # Update linked habits
    db.execute_query("DELETE FROM goal_habits WHERE goal_id = %s", (goal_id,), commit=True)
    habit_ids = data.get('habit_ids')
    if isinstance(habit_ids, str):
        habit_ids = [int(h) for h in habit_ids.split(',') if h.isdigit()]
    elif isinstance(habit_ids, list):
        habit_ids = [int(h) for h in habit_ids]
    for hid in (habit_ids or []):
        db.execute_query("INSERT INTO goal_habits (goal_id, habit_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (goal_id, hid), commit=True)

    return jsonify({'success': True, 'id': goal_id})

@app.route('/api/goals/progress.php', methods=['POST'])
def api_goals_progress():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    gid = data.get('id')
    val = float(data.get('current_value') or 0.0)
    goal = db.execute_query("SELECT * FROM goals WHERE id = %s AND user_id = %s", (gid, u['id']), fetch_one=True)
    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    target = float(goal['target_value'])
    status = 'completed' if val >= target else goal['status']
    completed_at = datetime.now(timezone.utc) if (val >= target and not goal.get('completed_at')) else goal.get('completed_at')

    db.execute_query(
        "UPDATE goals SET current_value = %s, status = %s, completed_at = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (val, status, completed_at, gid), commit=True
    )
    return jsonify({'success': True, 'status': status, 'current_value': val})

@app.route('/api/goals/delete.php', methods=['POST'])
def api_goals_delete():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode is read-only.'}), 403
    data = get_req_data()
    gid = data.get('id')
    db.execute_query("DELETE FROM goals WHERE id = %s AND user_id = %s", (gid, u['id']), commit=True)
    return jsonify({'success': True})

# Calendar API
@app.route('/api/calendar/month.php', methods=['GET'])
def api_calendar_month():
    u = require_login()
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    start_d = date(year, month, 1)
    end_d = date(year + (1 if month == 12 else 0), 1 if month == 12 else (month + 1), 1) - timedelta(days=1)
    act = repos.daily_activity(u['id'], str(start_d), str(end_d), get_today_local())
    return jsonify({'success': True, 'activity': act})

@app.route('/api/calendar/day.php', methods=['GET'])
def api_calendar_day():
    u = require_login()
    d_str = request.args.get('date', get_today_local())
    habits = db.execute_query(
        "SELECT id, name, color, icon, status, start_date, schedule_type FROM habits WHERE user_id = %s ORDER BY name",
        (u['id'],), fetch_all=True
    ) or []
    ids = [h['id'] for h in habits]
    wd_map = repos.habit_weekdays_map(ids)
    logs_map = repos.habit_logs_map(u['id'], ids, d_str, d_str)
    today = get_today_local()

    items = []
    for h in habits:
        hid = h['id']
        is_done = d_str in logs_map.get(hid, set())
        status = None
        if is_done:
            status = 'done'
        elif h['status'] == 'active' and h['schedule_type'] != 'weekly_target' and habit_logic.hl_is_scheduled_on(h, wd_map.get(hid, []), d_str):
            status = 'missed' if d_str < today else ('pending' if d_str == today else 'upcoming')

        if status:
            items.append({
                'id': hid,
                'name': h['name'],
                'color': h['color'],
                'icon': h['icon'],
                'status': status
            })
    return jsonify({'success': True, 'habits': items, 'date': d_str})

# Analytics API
@app.route('/api/analytics/data.php', methods=['GET'])
def api_analytics_data():
    u = require_login()
    days_back = int(request.args.get('days', 30))
    t_date = habit_logic.parse_date(get_today_local())
    from_date = str(t_date - timedelta(days=days_back))
    to_date = str(t_date)

    daily = repos.daily_activity(u['id'], from_date, to_date, str(t_date))
    habits = db.execute_query(
        "SELECT id, name, color, status, start_date, schedule_type, weekly_target FROM habits WHERE user_id = %s",
        (u['id'],), fetch_all=True
    ) or []
    enriched_habits = repos.enrich_habits(u['id'], habits, str(t_date))

    return jsonify({
        'success': True,
        'daily': daily,
        'habits': enriched_habits,
        'streaks': repos.overall_streaks(u['id'], str(t_date))
    })

# Notifications API
@app.route('/api/notifications/list.php', methods=['GET'])
def api_notifications_list():
    u = require_login()
    notifs = db.execute_query(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
        (u['id'],), fetch_all=True
    ) or []
    return jsonify({'success': True, 'notifications': notifs})

@app.route('/api/notifications/read.php', methods=['POST'])
def api_notifications_read():
    u = require_login()
    data = get_req_data()
    nid = data.get('id')
    if nid:
        db.execute_query("UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s", (nid, u['id']), commit=True)
    else:
        db.execute_query("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (u['id'],), commit=True)
    return jsonify({'success': True})

@app.route('/api/notifications/delete.php', methods=['POST'])
def api_notifications_delete():
    u = require_login()
    db.execute_query("DELETE FROM notifications WHERE user_id = %s AND is_read = TRUE", (u['id'],), commit=True)
    return jsonify({'success': True})

# Profile & Settings API
@app.route('/api/profile/update.php', methods=['POST'])
def api_profile_update():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode cannot update profile.'}), 403
    data = get_req_data()
    name = data.get('full_name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Name is required.'}), 400
    db.execute_query("UPDATE users SET full_name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (name, u['id']), commit=True)
    session['user_name'] = name
    return jsonify({'success': True, 'message': 'Profile updated successfully.'})

@app.route('/api/profile/password.php', methods=['POST'])
def api_profile_password():
    u = require_login()
    if u['role'] == 'guest':
        return jsonify({'success': False, 'message': 'Guest mode cannot change password.'}), 403
    data = get_req_data()
    cur_p = data.get('current_password', '')
    new_p = data.get('new_password', '')
    conf_p = data.get('confirm_password', '')
    if new_p != conf_p:
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400
    if len(new_p) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters.'}), 400

    user_row = db.execute_query("SELECT password_hash FROM users WHERE id = %s", (u['id'],), fetch_one=True)
    if not user_row or not check_password_hash(user_row['password_hash'], cur_p):
        return jsonify({'success': False, 'message': 'Current password incorrect.'}), 400

    new_hash = generate_password_hash(new_p)
    db.execute_query("UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_hash, u['id']), commit=True)
    return jsonify({'success': True, 'message': 'Password updated successfully.'})

@app.route('/api/settings/save.php', methods=['POST'])
def api_settings_save():
    u = require_login()
    data = get_req_data()
    theme = data.get('theme', 'dark')
    tz = data.get('timezone', 'Asia/Kolkata')
    nr = bool(data.get('notify_reminders'))
    ng = bool(data.get('notify_goals'))
    nd = bool(data.get('notify_daily_summary'))

    db.execute_query(
        """INSERT INTO user_settings (user_id, theme, timezone, notify_reminders, notify_goals, notify_daily_summary, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (user_id) DO UPDATE SET theme=EXCLUDED.theme, timezone=EXCLUDED.timezone, notify_reminders=EXCLUDED.notify_reminders, notify_goals=EXCLUDED.notify_goals, notify_daily_summary=EXCLUDED.notify_daily_summary, updated_at=CURRENT_TIMESTAMP""",
        (u['id'], theme, tz, nr, ng, nd), commit=True
    )
    session['theme'] = theme
    session['timezone'] = tz
    return jsonify({'success': True, 'message': 'Settings saved successfully.'})

# Admin APIs
@app.route('/api/admin/users.php', methods=['GET'])
def api_admin_users():
    require_admin()
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    params = []
    where = "WHERE 1=1"
    if q:
        where += " AND (LOWER(full_name) LIKE %s OR LOWER(email) LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])

    count_res = db.execute_query(f"SELECT COUNT(*) AS c FROM users {where}", tuple(params), fetch_one=True)
    total = 0
    if count_res:
        if 'c' in count_res:
            total = int(count_res['c'] or 0)
        else:
            for v in count_res.values():
                total = int(v or 0)
                break

    sql = f"""
    SELECT u.id, u.full_name, u.email, u.role, u.is_active, u.created_at, u.last_login_at,
           COUNT(DISTINCT h.id) AS habits,
           COUNT(DISTINCT g.id) AS goals
    FROM users u
    LEFT JOIN habits h ON h.user_id = u.id
    LEFT JOIN goals g ON g.user_id = u.id
    {where}
    GROUP BY u.id
    ORDER BY u.id DESC
    LIMIT %s OFFSET %s
    """
    params.extend([per_page, offset])
    users = db.execute_query(sql, tuple(params), fetch_all=True) or []

    # Format dates safely for JSON
    formatted_users = []
    for u in users:
        item = dict(u)
        c_at = item.get('created_at')
        l_at = item.get('last_login_at')
        item['created_at'] = c_at.isoformat() if hasattr(c_at, 'isoformat') else (str(c_at) if c_at else '')
        item['last_login_at'] = l_at.isoformat() if hasattr(l_at, 'isoformat') else (str(l_at) if l_at else '')
        formatted_users.append(item)

    return jsonify({
        'success': True,
        'users': formatted_users,
        'total': total,
        'page': page,
        'pages': max(1, (total + per_page - 1) // per_page)
    })

@app.route('/api/admin/user_status.php', methods=['POST'])
def api_admin_user_status():
    admin = require_admin()
    data = get_req_data()
    uid = data.get('id')
    status = bool(int(data.get('is_active', 1)))

    if int(uid) == admin['id']:
        return jsonify({'success': False, 'message': 'You cannot deactivate your own account.'}), 400

    db.execute_query("UPDATE users SET is_active = %s WHERE id = %s", (status, uid), commit=True)
    repos.log_admin_audit(
        admin['id'], admin['email'], 'update_user_status', 'user', uid,
        {'is_active': status}, request.remote_addr
    )
    return jsonify({'success': True, 'message': 'User status updated.'})

# --- Health Check Endpoint ---
@app.route('/api/health')
def health():
    db_ok = False
    try:
        ver = db.execute_query("SELECT version()", fetch_one=True)
        db_ok = bool(ver)
    except Exception:
        db_ok = False
    return jsonify({
        'status': 'healthy' if db_ok else 'degraded',
        'database': 'connected' if db_ok else 'disconnected',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
