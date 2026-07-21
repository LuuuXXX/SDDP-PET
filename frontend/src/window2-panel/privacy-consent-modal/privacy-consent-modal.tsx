/**
 * PrivacyConsentModal: first-launch consent (D1-10).
 *
 * Per specs/desktop-pet-ui/spec.md Requirement: 首次启动 MUST 弹出隐私同意 modal.
 *
 * D1-10 clarification (per analysis/07 §八): "拒绝" only rejects start_flow
 * RPC — the app MUST continue running so the user can open settings/review
 * history/switch consent later.
 */
interface Props {
  onConsent: () => void;
  onDecline: () => void;
}

export function PrivacyConsentModal({ onConsent, onDecline }: Props) {
  return (
    <div
      data-testid="privacy-consent-modal"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "white",
          padding: 24,
          borderRadius: 8,
          maxWidth: 480,
          boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 18 }}>隐私同意</h2>
        <p style={{ fontSize: 14, lineHeight: 1.6 }}>
          SDDP-Pet 将把您的 <strong>proposal 文本 + 项目代码片段</strong> 发送到
          您配置的远程 LLM provider（如 OpenAI / DeepSeek）以完成 SDDP 流程。
        </p>
        <p style={{ fontSize: 14, lineHeight: 1.6 }}>
          本工具内置 <strong>代码预过滤</strong>（正则脱敏），会尽量替换疑似密钥/PII
          为占位符，但<strong>非密码学级脱敏</strong>。请勿发送高敏感代码到任何 LLM。
        </p>
        <p style={{ fontSize: 12, color: "#6b7280" }}>
          拒绝后应用继续运行，但 <code>start_flow</code> 会被拒绝；可随时在设置页更改。
        </p>

        <div style={{ marginTop: 20, display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            onClick={onDecline}
            data-testid="privacy-decline"
            style={{
              padding: "8px 16px",
              background: "#f3f4f6",
              border: "1px solid #6b7280",
              cursor: "pointer",
              borderRadius: 4,
            }}
          >
            拒绝
          </button>
          <button
            onClick={onConsent}
            data-testid="privacy-consent"
            autoFocus
            style={{
              padding: "8px 16px",
              background: "#2563eb",
              color: "white",
              border: "1px solid #1d4ed8",
              cursor: "pointer",
              borderRadius: 4,
              fontWeight: 600,
            }}
          >
            同意
          </button>
        </div>
      </div>
    </div>
  );
}
