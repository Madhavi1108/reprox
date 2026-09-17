import type { ComparisonStatus } from "../api/types";

// Spec (§55) wants exactly 3 states (MATCH/DIFFERENCE/UNKNOWN); the
// backend has 5. SAME/DIFFERENT map cleanly; UNKNOWN, NOT_COMPARABLE, and
// PARTIALLY_MATCHING all collapse to the UNKNOWN badge - but the exact
// backend status is still shown as small print, so no information is
// lost by using the spec's 3-word vocabulary for the badge color/label.
const BADGE: Record<ComparisonStatus, { label: string; className: string }> = {
  SAME: { label: "MATCH", className: "bg-emerald-100 text-emerald-800" },
  DIFFERENT: { label: "DIFFERENCE", className: "bg-red-100 text-red-800" },
  UNKNOWN: { label: "UNKNOWN", className: "bg-slate-100 text-slate-700" },
  NOT_COMPARABLE: { label: "UNKNOWN", className: "bg-slate-100 text-slate-700" },
  PARTIALLY_MATCHING: { label: "UNKNOWN", className: "bg-amber-100 text-amber-800" },
};

export function StatusBadge({ status }: { status: ComparisonStatus }) {
  const badge = BADGE[status];
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badge.className}`}>{badge.label}</span>
      <span className="text-xs text-slate-400">{status}</span>
    </span>
  );
}
