import { useState } from "react";
import { ApiError, createProject, listProjects } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useApiResource } from "../hooks/useApiResource";

export function ProjectsPage() {
  const { state, refresh } = useApiResource(() => listProjects());
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createProject({ name, slug, description: description || null });
      setName("");
      setSlug("");
      setDescription("");
      refresh();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the project.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Projects</h1>
        <p className="text-sm text-slate-500">Every project REPROX is tracking experiments for.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">New Project</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <input
            required
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="slug-like-this"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <textarea
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {formError && <p className="text-sm text-red-600">{formError}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create Project"}
        </button>
      </form>

      {state.status === "loading" && <LoadingState />}
      {state.status === "error" && <ErrorState message={state.message} onRetry={refresh} />}
      {state.status === "ready" && (
        <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
          {state.data.items.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No projects yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {state.data.items.map((project) => (
                <li key={project.id} className="p-4">
                  <p className="font-medium text-slate-900">{project.name}</p>
                  <p className="text-sm text-slate-500">{project.slug}</p>
                  {project.description && <p className="mt-1 text-sm text-slate-600">{project.description}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
