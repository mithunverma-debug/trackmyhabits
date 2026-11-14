/* Notification history: read/unread, mark read, mark all read, delete. */
(function () {
  const $ = s => document.querySelector(s), list = $('#list');
  const icon = { habit_reminder: 'alarm-clock', goal_deadline: 'calendar-clock', goal_completed: 'trophy', daily_summary: 'bar-chart-3' };
  async function load() {
    const { ok, data } = await TMH.api('notifications/list.php?filter=' + $('#filter').value, null, 'GET');
    if (!ok) { list.innerHTML = `<div class="empty">${TMH.esc(data.message || 'Could not load.')}</div>`; return; }
    if (!data.notifications.length) { list.innerHTML = '<div class="empty">You are all caught up. No notifications.</div>'; return; }
    list.innerHTML = '<ul class="checklist">' + data.notifications.map(n => `
      <li class="notif ${n.is_read ? '' : 'unread'}"><span class="hicon sm" style="background:var(--primary)"><i data-lucide="${icon[n.type] || 'bell'}"></i></span>
        <div style="flex:1;min-width:0"><div><strong>${TMH.esc(n.title)}</strong> ${n.is_read ? '' : '<span class="badge badge-primary">New</span>'}</div>
          <div class="muted">${TMH.esc(n.message)}</div>
          <div class="small muted">${new Date(n.created_at).toLocaleString()}${n.link ? ` · <a href="${TMH.base}/${TMH.esc(n.link)}" data-open="${n.id}">Open</a>` : ''}</div></div>
        <div class="row" style="gap:4px">${n.is_read ? '' : `<button class="btn btn-sm" data-read="${n.id}">Mark read</button>`}<button class="btn btn-sm" data-del="${n.id}" aria-label="Delete">✕</button></div></li>`).join('') + '</ul>';
    TMH.initIcons();
  }
  list.addEventListener('click', async e => {
    const t = e.target;
    if (t.dataset.read) { await TMH.api('notifications/read.php', { id: +t.dataset.read }); load(); }
    if (t.dataset.del) { await TMH.api('notifications/delete.php', { id: +t.dataset.del }); load(); }
    if (t.dataset.open) { e.preventDefault(); await TMH.api('notifications/read.php', { id: +t.dataset.open }); location.href = t.href; } // mark read first, then open
  });
  $('#read-all').addEventListener('click', async () => { await TMH.api('notifications/read.php', { all: true }); TMH.toast('All marked as read.'); load(); });
  $('#del-read').addEventListener('click', async () => { if (confirm('Delete all read notifications?')) { await TMH.api('notifications/delete.php', { all_read: true }); load(); } });
  $('#filter').addEventListener('change', load); load();
})();
