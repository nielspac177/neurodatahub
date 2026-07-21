/**
 * filters.js — Conecta los checkboxes y la búsqueda con el store.
 *
 * Los chips son checkboxes nativos, así que la lectura del estado es leer el
 * formulario. No hay estado paralelo que se pueda desincronizar del DOM.
 */
import { FACETS, emptyFilters } from './url.js?v=2f5873b8';

const DEBOUNCE_MS = 120;

export function wireFilters({ form, searchInput, store }) {
  function readForm() {
    const filters = emptyFilters();
    for (const key of Object.keys(FACETS)) {
      form.querySelectorAll(`input[name="${key}"]:checked`).forEach((el) => {
        filters[key].push(el.value);
      });
    }
    return filters;
  }

  form.addEventListener('change', (e) => {
    if (e.target.matches('input[type="checkbox"]')) {
      store.set({ filters: readForm() });
    }
  });

  form.querySelectorAll('[data-clear-filters]').forEach((btn) => {
    btn.addEventListener('click', () => {
      form.querySelectorAll('input[type="checkbox"]:checked').forEach((el) => {
        el.checked = false;
      });
      if (searchInput) searchInput.value = '';
      store.set({ filters: emptyFilters(), q: '' });
    });
  });

  if (searchInput) {
    let t;
    searchInput.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => {
        store.set({ q: fold(searchInput.value.trim()) });
      }, DEBOUNCE_MS);
    });
  }

  /** Escribe el estado inicial (venido de la URL) en el formulario. */
  return function hydrate(state) {
    for (const [key, vals] of Object.entries(state.filters)) {
      for (const v of vals) {
        const el = form.querySelector(`input[name="${key}"][value="${CSS.escape(v)}"]`);
        if (el) el.checked = true;
      }
    }
    if (searchInput && state.q) searchInput.value = state.q;
  };
}

/** Debe coincidir con components._fold del lado Python. */
export function fold(s) {
  return s.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase();
}
