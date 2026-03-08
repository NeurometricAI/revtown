import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AdminPage } from './pages/admin/AdminPage';
import { ApprovePage } from './pages/approve/ApprovePage';
import { OptimizePage } from './pages/optimize/OptimizePage';
import { CampaignsPage } from './pages/campaigns/CampaignsPage';
import { DashboardPage } from './pages/DashboardPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="campaigns/*" element={<CampaignsPage />} />
        <Route path="admin/*" element={<AdminPage />} />
        <Route path="approve/*" element={<ApprovePage />} />
        <Route path="optimize/*" element={<OptimizePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
