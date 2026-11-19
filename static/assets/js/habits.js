/* Habits page: list, filters, create/edit dialog, complete/undo, status changes. */
(function () {
  const $ = s => document.querySelector(s);

  /* ----- Detail page: backfill buttons ----- */
  document.querySelectorAll('.js-toggle-day').forEach(btn => btn.addEventListener('click', async () => {
    btn.disabled = true;
    const { ok, data } = await TMH.api('habits/toggle', { habit_id: +btn.dataset.id, date: btn.dataset.date, completed: btn.dataset.done !== '1' });
    if (ok) location.reload(); else { TMH.toast(data.message, 'error'); btn.disabled = false; }
  }));

  const list = $('#habit-list'); if (!list) return; // rest only on the list page
  const dlg = $('#habit-dialog'), form = $('#habit-form');

  /* ----- Load + render ----- */
  async function load() {
    const qs = new URLSearchParams({ q: $('#f-q').value, category_id: $('#f-cat').value, status: $('#f-status').value });
    const { ok, data } = await TMH.api('habits/list?' + qs, null, 'GET');
    if (!ok) { list.innerHTML = `<div class="empty">${TMH.esc(data.message || 'Could not load habits.')}</div>`; return; }
    if (!data.habits.length) {
      const filtered = $('#f-q').value || $('#f-cat').value !== '0' || $('#f-status').value !== 'all';
      list.innerHTML = `<div class="empty card" style="grid-column:1/-1">${filtered ? 'No habits match your filters.' : 'No habits yet. Click “New habit” to create your first one.'}</div>`;
      return;
    }
    list.innerHTML = data.habits.map(card).join(''); TMH.initIcons();
  }
  function card(h) {
    const s = h.stats, weekly = h.schedule_type === 'weekly_target', unit = s.unit === 'weeks' ? 'wk' : 'd';
    const rate = s.completion_rate === null ? '—' : s.completion_rate + '%';
    const wk = weekly && h.week_progress ? ` · This week ${h.week_progress.count}/${h.week_progress.target}` : '';
    let main = '';
    if (h.status === 'active') {
      main = h.done_today
        ? `<button class="btn btn-sm btn-done" data-act="undo" data-id="${h.id}"><i data-lucide="check"></i> Done today</button>`
        : (h.due_today || weekly) ? `<button class="btn btn-sm btn-primary" data-act="done" data-id="${h.id}">Mark done</button>`
        : `<span class="badge">Not scheduled today</span>`;
    }
    const statusBtns = h.status === 'archived'
      ? `<button class="btn btn-sm" data-act="status" data-status="active" data-id="${h.id}">Restore</button>`
      : `<button class="btn btn-sm" data-act="status" data-status="${h.status === 'active' ? 'inactive' : 'active'}" data-id="${h.id}">${h.status === 'active' ? 'Pause' : 'Activate'}</button>
         <button class="btn btn-sm" data-act="status" data-status="archived" data-id="${h.id}">Archive</button>`;
    return `<div class="card habit-card ${h.status !== 'active' ? 'inactive' : ''}">
      <div class="row"><span class="hicon" style="background:${TMH.esc(h.color)}"><i data-lucide="${TMH.esc(h.icon)}"></i></span>
        <div><span class="name font-bold">${TMH.esc(h.name)}</span>
        <div class="muted small">${TMH.esc(h.schedule_label)}${wk}</div></div></div>
      <div class="meta"><span class="badge badge-primary">${TMH.esc(h.category_name)}</span>
        <span class="badge">🔥 ${s.current_streak}${unit} streak</span><span class="badge">Best ${s.longest_streak}${unit}</span><span class="badge">${rate}</span>
        ${h.status !== 'active' ? `<span class="badge badge-warning">${TMH.esc(h.status)}</span>` : ''}</div>
      <div class="actions">${main}${statusBtns}
        <button class="btn btn-sm" data-act="edit" data-id="${h.id}">Edit</button>
        <button class="btn btn-sm" data-act="delete" data-id="${h.id}">Delete</button></div></div>`;
  }

  /* ----- Actions (event delegation) ----- */
  list.addEventListener('click', async e => {
    const b = e.target.closest('button[data-act]'); if (!b) return;
    const id = +b.dataset.id, act = b.dataset.act; b.disabled = true;
    if (act === 'done' || act === 'undo') {
      const r = await TMH.api('habits/toggle', { habit_id: id, completed: act === 'done' });
      if (!r.ok) TMH.toast(r.data.message, 'error'); else TMH.toast(act === 'done' ? 'Nice work! Habit completed.' : 'Completion removed.');
      return load();
    }
    if (act === 'status') {
      const r = await TMH.api('habits/status', { id, status: b.dataset.status });
      TMH.toast(r.data.message, r.ok ? '' : 'error'); return load();
    }
    if (act === 'delete') {
      b.disabled = false;
      if (!confirm('Delete this habit and ALL its history? This cannot be undone. (Tip: Archive keeps the history.)')) return;
      const r = await TMH.api('habits/delete', { id }); TMH.toast(r.data.message, r.ok ? '' : 'error'); return load();
    }
    if (act === 'edit') {
      b.disabled = false;
      const qs = new URLSearchParams({ status: 'archived' });
      const all = [...(await TMH.api('habits/list?status=all', null, 'GET')).data.habits || [], ...(await TMH.api('habits/list?' + qs, null, 'GET')).data.habits || []];
      const h = all.find(x => x.id == id); if (h) openForm(h);
    }
  });

  /* ----- Dialog form ----- */
  function syncSchedule() {
    const t = form.schedule_type.value;
    $('#g-weekdays').hidden = t !== 'weekdays'; $('#g-target').hidden = t !== 'weekly_target';
  }
  form.schedule_type.addEventListener('change', syncSchedule);
  function openForm(h = null) {
    form.reset(); TMH.showErrors(form, {}); form.querySelector('.alert').hidden = true;
    $('#dlg-title').textContent = h ? 'Edit habit' : 'New habit';
    form.elements.id.value = h ? h.id : '';
    form.start_date.value = h ? h.start_date : new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD local
    if (h) {
      form.elements.name.value = h.name; form.description.value = h.description || ''; form.category_id.value = h.category_id;
      form.schedule_type.value = h.schedule_type; form.weekly_target.value = h.weekly_target || 3;
      form.reminder_time.value = (h.reminder_time || '').slice(0, 5);
      form.querySelector(`input[name=icon][value="${h.icon}"]`)?.click(); form.querySelector(`input[name=color][value="${h.color}"]`)?.click();
      form.querySelectorAll('input[name=weekdays]').forEach(c => c.checked = h.weekdays.includes(+c.value));
    }
    syncSchedule(); TMH.initIcons(); dlg.showModal();
  }
  $('#btn-new').addEventListener('click', () => openForm());
  $('#btn-cancel').addEventListener('click', () => dlg.close());
  $('#dlg-close-x').addEventListener('click', () => dlg.close());
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = form.querySelector('[type=submit]'); btn.disabled = true;
    const body = {
      id: form.elements.id.value || 0, name: form.elements.name.value, description: form.description.value, category_id: form.category_id.value,
      icon: form.icon.value, color: form.color.value, start_date: form.start_date.value, schedule_type: form.schedule_type.value,
      weekdays: [...form.querySelectorAll('input[name=weekdays]:checked')].map(c => +c.value),
      weekly_target: form.weekly_target.value, reminder_time: form.reminder_time.value,
    };
    const { ok, data } = await TMH.api('habits/save', body); btn.disabled = false;
    if (ok) { dlg.close(); TMH.toast(data.message); load(); }
    else { TMH.showErrors(form, data.errors); const a = form.querySelector('.alert'); a.textContent = data.message; a.hidden = false; }
  });

  /* ----- Filters ----- */
  let t; $('#f-q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(load, 250); });
  $('#f-cat').addEventListener('change', load); $('#f-status').addEventListener('change', load);
  load();
  if (new URLSearchParams(location.search).has('new')) openForm(); // dashboard "New habit" link
})();
