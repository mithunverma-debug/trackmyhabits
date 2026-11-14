/* Monthly calendar: month data and day details come from the API (MySQL). Weeks start on Monday. */
(function () {
  const $ = s => document.querySelector(s), pad = n => String(n).padStart(2, '0');
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  let y, m, today = null, selected = null, days = {};

  async function loadMonth() {
    const { ok, data } = await TMH.api(`calendar/month.php?year=${y}&month=${m}`, null, 'GET');
    if (!ok) { TMH.toast(data.message || 'Could not load calendar.', 'error'); return; }
    days = data.days; today = data.today; renderGrid();
    const s = data.summary;
    $('#month-summary').textContent = s.percent === null ? 'No scheduled habits this month yet.'
      : `This month: ${s.done} done, ${s.missed} missed, ${s.pending + s.upcoming} still to come (${s.percent}% of due habits done so far).`;
  }
  function renderGrid() {
    $('#month-title').textContent = `${MONTHS[m - 1]} ${y}`;
    const offset = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, count = new Date(Date.UTC(y, m, 0)).getUTCDate();
    let html = '<span></span>'.repeat(offset);
    for (let d = 1; d <= count; d++) {
      const key = `${y}-${pad(m)}-${pad(d)}`, c = days[key] || {};
      const dots = ['done', 'missed', 'pending', 'upcoming'].filter(k => c[k]).map(k => `<i class="dot s-${k}" title="${c[k]} ${k}"></i>`).join('');
      const label = Object.keys(c).length ? ` ${['done','missed','pending','upcoming'].filter(k => c[k]).map(k => c[k] + ' ' + k).join(', ')}` : '';
      html += `<button class="cal-cell ${key === today ? 'is-today' : ''} ${key === selected ? 'is-selected' : ''}" data-date="${key}" aria-label="${d} ${MONTHS[m - 1]}${label}"><b>${d}</b><span class="dots">${dots}</span></button>`;
    }
    $('#cal-grid').innerHTML = html;
  }

  async function showDay(date) {
    selected = date; renderGrid(); const panel = $('#day-panel'); panel.innerHTML = '<div class="empty">Loading…</div>';
    const { ok, data } = await TMH.api('calendar/day.php?date=' + date, null, 'GET');
    if (!ok) { panel.innerHTML = `<div class="empty">${TMH.esc(data.message)}</div>`; return; }
    const pretty = new Date(date + 'T00:00:00Z').toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
    const badge = { done: 'badge-success', missed: 'badge-error', pending: 'badge-warning', upcoming: '' };
    let h = `<h2>${TMH.esc(pretty)}</h2>`;
    const done = data.habits.filter(x => x.status === 'done').length;
    h += data.habits.length ? `<p class="muted small">${done} of ${data.habits.length} habit(s) completed</p><ul class="checklist">` + data.habits.map(x => `
      <li><span class="hicon sm" style="background:${TMH.esc(x.color)}"><i data-lucide="${TMH.esc(x.icon)}"></i></span>
      <div style="flex:1;min-width:0">${TMH.esc(x.name)}</div><span class="badge ${badge[x.status]}">${x.status}</span>
      ${data.editable && x.status !== 'upcoming' ? `<button class="btn btn-sm" data-habit="${x.id}" data-done="${x.status === 'done' ? 1 : 0}">${x.status === 'done' ? 'Undo' : 'Mark done'}</button>` : ''}</li>`).join('') + '</ul>'
      : '<p class="muted">No habit activity on this day.</p>';
    if (data.goals_due.length) h += '<h3 style="margin-top:16px">Goal deadlines</h3><ul class="checklist">' + data.goals_due.map(g => `<li><div style="flex:1">${TMH.esc(g.title)}<div class="small muted">${Number(g.current_value)} / ${Number(g.target_value)} ${TMH.esc(g.unit)}</div></div><span class="badge">${TMH.esc(g.status)}</span></li>`).join('') + '</ul>';
    if (data.goals_achieved.length) h += '<h3 style="margin-top:16px">Goals achieved</h3><ul class="checklist">' + data.goals_achieved.map(t => `<li>🎉 ${TMH.esc(t)}</li>`).join('') + '</ul>';
    if (!data.editable && data.date < today) h += '<p class="hint">Older days are locked to keep history honest.</p>';
    panel.innerHTML = h; TMH.initIcons();
    panel.querySelectorAll('button[data-habit]').forEach(b => b.addEventListener('click', async () => {
      b.disabled = true;
      const r = await TMH.api('habits/toggle.php', { habit_id: +b.dataset.habit, date, completed: b.dataset.done !== '1' });
      if (!r.ok) TMH.toast(r.data.message, 'error'); await loadMonth(); showDay(date);
    }));
  }

  $('#cal-grid').addEventListener('click', e => { const c = e.target.closest('.cal-cell'); if (c) showDay(c.dataset.date); });
  const go = async delta => { m += delta; if (m < 1) { m = 12; y--; } if (m > 12) { m = 1; y++; } await loadMonth(); };
  $('#prev').addEventListener('click', () => go(-1)); $('#next').addEventListener('click', () => go(1));
  $('#today').addEventListener('click', async () => { const n = new Date(); y = n.getFullYear(); m = n.getMonth() + 1; await loadMonth(); showDay(today); });
  const n = new Date(); y = n.getFullYear(); m = n.getMonth() + 1; loadMonth().then(() => showDay(today));
})();
