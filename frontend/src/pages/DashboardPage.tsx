import { Link } from "react-router-dom";
import { getDashboard } from "../api/client";
import { BarBreakdown } from "../components/BarBreakdown";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { StatCard } from "../components/StatCard";
import { useApiResource } from "../hooks/useApiResource";

export function DashboardPage() {
  const { state, refresh } = useApiResource(getDashboard);

  if (state.status === "loading") return <LoadingState label="Loading dashboard..." />;
  if (state.status === "error") return <ErrorState message={state.message} onRetry={refresh} />;

  const d = state.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">Live counts from the REPROX API.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total Projects" value={d.total_projects} />
        <StatCard label="Total Experiments" value={d.total_experiments} />
        <StatCard label="Total Runs" value={d.total_runs} />
        <StatCard label="Active Jobs" value={d.active_jobs} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-slate-900">Reproducibility Breakdown</h2>
        <BarBreakdown
          items={[
            { label: "Reproducible Runs", value: d.reproducible_runs, colorClassName: "bg-emerald-500" },
            { label: "Partial Reproductions", value: d.partial_reproductions, colorClassName: "bg-amber-500" },
            { label: "Failed Reproductions", value: d.failed_reproductions, colorClassName: "bg-red-500" },
            { label: "Insufficient Evidence", value: d.insufficient_evidence, colorClassName: "bg-slate-400" },
          ]}
        />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Recent Experiments</h2>
        {d.recent_experiments.length === 0 ? (
          <p className="text-sm text-slate-500">No experiments yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {d.recent_experiments.map((experiment) => (
              <li key={experiment.id} className="py-2">
                <Link to="/experiments" className="text-sm text-indigo-600 hover:underline">
                  {experiment.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
