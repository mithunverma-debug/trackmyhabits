/* Admin: overview chart and user management. The server re-checks the admin role on every call. */
(function () {
  const chart = document.getElementById('adminChart');
  if (chart && window.Chart) {
    const d = JSON.parse(chart.dataset.chart), css = getComputedStyle(document.documentElement);
    new Chart(chart, { type: 'bar', data: { labels: d.labels.map(x => x.slice(5)), datasets: [
        { label: 'New users', data: d.users, backgroundColor: css.getPropertyValue('--secondary').trim(), borderRadius: 4 },
        { label: 'Habit completions', data: d.logs, backgroundColor: css.getPropertyValue('--primary').trim(), borderRadius: 4 }] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
  }
  const body = document.getElementById('users'); if (!body) return;
  const $ = s => document.querySelector(s); let page = 1, pages = 1;
  async function load() {
    const { ok, data } = await TMH.api(`admin/users?q=${encodeURIComponent($('#q').value)}&page=${page}`, null, 'GET');
    if (!ok) { body.innerHTML = `<tr><td colspan="9" class="empty">${TMH.esc(data.message || 'Error')}</td></tr>`; return; }
    pages = data.pages; $('#count').textContent = `${data.total} user(s)`; $('#page').textContent = `Page ${data.page} of ${data.pages}`;
    $('#prev').disabled = page <= 1; $('#next').disabled = page >= pages;
    body.innerHTML = data.users.length ? data.users.map(u => `<tr><td>${TMH.esc(u.full_name)}</td><td>${TMH.esc(u.email)}</td>
      <td><span class="badge ${u.role === 'admin' ? 'badge-primary' : ''}">${u.role}</span></td><td>${u.habits}</td><td>${u.goals}</td>
      <td>${TMH.esc((u.created_at || '').slice(0, 10))}</td><td>${TMH.esc((u.last_login_at || '—').slice(0, 16))}</td>
      <td><span class="badge ${+u.is_active ? 'badge-success' : 'badge-error'}">${+u.is_active ? 'Active' : 'Deactivated'}</span></td>
      <td>${u.role === 'admin' ? '' : `<button class="btn btn-sm" data-id="${u.id}" data-active="${+u.is_active ? 0 : 1}">${+u.is_active ? 'Deactivate' : 'Activate'}</button>`}</td></tr>`).join('')
      : '<tr><td colspan="9" class="empty">No users found.</td></tr>';
  }
  body.addEventListener('click', async e => {
    const b = e.target.closest('button[data-id]'); if (!b) return;
    if (b.dataset.active === '0' && !confirm('Deactivate this account? The user will be unable to log in.')) return;
    b.disabled = true; const r = await TMH.api('admin/user_status', { id: +b.dataset.id, is_active: +b.dataset.active });
    TMH.toast(r.data.message, r.ok ? '' : 'error'); load();
  });
  let t; $('#q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { page = 1; load(); }, 300); });
  $('#prev').addEventListener('click', () => { page--; load(); }); $('#next').addEventListener('click', () => { page++; load(); }); load();
})();
