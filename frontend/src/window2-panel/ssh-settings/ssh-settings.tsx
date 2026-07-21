/**
 * SshSettings: SSH tunnel configuration form (D1-16).
 *
 * Per specs/remote-mode/spec.md: user fills host/port/username + key_ref;
 * the actual key is stored in OS credential manager (frontend/electron/secrets.ts).
 *
 * On "Test Connection", the form calls the main process via the `sddp.testSsh`
 * IPC bridge (registered in windows.ts). The main process:
 *   1. Fetches the PEM key via secrets.getApiKey(keyRef)
 *   2. Writes it to a 0600 temp file
 *   3. Spawns `ssh -L 8765:localhost:8765 -i <keyfile> <user>@<host>`
 *   4. Classifies stderr errors into 4 kinds (auth/network/port/unknown)
 *
 * For D1-16 manual verification: configure a real SSH server, fill the form,
 * click "Test Connection" → should show ✓ 连接成功.
 */
import { useState } from "react";

export interface SshConfig {
  host: string;
  port: number;
  username: string;
  /**
   * Reference to a key stored in OS credential manager via the secrets API.
   * The actual key material never touches localStorage or any file on disk
   * outside of the temp file used transiently by ssh -i.
   */
  keyRef: string;
}

interface TestResult {
  ok: boolean;
  /** One of: "auth_failed" | "network_unreachable" | "port_in_use" | "unknown" */
  errorKind?: string;
  message: string;
}

const ERROR_KIND_LABELS: Record<string, string> = {
  auth_failed: "认证失败",
  network_unreachable: "网络不可达",
  port_in_use: "端口被占用",
  unknown: "未知错误",
};

// IPC bridge contract is declared in src/shared/global.d.ts (single source of truth)

interface Props {
  /**
   * Optional in-process handler (used by unit tests). If omitted, the form
   * calls `window.sddp.testSsh()` (the production IPC bridge).
   */
  onTestConnection?: (cfg: SshConfig) => Promise<TestResult>;
}

export function SshSettings({ onTestConnection }: Props) {
  const [cfg, setCfg] = useState<SshConfig>({
    host: "",
    port: 22,
    username: "",
    keyRef: "ssh_default",
  });
  const [status, setStatus] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    const handler = onTestConnection ?? window.sddp?.testSsh;
    if (!handler) {
      setStatus({ ok: false, errorKind: "unknown", message: "SSH bridge 未就绪" });
      return;
    }
    setTesting(true);
    try {
      const r = await handler(cfg);
      setStatus(r);
    } catch (e) {
      setStatus({ ok: false, errorKind: "unknown", message: `异常: ${(e as Error).message}` });
    } finally {
      setTesting(false);
    }
  };

  return (
    <section data-testid="ssh-settings" style={{ fontSize: 13 }}>
      <h2 style={{ fontSize: 16, margin: "0 0 12px" }}>SSH 远程模式设置 (D1-16)</h2>
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        配置后，引擎可在远程 Linux 服务器运行，桌宠 UI 留在本地。SSH 隧道对前端透明（仍连 localhost:8765）。
      </p>

      <div style={{ display: "grid", gap: 8, maxWidth: 480 }}>
        <Field label="Host">
          <input
            type="text"
            value={cfg.host}
            onChange={(e) => setCfg({ ...cfg, host: e.target.value })}
            placeholder="example.com"
            data-testid="ssh-host"
            style={inputStyle}
          />
        </Field>
        <Field label="Port">
          <input
            type="number"
            value={cfg.port}
            onChange={(e) => setCfg({ ...cfg, port: Number(e.target.value) })}
            data-testid="ssh-port"
            style={inputStyle}
          />
        </Field>
        <Field label="Username">
          <input
            type="text"
            value={cfg.username}
            onChange={(e) => setCfg({ ...cfg, username: e.target.value })}
            placeholder="ubuntu"
            data-testid="ssh-username"
            style={inputStyle}
          />
        </Field>
        <Field label="Key Reference (alias for key stored in OS keyring)">
          <input
            type="text"
            value={cfg.keyRef}
            onChange={(e) => setCfg({ ...cfg, keyRef: e.target.value })}
            data-testid="ssh-key-ref"
            style={inputStyle}
          />
        </Field>
      </div>

      <div style={{ marginTop: 12 }}>
        <button
          onClick={handleTest}
          disabled={testing || !cfg.host || !cfg.username}
          data-testid="ssh-test-button"
          style={{ padding: "6px 16px" }}
        >
          {testing ? "测试中…" : "测试连接"}
        </button>
        {status && (
          <span
            data-testid="ssh-test-status"
            style={{
              marginLeft: 12,
              color: status.ok ? "#166534" : "#b91c1c",
            }}
          >
            {status.ok
              ? "✓ 连接成功"
              : `✗ ${ERROR_KIND_LABELS[status.errorKind ?? "unknown"] ?? status.errorKind}: ${status.message}`}
          </span>
        )}
      </div>
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  padding: 6,
  border: "1px solid #d1d5db",
  borderRadius: 4,
  fontSize: 13,
  width: "100%",
  boxSizing: "border-box",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block" }}>
      <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 2 }}>{label}</div>
      {children}
    </label>
  );
}
