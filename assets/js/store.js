/**
 * store.js — Contenedor de estado mínimo.
 *
 * Las notificaciones se agrupan en un microtask: un manejador que toca `q` y
 * `filters` produce un solo repintado, no dos.
 *
 * Deliberadamente NO se usa requestAnimationFrame. rAF no se dispara en una
 * pestaña oculta, así que filtrar y volver a la pestaña dejaba la rejilla
 * congelada con el estado anterior. Un microtask agrupa igual de bien y
 * siempre corre.
 */
export function createStore(initial) {
  let state = { ...initial };
  const subs = new Set();
  let queued = false;

  function flush() {
    queued = false;
    for (const fn of subs) fn(state);
  }

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      if (!queued) {
        queued = true;
        queueMicrotask(flush);
      }
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}
