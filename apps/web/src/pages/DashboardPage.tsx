import { Rocket, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react';

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">Overview of your GTM operations</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Campaigns"
          value="3"
          icon={Rocket}
          trend="+1 this week"
          color="blue"
        />
        <StatCard
          title="Pending Approvals"
          value="12"
          icon={CheckCircle}
          trend="5 high priority"
          color="yellow"
        />
        <StatCard
          title="Polecats Today"
          value="47"
          icon={TrendingUp}
          trend="+23% vs yesterday"
          color="green"
        />
        <StatCard
          title="Quality Alerts"
          value="2"
          icon={AlertTriangle}
          trend="Needs attention"
          color="red"
        />
      </div>

      {/* Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Approvals</h2>
          <div className="space-y-3">
            <ActivityItem
              title="Blog: Q1 Product Update"
              status="approved"
              time="5 min ago"
            />
            <ActivityItem
              title="Email: Follow-up sequence #3"
              status="pending"
              time="12 min ago"
            />
            <ActivityItem
              title="PR Pitch: TechCrunch"
              status="pending"
              time="1 hour ago"
            />
            <ActivityItem
              title="LinkedIn: Product launch"
              status="approved"
              time="2 hours ago"
            />
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Active Rigs</h2>
          <div className="space-y-3">
            <RigStatus name="Content Factory" status="active" tasks={5} />
            <RigStatus name="SDR Hive" status="active" tasks={12} />
            <RigStatus name="Social Command" status="active" tasks={3} />
            <RigStatus name="Press Room" status="active" tasks={2} />
            <RigStatus name="Intelligence Station" status="active" tasks={8} />
            <RigStatus name="Landing Pad" status="idle" tasks={0} />
            <RigStatus name="The Wire" status="active" tasks={1} />
            <RigStatus name="Repo Watch" status="idle" tasks={0} />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  color,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  trend: string;
  color: 'blue' | 'yellow' | 'green' | 'red';
}) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
  };

  return (
    <div className="card p-6">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-xs text-gray-500">{trend}</p>
        </div>
      </div>
    </div>
  );
}

function ActivityItem({
  title,
  status,
  time,
}: {
  title: string;
  status: 'approved' | 'pending' | 'rejected';
  time: string;
}) {
  const statusColors = {
    approved: 'badge-success',
    pending: 'badge-warning',
    rejected: 'badge-danger',
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-gray-500">{time}</p>
      </div>
      <span className={statusColors[status]}>{status}</span>
    </div>
  );
}

function RigStatus({
  name,
  status,
  tasks,
}: {
  name: string;
  status: 'active' | 'idle' | 'error';
  tasks: number;
}) {
  const statusColors = {
    active: 'bg-green-400',
    idle: 'bg-gray-300',
    error: 'bg-red-400',
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
        <span className="text-sm font-medium">{name}</span>
      </div>
      <span className="text-sm text-gray-500">
        {tasks > 0 ? `${tasks} tasks` : 'Idle'}
      </span>
    </div>
  );
}
