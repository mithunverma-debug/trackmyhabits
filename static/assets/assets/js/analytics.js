/* Analytics: all charts are drawn from /api/analytics/data (Supabase PostgreSQL). */
(function () {
  const $ = s => document.querySelector(s), css = getComputedStyle(document.documentElement);
  const col = n => css.getPropertyValue(n).trim(), charts = {};
  const fmtDate = d => new Date(d + 'T00:00:00Z').toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' });

  function draw(id, config, hasData, emptyMsg) {
    charts[id]?.destroy(); const canvas = $('#c-' + id), empty = $('#e-' + id);
    if (!canvas || !empty) return;
    canvas.parentElement.hidden = !hasData; empty.hidden = hasData; empty.textContent = emptyMsg;
    if (hasData && window.Chart) charts[id] = new Chart(canvas, config);
  }
  const axes = (extra = {}) => ({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
    scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%', color: col('--muted') }, grid: { color: col('--border') } },
              x: { ticks: { color: col('--muted'), maxTicksLimit: 10 }, grid: { display: false } } }, ...extra });
  const any = arr => Array.isArray(arr) && arr.some(v => v !== null);

  async function load() {
    const qs = new URLSearchParams(); const p = $('#preset').value;
    if (p === 'custom') { qs.set('from', $('#from').value); qs.set('to', $('#to').value); }
    else { const to = new Date(), from = new Date(); from.setDate(to.getDate() - (+p - 1)); qs.set('from', from.toLocaleDateString('en-CA')); qs.set('to', to.toLocaleDateString('en-CA')); }
    const { ok, data } = await TMH.api('analytics/data?' + qs, null, 'GET');
    const isReady = ok && Boolean(data?.summary); const alert = $('#alert'); alert.hidden = isReady;
    if (!isReady) { alert.textContent = data?.message || 'Could not load analytics.'; return; }
    const s = data.summary;
    $('#summary').innerHTML = [
      ['Overall completion', s.percent == null ? '—' : s.percent + '%', `${s.completed ?? 0} of ${s.scheduled ?? 0} scheduled`],
      ['Best day', s.best_day ? s.best_day.percent + '%' : '—', s.best_day ? fmtDate(s.best_day.date) : 'No data yet'],
      ['Current streak', (s.streaks?.current ?? 0) + ' d', 'Days with a habit done'], ['Longest streak', (s.streaks?.longest ?? 0) + ' d', ''],
    ].map(([l, v, sub]) => `<div class="card stat"><div class="label">${l}</div><div class="value">${TMH.esc(v)}</div><div class="small muted">${TMH.esc(sub)}</div></div>`).join('');

    const none = 'No scheduled habits in this period.';
    const d = data.daily || { labels: [], values: [], completed: [], scheduled: [] };
    draw('daily', { type: 'bar', data: { labels: d.labels.map(fmtDate), datasets: [{ data: d.values, backgroundColor: col('--primary'), borderRadius: 4 }] },
      options: axes({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.raw === null ? 'Nothing scheduled' : `${c.raw}% (${d.completed[c.dataIndex]}/${d.scheduled[c.dataIndex]})` } } } }) }, any(d.values), none);
    draw('trend', { type: 'line', data: { labels: (data.trend?.labels || []).map(fmtDate), datasets: [{ data: data.trend?.values || [], borderColor: col('--secondary') || '#0EA5E9', backgroundColor: 'transparent', tension: .3, pointRadius: 2, spanGaps: false }] }, options: axes() }, any(data.trend?.values), none);
    draw('weekly', { type: 'bar', data: { labels: data.weekly?.labels || [], datasets: [{ data: data.weekly?.values || [], backgroundColor: col('--primary'), borderRadius: 6, maxBarThickness: 48 }] }, options: axes() }, any(data.weekly?.values), none);
    draw('monthly', { type: 'bar', data: { labels: data.monthly?.labels || [], datasets: [{ data: data.monthly?.values || [], backgroundColor: col('--primary'), borderRadius: 6, maxBarThickness: 48 }] }, options: axes() }, any(data.monthly?.values), none);

    const h = data.habits || [];
    draw('habits', { type: 'bar', data: { labels: h.map(x => x.name), datasets: [{ data: h.map(x => x.rate), backgroundColor: h.map(x => x.color), borderRadius: 4 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.raw}% (${h[c.dataIndex].done} done, ${h[c.dataIndex].missed} missed)` } } },
        scales: { x: { min: 0, max: 100, ticks: { callback: v => v + '%', color: col('--muted') }, grid: { color: col('--border') } }, y: { ticks: { color: col('--muted') }, grid: { display: false } } } } },
      h.length > 0, 'No completed or missed habit periods in this range yet.');
    const g = data.goals || [];
    draw('goals', { type: 'bar', data: { labels: g.map(x => x.title), datasets: [{ data: g.map(x => x.percent), backgroundColor: g.map(x => x.status === 'completed' ? col('--success') : x.status === 'overdue' ? col('--error') : col('--primary')), borderRadius: 4 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.raw}% (${g[c.dataIndex].current}/${g[c.dataIndex].target} ${g[c.dataIndex].unit})` } } },
        scales: { x: { min: 0, max: 100, ticks: { callback: v => v + '%', color: col('--muted') }, grid: { color: col('--border') } }, y: { ticks: { color: col('--muted') }, grid: { display: false } } } } },
      g.length > 0, 'No goals yet. Create a goal to track its progress here.');
  }

  $('#preset').addEventListener('change', () => {
    const custom = $('#preset').value === 'custom';
    ['#from', '#to', '#apply'].forEach(s => $(s).hidden = !custom);
    if (custom && !$('#to').value) { $('#to').value = new Date().toLocaleDateString('en-CA'); const f = new Date(); f.setDate(f.getDate() - 29); $('#from').value = f.toLocaleDateString('en-CA'); }
    if (!custom) load();
  });
  $('#apply').addEventListener('click', load);
  load();
})();