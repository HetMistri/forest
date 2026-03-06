import { createBrowserRouter } from 'react-router-dom';
import React, { lazy, Suspense } from 'react';
import PageLoader from './components/PageLoader';

/**
 * Every URL is served dynamically by WPDynamicPage, which maps the
 * React Router pathname → /wp-pages{pathname}/index.html.
 * No explicit per-page routes are needed; the 80+ WP pages are all
 * served by a single catch-all route.
 *
 * The /forest-dashboard route serves the EcoKeeper Forest Intelligence
 * platform, integrated directly into the AMNEX site.
 */
const DynamicPage = lazy(() => import('./components/DynamicPage'));
const ForestDashboard = lazy(() => import('./components/forest/ForestDashboard'));

function withSuspense(element: React.ReactNode): React.ReactNode {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/forest-dashboard',
    element: withSuspense(<ForestDashboard />),
  },
  {
    path: '*',
    element: withSuspense(<DynamicPage />),
  },
]);

