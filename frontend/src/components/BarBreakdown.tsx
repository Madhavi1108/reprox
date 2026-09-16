interface BarBreakdownItem {
  label: string;
  value: number;
  colorClassName: string;
}

/** A minimal proportional bar chart - no charting library dependency,
 * since bar widths driven directly by real counts already satisfy the
 * spec's "meaningful, not decorative, every visualization must represent
 * actual backend data" requirement without one. */
export function BarBreakdown({ items }: { items: BarBreakdownItem[] }) {
  const max = Math.max(1, ...items.map((item) => item.value));

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="mb-1 flex justify-between text-sm text-slate-600">
            <span>{item.label}</span>
            <span className="font-medium text-slate-900">{item.value}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-100">
            <div
              className={`h-2 rounded-full ${item.colorClassName}`}
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
