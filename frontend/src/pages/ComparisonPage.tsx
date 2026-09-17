import { useState } from "react";
import { ApiError, compareRuns, getReproducibility } from "../api/client";
import type { Comparison, Difference, DifferenceCategory, Reproducibility, RunProvenanceIn } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

const SECTIONS: { category: DifferenceCategory; label: string; statusKey: keyof Comparison }[] = [
  { category: "CODE", label: "Code", statusKey: "code_status" },
  { category: "DATASET", label: "Dataset", statusKey: "dataset_status" },
  { category: "ENVIRONMENT", label: "Environment", statusKey: "environment_status" },
  { category: "CONFIGURATION", label: "Configuration", statusKey: "configuration_status" },
  { category: "RANDOMNESS", label: "Randomness", statusKey: "randomness_status" },
  { category: "METRICS", label: "Metrics", statusKey: "metrics_status" },
];

function parseProvenanceJson(text: string): RunProvenanceIn | undefined {
  if (!text.trim()) return undefined;
  return JSON.parse(text) as RunProvenanceIn;
}

export function ComparisonPage() {
  const [baseRunId, setBaseRunId] = useState("");
  const [compareRunId, setCompareRunId] = useState("");
  const [baseProvenanceText, setBaseProvenanceText] = useState("");
  const [compareProvenanceText, setCompareProvenanceText] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [reproducibility, setReproducibility] = useState<Reproducibility | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    setComparison(null);
    setReproducibility(null);

    let base: RunProvenanceIn | undefined;
    let compare: RunProvenanceIn | undefined;
    try {
      base = parseProvenanceJson(baseProvenanceText);
      compare = parseProvenanceJson(compareProvenanceText);
    } catch {
      setFormError("Provenance payloads must be valid JSON.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await compareRuns(baseRunId, { compare_run_id: compareRunId, base, compare });
      setComparison(result);
      try {
        setReproducibility(await getReproducibility(result.id));
      } catch {
        // A classification should always exist once a comparison is
        // created, but this view degrades gracefully if it doesn't.
      }
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not compare these runs.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Experiment Comparison</h1>
        <p className="text-sm text-slate-500">Side-by-side ORIGINAL vs REPRODUCTION, with evidence per category.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="base-run-id" className="mb-1 block text-xs font-medium text-slate-600">
              Base run ID (ORIGINAL)
            </label>
            <input
              id="base-run-id"
              required
              placeholder="Base run ID (ORIGINAL)"
              value={baseRunId}
              onChange={(e) => setBaseRunId(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="compare-run-id" className="mb-1 block text-xs font-medium text-slate-600">
              Compare run ID (REPRODUCTION)
            </label>
            <input
              id="compare-run-id"
              required
              placeholder="Compare run ID (REPRODUCTION)"
              value={compareRunId}
              onChange={(e) => setCompareRunId(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-sm font-medium text-indigo-600 hover:underline"
        >
          {showAdvanced ? "Hide" : "Show"} advanced provenance payloads
        </button>

        {showAdvanced && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="base-provenance-json" className="mb-1 block text-xs font-medium text-slate-500">
                Base provenance JSON (code/dataset/environment/configuration/randomness/metrics)
              </label>
              <textarea
                id="base-provenance-json"
                rows={6}
                placeholder='{"metrics": {"accuracy": 0.94}}'
                value={baseProvenanceText}
                onChange={(e) => setBaseProvenanceText(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
              />
            </div>
            <div>
              <label htmlFor="compare-provenance-json" className="mb-1 block text-xs font-medium text-slate-500">
                Compare provenance JSON
              </label>
              <textarea
                id="compare-provenance-json"
                rows={6}
                placeholder='{"metrics": {"accuracy": 0.81}}'
                value={compareProvenanceText}
                onChange={(e) => setCompareProvenanceText(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
              />
            </div>
            <p className="col-span-full text-xs text-slate-400">
              Without these, every category will honestly report NOT_COMPARABLE - no phase yet persists real
              captured provenance for a run (see docs/API.md).
            </p>
          </div>
        )}

        {formError && <p className="text-sm text-red-600">{formError}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? "Comparing..." : "Compare Runs"}
        </button>
      </form>

      {comparison && (
        <div className="space-y-4">
          {reproducibility && (
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-indigo-500">Reproducibility</p>
              <p className="text-lg font-semibold text-indigo-900">{reproducibility.classification}</p>
            </div>
          )}

          {SECTIONS.map((section) => {
            const status = comparison[section.statusKey] as Comparison["code_status"];
            const evidence: Difference[] = comparison.differences.filter((d) => d.category === section.category);
            return (
              <div key={section.category} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">{section.label}</h2>
                  <StatusBadge status={status} />
                </div>
                {evidence.length === 0 ? (
                  <p className="text-sm text-slate-400">No differences recorded.</p>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="text-xs uppercase text-slate-400">
                        <th className="py-1 pr-4">Field</th>
                        <th className="py-1 pr-4">Original</th>
                        <th className="py-1 pr-4">Reproduction</th>
                        <th className="py-1 pr-4">Severity</th>
                        <th className="py-1">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.map((diff) => (
                        <tr key={diff.id} className="border-t border-slate-100">
                          <td className="py-1.5 pr-4 font-mono text-xs text-slate-700">{diff.field}</td>
                          <td className="py-1.5 pr-4 text-slate-600">{diff.old_value ?? "—"}</td>
                          <td className="py-1.5 pr-4 text-slate-600">{diff.new_value ?? "—"}</td>
                          <td className="py-1.5 pr-4 text-slate-600">{diff.severity}</td>
                          <td className="py-1.5 text-slate-600">{diff.confidence}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
