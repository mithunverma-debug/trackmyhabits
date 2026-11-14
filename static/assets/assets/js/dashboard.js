/* Dashboard: checklist toggles + weekly chart (data comes from the server, from MySQL). */
document.querySelectorAll('.js-check').forEach(btn => btn.addEventListener('click', async () => {
  btn.disabled = true;
  const { ok, data } = await TMH.api('habits/toggle.php', { habit_id: +btn.dataset.id, completed: btn.dataset.done !== '1' });
  if (ok) location.reload(); else { TMH.toast(data.message, 'error'); btn.disabled = false; }
}));

(function () {
  const canvas = document.getElementById('weekChart');
  if (!canvas || !window.Chart) return;
  const { labels, values } = JSON.parse(canvas.dataset.chart);
  const css = getComputedStyle(document.documentElement);
  new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Completion %', data: values, backgroundColor: css.getPropertyValue('--primary').trim(), borderRadius: 6, maxBarThickness: 36 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%', color: css.getPropertyValue('--muted').trim() }, grid: { color: css.getPropertyValue('--border').trim() } },
                x: { ticks: { color: css.getPropertyValue('--muted').trim() }, grid: { display: false } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.raw === null ? 'Nothing scheduled' : c.raw + '% completed' } } },
    },
  });
})();
