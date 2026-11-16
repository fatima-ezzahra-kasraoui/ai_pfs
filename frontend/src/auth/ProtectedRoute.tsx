import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

/** Confort d'affichage : redirige vers /login en mémorisant la page demandée. Pas une barrière de sécurité. */
export function ProtectedRoute() {
  const { user, checking } = useAuth();
  const location = useLocation();
  if (checking) return <p role="status">Vérification de la session…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <Outlet />;
}
