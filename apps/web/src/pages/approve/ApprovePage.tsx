import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import clsx from 'clsx';
import {
  CheckCircle,
  XCircle,
  Edit,
  ArrowLeft,
  AlertTriangle,
  FileText,
  Mail,
  MessageSquare,
  Newspaper,
  BarChart,
} from 'lucide-react';

// Mock data for approval queue
const mockApprovalItems = [
  {
    id: '1',
    type: 'content',
    title: 'Blog: Q1 Product Update',
    rig: 'Content Factory',
    urgency: 'normal',
    score: 0.92,
    createdAt: '5 min ago',
  },
  {
    id: '2',
    type: 'outreach',
    title: 'Email: Follow-up to Demo Request',
    rig: 'SDR Hive',
    urgency: 'high',
    score: 0.85,
    createdAt: '12 min ago',
  },
  {
    id: '3',
    type: 'pr_pitch',
    title: 'PR Pitch: TechCrunch - Series A',
    rig: 'Press Room',
    urgency: 'critical',
    score: 0.88,
    createdAt: '1 hour ago',
  },
  {
    id: '4',
    type: 'sms',
    title: 'SMS: Meeting Confirmation',
    rig: 'The Wire',
    urgency: 'high',
    score: 0.95,
    createdAt: '2 hours ago',
  },
  {
    id: '5',
    type: 'test_winner',
    title: 'A/B Test: Landing Page CTA',
    rig: 'Landing Pad',
    urgency: 'normal',
    score: 0.97,
    createdAt: '3 hours ago',
  },
];

export function ApprovePage() {
  return (
    <Routes>
      <Route index element={<ApprovalQueue />} />
      <Route path=":itemId" element={<ApprovalDetail />} />
    </Routes>
  );
}

function ApprovalQueue() {
  const [filter, setFilter] = useState<string>('all');

  const typeIcons: Record<string, React.ElementType> = {
    content: FileText,
    outreach: Mail,
    pr_pitch: Newspaper,
    sms: MessageSquare,
    test_winner: BarChart,
  };

  const filteredItems =
    filter === 'all'
      ? mockApprovalItems
      : mockApprovalItems.filter((item) => item.type === filter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
          <p className="text-gray-600">
            Review and approve outputs before they go live
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge-warning">
            {mockApprovalItems.length} pending
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {['all', 'content', 'outreach', 'pr_pitch', 'sms', 'test_winner'].map(
          (type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={clsx(
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                filter === type
                  ? 'bg-brand-100 text-brand-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {type === 'all'
                ? 'All'
                : type.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            </button>
          )
        )}
      </div>

      {/* Queue */}
      <div className="space-y-3">
        {filteredItems.map((item) => {
          const Icon = typeIcons[item.type] || FileText;
          return (
            <div
              key={item.id}
              className="card p-4 flex items-center justify-between hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-4">
                <div className="p-2 bg-gray-100 rounded-lg">
                  <Icon className="w-5 h-5 text-gray-600" />
                </div>
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-sm text-gray-500">
                    {item.rig} · {item.createdAt}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <span
                    className={clsx(
                      'text-sm',
                      item.urgency === 'critical' && 'text-red-600 font-medium',
                      item.urgency === 'high' && 'text-orange-600',
                      item.urgency === 'normal' && 'text-gray-600'
                    )}
                  >
                    {item.urgency.charAt(0).toUpperCase() + item.urgency.slice(1)}
                  </span>
                  <p className="text-sm text-gray-500">
                    Score: {(item.score * 100).toFixed(0)}%
                  </p>
                </div>

                <div className="flex gap-2">
                  <button className="btn-ghost h-9 px-3 text-green-600 hover:bg-green-50">
                    <CheckCircle className="w-4 h-4" />
                  </button>
                  <button className="btn-ghost h-9 px-3 text-red-600 hover:bg-red-50">
                    <XCircle className="w-4 h-4" />
                  </button>
                  <a
                    href={`/approve/${item.id}`}
                    className="btn-secondary h-9 px-3"
                  >
                    Review
                  </a>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ApprovalDetail() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <a href="/approve" className="btn-ghost h-9 px-3">
          <ArrowLeft className="w-4 h-4" />
        </a>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Review Content</h1>
          <p className="text-gray-600">Blog: Q1 Product Update</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Content Preview */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-6">
            <h2 className="text-lg font-semibold mb-4">Content Preview</h2>
            <div className="prose max-w-none">
              <h1>Q1 Product Update: What's New in RevTown</h1>
              <p>
                We're excited to share the latest updates to RevTown, our
                autonomous go-to-market execution platform. This quarter, we've
                focused on improving the efficiency and quality of AI-generated
                content across all Rigs.
              </p>
              <h2>New Features</h2>
              <ul>
                <li>Enhanced Refinery checks for better content quality</li>
                <li>Improved Witness contradiction detection</li>
                <li>New Polecat types for social media management</li>
              </ul>
              <p>
                Stay tuned for more updates as we continue to build the future
                of GTM automation.
              </p>
            </div>
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold mb-4">Edit Content</h2>
            <textarea
              className="input h-48 font-mono text-sm"
              defaultValue="# Q1 Product Update: What's New in RevTown..."
            />
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions */}
          <div className="card p-6 space-y-4">
            <h2 className="text-lg font-semibold">Decision</h2>
            <div className="space-y-2">
              <button className="btn-primary w-full flex items-center justify-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Approve
              </button>
              <button className="btn-secondary w-full flex items-center justify-center gap-2">
                <Edit className="w-4 h-4" />
                Edit & Approve
              </button>
              <button className="btn-destructive w-full flex items-center justify-center gap-2">
                <XCircle className="w-4 h-4" />
                Reject
              </button>
            </div>
          </div>

          {/* Refinery Scores */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold mb-4">Refinery Scores</h2>
            <div className="space-y-3">
              <ScoreRow name="Brand Voice" score={0.92} />
              <ScoreRow name="SEO Grade" score={0.88} />
              <ScoreRow name="Readability" score={0.95} />
              <ScoreRow name="Hallucination" score={0.85} />
              <ScoreRow name="Legal Flags" score={1.0} />
            </div>
          </div>

          {/* Warnings */}
          <div className="card p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
              Warnings
            </h2>
            <ul className="text-sm space-y-2 text-gray-600">
              <li>• Keyword density for "GTM" is below optimal</li>
              <li>• Consider adding a stronger CTA</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoreRow({ name, score }: { name: string; score: number }) {
  const percentage = score * 100;
  const color =
    percentage >= 90
      ? 'bg-green-500'
      : percentage >= 70
        ? 'bg-yellow-500'
        : 'bg-red-500';

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{name}</span>
        <span>{percentage.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`${color} h-2 rounded-full`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
