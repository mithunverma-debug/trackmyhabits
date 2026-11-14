/* Goals page: list, filters, create/edit, progress update, complete/pause/reopen/delete. */
(function () {
  const $ = s => document.querySelector(s);
  const list = $('#goal-list'), gd = $('#goal-dialog'), gf = $('#goal-form'), pd = $('#prog-dialog'), pf = $('#prog-form');
  let goals = [];
  const fmt = n => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

  async function load() {
    const qs = new URLSearchParams({ q: $('#f-q').value, status: $('#f-status').value });
    const { ok, data } = await TMH.api('goals/list.php?' + qs, null, 'GET');
    if (!ok) { list.innerHTML = `<div class="empty">${TMH.esc(data.message || 'Could not load goals.')}</div>`; return; }
    goals = data.goals;
    if (!goals.length) {
      const filtered = $('#f-q').value || $('#f-status').value !== 'all';
      list.innerHTML = `<div class="empty card" style="grid-column:1/-1">${filtered ? 'No goals match your filters.' : 'No goals yet. Click “New goal” to set your first SMART goal.'}</div>`; return;
    }
    list.innerHTML = goals.map(card).join(''); TMH.initIcons();
  }
  function card(g) {
    const badge = { active: 'badge-primary', completed: 'badge-success', overdue: 'badge-error', paused: 'badge-warning' }[g.display_status];
    const due = g.display_status === 'completed' ? 'Completed' : g.days_left < 0 ? `${-g.days_left} day(s) overdue` : g.days_left === 0 ? 'Due today' : `${g.days_left} day(s) left`;
    const habits = g.habits.map(h => `<span class="badge" style="border-left:3px solid ${TMH.esc(h.color)}">${TMH.esc(h.name)}</span>`).join('');
    let btns = '';
    if (g.status === 'active') btns = `<button class="btn btn-sm btn-primary" data-act="progress" data-id="${g.id}">Update progress</button>
      <button class="btn btn-sm" data-act="complete" data-id="${g.id}">Mark complete</button><button class="btn btn-sm" data-act="pause" data-id="${g.id}">Pause</button>`;
    else if (g.status === 'paused') btns = `<button class="btn btn-sm" data-act="resume" data-id="${g.id}">Resume</button>`;
    else btns = `<button class="btn btn-sm" data-act="reopen" data-id="${g.id}">Reopen</button>`;
    return `<div class="card goal-card"><div class="row" style="justify-content:space-between;align-items:flex-start">
      <h3 style="margin:0">${TMH.esc(g.title)}</h3><span class="badge ${badge}">${TMH.esc(g.display_status)}</span></div>
      <p class="muted small" style="margin:0">${TMH.esc(g.specific_objective)}</p>
      <div><div class="row" style="justify-content:space-between"><strong>${fmt(g.current_value)} / ${fmt(g.target_value)} ${TMH.esc(g.unit)}</strong><span class="small muted">${g.percent}%</span></div>
        <div class="progress" role="progressbar" aria-valuenow="${g.percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:${g.percent}%"></span></div></div>
      <div class="muted small">${TMH.esc(g.start_date)} → ${TMH.esc(g.deadline)} · ${due} · ${TMH.esc(g.priority)} priority</div>
      ${habits ? `<div class="meta">${habits}</div><div class="muted small">${g.linked_completions} linked habit completion(s) in this period</div>` : ''}
      <div class="actions">${btns}<button class="btn btn-sm" data-act="edit" data-id="${g.id}">Edit</button><button class="btn btn-sm" data-act="delete" data-id="${g.id}">Delete</button></div></div>`;
  }

  list.addEventListener('click', async e => {
    const b = e.target.closest('button[data-act]'); if (!b) return;
    const id = +b.dataset.id, act = b.dataset.act, g = goals.find(x => x.id === id);
    if (act === 'edit') return openGoal(g);
    if (act === 'progress') {
      pf.reset(); TMH.showErrors(pf, {}); pf.querySelector('.alert').hidden = true;
      pf.elements.id.value = id; pf.current_value.value = g.current_value; $('#prog-title').textContent = g.title;
      $('#p-label').textContent = `Current progress (${g.unit}) — target ${fmt(g.target_value)}`; return pd.showModal();
    }
    if (act === 'delete') { if (!confirm('Delete this goal? Linked habits are kept.')) return;
      const r = await TMH.api('goals/delete.php', { id }); TMH.toast(r.data.message, r.ok ? '' : 'error'); return load(); }
    let body = { id, action: act };
    if (act === 'complete' && g.current_value < g.target_value) {
      if (!confirm('You have not reached the target yet. Mark this goal as completed anyway?')) return;
      body.confirm = true;
    }
    b.disabled = true; const r = await TMH.api('goals/state.php', body);
    TMH.toast(r.data.message, r.ok ? '' : 'error'); load();
  });

  function openGoal(g = null) {
    gf.reset(); TMH.showErrors(gf, {}); gf.querySelector('.alert').hidden = true;
    $('#dlg-title').textContent = g ? 'Edit goal' : 'New goal'; gf.elements.id.value = g ? g.id : '';
    const today = new Date().toLocaleDateString('en-CA'); gf.start_date.value = g ? g.start_date : today;
    if (g) {
      gf.elements.title.value = g.title; gf.specific_objective.value = g.specific_objective; gf.description.value = g.description || '';
      gf.target_value.value = g.target_value; gf.current_value.value = g.current_value; gf.unit.value = g.unit;
      gf.deadline.value = g.deadline; gf.category_id.value = g.category_id || 0; gf.priority.value = g.priority;
    }
    gf.querySelectorAll('input[name=habit_ids]').forEach(c => c.checked = !!g && g.habit_ids.includes(+c.value));
    gd.showModal();
  }
  $('#btn-new').addEventListener('click', () => openGoal());
  document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));

  gf.addEventListener('submit', async e => {
    e.preventDefault(); const btn = gf.querySelector('[type=submit]'); btn.disabled = true;
    const body = { id: gf.elements.id.value || 0 };
    ['title', 'specific_objective', 'description', 'target_value', 'current_value', 'unit', 'start_date', 'deadline', 'category_id', 'priority'].forEach(k => body[k] = gf.elements[k].value);
    body.habit_ids = [...gf.querySelectorAll('input[name=habit_ids]:checked')].map(c => +c.value);
    const { ok, data } = await TMH.api('goals/save.php', body); btn.disabled = false;
    if (ok) { gd.close(); TMH.toast(data.message); load(); }
    else { TMH.showErrors(gf, data.errors); const a = gf.querySelector('.alert'); a.textContent = data.message; a.hidden = false; }
  });
  pf.addEventListener('submit', async e => {
    e.preventDefault(); const btn = pf.querySelector('[type=submit]'); btn.disabled = true;
    const { ok, data } = await TMH.api('goals/progress.php', { id: +pf.elements.id.value, current_value: pf.current_value.value }); btn.disabled = false;
    if (ok) { pd.close(); TMH.toast(data.message); load(); } else { TMH.showErrors(pf, data.errors); const a = pf.querySelector('.alert'); a.textContent = data.message; a.hidden = false; }
  });

  let t; $('#f-q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(load, 250); });
  $('#f-status').addEventListener('change', load); load();
})();
