import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConvexProvider, ConvexReactClient } from "convex/react";
import "./index.css";
import App from "./App.tsx";

// VITE_CONVEX_URL is set after running `npx convex dev` in the frontend/ directory
const convex = new ConvexReactClient(
  import.meta.env.VITE_CONVEX_URL ?? "https://placeholder.convex.cloud"
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConvexProvider client={convex}>
      <App />
    </ConvexProvider>
  </StrictMode>
);
