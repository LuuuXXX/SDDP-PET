/**
 * DiagnosticPanel: shows 4 metrics (D1-14/D1-15) + recent errors.
 *
 * Per specs/observability/spec.md: 4 metrics — flow_time_seconds /
 * agent_latency_seconds / token_consumption_rate / error_rate. In DP1 these
 * are derived from cost_update messages + an in-memory rolling window of
 * recent errors. A future task (6.x) will read historical metrics from
 * `~/.sddp-pet/metrics.json` for the long-term average.
 */
import type { CostUpdate, ErrorMessage } from "../../shared/ws-schemas";

interface Props {
  lastCost: CostUpdate | null;
  errors: ErrorMessage[];
}

interface MetricCard {
  label: string;
  value: string;
  alert?: boolean;
}

export function DiagnosticPanel({ lastCost, errors }: Props) {
  const recentErrors = errors.slice(-100);
  const errorRate = errors.length === 0 ? 0 : recentErrors.filter((e) => e.severity === "critical" || e.severity === "error").length / Math.max(recentErrors.length, 1);

  const cards: MetricCard[] = [
    {
      label: "总 token 数",
      value: lastCost ? String(lastCost.total_tokens) : "—",
    },
    {
      label: "估算成本 (USD)",
      value: lastCost ? `$${lastCost.estimated_cost_usd.toFixed(4)}` : "—",
    },
    {
      label: "错误率",
      value: `${(errorRate * 100).toFixed(1)}%`,
      alert: errorRate > 0.1, // D1-15 scenario: error_rate > 0.1 → red
    },
    {
      label: "历史 flow 数",
      value: String(recentErrors.length || 0),
    },
  ];

  return (
    <section data-testid="diagnostic-panel">
      <h2 style={{ fontSize: 16, margin: "0 0 12px" }}>诊断指标 (D1-15)</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {cards.map((c) => (
          <div
            key={c.label}
            data-testid={`metric-card-${c.label}`}
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: 10,
              background: c.alert ? "#fee2e2" : "#f9fafb",
            }}
          >
            <div style={{ fontSize: 11, color: "#6b7280" }}>{c.label}</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: c.alert ? "#b91c1c" : "#111827" }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
