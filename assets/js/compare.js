/**
 * compare.js — Selección de datasets para comparar.
 *
 * El tope de 4 NO se implementa deshabilitando las casillas restantes: eso
 * sacaría 17 casillas del orden de tabulación y del árbol de accesibilidad, y
 * un usuario de teclado se encontraría la página mutilada sin explicación. En
 * su lugar la casilla sigue siendo operable, se revierte la marca y se anuncia
 * el límite, dejando el foco donde el usuario lo puso.
 */
import { announceNow } from './a11y.js?v=2f5873b8';

const MAX = 4;
const KEY = 'cmp';

export function wireCompare({ strings, root }) {
  const tray = document.getElementById('cmp-tray');
  const list = document.getElementById('cmp-tray-list');
  const go = document.getElementById('cmp-go');
  const clear = document.getElementById('cmp-clear');
  const boxes = Array.from(document.querySelectorAll('[data-compare]'));
  if (!tray || !boxes.length) return;

  const names = new Map(
    boxes.map((b) => [
      b.dataset.compare,
      b.closest('[data-id]')?.querySelector('.card__title')?.textContent.trim() || b.dataset.compare,
    ])
  );

  let selected = readUrl();

  function readUrl() {
    const raw = new URLSearchParams(location.search).get(KEY);
    return raw ? raw.split(',').filter((id) => names.has(id)).slice(0, MAX) : [];
  }

  function syncUrl() {
    const p = new URLSearchParams(location.search);
    if (selected.length) p.set(KEY, selected.join(','));
    else p.delete(KEY);
    const qs = p.toString();
    history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
  }

  function render() {
    tray.hidden = selected.length === 0;
    list.innerHTML = '';

    for (const id of selected) {
      const li = document.createElement('li');
      li.className = 'cmp-tray__item';
      li.append(names.get(id) || id);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn--ghost';
      btn.dataset.remove = id;
      btn.append('×');
      const sr = document.createElement('span');
      sr.className = 'visually-hidden';
      sr.textContent = (strings.compare_remove || 'Remove {name}')
        .replace('{name}', names.get(id) || id);
      btn.append(sr);
      li.append(btn);
      list.append(li);
    }

    // Comparar exige al menos dos; con uno solo el enlace no tiene sentido.
    go.hidden = selected.length < 2;
    go.href = `${root}compare/?${KEY}=${selected.join(',')}`;
    for (const b of boxes) b.checked = selected.includes(b.dataset.compare);
    syncUrl();
  }

  for (const box of boxes) {
    box.addEventListener('change', () => {
      const id = box.dataset.compare;
      if (box.checked) {
        if (selected.length >= MAX) {
          box.checked = false;                     // revertir, no deshabilitar
          announceNow(strings.compare_max || 'Maximum reached');
          return;
        }
        selected.push(id);
      } else {
        selected = selected.filter((x) => x !== id);
      }
      render();
    });
  }

  list.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-remove]');
    if (!btn) return;
    const id = btn.dataset.remove;
    const idx = selected.indexOf(id);
    selected = selected.filter((x) => x !== id);
    render();

    // El foco nunca puede caer a <body>: pasa al siguiente elemento de la
    // bandeja, o al botón de comparar, o de vuelta a la casilla de origen.
    const next = list.querySelectorAll('[data-remove]')[Math.min(idx, selected.length - 1)];
    if (next) next.focus();
    else if (!tray.hidden) go.focus();
    else document.querySelector(`[data-compare="${CSS.escape(id)}"]`)?.focus();
  });

  clear?.addEventListener('click', () => {
    selected = [];
    render();
    document.getElementById('results-heading')?.focus({ preventScroll: true });
  });

  render();
}

/**
 * Página /compare/: oculta las columnas no seleccionadas.
 *
 * La tabla llega del servidor con TODAS las columnas, así que sin JS se ve la
 * comparación completa en vez de una página vacía.
 */
export function wireComparePage(strings) {
  const table = document.querySelector('.cmp-table');
  if (!table) return;
  const wanted = (new URLSearchParams(location.search).get(KEY) || '')
    .split(',').filter(Boolean);
  if (!wanted.length) return;

  let shown = 0;
  for (const cell of table.querySelectorAll('[data-ds]')) {
    const keep = wanted.includes(cell.dataset.ds);
    cell.hidden = !keep;
    if (keep && cell.tagName === 'TH') shown += 1;
  }

  const caption = table.querySelector('caption');
  if (caption && shown) {
    caption.textContent = (strings.compare_caption || '{n}').replace('{n}', shown);
  }
}
