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
import People from "./pages/People";
import Profiles from "./pages/Profiles";
import Webhooks from "./pages/Webhooks";
import ApiKeys from "./pages/ApiKeys";
import Users from "./pages/Users";
import Docs from "./pages/Docs";
import Report from "./pages/Report";
import Reported from "./pages/Reported";
import Training from "./pages/Training";
import Settings from "./pages/Settings";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <Spinner />;
  if (!user) return <Login />;
  // Temporary-password accounts must set a new password before anything else.
  if (user.must_change_password) return <ForceChangePassword />;

  const can = (perm: string) => user.role === "admin" || (user.permissions || []).includes(perm);

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/campaigns" element={<Campaigns />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/pages" element={<LandingPages />} />
        <Route path="/groups" element={<Groups />} />
        <Route path="/people" element={<People />} />
        <Route path="/profiles" element={<Profiles />} />
        <Route path="/apikeys" element={<ApiKeys />} />
        <Route path="/training" element={<Training />} />
        <Route path="/docs" element={<Docs />} />
        {can("reported:view") && <Route path="/reported" element={<Reported />} />}
        {can("webhooks:manage") && <Route path="/webhooks" element={<Webhooks />} />}
        {can("users:manage") && <Route path="/users" element={<Users />} />}
        {can("settings:manage") && <Route path="/settings" element={<Settings />} />}
      </Route>
      <Route path="/print-report" element={<Report />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
