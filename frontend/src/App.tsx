import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import SetupPage from "./pages/SetupPage";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ReplayPage from "./pages/ReplayPage";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/replay" element={<ReplayPage />} />
      </Routes>
    </Layout>
  );
}

export default App;
