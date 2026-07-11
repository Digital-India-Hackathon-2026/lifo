import { useCallback, useState } from "react";
import { ApiError, NetworkError } from "@/api/client";

export type ApiCallState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError | NetworkError | Error }
  | { status: "success"; data: T };

/**
 * One hook, reused by every screen — loading/error/success are always real
 * network states, never mocked. `run` takes the actual API-client call to make.
 */
export function useApiCall<T>() {
  const [state, setState] = useState<ApiCallState<T>>({ status: "idle" });

  const run = useCallback(async (call: () => Promise<T>) => {
    setState({ status: "loading" });
    try {
      const data = await call();
      setState({ status: "success", data });
      return data;
    } catch (err) {
      const error =
        err instanceof ApiError || err instanceof NetworkError
          ? err
          : err instanceof Error
            ? err
            : new Error(String(err));
      setState({ status: "error", error });
      return undefined;
    }
  }, []);

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, run, reset };
}
