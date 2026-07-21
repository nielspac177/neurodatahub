/**
 * a11y.js — Región viva compartida.
 *
 * El conteo se anuncia con retardo de 500 ms al final: anunciar en cada
 * pulsación es peor que el silencio, porque el lector de pantalla interrumpe
 * al usuario mientras sigue escribiendo.
 */
const region = () => document.getElementById('a11y-live');

let timer;

export function announce(message, { delay = 500 } = {}) {
  clearTimeout(timer);
  timer = setTimeout(() => {
    const el = region();
    if (el) el.textContent = message;
  }, delay);
}

/** Para confirmaciones inmediatas (copiar, límite alcanzado). */
export function announceNow(message) {
  clearTimeout(timer);
  const el = region();
  if (el) el.textContent = message;
}
