/**
 * url.js — Estado <-> URLSearchParams.
 *
 * Las claves son cortas y los valores van unidos por comas, para que un
 * docente pueda enviar a sus estudiantes un enlace ya filtrado:
 *     /?m=electrophysiology,bci&a=open&q=seizure
 *
 * Los valores por defecto se omiten, de modo que una URL limpia siga limpia.
 */

/** Nombre del facet -> atributo data-* de la tarjeta, y si es multivalor. */
export const FACETS = {
  m: { attr: 'modality', multi: false },
  c: { attr: 'category', multi: true },
  a: { attr: 'access', multi: false },
  d: { attr: 'difficulty', multi: false },
  s: { attr: 'skills', multi: true },
};

export function encode(state) {
  const p = new URLSearchParams();
  for (const key of Object.keys(FACETS)) {
    const vals = state.filters[key];
    if (vals && vals.length) p.set(key, vals.join(','));
  }
  if (state.q) p.set('q', state.q);
  return p;
}

export function decode(params) {
  const filters = {};
  for (const key of Object.keys(FACETS)) {
    const raw = params.get(key);
    filters[key] = raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : [];
  }
  return { filters, q: params.get('q') || '' };
}

export function emptyFilters() {
  return Object.fromEntries(Object.keys(FACETS).map((k) => [k, []]));
}

/**
 * replaceState, nunca pushState: filtrar no debe llenar el historial de
 * atrás con una entrada por pulsación de tecla.
 */
export function applyToUrl(state) {
  const p = encode(state);
  const qs = p.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}
