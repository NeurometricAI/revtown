import { Routes, Route } from 'react-router-dom';
import { Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';
import {
  Settings,
  Key,
  Puzzle,
  Users,
  CreditCard,
  Shield,
  Sliders,
} from 'lucide-react';

const adminNav = [
  { name: 'General', href: '/admin', icon: Settings },
  { name: 'Rigs', href: '/admin/rigs', icon: Sliders },
  { name: 'Credentials', href: '/admin/credentials', icon: Key },
  { name: 'Plugins', href: '/admin/plugins', icon: Puzzle },
  { name: 'Team', href: '/admin/team', icon: Users },
  { name: 'Billing', href: '/admin/billing', icon: CreditCard },
  { name: 'Security', href: '/admin/security', icon: Shield },
];

export function AdminPage() {
  const location = useLocation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin</h1>
        <p className="text-gray-600">Manage your RevTown configuration</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <nav className="w-48 space-y-1">
          {adminNav.map((item) => (
            <Link
              key={item.name}
              to={item.href}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                location.pathname === item.href
                  ? 'bg-brand-50 text-brand-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </Link>
          ))}
        </nav>

        {/* Content */}
        <div className="flex-1">
          <Routes>
            <Route index element={<GeneralSettings />} />
            <Route path="rigs" element={<RigSettings />} />
            <Route path="credentials" element={<CredentialSettings />} />
            <Route path="plugins" element={<PluginSettings />} />
            <Route path="team" element={<TeamSettings />} />
            <Route path="billing" element={<BillingSettings />} />
            <Route path="security" element={<SecuritySettings />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

function GeneralSettings() {
  return (
    <div className="card p-6 space-y-6">
      <h2 className="text-lg font-semibold">General Settings</h2>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Organization Name
          </label>
          <input type="text" className="input" defaultValue="Demo Organization" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Brand Voice Guidelines
          </label>
          <textarea
            className="input h-24"
            placeholder="Describe your brand's tone and voice..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Default Approval Mode
          </label>
          <select className="input">
            <option>Require approval for all outputs</option>
            <option>Auto-approve high-confidence outputs</option>
            <option>Manual review only for PR/SMS</option>
          </select>
        </div>

        <button className="btn-primary">Save Changes</button>
      </div>
    </div>
  );
}

function RigSettings() {
  const rigs = [
    { name: 'Content Factory', enabled: true, concurrency: 5 },
    { name: 'SDR Hive', enabled: true, concurrency: 10 },
    { name: 'Social Command', enabled: true, concurrency: 5 },
    { name: 'Press Room', enabled: true, concurrency: 3 },
    { name: 'Intelligence Station', enabled: true, concurrency: 5 },
    { name: 'Landing Pad', enabled: true, concurrency: 3 },
    { name: 'The Wire', enabled: true, concurrency: 2 },
    { name: 'Repo Watch', enabled: false, concurrency: 5 },
  ];

  return (
    <div className="card p-6 space-y-6">
      <h2 className="text-lg font-semibold">Rig Configuration</h2>

      <div className="space-y-4">
        {rigs.map((rig) => (
          <div
            key={rig.name}
            className="flex items-center justify-between p-4 border rounded-lg"
          >
            <div className="flex items-center gap-4">
              <input
                type="checkbox"
                defaultChecked={rig.enabled}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="font-medium">{rig.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Concurrency:</label>
              <input
                type="number"
                defaultValue={rig.concurrency}
                className="input w-20"
                min={1}
                max={50}
              />
            </div>
          </div>
        ))}
      </div>

      <button className="btn-primary">Save Configuration</button>
    </div>
  );
}

function CredentialSettings() {
  return (
    <div className="card p-6 space-y-6">
      <h2 className="text-lg font-semibold">API Credentials</h2>
      <p className="text-sm text-gray-600">
        Credentials are stored securely in Vault and never exposed in the UI.
      </p>

      <div className="space-y-4">
        <CredentialRow name="Neurometric API" status="configured" />
        <CredentialRow name="Twilio (SMS)" status="not_configured" />
        <CredentialRow name="Vercel API" status="configured" />
        <CredentialRow name="GitHub App" status="not_configured" />
        <CredentialRow name="LinkedIn API" status="not_configured" />
        <CredentialRow name="Twitter/X API" status="not_configured" />
      </div>
    </div>
  );
}

function CredentialRow({
  name,
  status,
}: {
  name: string;
  status: 'configured' | 'not_configured';
}) {
  return (
    <div className="flex items-center justify-between p-4 border rounded-lg">
      <span className="font-medium">{name}</span>
      <div className="flex items-center gap-3">
        <span
          className={status === 'configured' ? 'badge-success' : 'badge-warning'}
        >
          {status === 'configured' ? 'Configured' : 'Not Configured'}
        </span>
        <button className="btn-secondary text-sm h-8">
          {status === 'configured' ? 'Update' : 'Configure'}
        </button>
      </div>
    </div>
  );
}

function PluginSettings() {
  return (
    <div className="card p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Plugins</h2>
        <button className="btn-primary">Install Plugin</button>
      </div>

      <div className="text-center py-8 text-gray-500">
        <Puzzle className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p>No plugins installed</p>
        <p className="text-sm">Browse the plugin registry to get started</p>
      </div>
    </div>
  );
}

function TeamSettings() {
  return (
    <div className="card p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Team Members</h2>
        <button className="btn-primary">Invite Member</button>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
              <span className="font-medium text-brand-700">A</span>
            </div>
            <div>
              <p className="font-medium">Admin User</p>
              <p className="text-sm text-gray-500">admin@example.com</p>
            </div>
          </div>
          <span className="badge-default">Owner</span>
        </div>
      </div>
    </div>
  );
}

function BillingSettings() {
  return (
    <div className="card p-6 space-y-6">
      <h2 className="text-lg font-semibold">Billing & Usage</h2>

      <div className="p-4 bg-brand-50 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold text-brand-900">Free Plan</p>
            <p className="text-sm text-brand-700">
              100 Polecat executions/month
            </p>
          </div>
          <button className="btn-primary">Upgrade</button>
        </div>
      </div>

      <div>
        <h3 className="font-medium mb-3">Current Usage</h3>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Polecat Executions</span>
            <span>47 / 100</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-brand-600 h-2 rounded-full"
              style={{ width: '47%' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function SecuritySettings() {
  return (
    <div className="card p-6 space-y-6">
      <h2 className="text-lg font-semibold">Security & API Keys</h2>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium">API Keys</h3>
          <button className="btn-secondary">Create API Key</button>
        </div>

        <div className="text-center py-8 text-gray-500">
          <Key className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No API keys created</p>
        </div>
      </div>
    </div>
  );
}
