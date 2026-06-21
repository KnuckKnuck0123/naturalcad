export type RunStatus = "submitted" | "resolving_spec" | "awaiting_clarification" | "generating_code" | "executing" | "publishing" | "completed" | "failed";
export type AttachmentStatus = "reserved" | "processing" | "ready" | "failed" | "deleted";

export type Project = { id: string; title: string; mode: string; output_type: string; created_at: string; updated_at: string };
export type PartSpec = { spec_version: string; intent: string; mode: string; output_type: string; units: "mm"; semantic_part: Record<string, unknown>; geometry: Record<string, unknown>; dimensions: Record<string, number>; constraints: Record<string, unknown>[]; assumptions: string[]; uncertainties: string[] };
export type Version = { id: string; project_id: string; parent_version_id?: string | null; prompt: string; profile: string; model: string; artifacts: Record<string, string>; spec?: PartSpec | null; spec_delta: Record<string, unknown>[]; change_summary: string; status: "completed" | "failed"; error?: string | null; created_at: string };
export type Message = { id: string; role: "user" | "assistant"; content: string; attachment_ids: string[]; run_id?: string | null; version_id?: string | null; created_at: string };
export type GenerationRun = { id: string; project_id: string; parent_version_id?: string | null; message: string; attachment_ids: string[]; status: RunStatus; clarification_questions: string[]; error?: string | null; version_id?: string | null; change_summary: string; created_at: string; updated_at: string };
export type Attachment = { id: string; project_id: string; status: AttachmentStatus; content_type: string; size_bytes: number; width?: number | null; height?: number | null; upload_url?: string | null; preview_url?: string | null; expires_at: string; created_at: string };
export type ProjectDetail = { project: Project; versions: Version[]; messages: Message[]; runs: GenerationRun[]; attachments: Attachment[] };
