import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

export type ApiResourceState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

/** Fetches `fetcher()` on mount and whenever `deps` change, exposing a
 * loading/error/ready state plus a `refresh` callback for post-mutation
 * refetches (e.g. after a create-form submit). */
export function useApiResource<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<ApiResourceState<T>>({ status: "loading" });

  const load = useCallback(() => {
    setState({ status: "loading" });
    fetcher()
      .then((data) => setState({ status: "ready", data }))
      .catch((err: unknown) => {
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        setState({ status: "error", message });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { state, refresh: load };
}
