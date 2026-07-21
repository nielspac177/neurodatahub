/**
 * main.js — Punto de entrada. Enruta según <html data-page>.
 *
 * Módulos ES nativos, sin empaquetador ni transpilación: el sitio se
 * despliega tal cual en GitHub Pages.
 */
import { createStore } from './store.js';
import { decode, applyToUrl, emptyFilters } from './url.js';
import { wireFilters } from './filters.js';
import { createGrid } from './grid.js';
import { wireTheme } from './theme.js';
import { wireClipboard } from './clipboard.js';

function readStrings() {
  const el = document.getElementById('i18n');
  try {
    return el ? JSON.parse(el.textContent) : {};
  } catch (e) {
    return {};
  }
}

const strings = readStrings();
wireTheme(document.getElementById('theme-toggle'));
wireClipboard(strings);

const page = document.documentElement.dataset.page;

if (page === 'datasets' || page === 'projects') {
  const form = document.getElementById('filters');
  const results = document.getElementById('results');

  if (form && results) {
    // Decodificar la URL ANTES del primer repintado: un enlace ya filtrado
    // nunca debe mostrar la rejilla completa y luego saltar.
    const initial = decode(new URLSearchParams(location.search));
    const store = createStore({
      filters: { ...emptyFilters(), ...initial.filters },
      q: initial.q,
    });

    const hydrate = wireFilters({
      form,
      searchInput: document.getElementById('q'),
      store,
    });
    hydrate(store.get());

    const apply = createGrid({
      root: results,
      statusEl: document.getElementById('results-status'),
      emptyEl: document.getElementById('empty'),
      headingEl: document.getElementById('results-heading'),
      strings,
      countKey: page === 'projects' ? 'count_projects' : 'count',
    });

    store.subscribe((state) => {
      apply(state);
      applyToUrl(state);
    });

    apply(store.get());

    // El formulario nunca navega: el estado ya vive en la URL.
    form.addEventListener('submit', (e) => e.preventDefault());
  }
}
