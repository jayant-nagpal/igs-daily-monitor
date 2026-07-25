import { createContext, useContext, type ReactNode } from 'react';
import type { DashboardState } from './types/dashboard';
import { useDashboardData } from './hooks/useDashboardData';

const DataContext = createContext<DashboardState | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const state = useDashboardData();
  return <DataContext.Provider value={state}>{children}</DataContext.Provider>;
}

export function useData(): DashboardState {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
