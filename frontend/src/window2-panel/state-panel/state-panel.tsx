/**
 * StatePanel: shows live agent_state_change + document list + flow controls.
 *
 * Per D1-2: state panel is one of the 6 mandatory window2 panels.
 */
import { useState } from "react";
import type { AgentStateChange, DocumentProduced, FeedbackRequired } from "../../shared/ws-schemas";

interface Props {
  lastStateChange: AgentStateChange | null;
  documents: DocumentProduced[];
  pendingFeedback: FeedbackRequired | null;
  currentFlowId: string | null;
  onStartFlow: (proposal: string, projectPath: string) => Promise<void>;
  onFeedback: (outcome: "y" | "n" | "e") => Promise<void>;
  onAbort: () => Promise<void>;
}

export function StatePanel({
  lastStateChange,
  documents,
  pendingFeedback: _pendingFeedback,
  currentFlowId,
  onStartFlow,
  onAbort,
}: Props) {
  const [proposal, setProposal] = useState("");
  const [projectPath, setProjectPath] = useState(".");

  return (
    <section data-testid="state-panel" style={{ marginBottom: 16 }}>
      <h2 style={{ fontSize: 16, margin: "0 0 8px" }}>流程状态</h2>

      {!currentFlowId ? (
        <div data-testid="start-flow-form" style={{ marginBottom: 12 }}>
          <textarea
            value={proposal}
            onChange={(e) => setProposal(e.target.value)}
            placeholder="输入 proposal 文本…"
            data-testid="proposal-input"
            style={{ width: "100%", minHeight: 80, padding: 6, boxSizing: "border-box" }}
          />
          <input
            type="text"
            value={projectPath}
            onChange={(e) => setProjectPath(e.target.value)}
            placeholder="项目路径"
            data-testid="project-path-input"
            style={{ width: "100%", padding: 6, margin: "4px 0", boxSizing: "border-box" }}
          />
          <button
            onClick={() => onStartFlow(proposal, projectPath)}
            disabled={!proposal.trim()}
            data-testid="start-flow-button"
            style={{ padding: "6px 16px" }}
          >
            启动流程
          </button>
        </div>
      ) : (
        <div data-testid="active-flow">
          <div>Flow ID: <code>{currentFlowId}</code></div>
          {lastStateChange && (
            <div data-testid="agent-state">
              {lastStateChange.agent} → <strong>{lastStateChange.state}</strong>
              {lastStateChange.detail ? ` (${lastStateChange.detail})` : ""}
            </div>
          )}
          <button
            onClick={onAbort}
            data-testid="abort-button"
            style={{ padding: "4px 12px", color: "#b91c1c" }}
          >
            中止
          </button>
        </div>
      )}

      <h3 style={{ fontSize: 14, margin: "12px 0 4px" }}>产出文档</h3>
      {documents.length === 0 ? (
        <div style={{ color: "#6b7280", fontSize: 13 }}>（暂无）</div>
      ) : (
        <ul data-testid="documents-list" style={{ margin: 0, paddingLeft: 20 }}>
          {documents.map((d, i) => (
            <li key={i} data-testid={`document-${d.doc_type}`}>
              <strong>{d.doc_type}</strong>: {d.summary || d.doc_id}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
