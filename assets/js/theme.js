/**
 * theme.js — Conmutador de tema.
 *
 * El valor inicial ya lo escribió el script en línea de <head> antes del
 * primer pintado; aquí sólo se maneja el botón.
 */
const KEY = 'ndh-theme';

export function wireTheme(button) {
  if (!button) return;

  const current = () =>
    document.documentElement.dataset.theme ||
    (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');

  const sync = () => button.setAttribute('aria-pressed', String(current() === 'light'));
  sync();

  button.addEventListener('click', () => {
    const next = current() === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch (e) { /* modo privado: el tema sigue funcionando en esta sesión */ }
    sync();
  });
}
