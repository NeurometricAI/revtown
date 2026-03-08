import { Routes, Route } from 'react-router-dom';
import { BarChart3, TrendingUp, Zap, Target } from 'lucide-react';

export function OptimizePage() {
  return (
    <Routes>
      <Route index element={<OptimizeDashboard />} />
    </Routes>
  );
}

function OptimizeDashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics & Optimize</h1>
        <p className="text-gray-600">Performance insights and optimization</p>
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Content Performance"
          value="87%"
          change="+5%"
          icon={BarChart3}
        />
        <MetricCard
          title="A/B Test Win Rate"
          value="62%"
          change="+12%"
          icon={Target}
        />
        <MetricCard
          title="Avg. Refinery Score"
          value="91%"
          change="+3%"
          icon={Zap}
        />
        <MetricCard
          title="Polecat Efficiency"
          value="94%"
          change="+8%"
          icon={TrendingUp}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Campaign Funnel */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Campaign Funnel</h2>
          <div className="space-y-4">
            <FunnelStep label="Leads Generated" value={1250} percentage={100} />
            <FunnelStep label="Enriched" value={980} percentage={78} />
            <FunnelStep label="Qualified" value={540} percentage={43} />
            <FunnelStep label="Contacted" value={320} percentage={26} />
            <FunnelStep label="Engaged" value={85} percentage={7} />
            <FunnelStep label="Converted" value={12} percentage={1} />
          </div>
        </div>

        {/* A/B Tests */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Active A/B Tests</h2>
          <div className="space-y-4">
            <TestRow
              name="Landing Page CTA"
              status="running"
              confidence={87}
              winner="Variant B"
            />
            <TestRow
              name="Email Subject Lines"
              status="running"
              confidence={62}
              winner="Control"
            />
            <TestRow
              name="Social Post Format"
              status="completed"
              confidence={95}
              winner="Variant A"
            />
          </div>
        </div>

        {/* Neurometric Performance */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Neurometric Performance</h2>
          <div className="space-y-4">
            <ModelRow
              taskClass="Blog Draft"
              model="Claude Sonnet"
              status="optimal"
              avgLatency="2.3s"
            />
            <ModelRow
              taskClass="Email Personalization"
              model="Claude Haiku"
              status="optimal"
              avgLatency="0.8s"
            />
            <ModelRow
              taskClass="Competitor Analysis"
              model="Claude Opus"
              status="evaluating"
              avgLatency="4.5s"
            />
            <ModelRow
              taskClass="PR Pitch Draft"
              model="Claude Sonnet"
              status="optimal"
              avgLatency="2.1s"
            />
          </div>
        </div>

        {/* Content Attribution */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Content Attribution</h2>
          <div className="space-y-4">
            <AttributionRow content="Q4 Product Guide" leads={45} conversions={3} />
            <AttributionRow content="Integration Tutorial" leads={38} conversions={2} />
            <AttributionRow content="Pricing Comparison" leads={29} conversions={4} />
            <AttributionRow content="Customer Success Story" leads={22} conversions={1} />
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  change,
  icon: Icon,
}: {
  title: string;
  value: string;
  change: string;
  icon: React.ElementType;
}) {
  const isPositive = change.startsWith('+');

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          <p
            className={`text-sm mt-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}
          >
            {change} vs last period
          </p>
        </div>
        <div className="p-3 bg-brand-50 rounded-lg">
          <Icon className="w-6 h-6 text-brand-600" />
        </div>
      </div>
    </div>
  );
}

function FunnelStep({
  label,
  value,
  percentage,
}: {
  label: string;
  value: number;
  percentage: number;
}) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{label}</span>
        <span className="font-medium">
          {value.toLocaleString()} ({percentage}%)
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-3">
        <div
          className="bg-brand-500 h-3 rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function TestRow({
  name,
  status,
  confidence,
  winner,
}: {
  name: string;
  status: 'running' | 'completed' | 'paused';
  confidence: number;
  winner: string;
}) {
  const statusColors = {
    running: 'badge-warning',
    completed: 'badge-success',
    paused: 'badge-secondary',
  };

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-sm text-gray-500">
          Leading: {winner} ({confidence}% confidence)
        </p>
      </div>
      <span className={statusColors[status]}>{status}</span>
    </div>
  );
}

function ModelRow({
  taskClass,
  model,
  status,
  avgLatency,
}: {
  taskClass: string;
  model: string;
  status: 'optimal' | 'evaluating' | 'deprecated';
  avgLatency: string;
}) {
  const statusColors = {
    optimal: 'text-green-600',
    evaluating: 'text-yellow-600',
    deprecated: 'text-red-600',
  };

  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div>
        <p className="font-medium">{taskClass}</p>
        <p className="text-sm text-gray-500">
          {model} · Avg latency: {avgLatency}
        </p>
      </div>
      <span className={`text-sm font-medium ${statusColors[status]}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    </div>
  );
}

function AttributionRow({
  content,
  leads,
  conversions,
}: {
  content: string;
  leads: number;
  conversions: number;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <p className="font-medium">{content}</p>
      <div className="text-right">
        <p className="text-sm">
          <span className="font-medium">{leads}</span>{' '}
          <span className="text-gray-500">leads</span>
        </p>
        <p className="text-sm">
          <span className="font-medium">{conversions}</span>{' '}
          <span className="text-gray-500">conversions</span>
        </p>
      </div>
    </div>
  );
}
