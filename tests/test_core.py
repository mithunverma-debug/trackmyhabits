"""
Unit and integration tests for TrackMyHabits Flask & habit_logic.
"""
import pytest
from datetime import datetime, date, timedelta
import habit_logic

def test_habit_logic_weekday():
    # Monday is 1, Sunday is 7
    d_mon = date(2026, 11, 9)
    assert habit_logic.hl_weekday(d_mon) == 1
    d_sun = date(2026, 11, 15)
    assert habit_logic.hl_weekday(d_sun) == 7

def test_habit_streak_daily():
    habit = {
        'start_date': '2026-11-01',
        'schedule_type': 'daily',
        'status': 'active'
    }
    weekdays = []
    # Logged 2026-11-01, 2026-11-02, 2026-11-03
    logs = {'2026-11-01', '2026-11-02', '2026-11-03'}
    today = '2026-11-03'
    stats = habit_logic.hl_stats(habit, weekdays, logs, today)
    assert stats['current_streak'] == 3
    assert stats['longest_streak'] == 3
    assert stats['done_periods'] == 3
    assert stats['missed_periods'] == 0

def test_habit_streak_with_missed():
    habit = {
        'start_date': '2026-11-01',
        'schedule_type': 'daily',
        'status': 'active'
    }
    weekdays = []
    # Done day 1, missed day 2, done day 3
    logs = {'2026-11-01', '2026-11-03'}
    today = '2026-11-03'
    stats = habit_logic.hl_stats(habit, weekdays, logs, today)
    assert stats['current_streak'] == 1
    assert stats['longest_streak'] == 1
    assert stats['done_periods'] == 2
    assert stats['missed_periods'] == 1

def test_activity_streaks():
    dates = ['2026-11-01', '2026-11-02', '2026-11-03', '2026-11-05', '2026-11-06']
    today = '2026-11-06'
    res = habit_logic.hl_activity_streaks(dates, today)
    assert res['current'] == 2
    assert res['longest'] == 3

def test_flask_app_routes():
    from app import app
    app.config['TESTING'] = True
    client = app.test_client()

    # Home redirects to login
    res = client.get('/', follow_redirects=False)
    assert res.status_code == 302
    assert '/login' in res.location

    # Login page loads
    res_login = client.get('/login')
    assert res_login.status_code == 200
    assert b"Sign In - TrackMyHabits" in res_login.data
