import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { createLogger } from "./utils/logger";

const logger = createLogger("router");

function App() {
  useEffect(() => {
    logger.info("Router initialized", {
      pathname: window.location.pathname,
      search: window.location.search,
      hash: window.location.hash,
    });

    const unsubscribe = router.subscribe((state) => {
      logger.info("Route transition", {
        pathname: state.location.pathname,
        search: state.location.search,
        hash: state.location.hash,
        navigationState: state.navigation.state,
        revalidation: state.revalidation,
      });
    });

    return () => {
      unsubscribe();
      logger.info("Router subscription disposed");
    };
  }, []);

  return <RouterProvider router={router} />;
}

export default App;
