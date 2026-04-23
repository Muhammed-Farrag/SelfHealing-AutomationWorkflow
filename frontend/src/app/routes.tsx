import { createBrowserRouter } from 'react-router';
import { Root } from './pages/Root';
import { Dashboard } from './pages/Dashboard';
import { Episodes } from './pages/Episodes';
import { RepairPlans } from './pages/RepairPlans';
import { ReviewQueue } from './pages/ReviewQueue';
import { AuditTrail } from './pages/AuditTrail';
import { Rollback } from './pages/Rollback';
import { Intelligence } from './pages/Intelligence';
import { Settings } from './pages/Settings';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Root,
    children: [
      { index: true, Component: Dashboard },
      { path: 'episodes', Component: Episodes },
      { path: 'plans', Component: RepairPlans },
      { path: 'review', Component: ReviewQueue },
      { path: 'audit', Component: AuditTrail },
      { path: 'rollback', Component: Rollback },
      { path: 'intelligence', Component: Intelligence },
      { path: 'settings', Component: Settings },
    ],
  },
]);
