import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import ForceChangePassword from "./pages/ForceChangePassword";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import CampaignDetail from "./pages/CampaignDetail";
import Templates from "./pages/Templates";
import LandingPages from "./pages/LandingPages";
import Groups from "./pages/Groups";
import Profiles from "./pages/Profiles";
import Webhooks from "./pages/Webhooks";
import ApiKeys from "./pages/ApiKeys";
import Users from "./pages/Users";
import Docs from "./pages/Docs";
import Report from "./pages/Report";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <Spinner />;
  if (!user) return <Login />;
  // Temporary-password accounts must set a new password before anything else.
  if (user.must_change_password) return <ForceChangePassword />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/campaigns" element={<Campaigns />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/pages" element={<LandingPages />} />
        <Route path="/groups" element={<Groups />} />
        <Route path="/profiles" element={<Profiles />} />
        <Route path="/apikeys" element={<ApiKeys />} />
        <Route path="/docs" element={<Docs />} />
        {user.role === "admin" && <Route path="/webhooks" element={<Webhooks />} />}
        {user.role === "admin" && <Route path="/users" element={<Users />} />}
      </Route>
      <Route path="/print-report" element={<Report />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
