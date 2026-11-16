import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { MainLayout } from "./components/layout/MainLayout";
import ApprovalCenter from "./pages/ApprovalCenter";
import AttackSimulation from "./pages/AttackSimulation";
import AuditTrail from "./pages/AuditTrail";
import DetectionAnalytics from "./pages/DetectionAnalytics";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Settings from "./pages/Settings";
import ThreatMonitoring from "./pages/ThreatMonitoring";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route index element={<Overview />} />
          <Route path="lab" element={<AttackSimulation />} />
          <Route path="threats" element={<ThreatMonitoring />} />
          <Route path="approvals" element={<ApprovalCenter />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="analytics" element={<DetectionAnalytics />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Route>
      </Route>
    </Routes>
  );
}
