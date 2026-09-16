export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return <p className="py-8 text-center text-slate-500">{label}</p>;
}
