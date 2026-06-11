// Cleo — shared overview context (counts power sidebar badges + the Brief view).

import { createContext, useContext, type ReactNode } from 'react';
import { getOverview, type Overview } from '../api';
import { useFetch, type Fetched } from './useFetch';

const OverviewCtx = createContext<Fetched<Overview> | null>(null);

export function OverviewProvider({ children }: { children: ReactNode }) {
  const state = useFetch<Overview>(() => getOverview(), []);
  return <OverviewCtx.Provider value={state}>{children}</OverviewCtx.Provider>;
}

export function useOverview(): Fetched<Overview> {
  const ctx = useContext(OverviewCtx);
  if (!ctx) throw new Error('useOverview must be used inside OverviewProvider');
  return ctx;
}
