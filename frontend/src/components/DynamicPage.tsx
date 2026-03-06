/**
 * Dynamic page loader.
 * Reads the current React Router pathname and maps it to the corresponding
 * static WordPress HTML file in /public/wp-pages/.
 *
 * URL mapping:
 *   /              → /wp-pages/index.html
 *   /about-us      → /wp-pages/about-us/index.html
 *   /industries/agriculture → /wp-pages/industries/agriculture/index.html
 */
import { useLocation } from 'react-router-dom';
import PageRenderer from './PageRenderer';
import { pathToWpFile } from '../utils/wordpressParser';

export default function DynamicPage() {
  const { pathname } = useLocation();
  const fileUrl = pathToWpFile(pathname);
  return <PageRenderer fileUrl={fileUrl} spaPathname={pathname} />;
}
