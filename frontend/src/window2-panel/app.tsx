/**
 * window2 React root: hosts 6 panel types per D1-2.
 *
 * State-panel: shows agent_state_change messages (live role + state)
 * Diagnostic-panel: shows 4 metrics (D1-15)
 * Confirm-panel: shows feedback_required payload + y/n/e buttons (D1-8 split)
 * Cost-display: shows total_tokens + estimated_cost_usd
 * SSH-settings: SSH config form (D1-16)
 * Privacy-consent-modal: first-launch consent (D1-10)
 *
 * A single React Router (or simple tab state) switches between them. For DP1
 * we use simple tab state (no router) — keeping the bundle small.
 */
import { StrictMode, useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  createSddpClient,
  newStartFlowRequest,
  newUserFeedbackRequest,
  newAbortFlowRequest,
  type SddpClient,
  type ConnectionState,
} from "../shared/ws-client";
import type {
  AgentStateChange,
  DocumentProduced,
  CostUpdate,
  FeedbackRequired,
  ErrorMessage,
} from "../shared/ws-schemas";
import { StatePanel } from "./state-panel/state-panel";
import { DiagnosticPanel } from "./diagnostic-panel/diagnostic-panel";
import { ConfirmPanel } from "./confirm-panel/confirm-panel";
import { CostDisplay } from "./cost-display/cost-display";
import { SshSettings } from "./ssh-settings/ssh-settings";
import { PrivacyConsentModal } from "./privacy-consent-modal/privacy-consent-modal";

const PRIVACY_CONSENT_KEY = "sddp:privacy-consent";

type Tab = "state" | "diagnostic" | "settings";

function App() {
  const [client, setClient] = useState<SddpClient | null>(null);
  const [connState, setConnState] = useState<ConnectionState>("disconnected");
  const [tab, setTab] = useState<Tab>("state");

  const [lastStateChange, setLastStateChange] = useState<AgentStateChange | null>(null);
  const [documents, setDocuments] = useState<DocumentProduced[]>([]);
  const [lastCost, setLastCost] = useState<CostUpdate | null>(null);
  const [errors, setErrors] = useState<ErrorMessage[]>([]);
  const [pendingFeedback, setPendingFeedback] = useState<FeedbackRequired | null>(null);
  const [currentFlowId, setCurrentFlowId] = useState<string | null>(null);

  const [consented, setConsented] = useState<boolean>(() => {
    return localStorage.getItem(PRIVACY_CONSENT_KEY) === "true";
  });

  // Connect WS on mount
  useEffect(() => {
    const c = createSddpClient({
      onMessage: (msg) => {
        switch (msg.type) {
          case "agent_state_change":
            setLastStateChange(msg);
            // Also broadcast to window1 (pet state)
            window.postMessage(
              {
                type: "sddp:pet-update",
                petState: msg.state === "idle" ? "idle" : msg.state === "working" ? "working" : msg.state === "waiting" ? "waiting" : "error",
                bubbleText: msg.detail ?? undefined,
              },
              window.location.origin,
            );
            break;
          case "document_produced":
            setDocuments((prev) => [...prev, msg]);
            break;
          case "cost_update":
            setLastCost(msg);
            break;
          case "feedback_required":
            setPendingFeedback(msg);
            window.postMessage(
              { type: "sddp:pet-update", petState: "waiting", bubbleText: msg.message },
              window.location.origin,
            );
            break;
          case "error":
            setErrors((prev) => [...prev, msg]);
            break;
          default:
            break;
        }
      },
      onConnectionStateChange: setConnState,
    });
    setClient(c);
    c.connect().catch((err) => console.error("WS connect failed:", err));
    return () => c.close();
  }, []);

  const handleStartFlow = useCallback(
    async (proposal: string, projectPath: string) => {
      if (!client) return;
      if (!consented) {
        setErrors((prev) => [
          ...prev,
          {
            type: "error",
            timestamp: new Date().toISOString(),
            error_code: "PRIVACY_CONSENT_REQUIRED",
            message: "用户尚未同意隐私协议；请在设置页接受后再启动流程",
            severity: "warning",
            recoverable: true,
          } as ErrorMessage,
        ]);
        return;
      }
      const req = newStartFlowRequest(proposal, projectPath);
      const resp = await client.sendRpc(req);
      if (resp.type === "flow_started") {
        setCurrentFlowId(resp.flow_id);
        setDocuments([]); // reset for new flow
        setErrors([]);
      }
    },
    [client, consented],
  );

  const handleFeedback = useCallback(
    async (outcome: "y" | "n" | "e") => {
      if (!client || !pendingFeedback || !pendingFeedback.flow_id) return;
      const req = newUserFeedbackRequest(pendingFeedback.flow_id, outcome);
      await client.sendRpc(req);
      setPendingFeedback(null);
    },
    [client, pendingFeedback],
  );

  const handleAbort = useCallback(async () => {
    if (!client || !currentFlowId) return;
    const req = newAbortFlowRequest(currentFlowId);
    await client.sendRpc(req);
    setCurrentFlowId(null);
    setPendingFeedback(null);
  }, [client, currentFlowId]);

  // First-launch: show consent modal
  if (!consented) {
    return (
      <PrivacyConsentModal
        onConsent={() => {
          localStorage.setItem(PRIVACY_CONSENT_KEY, "true");
          setConsented(true);
        }}
        onDecline={() => {
          localStorage.setItem(PRIVACY_CONSENT_KEY, "false");
          // Stay mounted so user can review settings; per D1-10 clarification,
          // declining does NOT exit the app — it just rejects start_flow.
          setConsented(false);
        }}
      />
    );
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 16, fontSize: 14 }}>
      <header style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h1 style={{ fontSize: 18, margin: 0 }}>SDDP-Pet</h1>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 8,
            background: connState === "connected" ? "#dcfce7" : "#fef3c7",
            color: connState === "connected" ? "#166534" : "#92400e",
            fontSize: 12,
          }}
          data-testid="conn-state"
        >
          {connState}
        </span>
      </header>

      <nav style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <TabButton active={tab === "state"} onClick={() => setTab("state")}>状态</TabButton>
        <TabButton active={tab === "diagnostic"} onClick={() => setTab("diagnostic")}>诊断</TabButton>
        <TabButton active={tab === "settings"} onClick={() => setTab("settings")}>设置</TabButton>
      </nav>

      {tab === "state" && (
        <>
          <CostDisplay lastCost={lastCost} />
          <StatePanel
            lastStateChange={lastStateChange}
            documents={documents}
            pendingFeedback={pendingFeedback}
            onStartFlow={handleStartFlow}
            onFeedback={handleFeedback}
            onAbort={handleAbort}
            currentFlowId={currentFlowId}
          />
        </>
      )}

      {tab === "diagnostic" && (
        <DiagnosticPanel lastCost={lastCost} errors={errors} />
      )}

      {tab === "settings" && (
        <SshSettings />
      )}

      {pendingFeedback && tab === "state" && (
        <ConfirmPanel
          feedback={pendingFeedback}
          onY={() => handleFeedback("y")}
          onN={() => handleFeedback("n")}
          onE={() => handleFeedback("e")}
        />
      )}

      {errors.length > 0 && (
        <section data-testid="errors-section" style={{ marginTop: 16, color: "#b91c1c" }}>
          <h3>最近错误</h3>
          <ul>
            {errors.slice(-3).map((e, i) => (
              <li key={i} data-testid="error-item">
                [{e.error_code}] {e.message}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "6px 12px",
        background: active ? "#dbeafe" : "#f3f4f6",
        border: "1px solid #d1d5db",
        borderRadius: 6,
        cursor: "pointer",
        fontWeight: active ? 600 : 400,
      }}
    >
      {children}
    </button>
  );
}

// React 19 root API
const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
