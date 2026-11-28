import { describe, test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function createMemoryStorage() {
  const store = new Map();
  return {
    getItem(k) {
      return store.has(k) ? store.get(k) : null;
    },
    setItem(k, v) {
      store.set(k, String(v));
    },
    removeItem(k) {
      store.delete(k);
    },
    clear() {
      store.clear();
    },
  };
}

// Install minimal browser globals before importing api-client
globalThis.window = {
  sessionStorage: createMemoryStorage(),
  localStorage: createMemoryStorage(),
};

const apiModule = await import("../src/lib/api-client.ts");
const {
  default: api,
  ApiError,
  setSessionTokens,
  clearSessionTokens,
  getAccessToken,
  getRefreshToken,
  hasRefreshToken,
  setAuthFailureHandler,
} = apiModule;

describe("Frontend Auth Lifecycle", { concurrency: false }, () => {
test("unauthenticated initialization makes zero refresh calls and blocks protected views in source", async () => {
  clearSessionTokens();
  let fetchCalls = 0;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    throw new Error("Should not call fetch when no refresh token exists");
  };

  assert.equal(getAccessToken(), null);
  assert.equal(hasRefreshToken(), false);
  const res = await api.refresh();
  assert.equal(res, null);
  assert.equal(fetchCalls, 0);

  // Verify AppContext & page.tsx gate unauthenticated users before fetching projects
  const appContextSrc = fs.readFileSync(path.join(__dirname, "../src/context/AppContext.tsx"), "utf8");
  const pageSrc = fs.readFileSync(path.join(__dirname, "../src/app/page.tsx"), "utf8");
  assert.match(appContextSrc, /Unauthenticated visitors must not trigger protected API requests/);
  assert.doesNotMatch(appContextSrc, /Load public project list/);
  assert.match(pageSrc, /if \(!user\)[\s\S]*<AuthModal isOpen=\{true\} requireAuth=\{true\}/);
});

test("successful login stores access token in memory only and loads projects with Bearer auth", async () => {
  clearSessionTokens();
  const seenRequests = [];

  globalThis.fetch = async (url, options = {}) => {
    seenRequests.push({ url, headers: options.headers || {} });
    if (url.endsWith("/api/v1/auth/login")) {
      return new Response(
        JSON.stringify({ access_token: "acc_1", refresh_token: "ref_1", expires_in: 1800 }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (url.endsWith("/api/v1/auth/me")) {
      return new Response(
        JSON.stringify({ id: "u1", email: "a@b.com", username: "alice", is_active: true, created_at: "2026-01-01" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (url.endsWith("/api/v1/projects")) {
      return new Response(
        JSON.stringify([{ id: "p1", name: "Alpha", created_at: "2026-01-01", updated_at: "2026-01-01" }]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    return new Response(null, { status: 404 });
  };

  const loginData = await api.login({ email: "a@b.com", password: "SecretPassword1!" });
  setSessionTokens(loginData.access_token, loginData.refresh_token);

  // Access token stays in memory; never persisted in localStorage
  assert.equal(getAccessToken(), "acc_1");
  assert.equal(getRefreshToken(), "ref_1");
  assert.equal(globalThis.window.localStorage.getItem("ag_access_token"), null);
  assert.equal(globalThis.window.localStorage.getItem("ag_refresh_token"), null);

  const me = await api.getMe();
  const projects = await api.listProjects();
  assert.equal(me.username, "alice");
  assert.equal(projects.length, 1);
  assert.equal(seenRequests[1].headers.Authorization, "Bearer acc_1");
  assert.equal(seenRequests[2].headers.Authorization, "Bearer acc_1");
});

test("concurrent 401 responses trigger a single refresh call, rotate tokens, and retry all requests", async () => {
  clearSessionTokens();
  setSessionTokens("expired_acc", "ref_old");

  let refreshCount = 0;
  let protectedAttempts = 0;

  globalThis.fetch = async (url, options = {}) => {
    if (url.endsWith("/api/v1/auth/refresh")) {
      refreshCount += 1;
      const body = JSON.parse(options.body);
      assert.equal(body.refresh_token, "ref_old");
      await new Promise((r) => setTimeout(r, 20));
      return new Response(
        JSON.stringify({ access_token: "fresh_acc", refresh_token: "ref_rotated", expires_in: 1800 }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    protectedAttempts += 1;
    const auth = options.headers?.Authorization;
    if (auth === "Bearer expired_acc") {
      return new Response(
        JSON.stringify({ detail: { code: "UNAUTHORIZED", message: "Access token has expired" } }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );
    }
    if (auth === "Bearer fresh_acc") {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(null, { status: 401 });
  };

  // Trigger 4 simultaneous requests that all initially fail 401 with expired_acc
  const results = await Promise.all([
    api.listProjects(),
    api.listAgents("p1"),
    api.listTools("p1"),
    api.listApprovals("p1", "PENDING"),
  ]);

  assert.equal(results.length, 4);
  assert.equal(refreshCount, 1, "Single-flight coordinator must issue exactly 1 refresh request");
  assert.equal(protectedAttempts, 8);
  assert.equal(getAccessToken(), "fresh_acc");
  assert.equal(getRefreshToken(), "ref_rotated");
});

test("failed refresh clears tokens, invokes authFailureHandler, and rejects with 401 ApiError", async () => {
  clearSessionTokens();
  setSessionTokens("expired_acc", "revoked_ref");

  let authFailureTriggered = 0;
  setAuthFailureHandler(() => {
    authFailureTriggered += 1;
  });

  globalThis.fetch = async (url) => {
    if (url.endsWith("/api/v1/auth/refresh")) {
      return new Response(
        JSON.stringify({ detail: { code: "UNAUTHORIZED", message: "Refresh token revoked" } }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );
    }
    return new Response(
      JSON.stringify({ detail: { code: "UNAUTHORIZED", message: "Expired" } }),
      { status: 401, headers: { "Content-Type": "application/json" } }
    );
  };

  await assert.rejects(
    () => api.listProjects(),
    (err) => err instanceof ApiError && err.status === 401
  );

  assert.equal(authFailureTriggered, 1);
  assert.equal(getAccessToken(), null);
  assert.equal(getRefreshToken(), null);
  setAuthFailureHandler(null);
});
});
