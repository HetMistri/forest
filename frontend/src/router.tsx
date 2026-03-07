import { Navigate, createBrowserRouter } from 'react-router-dom';
import React, { lazy, Suspense } from 'react';
import PageLoader from './components/PageLoader';

/**
 * The app now deploys only the EcoKeeper Forest Intelligence dashboard.
 * Root path serves the dashboard directly.
 */
const ForestDashboard = lazy(() => import('./components/forest/ForestDashboard'));

function withSuspense(element: React.ReactNode): React.ReactNode {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: withSuspense(<ForestDashboard />),
  },
  {
    path: '/forest-dashboard',
    element: withSuspense(<ForestDashboard />),
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

