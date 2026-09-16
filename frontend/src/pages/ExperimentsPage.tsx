import { useState } from "react";
import { ApiError, createExperiment, listExperiments, listProjects } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useApiResource } from "../hooks/useApiResource";

export function ExperimentsPage() {
  const { state, refresh } = useApiResource(() => listExperiments());
  const { state: projectsState } = useApiResource(() => listProjects());

  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [workloadType, setWorkloadType] = useState("sklearn_tabular");
  const [entrypointScript, setEntrypointScript] = useState("train.py");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const projects = projectsState.status === "ready" ? projectsState.data.items : [];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createExperiment({
        project_id: projectId,
        name,
        workload_type: workloadType,
        entrypoint_script: entrypointScript,
      });
      setName("");
      refresh();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the experiment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Experiments</h1>
        <p className="text-sm text-slate-500">Workloads registered for reproducibility tracking.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">New Experiment</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <select
            required
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="" disabled>
              {projects.length === 0 ? "No projects yet - create one first" : "Select a project"}
            </option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <input
            required
            placeholder="Experiment name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Workload type"
            value={workloadType}
            onChange={(e) => setWorkloadType(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Entrypoint script"
            value={entrypointScript}
            onChange={(e) => setEntrypointScript(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        {formError && <p className="text-sm text-red-600">{formError}</p>}
        <button
          type="submit"
          disabled={submitting || projectId === ""}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create Experiment"}
        </button>
      </form>

      {state.status === "loading" && <LoadingState />}
      {state.status === "error" && <ErrorState message={state.message} onRetry={refresh} />}
      {state.status === "ready" && (
        <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
          {state.data.items.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No experiments yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {state.data.items.map((experiment) => (
                <li key={experiment.id} className="p-4">
                  <p className="font-medium text-slate-900">{experiment.name}</p>
                  <p className="text-sm text-slate-500">
                    {experiment.workload_type} · {experiment.entrypoint_script}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
