import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="as-shell flex min-h-screen">
      <a className="skip" href="#main">
        Aller au contenu
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main id="main" tabIndex={-1} className="w-full flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
