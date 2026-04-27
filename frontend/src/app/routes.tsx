import { createBrowserRouter } from 'react-router';
import { Root } from './pages/Root';
import { Dashboard } from './pages/Dashboard';
import { Episodes } from './pages/Episodes';
import { RepairPlans } from './pages/RepairPlans';
import { ReviewQueue } from './pages/ReviewQueue';
import { AuditTrail } from './pages/AuditTrail';
import { Rollback } from './pages/Rollback';
import { Intelligence } from './pages/Intelligence';
import { Benchmark } from './pages/Benchmark';
import { Settings } from './pages/Settings';
import { PageErrorBoundary } from './components/PageErrorBoundary';
import React from 'react';

/** Wraps a page component with a PageErrorBoundary scoped to that page's name. */
function withBoundary(Component: React.ComponentType, name: string) {
  return function BoundedPage() {
    return (
      <PageErrorBoundary pageName={name}>
        <Component />
      </PageErrorBoundary>
    );
  };
}

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Root,
    children: [
      { index: true,              Component: withBoundary(Dashboard,   'Dashboard') },
      { path: 'episodes',         Component: withBoundary(Episodes,    'Episodes') },
      { path: 'plans',            Component: withBoundary(RepairPlans, 'Repair Plans') },
      { path: 'review',           Component: withBoundary(ReviewQueue, 'Review Queue') },
      { path: 'audit',            Component: withBoundary(AuditTrail,  'Audit Trail') },
      { path: 'rollback',         Component: withBoundary(Rollback,    'Rollback') },
      { path: 'intelligence',     Component: withBoundary(Intelligence,'Intelligence') },
      { path: 'benchmark',        Component: withBoundary(Benchmark,   'Benchmark') },
      { path: 'settings',         Component: withBoundary(Settings,    'Settings') },
    ],
  },
]);
