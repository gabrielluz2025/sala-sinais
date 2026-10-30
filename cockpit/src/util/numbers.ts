/** Coerce API/JSON values to finite numbers with a safe fallback. */
export function asFiniteNumber(value: unknown, fallback = 0): number {
  if (value == null) return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function asFiniteNumberOrNull(value: unknown): number | null {
  if (value == null) return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function safeFixed(value: unknown, digits = 2, fallback = "—"): string {
  const n = asFiniteNumberOrNull(value);
  return n == null ? fallback : n.toFixed(digits);
}

export function sanitizeMidMap(mids: Record<string, number> | null | undefined): Record<string, number> {
  const out: Record<string, number> = {};
  if (!mids) return out;
  for (const [key, raw] of Object.entries(mids)) {
    const n = asFiniteNumberOrNull(raw);
    if (n != null) out[key.toUpperCase()] = n;
  }
  return out;
}
