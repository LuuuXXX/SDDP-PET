/**
 * window2 panel React component tests (task 5.12 partial).
 *
 * Tests the 6 panel components in isolation with @testing-library/react.
 * Verifies they render required DOM elements per D1-2.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { StatePanel } from "../../src/window2-panel/state-panel/state-panel";
import { DiagnosticPanel } from "../../src/window2-panel/diagnostic-panel/diagnostic-panel";
import { ConfirmPanel } from "../../src/window2-panel/confirm-panel/confirm-panel";
import { CostDisplay } from "../../src/window2-panel/cost-display/cost-display";
import { SshSettings } from "../../src/window2-panel/ssh-settings/ssh-settings";
import { PrivacyConsentModal } from "../../src/window2-panel/privacy-consent-modal/privacy-consent-modal";

import type {
  AgentStateChange,
  CostUpdate,
  DocumentProduced,
  FeedbackRequired,
} from "../../src/shared/ws-schemas";

function ts() {
  return new Date().toISOString();
}

describe("<StatePanel />", () => {
  it("renders start-flow form when no currentFlowId", () => {
    render(
      <StatePanel
        lastStateChange={null}
        documents={[]}
        pendingFeedback={null}
        currentFlowId={null}
        onStartFlow={vi.fn()}
        onFeedback={vi.fn()}
        onAbort={vi.fn()}
      />,
    );
    expect(screen.getByTestId("start-flow-form")).toBeInTheDocument();
    expect(screen.getByTestId("proposal-input")).toBeInTheDocument();
    expect(screen.getByTestId("start-flow-button")).toBeDisabled(); // empty proposal
  });

  it("enables start button when proposal is non-empty", () => {
    render(
      <StatePanel
        lastStateChange={null}
        documents={[]}
        pendingFeedback={null}
        currentFlowId={null}
        onStartFlow={vi.fn()}
        onFeedback={vi.fn()}
        onAbort={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("proposal-input"), { target: { value: "test proposal" } });
    expect(screen.getByTestId("start-flow-button")).not.toBeDisabled();
  });

  it("renders active-flow view when currentFlowId is set", () => {
    const stateChange: AgentStateChange = {
      type: "agent_state_change",
      timestamp: ts(),
      agent: "architect",
      state: "working",
    };
    render(
      <StatePanel
        lastStateChange={stateChange}
        documents={[]}
        pendingFeedback={null}
        currentFlowId="fid-test"
        onStartFlow={vi.fn()}
        onFeedback={vi.fn()}
        onAbort={vi.fn()}
      />,
    );
    expect(screen.getByTestId("active-flow")).toBeInTheDocument();
    expect(screen.getByTestId("agent-state").textContent).toContain("architect");
    expect(screen.getByTestId("agent-state").textContent).toContain("working");
  });

  it("renders document list", () => {
    const docs: DocumentProduced[] = [
      {
        type: "document_produced",
        timestamp: ts(),
        agent: "architect",
        doc_type: "delta_spec",
        doc_id: "ds-1",
        summary: "spec summary",
      },
    ];
    render(
      <StatePanel
        lastStateChange={null}
        documents={docs}
        pendingFeedback={null}
        currentFlowId="fid-test"
        onStartFlow={vi.fn()}
        onFeedback={vi.fn()}
        onAbort={vi.fn()}
      />,
    );
    expect(screen.getByTestId("document-delta_spec")).toBeInTheDocument();
    expect(screen.getByTestId("document-delta_spec").textContent).toContain("spec summary");
  });
});

describe("<DiagnosticPanel /> (D1-15)", () => {
  it("renders 4 metric cards", () => {
    render(<DiagnosticPanel lastCost={null} errors={[]} />);
    // cards keyed by label
    expect(screen.getByTestId("metric-card-总 token 数")).toBeInTheDocument();
    expect(screen.getByTestId("metric-card-估算成本 (USD)")).toBeInTheDocument();
    expect(screen.getByTestId("metric-card-错误率")).toBeInTheDocument();
    expect(screen.getByTestId("metric-card-历史 flow 数")).toBeInTheDocument();
  });

  it("renders cost values from lastCost", () => {
    const cost: CostUpdate = {
      type: "cost_update",
      timestamp: ts(),
      total_tokens: 12345,
      estimated_cost_usd: 0.0567,
      round_tokens: {},
    };
    render(<DiagnosticPanel lastCost={cost} errors={[]} />);
    // DiagnosticPanel shows the raw total_tokens; the formatted version is in
    // CostDisplay (covered separately). Assert raw value here.
    expect(screen.getByTestId("metric-card-总 token 数").textContent).toContain("12345");
    expect(screen.getByTestId("metric-card-估算成本 (USD)").textContent).toContain("$0.0567");
  });
});

describe("<ConfirmPanel /> (D1-8)", () => {
  const feedback: FeedbackRequired = {
    type: "feedback_required",
    timestamp: ts(),
    method: "design_confirmation",
    message: "等待方案确认",
    output: { title: "Mock Design" },
  };

  it("renders the 3 buttons (y/n/e)", () => {
    render(<ConfirmPanel feedback={feedback} onY={vi.fn()} onN={vi.fn()} onE={vi.fn()} />);
    expect(screen.getByTestId("confirm-y")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-n")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-e")).toBeInTheDocument();
  });

  it("shows method label and payload", () => {
    render(<ConfirmPanel feedback={feedback} onY={vi.fn()} onN={vi.fn()} onE={vi.fn()} />);
    expect(screen.getByText(/方案确认/)).toBeInTheDocument();
    expect(screen.getByTestId("confirm-payload").textContent).toContain("Mock Design");
  });

  it("fires onY when 同意 clicked", () => {
    const onY = vi.fn();
    render(<ConfirmPanel feedback={feedback} onY={onY} onN={vi.fn()} onE={vi.fn()} />);
    fireEvent.click(screen.getByTestId("confirm-y"));
    expect(onY).toHaveBeenCalledOnce();
  });
});

describe("<CostDisplay />", () => {
  it("shows em-dash when no cost data", () => {
    render(<CostDisplay lastCost={null} />);
    expect(screen.getByTestId("total-tokens").textContent).toContain("—");
  });
});

describe("<SshSettings /> (D1-16)", () => {
  it("renders the 4 form fields + test button", () => {
    render(<SshSettings />);
    expect(screen.getByTestId("ssh-host")).toBeInTheDocument();
    expect(screen.getByTestId("ssh-port")).toBeInTheDocument();
    expect(screen.getByTestId("ssh-username")).toBeInTheDocument();
    expect(screen.getByTestId("ssh-key-ref")).toBeInTheDocument();
    expect(screen.getByTestId("ssh-test-button")).toBeDisabled(); // empty host/user
  });

  it("enables test button when host + username provided", () => {
    render(<SshSettings />);
    fireEvent.change(screen.getByTestId("ssh-host"), { target: { value: "example.com" } });
    fireEvent.change(screen.getByTestId("ssh-username"), { target: { value: "ubuntu" } });
    expect(screen.getByTestId("ssh-test-button")).not.toBeDisabled();
  });
});

describe("<PrivacyConsentModal /> (D1-10)", () => {
  it("renders with both consent + decline buttons", () => {
    render(<PrivacyConsentModal onConsent={vi.fn()} onDecline={vi.fn()} />);
    expect(screen.getByTestId("privacy-consent")).toBeInTheDocument();
    expect(screen.getByTestId("privacy-decline")).toBeInTheDocument();
    expect(screen.getByText(/proposal 文本/)).toBeInTheDocument();
  });

  it("fires onConsent when 同意 clicked", () => {
    const onConsent = vi.fn();
    render(<PrivacyConsentModal onConsent={onConsent} onDecline={vi.fn()} />);
    fireEvent.click(screen.getByTestId("privacy-consent"));
    expect(onConsent).toHaveBeenCalledOnce();
  });

  it("fires onDecline when 拒绝 clicked", () => {
    const onDecline = vi.fn();
    render(<PrivacyConsentModal onConsent={vi.fn()} onDecline={onDecline} />);
    fireEvent.click(screen.getByTestId("privacy-decline"));
    expect(onDecline).toHaveBeenCalledOnce();
  });
});
