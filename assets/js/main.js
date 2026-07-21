/**
 * main.js — Punto de entrada. Enruta según <html data-page>.
 *
 * Módulos ES nativos, sin empaquetador ni transpilación: el sitio se
 * despliega tal cual en GitHub Pages.
 */
import { createStore } from './store.js?v=2f5873b8';
import { decode, applyToUrl, emptyFilters } from './url.js?v=2f5873b8';
import { wireFilters } from './filters.js?v=2f5873b8';
import { createGrid } from './grid.js?v=2f5873b8';
import { wireTheme } from './theme.js?v=2f5873b8';
import { wireClipboard } from './clipboard.js?v=2f5873b8';
import { wireCompare, wireComparePage } from './compare.js?v=2f5873b8';

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

// Profundidad de la página -> prefijo relativo, porque un sitio de proyecto de
// GitHub Pages vive en /<repo>/ y una ruta absoluta se rompería.
const root = document.querySelector('link[rel=stylesheet]')
  ?.getAttribute('href')?.split('assets/')[0] ?? '';

if (page === 'compare') wireComparePage(strings);
if (page === 'datasets') wireCompare({ strings, root });

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
