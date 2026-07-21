/**
 * ConfirmPanel: shows feedback_required payload + y/n/e buttons (D1-8 split).
 *
 * Per specs/desktop-pet-ui/spec.md Requirement: 人类反馈确认点 MUST 由 window2
 * ConfirmPanel 承载: window1 仅显示提示. The pet (window1) shows a short prompt;
 * this panel shows the full payload and the actual buttons.
 *
 * D1-8 verification: same proposal MUST produce same doc set in CLI vs UI.
 * This panel is the only place user feedback is collected in UI mode.
 */
import type { FeedbackRequired } from "../../shared/ws-schemas";

interface Props {
  feedback: FeedbackRequired;
  onY: () => void;
  onN: () => void;
  onE: () => void;
}

const METHOD_LABELS: Record<FeedbackRequired["method"], string> = {
  requirement_confirmation: "需求确认",
  design_confirmation: "方案确认",
  task_confirmation: "任务确认",
};

export function ConfirmPanel({ feedback, onY, onN, onE }: Props) {
  return (
    <section
      data-testid="confirm-panel"
      style={{
        marginTop: 12,
        padding: 12,
        border: "2px solid #facc15",
        borderRadius: 8,
        background: "#fffbeb",
      }}
    >
      <h3 style={{ margin: "0 0 8px", fontSize: 14, color: "#92400e" }}>
        待确认: {METHOD_LABELS[feedback.method]}
      </h3>
      <pre
        data-testid="confirm-payload"
        style={{
          background: "white",
          padding: 8,
          borderRadius: 4,
          maxHeight: 240,
          overflow: "auto",
          fontSize: 12,
          margin: "0 0 8px",
        }}
      >
        {JSON.stringify(feedback.output, null, 2)}
      </pre>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={onY}
          data-testid="confirm-y"
          style={{ padding: "6px 16px", background: "#dcfce7", border: "1px solid #16a34a", cursor: "pointer" }}
        >
          ✓ 同意 (y)
        </button>
        <button
          onClick={onN}
          data-testid="confirm-n"
          style={{ padding: "6px 16px", background: "#fee2e2", border: "1px solid #dc2626", cursor: "pointer" }}
        >
          ✗ 拒绝 (n)
        </button>
        <button
          onClick={onE}
          data-testid="confirm-e"
          style={{ padding: "6px 16px", background: "#f3f4f6", border: "1px solid #6b7280", cursor: "pointer" }}
        >
          ✎ 编辑 (e)
        </button>
      </div>
    </section>
  );
}
