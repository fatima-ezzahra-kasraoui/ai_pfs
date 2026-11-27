import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { MainLayout } from "./components/layout/MainLayout";
import { PremiumPage } from "./pages/PremiumPages";
import LiveWorkspace from "./pages/LiveWorkspace";
import AttackSimulation from "./pages/AttackSimulation";
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
        <Route element={<MainLayout />}>
          <Route index element={<Overview />} />
          <Route path="lab" element={<AttackSimulation />} />
          <Route path="threats" element={<PremiumPage kind="threats" />} />
          <Route path="approvals" element={<PremiumPage kind="approvals" />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="analytics" element={<DetectionAnalytics />} />
          <Route path="settings" element={<Settings />} />
          <Route path="workspace" element={<LiveWorkspace />} />
          <Route path="inspector" element={<PremiumPage kind="inspector" />} />
          <Route path="agents" element={<PremiumPage kind="agents" />} />
          <Route path="executions" element={<PremiumPage kind="executions" />} />
          <Route path="incidents" element={<PremiumPage kind="incidents" />} />
          <Route path="policies" element={<PremiumPage kind="policies" />} />
          <Route path="models" element={<PremiumPage kind="models" />} />
          <Route path="integrations" element={<PremiumPage kind="integrations" />} />
          <Route path="api-docs" element={<PremiumPage kind="api-docs" />} />
          <Route path="users" element={<PremiumPage kind="users" />} />
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Route>
      </Route>
    </Routes>
  );
}
