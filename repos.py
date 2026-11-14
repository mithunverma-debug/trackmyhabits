"""
Repository helpers for Habits, Schedules, Logs, SMART Goals, and Notifications.
"""
from datetime import datetime, date, timedelta, timezone
from db import execute_query, utc_now_iso
import habit_logic

def find_habit(uid, habit_id):
    sql = """
    SELECT h.*, c.name AS category_name
    FROM habits h
    JOIN habit_categories c ON c.id = h.category_id
    WHERE h.id = %s AND h.user_id = %s
    """
    return execute_query(sql, (habit_id, uid), fetch_one=True)

def habit_weekdays_map(habit_ids):
    if not habit_ids:
        return {}
    sql = f"SELECT habit_id, weekday FROM habit_schedules WHERE habit_id IN ({','.join(['%s']*len(habit_ids))}) ORDER BY weekday"
    rows = execute_query(sql, tuple(habit_ids), fetch_all=True)
    m = {}
    for r in rows:
        hid = r['habit_id']
        m.setdefault(hid, []).append(r['weekday'])
    return m

def habit_logs_map(uid, habit_ids, from_date=None, to_date=None):
    if not habit_ids:
        return {}
    params = [uid] + list(habit_ids)
    sql = f"SELECT habit_id, log_date FROM habit_logs WHERE user_id = %s AND habit_id IN ({','.join(['%s']*len(habit_ids))})"
    if from_date:
        sql += " AND log_date >= %s"
        params.append(str(from_date))
    if to_date:
        sql += " AND log_date <= %s"
        params.append(str(to_date))
    rows = execute_query(sql, tuple(params), fetch_all=True)
    m = {}
    for r in rows:
        hid = r['habit_id']
        d_str = habit_logic.format_date(r['log_date'])
        m.setdefault(hid, set()).add(d_str)
    return m

def enrich_habits(uid, habits, today_str):
    if not habits:
        return []
    ids = [h['id'] for h in habits]
    wd_map = habit_weekdays_map(ids)
    logs_map = habit_logs_map(uid, ids)

    out = []
    for h in habits:
        hid = h['id']
        w = wd_map.get(hid, [])
        l_set = logs_map.get(hid, set())

        item = dict(h)
        item['weekdays'] = w
        item['schedule_label'] = habit_logic.hl_schedule_label(h, w)
        item['stats'] = habit_logic.hl_stats(h, w, l_set, today_str)
        item['done_today'] = today_str in l_set
        item['due_today'] = habit_logic.hl_due_today(h, w, l_set, today_str)

        if h.get('schedule_type') == 'weekly_target':
            periods = habit_logic.hl_periods(h, w, l_set, today_str)
            last_p = periods[-1] if periods else None
            item['week_progress'] = {'count': last_p['count'], 'target': last_p['target']} if last_p else None

        out.append(item)
    return out

def daily_activity(uid, from_date, to_date, today_str):
    sql = "SELECT * FROM habits WHERE user_id = %s AND status = 'active'"
    habits = execute_query(sql, (uid,), fetch_all=True)
    if not habits:
        return {}
    ids = [h['id'] for h in habits]
    wd_map = habit_weekdays_map(ids)
    logs_map = habit_logs_map(uid, ids, from_date, to_date)

    out = {}
    cur = habit_logic.parse_date(from_date)
    end = habit_logic.parse_date(to_date)
    while cur <= end:
        k = habit_logic.format_date(cur)
        s = 0
        d = 0
        for h in habits:
            hid = h['id']
            if k < habit_logic.format_date(h['start_date']):
                continue
            is_done = k in logs_map.get(hid, set())
            sched = h.get('schedule_type', 'daily')
            if sched == 'weekly_target':
                if is_done:
                    s += 1
                    d += 1
            elif habit_logic.hl_is_scheduled_on(h, wd_map.get(hid, []), k):
                s += 1
                if is_done:
                    d += 1
        out[k] = {'scheduled': s, 'completed': d}
        cur += timedelta(days=1)
    return out

def overall_streaks(uid, today_str):
    sql = "SELECT DISTINCT log_date FROM habit_logs WHERE user_id = %s"
    rows = execute_query(sql, (uid,), fetch_all=True)
    dates_list = [r['log_date'] for r in rows]
    return habit_logic.hl_activity_streaks(dates_list, today_str)

def recent_activity(uid, limit=8):
    sql = """
    SELECT h.name, h.color, l.log_date, l.completed_at
    FROM habit_logs l
    JOIN habits h ON h.id = l.habit_id
    WHERE l.user_id = %s
    ORDER BY l.completed_at DESC
    LIMIT %s
    """
    rows = execute_query(sql, (uid, limit), fetch_all=True)
    items = []
    for r in rows:
        items.append({
            'time': r['completed_at'].isoformat() if hasattr(r['completed_at'], 'isoformat') else str(r['completed_at']),
            'text': f"Completed “{r['name']}”",
            'sub': f"for {habit_logic.format_date(r['log_date'])}",
            'color': r['color']
        })

    sql_goals = """
    SELECT title, completed_at
    FROM goals
    WHERE user_id = %s AND status = 'completed' AND completed_at IS NOT NULL
    ORDER BY completed_at DESC
    LIMIT 3
    """
    g_rows = execute_query(sql_goals, (uid,), fetch_all=True)
    for gr in g_rows:
        items.append({
            'time': gr['completed_at'].isoformat() if hasattr(gr['completed_at'], 'isoformat') else str(gr['completed_at']),
            'text': f"Goal achieved: “{gr['title']}”",
            'sub': '',
            'color': '#16A34A'
        })
    items.sort(key=lambda x: x['time'], reverse=True)
    return items[:limit]

def enrich_goals(uid, goals, today_str):
    if not goals:
        return []
    ids = [g['id'] for g in goals]
    sql_links = f"""
    SELECT gh.goal_id, h.id, h.name, h.color, h.icon
    FROM goal_habits gh
    JOIN habits h ON h.id = gh.habit_id
    WHERE h.user_id = %s AND gh.goal_id IN ({','.join(['%s']*len(ids))})
    """
    links_rows = execute_query(sql_links, tuple([uid] + ids), fetch_all=True)
    links_map = {}
    for r in links_rows:
        links_map.setdefault(r['goal_id'], []).append(r)

    out = []
    t_date = habit_logic.parse_date(today_str)
    for g in goals:
        item = dict(g)
        gid = g['id']
        cur = float(g.get('current_value') or 0.0)
        tar = float(g.get('target_value') or 1.0)
        item['percent'] = round(min(100.0, cur / tar * 100), 1) if tar > 0 else 0.0

        dl_date = habit_logic.parse_date(g['deadline'])
        days_left = (dl_date - t_date).days
        item['days_left'] = days_left

        if g.get('status') == 'active' and dl_date < t_date:
            item['display_status'] = 'overdue'
        else:
            item['display_status'] = g.get('status')

        item['habits'] = links_map.get(gid, [])
        item['habit_ids'] = [h['id'] for h in item['habits']]
        out.append(item)
    return out

def add_notification(uid, n_type, title, message, link, dedupe_key):
    sql = """
    INSERT INTO notifications (user_id, type, title, message, link, dedupe_key)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, dedupe_key) DO NOTHING
    """
    execute_query(sql, (uid, n_type, title, message, link, dedupe_key), commit=True)

def log_admin_audit(actor_id, actor_email, action, target_type, target_id=None, details=None, ip_address=None):
    import json
    sql = """
    INSERT INTO audit_logs (actor_id, actor_email, action, target_type, target_id, details, ip_address)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute_query(sql, (actor_id, actor_email, action, target_type, str(target_id) if target_id else None, json.dumps(details or {}), ip_address), commit=True)
