/**
 * zod schemas mirroring backend `sddp/ipc/schemas.py` (Dev-Phase 1 D1-4/D1-5/D1-6).
 *
 * Per analysis/08 §三 contract — every message MUST validate against its zod
 * schema; mismatches surface as a typed Error to the caller (does NOT crash
 * the WS connection; backend pushes `error` Push for malformed JSON).
 *
 * These schemas MUST stay byte-identical to the Pydantic models in backend.
 * A future cross-language contract test (analysis/08 §九 optional D1-17) will
 * pin them.
 */
import { z } from "zod";

// ---- enums (string literal unions) ----

export const ErrorCodeSchema = z.enum([
  "LLM_TIMEOUT",
  "LLM_AUTH_FAIL",
  "LLM_RATE_LIMIT",
  "PARSE_FAILURE",
  "FLOW_STUCK",
  "KNOWLEDGE_GRAPH_ERROR",
  "SSH_CONNECTION_LOST",
  "PRIVACY_CONSENT_REQUIRED",
]);
export type ErrorCode = z.infer<typeof ErrorCodeSchema>;

export const SeveritySchema = z.enum(["critical", "error", "warning"]);
export type Severity = z.infer<typeof SeveritySchema>;

export const AgentStateSchema = z.enum(["working", "idle", "waiting", "error"]);
export type AgentState = z.infer<typeof AgentStateSchema>;

export const DocTypeSchema = z.enum([
  "proposal",
  "delta_spec",
  "delta_design",
  "architecture_research",
  "code_suggestions",
]);
export type DocType = z.infer<typeof DocTypeSchema>;

export const FeedbackMethodSchema = z.enum([
  "requirement_confirmation",
  "design_confirmation",
  "task_confirmation",
]);
export type FeedbackMethod = z.infer<typeof FeedbackMethodSchema>;

export const FlowStatusSchema = z.enum(["running", "resuming", "aborted", "completed"]);
export type FlowStatus = z.infer<typeof FlowStatusSchema>;

export const FeedbackOutcomeSchema = z.enum(["y", "n", "e"]);
export type FeedbackOutcome = z.infer<typeof FeedbackOutcomeSchema>;

// ---- base shape ----

const BaseFields = {
  type: z.string(),
  timestamp: z.string(),
  flow_id: z.string().nullable().optional(),
};

// ---- 5 Push messages (engine → frontend) ----

export const AgentStateChangeSchema = z.object({
  ...BaseFields,
  type: z.literal("agent_state_change"),
  agent: z.string(),
  state: AgentStateSchema,
  phase: z.string().nullable().optional(),
  round: z.number().nullable().optional(),
  role: z.string().nullable().optional(), // DP2 additive (architect/critic/empiricist/orchestrator)
  detail: z.string().nullable().optional(),
});
export type AgentStateChange = z.infer<typeof AgentStateChangeSchema>;

export const DocumentProducedSchema = z.object({
  ...BaseFields,
  type: z.literal("document_produced"),
  agent: z.string(),
  doc_type: DocTypeSchema,
  doc_id: z.string(),
  summary: z.string().default(""),
});
export type DocumentProduced = z.infer<typeof DocumentProducedSchema>;

export const CostUpdateSchema = z.object({
  ...BaseFields,
  type: z.literal("cost_update"),
  total_tokens: z.number(),
  estimated_cost_usd: z.number(),
  round_tokens: z.record(z.string(), z.number()).default({}),
});
export type CostUpdate = z.infer<typeof CostUpdateSchema>;

export const FeedbackRequiredSchema = z.object({
  ...BaseFields,
  type: z.literal("feedback_required"),
  method: FeedbackMethodSchema,
  message: z.string(),
  output: z.record(z.string(), z.unknown()),
});
export type FeedbackRequired = z.infer<typeof FeedbackRequiredSchema>;

export const ErrorMessageSchema = z.object({
  ...BaseFields,
  type: z.literal("error"),
  agent: z.string().nullable().optional(),
  error_code: ErrorCodeSchema,
  message: z.string(),
  severity: SeveritySchema.default("error"),
  recoverable: z.boolean().default(true),
});
export type ErrorMessage = z.infer<typeof ErrorMessageSchema>;

// ---- 4 RPC responses (correlated by message_id) ----

export const FlowStartedSchema = z.object({
  ...BaseFields,
  type: z.literal("flow_started"),
  message_id: z.string(),
  flow_id: z.string(),
  status: z.literal("running"),
});
export type FlowStarted = z.infer<typeof FlowStartedSchema>;

export const FeedbackAcceptedSchema = z.object({
  ...BaseFields,
  type: z.literal("feedback_accepted"),
  message_id: z.string(),
  flow_id: z.string(),
  status: z.literal("resuming"),
});
export type FeedbackAccepted = z.infer<typeof FeedbackAcceptedSchema>;

export const FlowResumedSchema = z.object({
  ...BaseFields,
  type: z.literal("flow_resumed"),
  message_id: z.string(),
  flow_id: z.string(),
  status: z.literal("running"),
});
export type FlowResumed = z.infer<typeof FlowResumedSchema>;

export const FlowAbortedSchema = z.object({
  ...BaseFields,
  type: z.literal("flow_aborted"),
  message_id: z.string(),
  flow_id: z.string(),
  status: z.literal("aborted"),
});
export type FlowAborted = z.infer<typeof FlowAbortedSchema>;

// ---- heartbeat (application-layer, not RFC 6455 — Decision 3) ----

export const PingSchema = z.object({
  ...BaseFields,
  type: z.literal("ping"),
});
export type Ping = z.infer<typeof PingSchema>;

export const PongSchema = z.object({
  ...BaseFields,
  type: z.literal("pong"),
  ping_timestamp: z.string(),
});
export type Pong = z.infer<typeof PongSchema>;

// ---- discriminated union of all messages client may receive ----

export const ServerMessageSchema = z.discriminatedUnion("type", [
  AgentStateChangeSchema,
  DocumentProducedSchema,
  CostUpdateSchema,
  FeedbackRequiredSchema,
  ErrorMessageSchema,
  FlowStartedSchema,
  FeedbackAcceptedSchema,
  FlowResumedSchema,
  FlowAbortedSchema,
  PingSchema,
  PongSchema,
]);
export type ServerMessage = z.infer<typeof ServerMessageSchema>;

// ---- request payloads (what client sends) ----

export interface StartFlowRequest {
  type: "start_flow";
  message_id: string;
  flow_id?: string;
  timestamp: string;
  proposal: string;
  pcm?: unknown;
  project_path: string;
  phase?: "linear" | "confrontation"; // DP2 additive (default 'linear')
}

export interface UserFeedbackRequest {
  type: "user_feedback";
  message_id: string;
  flow_id: string;
  timestamp: string;
  feedback: FeedbackOutcome;
  outcome?: unknown;
}

export interface ResumeFlowRequest {
  type: "resume_flow";
  message_id: string;
  flow_id: string;
  timestamp: string;
  feedback?: FeedbackOutcome;
}

export interface AbortFlowRequest {
  type: "abort_flow";
  message_id: string;
  flow_id: string;
  timestamp: string;
}

export interface PongReply {
  type: "pong";
  timestamp: string;
  ping_timestamp: string;
  flow_id?: string | null;
}

export type ClientMessage =
  | StartFlowRequest
  | UserFeedbackRequest
  | ResumeFlowRequest
  | AbortFlowRequest
  | PongReply;
