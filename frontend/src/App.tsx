import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./lib/auth";
import Admin from "./pages/Admin";
import Analysis from "./pages/Analysis";
import AuthPage from "./pages/AuthPage";
import CaseDetail from "./pages/CaseDetail";
import Cases from "./pages/Cases";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Home from "./pages/Home";
import NewCase from "./pages/NewCase";
import Profile from "./pages/Profile";

function Protected({ roles }: { roles?: string[] }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8 text-mute">Loading…</p>;
  if (!user) return <Navigate to="/welcome" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <Layout />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/welcome" element={<AuthPage />} />
      <Route path="/login" element={<Navigate to="/welcome" replace />} />
      <Route path="/register" element={<Navigate to="/welcome?mode=signup" replace />} />
      <Route element={<Protected />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/new" element={<NewCase />} />
        <Route path="/cases/:id" element={<CaseDetail />} />
        <Route path="/history" element={<History />} />
        <Route path="/analysis/:id" element={<Analysis />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route element={<Protected roles={["admin"]} />}><Route path="/admin" element={<Admin />} /></Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

