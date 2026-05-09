import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Onboarding from "./pages/Onboarding";
import History from "./pages/History";

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <aside className="sidebar">
          <h2>PitchSnap</h2>
          <nav>
            <NavLink
              to="/dashboard"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              📊 Dashboard
            </NavLink>
            <NavLink
              to="/onboarding"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              🎭 Onboarding
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              🕑 History
            </NavLink>
          </nav>
        </aside>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
