import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
      <h1 className="text-lg font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-600">There's no REPROX page at this address.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700">
        Back to Dashboard
      </Link>
    </div>
  );
}
