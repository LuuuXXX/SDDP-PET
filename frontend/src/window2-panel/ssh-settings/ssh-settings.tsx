/**
 * SshSettings: SSH tunnel configuration form (D1-16).
 *
 * Per specs/remote-mode/spec.md: user fills host/port/username + key_ref;
 * the actual key is stored in OS credential manager (frontend/electron/secrets.ts).
 *
 * On "Test Connection", the form calls a bridge function (TODO task 4.x) that
 * spawns `ssh -L 8765:localhost:8765 ...`. For DP1 task 5.5 we only render
 * the form; the SSH spawning is wired in task 4.x (frontend/electron/ssh-tunnel.ts).
 */
import { useState } from "react";

interface Props {
  onTestConnection?: (cfg: SshConfig) => Promise<{ ok: boolean; error?: string }>;
}

export interface SshConfig {
  host: string;
  port: number;
  username: string;
  keyRef: string; // alias for a key stored in OS credential manager
}

export function SshSettings({ onTestConnection }: Props) {
  const [cfg, setCfg] = useState<SshConfig>({
    host: "",
    port: 22,
    username: "",
    keyRef: "ssh_default",
  });
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    if (!onTestConnection) {
      setStatus({ ok: false, message: "SSH bridge not wired yet (task 4.x)" });
      return;
    }
    setTesting(true);
    try {
      const r = await onTestConnection(cfg);
      setStatus({
        ok: r.ok,
        message: r.ok ? "连接成功" : `连接失败: ${r.error ?? "unknown"}`,
      });
    } catch (e) {
      setStatus({ ok: false, message: `错误: ${(e as Error).message}` });
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
            {status.message}
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
