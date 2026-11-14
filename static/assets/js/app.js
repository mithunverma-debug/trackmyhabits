/* Shared JS: CSRF-aware API helper, toasts, theme toggle, mobile menu, form helpers. */
const TMH = {
  csrf: document.querySelector('meta[name="csrf-token"]')?.content || '',
  base: document.querySelector('meta[name="base-url"]')?.content || '',

  /** POST/GET JSON to our API. Returns {ok, status, data}. */
  async api(path, body = null, method = 'POST') {
    const opts = { method, headers: { 'X-CSRF-Token': TMH.csrf, 'Accept': 'application/json' }, credentials: 'same-origin' };
    if (method !== 'GET' && body !== null) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    try {
      const res = await fetch(TMH.base + '/api/' + path, opts);
      const data = await res.json().catch(() => ({ success: false, message: 'Unexpected server response.' }));
      if (res.status === 401 && !location.pathname.endsWith('login.php')) location.href = TMH.base + '/login.php';
      return { ok: res.ok && data.success, status: res.status, data };
    } catch (err) {
      return { ok: false, status: 0, data: { success: false, message: 'Network error. Is Apache running?' } };
    }
  },

  toast(msg, type = '') {
    let box = document.getElementById('toasts');
    if (!box) { box = document.createElement('div'); box.id = 'toasts'; document.body.appendChild(box); }
    const t = document.createElement('div'); t.className = 'toast ' + type; t.textContent = msg; // textContent = XSS-safe
    box.appendChild(t); setTimeout(() => t.remove(), 3500);
  },

  /** Show server validation errors next to fields (field names must match input names). */
  showErrors(form, errors) {
    form.querySelectorAll('.field-error').forEach(el => el.textContent = '');
    form.querySelectorAll('.input').forEach(el => el.classList.remove('invalid'));
    Object.entries(errors || {}).forEach(([name, msg]) => {
      const input = form.querySelector(`[name="${name}"]`); const out = form.querySelector(`[data-error="${name}"]`);
      if (input) input.classList.add('invalid'); if (out) out.textContent = msg;
    });
  },

  syncThemeButtons() {
    const dark = document.documentElement.dataset.theme !== 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(b => { b.textContent = dark ? '☀️' : '🌙'; b.title = dark ? 'Switch to light theme' : 'Switch to dark theme'; });
  },

  initIcons() { if (window.lucide) lucide.createIcons({ attrs: { class: 'icon' } }); },
  esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; },
};

/** Generic AJAX form: <form data-api="auth/login.php" data-redirect="dashboard.php"> */
document.querySelectorAll('form[data-api]').forEach(form => {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;
    const btn = form.querySelector('button[type="submit"]'); const alertBox = form.querySelector('.alert');
    const payload = Object.fromEntries(new FormData(form).entries());
    TMH.showErrors(form, {}); if (alertBox) alertBox.hidden = true; btn.disabled = true;
    const { ok, data } = await TMH.api(form.dataset.api, payload);
    btn.disabled = false;
    if (ok && form.dataset.toast !== undefined) {   // stay on page, just confirm
      TMH.toast(data.message || 'Saved.');
      if (data.theme) { document.documentElement.dataset.theme = data.theme; try { localStorage.setItem('tmh-theme', data.theme); } catch (e) {} TMH.syncThemeButtons(); }
      if (form.dataset.reset !== undefined) form.reset();
      if (form.dataset.reload !== undefined) setTimeout(() => location.reload(), 600);
      return;
    }
    if (ok) { location.href = TMH.base + '/' + (data.redirect || form.dataset.redirect || ''); return; }
    TMH.showErrors(form, data.errors);
    if (alertBox) { alertBox.textContent = data.message || 'Something went wrong.'; alertBox.hidden = false; }
  });
});

/* Theme toggle, mobile menu, password show/hide. */
(function () {
  const loggedIn = !!document.querySelector('meta[name="logged-in"]');
  TMH.syncThemeButtons();
  document.querySelectorAll('[data-theme-toggle]').forEach(b => b.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next; TMH.syncThemeButtons();
    try { localStorage.setItem('tmh-theme', next); } catch (e) {}
    if (loggedIn) TMH.api('settings/theme.php', { theme: next }); // saved to the account
  }));
  const menu = document.querySelector('[data-menu-toggle]');
  if (menu) {
    menu.addEventListener('click', () => document.body.classList.toggle('nav-open'));
    document.querySelector('.backdrop')?.addEventListener('click', () => document.body.classList.remove('nav-open'));
  }
  document.querySelectorAll('[data-toggle-password]').forEach(btn => btn.addEventListener('click', () => {
    const input = document.querySelector(btn.dataset.togglePassword); if (!input) return;
    const show = input.type === 'password'; input.type = show ? 'text' : 'password';
    btn.textContent = show ? 'Hide' : 'Show'; btn.setAttribute('aria-pressed', show ? 'true' : 'false');
  }));
  TMH.initIcons();
})();
