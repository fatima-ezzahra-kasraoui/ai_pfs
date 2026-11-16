import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { applyTheme, loadTheme } from "./preferences";
import "@fontsource-variable/inter";
import "./styles.css";

const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true } as const;

applyTheme(loadTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter future={ROUTER_FUTURE}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
