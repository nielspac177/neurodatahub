/**
 * grid.js — Aplica el estado a un DOM ya renderizado.
 *
 * Las tarjetas ya existen en el HTML; aquí sólo se conmuta el atributo
 * `hidden`, que las quita a la vez del árbol de accesibilidad y del orden de
 * tabulación. No se construye HTML ni se vuelve a analizar nada.
 */
import { FACETS } from './url.js';
import { announce } from './a11y.js';

export function createGrid({ root, statusEl, emptyEl, headingEl, strings, countKey }) {
  const cards = Array.from(root.querySelectorAll('[data-id]'));
  const total = cards.length;

  // Pajar pre-normalizado y pre-minusculizado por build.py.
  const index = new Map();
  const island = document.getElementById('search-index');
  if (island) {
    for (const row of JSON.parse(island.textContent)) index.set(row.id, row.hay);
  }

  const values = (card, attr) => (card.dataset[attr] || '').split(/\s+/).filter(Boolean);

  function matches(card, state) {
    for (const [key, cfg] of Object.entries(FACETS)) {
      const wanted = state.filters[key];
      if (!wanted || !wanted.length) continue;
      const have = values(card, cfg.attr);
      // OR dentro de un facet, AND entre facets.
      if (!wanted.some((w) => have.includes(w))) return false;
    }
    if (state.q) {
      const hay = index.get(card.dataset.id) || '';
      // AND por token: "eeg seizure" acierta en cualquier orden.
      if (!state.q.split(/\s+/).every((tok) => hay.includes(tok))) return false;
    }
    return true;
  }

  return function apply(state) {
    let shown = 0;
    for (const card of cards) {
      const ok = matches(card, state);
      card.hidden = !ok;
      if (ok) shown += 1;
    }

    const text = (strings[countKey] || '{n}/{total}')
      .replace('{n}', shown)
      .replace('{total}', total);
    if (statusEl) statusEl.textContent = text;
    if (emptyEl) emptyEl.hidden = shown !== 0;
    announce(text);

    // Si un filtro deja la rejilla vacía, llevar el foco al encabezado para
    // que el usuario de teclado no se quede navegando una lista invisible.
    if (shown === 0 && headingEl && document.activeElement !== headingEl) {
      headingEl.focus({ preventScroll: true });
    }
  };
}
