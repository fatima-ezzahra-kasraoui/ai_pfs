import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import AuditTrail from "./pages/AuditTrail";
import DetectionAnalytics from "./pages/DetectionAnalytics";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="analytics" element={<DetectionAnalytics />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Route>
      </Route>
    </Routes>
  );
}
