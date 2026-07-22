/**
 * App-level privacy-consent flow (Dev-Phase 1 task 7.3 logic layer).
 *
 * D1-10 contract (specs/desktop-pet-ui/spec.md + analysis/07 §八):
 *   - First launch MUST show privacy-consent modal
 *   - Decline → app keeps running, but start_flow is rejected
 *   - Consent persists to localStorage; subsequent launches skip the modal
 *   - After consent, the start-flow form is reachable
 *
 * The ws-client is mocked so these tests are pure UI logic (no real WebSocket).
 * The full real-Electron rendering path lives in tests/e2e/privacy-consent.test.ts.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock ws-client so App never opens a real socket.
vi.mock("../../src/shared/ws-client", () => {
  const mkFlowStarted = () => ({
    type: "flow_started",
    message_id: "mid-mock",
    flow_id: "fid-mock",
    timestamp: new Date().toISOString(),
    status: "running",
  });
  return {
    createSddpClient: () => ({
      connect: () => Promise.resolve(),
      close: () => {},
      getState: () => "connected",
      sendRpc: vi.fn(async () => mkFlowStarted()),
    }),
    newStartFlowRequest: (proposal: string, projectPath: string) => ({
      type: "start_flow",
      message_id: "mid-mock",
      timestamp: new Date().toISOString(),
      proposal,
      project_path: projectPath,
    }),
    newUserFeedbackRequest: (flowId: string, feedback: string) => ({
      type: "user_feedback",
      message_id: "mid-mock",
      flow_id: flowId,
      timestamp: new Date().toISOString(),
      feedback,
    }),
    newAbortFlowRequest: (flowId: string) => ({
      type: "abort_flow",
      message_id: "mid-mock",
      flow_id: flowId,
      timestamp: new Date().toISOString(),
    }),
  };
});

import { App } from "../../src/window2-panel/app";

describe("App privacy-consent flow (D1-10, task 7.3)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("first launch shows the privacy-consent modal and not the main panel", () => {
    render(<App />);
    expect(screen.getByTestId("privacy-consent-modal")).toBeInTheDocument();
    expect(screen.queryByTestId("start-flow-form")).toBeNull();
    expect(screen.queryByTestId("conn-state")).toBeNull();
  });

  it("clicking 同意 persists consent and reveals the main panel", () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("privacy-consent"));
    expect(localStorage.getItem("sddp:privacy-consent")).toBe("true");
    expect(screen.queryByTestId("privacy-consent-modal")).toBeNull();
    expect(screen.getByText("SDDP-Pet")).toBeInTheDocument();
    expect(screen.getByTestId("conn-state")).toBeInTheDocument();
  });

  it("decline keeps the app running (modal still mounted, no crash)", () => {
    render(<App />);
    fireEvent.click(screen.getByTestId("privacy-decline"));
    expect(localStorage.getItem("sddp:privacy-consent")).toBe("false");
    // App is still alive: the modal is re-rendered (decline does NOT exit)
    expect(screen.getByTestId("privacy-consent-modal")).toBeInTheDocument();
  });

  it("consent is read from localStorage on a fresh instance (cross-session)", () => {
    localStorage.setItem("sddp:privacy-consent", "true");
    render(<App />);
    expect(screen.queryByTestId("privacy-consent-modal")).toBeNull();
    expect(screen.getByText("SDDP-Pet")).toBeInTheDocument();
  });

  it("after consent, submitting a proposal starts a flow (active-flow shown)", async () => {
    localStorage.setItem("sddp:privacy-consent", "true");
    render(<App />);
    fireEvent.change(screen.getByTestId("proposal-input"), {
      target: { value: "加一个配置热重载功能" },
    });
    fireEvent.click(screen.getByTestId("start-flow-button"));
    await waitFor(() =>
      expect(screen.getByTestId("active-flow")).toBeInTheDocument(),
    );
    expect(screen.getByText(/fid-mock/)).toBeInTheDocument();
  });
});
