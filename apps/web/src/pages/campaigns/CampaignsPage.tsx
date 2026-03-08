import { Routes, Route } from 'react-router-dom';
import { Plus, Rocket, MoreVertical } from 'lucide-react';

// Mock campaign data
const mockCampaigns = [
  {
    id: '1',
    name: 'Q1 Product Launch',
    status: 'active',
    goal: 'Generate 500 MQLs for new product launch',
    progress: 65,
    beads: { leads: 320, assets: 12, tests: 3 },
  },
  {
    id: '2',
    name: 'Enterprise Expansion',
    status: 'active',
    goal: 'Target enterprise accounts in finance sector',
    progress: 42,
    beads: { leads: 85, assets: 8, tests: 2 },
  },
  {
    id: '3',
    name: 'Developer Relations',
    status: 'draft',
    goal: 'Increase GitHub stars and developer engagement',
    progress: 0,
    beads: { leads: 0, assets: 2, tests: 0 },
  },
];

export function CampaignsPage() {
  return (
    <Routes>
      <Route index element={<CampaignsList />} />
      <Route path=":campaignId" element={<CampaignDetail />} />
    </Routes>
  );
}

function CampaignsList() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
          <p className="text-gray-600">Manage your GTM campaigns</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Campaign
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {mockCampaigns.map((campaign) => (
          <a
            key={campaign.id}
            href={`/campaigns/${campaign.id}`}
            className="card p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="p-2 bg-brand-50 rounded-lg">
                <Rocket className="w-5 h-5 text-brand-600" />
              </div>
              <button className="btn-ghost h-8 w-8 p-0">
                <MoreVertical className="w-4 h-4" />
              </button>
            </div>

            <h3 className="font-semibold text-lg mb-2">{campaign.name}</h3>
            <p className="text-sm text-gray-600 mb-4 line-clamp-2">
              {campaign.goal}
            </p>

            <div className="flex items-center gap-2 mb-4">
              <span
                className={
                  campaign.status === 'active' ? 'badge-success' : 'badge-secondary'
                }
              >
                {campaign.status}
              </span>
            </div>

            {campaign.status === 'active' && (
              <>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Progress</span>
                  <span className="font-medium">{campaign.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                  <div
                    className="bg-brand-500 h-2 rounded-full"
                    style={{ width: `${campaign.progress}%` }}
                  />
                </div>
              </>
            )}

            <div className="flex gap-4 text-sm text-gray-500">
              <span>{campaign.beads.leads} leads</span>
              <span>{campaign.beads.assets} assets</span>
              <span>{campaign.beads.tests} tests</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

function CampaignDetail() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Q1 Product Launch</h1>
          <p className="text-gray-600">
            Generate 500 MQLs for new product launch
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">Edit</button>
          <button className="btn-primary">Start Convoy</button>
        </div>
      </div>

      {/* Campaign Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="card p-4">
          <p className="text-sm text-gray-600">Leads</p>
          <p className="text-2xl font-bold">320</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-600">Assets</p>
          <p className="text-2xl font-bold">12</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-600">A/B Tests</p>
          <p className="text-2xl font-bold">3</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-600">Polecats Run</p>
          <p className="text-2xl font-bold">156</p>
        </div>
      </div>

      {/* Convoy Status */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Active Convoy</h2>
        <div className="space-y-4">
          <ConvoyStep
            step={1}
            name="Generate Initial Content"
            rig="Content Factory"
            status="completed"
          />
          <ConvoyStep
            step={2}
            name="Enrich Lead Database"
            rig="SDR Hive"
            status="completed"
          />
          <ConvoyStep
            step={3}
            name="Launch Social Campaign"
            rig="Social Command"
            status="running"
          />
          <ConvoyStep
            step={4}
            name="Monitor Competitors"
            rig="Intelligence Station"
            status="pending"
          />
          <ConvoyStep
            step={5}
            name="Optimize Landing Pages"
            rig="Landing Pad"
            status="pending"
          />
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
        <div className="space-y-3">
          <ActivityItem
            action="BlogDraftPolecat completed"
            details="Created 'Q1 Product Update' blog post"
            time="5 min ago"
          />
          <ActivityItem
            action="EnrichPolecat completed"
            details="Enriched 45 new leads"
            time="12 min ago"
          />
          <ActivityItem
            action="DraftTweetPolecat completed"
            details="Generated 3 tweet variants"
            time="1 hour ago"
          />
        </div>
      </div>
    </div>
  );
}

function ConvoyStep({
  step,
  name,
  rig,
  status,
}: {
  step: number;
  name: string;
  rig: string;
  status: 'completed' | 'running' | 'pending';
}) {
  const statusStyles = {
    completed: 'bg-green-500',
    running: 'bg-yellow-500 animate-pulse',
    pending: 'bg-gray-300',
  };

  return (
    <div className="flex items-center gap-4">
      <div className={`w-8 h-8 rounded-full ${statusStyles[status]} flex items-center justify-center`}>
        <span className="text-white text-sm font-medium">{step}</span>
      </div>
      <div className="flex-1">
        <p className="font-medium">{name}</p>
        <p className="text-sm text-gray-500">{rig}</p>
      </div>
      <span
        className={
          status === 'completed'
            ? 'badge-success'
            : status === 'running'
              ? 'badge-warning'
              : 'badge-secondary'
        }
      >
        {status}
      </span>
    </div>
  );
}

function ActivityItem({
  action,
  details,
  time,
}: {
  action: string;
  details: string;
  time: string;
}) {
  return (
    <div className="py-3 border-b border-gray-100 last:border-0">
      <p className="font-medium">{action}</p>
      <p className="text-sm text-gray-600">{details}</p>
      <p className="text-xs text-gray-400 mt-1">{time}</p>
    </div>
  );
}
