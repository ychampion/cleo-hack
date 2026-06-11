// Cleo — minimal fetch hook: loading / error / data / reload. No state library.

import { useCallback, useEffect, useRef, useState } from 'react';

export interface Fetched<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
}

export function useFetch<T>(
  fn: () => Promise<T>,
  deps: unknown[] = []
): Fetched<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      if (id !== seq.current) return; // a newer request superseded this one
      setData(result);
      setLoading(false);
    } catch (e) {
      if (id !== seq.current) return;
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
    // deps are the caller's query inputs; fn itself is intentionally excluded
    // so callers can pass inline closures without memoizing.
  }, deps);

  useEffect(() => {
    void load();
    return () => {
      seq.current++; // invalidate in-flight request on unmount/dep change
    };
  }, [load]);

  return { data, error, loading, reload: load };
}
