"""
Pure Python habit, schedule, streak, and period calculation logic.
Faithful port of includes/habit_logic.php
"""
from datetime import datetime, date, timedelta, timezone

HABIT_ICONS = [
    'check-circle', 'droplet', 'dumbbell', 'book-open', 'brain', 'moon',
    'sun', 'apple', 'heart', 'coffee', 'footprints', 'bike', 'pencil',
    'piggy-bank', 'music', 'leaf', 'smile', 'target', 'code', 'briefcase'
]

HABIT_COLORS = [
    '#4F46E5', '#0EA5E9', '#16A34A', '#D97706', '#DC2626', '#DB2777', '#7C3AED', '#0D9488'
]

BACKFILL_DAYS = 7

def parse_date(s):
    if isinstance(s, date):
        return s
    if isinstance(s, str):
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    return s

def format_date(d):
    if isinstance(d, (datetime, date)):
        return d.strftime('%Y-%m-%d')
    return str(d)

def hl_weekday(d):
    """1=Mon ... 7=Sun (ISO weekday)"""
    return d.isoweekday()

def hl_week_start(d):
    return d - timedelta(days=hl_weekday(d) - 1)

def hl_is_scheduled_on(habit, weekdays, check_date):
    check_date = parse_date(check_date)
    start_date = parse_date(habit['start_date'])
    if check_date < start_date:
        return False
    sched = habit.get('schedule_type', 'daily')
    if sched == 'weekdays':
        return hl_weekday(check_date) in weekdays
    return True

def hl_periods(habit, weekdays, logs_set, today):
    """
    Builds the period list.
    logs_set: set of 'YYYY-MM-DD' strings
    """
    start = parse_date(habit['start_date'])
    t = parse_date(today)
    out = []

    sched = habit.get('schedule_type', 'daily')
    if sched == 'weekly_target':
        target = max(1, int(habit.get('weekly_target') or 1))
        w = hl_week_start(start)
        while w <= t:
            we = w + timedelta(days=6)
            from_d = max(w, start)
            to_d = min(we, t)
            avail = (we - from_d).days + 1
            need = min(target, avail)

            f_str = format_date(from_d)
            tt_str = format_date(to_d)
            count = sum(1 for log_d in logs_set if f_str <= log_d <= tt_str)

            we_str = format_date(we)
            today_str = format_date(t)
            if count >= need:
                status = 'done'
            elif we_str < today_str:
                status = 'missed'
            else:
                status = 'pending'

            out.append({
                'start': format_date(w),
                'end': we_str,
                'status': status,
                'count': count,
                'target': need
            })
            w += timedelta(days=7)
        return out

    # Daily or weekdays
    cur = start
    today_str = format_date(t)
    while cur <= t:
        cur_iso = hl_weekday(cur)
        if sched == 'weekdays' and cur_iso not in weekdays:
            cur += timedelta(days=1)
            continue
        k = format_date(cur)
        if k in logs_set:
            status = 'done'
        elif k < today_str:
            status = 'missed'
        else:
            status = 'pending'

        out.append({'start': k, 'end': k, 'status': status})
        cur += timedelta(days=1)
    return out

def hl_stats(habit, weekdays, logs_set, today):
    periods = hl_periods(habit, weekdays, logs_set, today)
    run = 0
    longest = 0
    done = 0
    missed = 0
    for p in periods:
        if p['status'] == 'done':
            run += 1
            done += 1
            longest = max(longest, run)
        elif p['status'] == 'missed':
            run = 0
            missed += 1

    den = done + missed
    comp_rate = round(done / den * 100, 1) if den > 0 else None

    return {
        'current_streak': run,
        'longest_streak': longest,
        'done_periods': done,
        'missed_periods': missed,
        'completion_rate': comp_rate,
        'total_completions': len(logs_set),
        'unit': 'weeks' if habit.get('schedule_type') == 'weekly_target' else 'days'
    }

def hl_due_today(habit, weekdays, logs_set, today):
    start = parse_date(habit['start_date'])
    t = parse_date(today)
    today_str = format_date(t)
    if habit.get('status') != 'active' or t < start:
        return False
    if today_str in logs_set:
        return True
    sched = habit.get('schedule_type', 'daily')
    if sched != 'weekly_target':
        return hl_is_scheduled_on(habit, weekdays, today)
    periods = hl_periods(habit, weekdays, logs_set, today)
    if periods:
        last = periods[-1]
        return last['status'] != 'done'
    return True

def hl_schedule_label(habit, weekdays):
    names = {1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'}
    sched = habit.get('schedule_type', 'daily')
    if sched == 'daily':
        return 'Every day'
    elif sched == 'weekdays':
        return ', '.join(names.get(w, '') for w in weekdays)
    elif sched == 'weekly_target':
        return f"{int(habit.get('weekly_target') or 1)}× per week"
    return ''

def hl_activity_streaks(dates_list, today):
    """
    Overall activity streaks across all habits.
    """
    if not dates_list:
        return {'current': 0, 'longest': 0}
    clean_dates = sorted(list(set(format_date(d) for d in dates_list)))
    dates_set = set(clean_dates)

    longest = 0
    run = 0
    prev = None
    for d_str in clean_dates:
        d = parse_date(d_str)
        if prev is not None and (prev + timedelta(days=1)) == d:
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        prev = d

    today_date = parse_date(today)
    today_str = format_date(today_date)
    # If today hasn't been completed yet, check starting from yesterday
    cur = 0
    check = today_date if today_str in dates_set else (today_date - timedelta(days=1))
    while format_date(check) in dates_set:
        cur += 1
        check -= timedelta(days=1)

    return {'current': cur, 'longest': longest}

def hl_range_stats(habit, weekdays, logs_set, today, from_date, to_date):
    """
    Done/missed counts for periods that overlap [from_date, to_date].
    Pending periods are ignored.
    Faithful port of PHP hl_range_stats.
    """
    done = 0
    missed = 0
    periods = hl_periods(habit, weekdays, logs_set, today)
    for p in periods:
        if p['end'] < from_date or p['start'] > to_date:
            continue
        if p['status'] == 'done':
            done += 1
        elif p['status'] == 'missed':
            missed += 1
    den = done + missed
    rate = round(done / den * 100, 1) if den > 0 else None
    return {'done': done, 'missed': missed, 'rate': rate}
