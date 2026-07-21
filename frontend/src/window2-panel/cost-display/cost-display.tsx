/**
 * CostDisplay: shows total_tokens + estimated_cost_usd (D1-2 panel component).
 *
 * Compact card at the top of the state panel.
 */
import type { CostUpdate } from "../../shared/ws-schemas";

interface Props {
  lastCost: CostUpdate | null;
}

export function CostDisplay({ lastCost }: Props) {
  return (
    <div
      data-testid="cost-display"
      style={{
        marginBottom: 12,
        padding: 8,
        background: "#f0f9ff",
        border: "1px solid #bae6fd",
        borderRadius: 6,
        display: "flex",
        justifyContent: "space-between",
        fontSize: 13,
      }}
    >
      <div>
        <span style={{ color: "#6b7280" }}>tokens:</span>{" "}
        <strong data-testid="total-tokens">
          {lastCost ? lastCost.total_tokens.toLocaleString() : "—"}
        </strong>
      </div>
      <div>
        <span style={{ color: "#6b7280" }}>cost:</span>{" "}
        <strong data-testid="estimated-cost">
          {lastCost ? `$${lastCost.estimated_cost_usd.toFixed(4)}` : "—"}
        </strong>
      </div>
    </div>
  );
}
