/**
 * clipboard.js — Botones de copiar en los fragmentos de código.
 *
 * Los botones se marcan como operativos sólo desde aquí: si el módulo no
 * carga, no queda un botón muerto en la página.
 */
import { announceNow } from './a11y.js?v=2f5873b8';

export function wireClipboard(strings) {
  const buttons = document.querySelectorAll('.snippet__copy');
  if (!buttons.length || !navigator.clipboard) {
    buttons.forEach((b) => b.remove());
    return;
  }

  buttons.forEach((btn) => {
    const pre = btn.closest('.snippet')?.querySelector('pre');
    if (!pre) return;

    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(pre.textContent);
      } catch (e) {
        return;
      }
      const label = btn.firstChild;
      const original = label.textContent;
      label.textContent = strings.copied || 'Copied';
      announceNow(strings.copied || 'Copied');
      setTimeout(() => { label.textContent = original; }, 2000);
    });
  });
}
