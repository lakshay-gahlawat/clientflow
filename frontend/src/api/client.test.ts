import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from "axios";

// The highest-value, highest-risk piece of frontend logic in this app,
// per the engineering audit: the response interceptor's transparent
// refresh-on-401 flow, and specifically that concurrent 401s share a
// SINGLE refresh call. If two requests independently triggered refresh,
// the second would replay an already-rotated refresh token, which the
// backend treats as a theft signal and kills the entire session (see
// backend/app/services/auth_service.py::rotate_session). That failure
// mode is exactly what this test suite exists to catch.
//
// Tested via a custom axios adapter (zero new dependencies) rather than
// mocking axios wholesale — this exercises the REAL interceptor code
// registered on the real apiClient instance, not a re-implementation of
// it.

interface FakeAdapterConfig {
  refreshShouldSucceed: boolean;
  protectedEndpointFailsUntilRetried: boolean;
}

function installFakeAdapter(apiClient: typeof import("./client").apiClient, config: FakeAdapterConfig) {
  const calls: { url: string | undefined; retried: boolean | undefined }[] = [];

  apiClient.defaults.adapter = async (axiosConfig: AxiosRequestConfig): Promise<AxiosResponse> => {
    const cfg = axiosConfig as AxiosRequestConfig & { _isRefreshCall?: boolean; _retried?: boolean };
    calls.push({ url: cfg.url, retried: cfg._retried });

    const respond = (status: number, data: unknown): AxiosResponse => ({
      data,
      status,
      statusText: String(status),
      headers: {},
      config: axiosConfig as InternalAxiosRequestConfig,
    });

    const reject401 = () => {
      const error: any = new Error("Unauthorized");
      error.isAxiosError = true;
      error.config = axiosConfig;
      error.response = respond(401, { detail: "Not authenticated" });
      throw error;
    };

    if (cfg.url === "/auth/refresh") {
      if (config.refreshShouldSucceed) {
        return respond(200, {
          access_token: "new-access-token",
          token_type: "bearer",
          user: { id: "u1", email: "a@test.com", full_name: "A" },
        });
      }
      const error: any = new Error("Unauthorized");
      error.isAxiosError = true;
      error.config = axiosConfig;
      error.response = respond(401, { detail: "Invalid refresh token" });
      throw error;
    }

    if (cfg.url === "/protected") {
      if (config.protectedEndpointFailsUntilRetried && !cfg._retried) {
        reject401();
      }
      return respond(200, { ok: true });
    }

    return respond(200, {});
  };

  return calls;
}

describe("api client — refresh interceptor", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches the Authorization header only when an access token is set", async () => {
    const { apiClient, setAccessToken } = await import("./client");
    const calls: AxiosRequestConfig[] = [];
    apiClient.defaults.adapter = async (config: AxiosRequestConfig): Promise<AxiosResponse> => {
      calls.push(config);
      return { data: {}, status: 200, statusText: "OK", headers: {}, config: config as InternalAxiosRequestConfig };
    };

    setAccessToken(null);
    await apiClient.get("/whatever");
    expect(calls[0]!.headers?.Authorization).toBeUndefined();

    setAccessToken("token-123");
    await apiClient.get("/whatever");
    expect(calls[1]!.headers?.Authorization).toBe("Bearer token-123");

    setAccessToken(null);
  });

  it("transparently refreshes and retries on a 401, succeeding on retry", async () => {
    const { apiClient, setAccessToken } = await import("./client");
    setAccessToken("stale-token");
    const calls = installFakeAdapter(apiClient, {
      refreshShouldSucceed: true,
      protectedEndpointFailsUntilRetried: true,
    });

    const response = await apiClient.get("/protected");

    expect(response.status).toBe(200);
    expect(response.data).toEqual({ ok: true });
    // First attempt at /protected (401), then /auth/refresh, then the retried /protected.
    expect(calls.map((c) => c.url)).toEqual(["/protected", "/auth/refresh", "/protected"]);
    setAccessToken(null);
  });

  it("shares ONE refresh call across concurrent 401s — the critical correctness property", async () => {
    const { apiClient, setAccessToken } = await import("./client");
    setAccessToken("stale-token");
    const calls = installFakeAdapter(apiClient, {
      refreshShouldSucceed: true,
      protectedEndpointFailsUntilRetried: true,
    });

    // Two requests that will BOTH hit a 401 before either has a chance
    // to complete its own refresh — this is exactly the race the shared
    // refreshPromise exists to prevent.
    const [r1, r2] = await Promise.all([apiClient.get("/protected"), apiClient.get("/protected")]);

    expect(r1.status).toBe(200);
    expect(r2.status).toBe(200);
    const refreshCalls = calls.filter((c) => c.url === "/auth/refresh");
    expect(refreshCalls.length).toBe(1);
    setAccessToken(null);
  });

  it("clears the access token and broadcasts a null session when refresh fails", async () => {
    const { apiClient, setAccessToken, onSessionChange } = await import("./client");
    setAccessToken("stale-token");
    installFakeAdapter(apiClient, {
      refreshShouldSucceed: false,
      protectedEndpointFailsUntilRetried: true,
    });

    const sessionUpdates: (import("./types").User | null)[] = [];
    const unsubscribe = onSessionChange((user) => sessionUpdates.push(user));

    await expect(apiClient.get("/protected")).rejects.toThrow();

    expect(sessionUpdates).toContain(null);
    unsubscribe();
  });

  it("restoreSession returns the user on a successful refresh, null otherwise", async () => {
    const { apiClient, restoreSession, setAccessToken } = await import("./client");

    installFakeAdapter(apiClient, { refreshShouldSucceed: true, protectedEndpointFailsUntilRetried: false });
    const user = await restoreSession();
    expect(user).toEqual({ id: "u1", email: "a@test.com", full_name: "A" });
    setAccessToken(null);

    installFakeAdapter(apiClient, { refreshShouldSucceed: false, protectedEndpointFailsUntilRetried: false });
    const noUser = await restoreSession();
    expect(noUser).toBeNull();
  });

  it("restoreSession does not rotate again when a session was already restored", async () => {
    const { apiClient, restoreSession, setAccessToken } = await import("./client");
    const calls = installFakeAdapter(apiClient, {
      refreshShouldSucceed: true,
      protectedEndpointFailsUntilRetried: false,
    });

    const first = await restoreSession();
    const second = await restoreSession();

    expect(first).toEqual({ id: "u1", email: "a@test.com", full_name: "A" });
    expect(second).toEqual(first);
    expect(calls.filter((c) => c.url === "/auth/refresh")).toHaveLength(1);
    setAccessToken(null);
  });
});

describe("api client — extractErrorMessage", () => {
  it("extracts a plain string detail", async () => {
    const { extractErrorMessage } = await import("./client");
    const axios = (await import("axios")).default;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(true);
    const error = { response: { data: { detail: "Invalid email or password" } } };
    expect(extractErrorMessage(error)).toBe("Invalid email or password");
  });

  it("joins a Pydantic-style validation error array", async () => {
    const { extractErrorMessage } = await import("./client");
    const axios = (await import("axios")).default;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(true);
    const error = {
      response: {
        data: { detail: [{ msg: "field required", loc: ["body", "email"] }, { msg: "too short", loc: ["body", "password"] }] },
      },
    };
    expect(extractErrorMessage(error)).toBe("field required; too short");
  });

  it("falls back to a network-error message for connection failures", async () => {
    const { extractErrorMessage } = await import("./client");
    const axios = (await import("axios")).default;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(true);
    const error = { code: "ERR_NETWORK", response: undefined };
    expect(extractErrorMessage(error)).toBe("Can't reach the server — check your connection and try again.");
  });

  it("uses the provided fallback for a non-axios error", async () => {
    const { extractErrorMessage } = await import("./client");
    const axios = (await import("axios")).default;
    vi.spyOn(axios, "isAxiosError").mockReturnValue(false);
    expect(extractErrorMessage(new Error("boom"), "Custom fallback")).toBe("Custom fallback");
  });
});
