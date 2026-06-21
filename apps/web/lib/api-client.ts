import type { Attachment, GenerationRun, Project, ProjectDetail } from "@/lib/api-types";

const base = "/api/naturalcad";

async function request<T>(path: string, method: "GET" | "POST" | "DELETE", body?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail?.error || error.error || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function createGuestSession() {
  return request<{ actor_type: "guest"; quotas: Record<string, number> }>("/auth/guest", "POST", {});
}

export function createProject() {
  return request<Project>("/projects", "POST", { title: "Untitled Project", mode: "part", output_type: "3d_solid" });
}

export function getProject(projectId: string) {
  return request<ProjectDetail>(`/projects/${projectId}`, "GET");
}

export function startGeneration(projectId: string, message: string, parentVersionId: string | null, attachmentIds: string[]) {
  return request<GenerationRun>(`/projects/${projectId}/generations`, "POST", {
    message, parent_version_id: parentVersionId, attachment_ids: attachmentIds,
    profile: "balanced", idempotency_key: crypto.randomUUID(),
  });
}

export function getGeneration(projectId: string, runId: string) {
  return request<GenerationRun>(`/projects/${projectId}/generations/${runId}`, "GET");
}

export function answerClarification(projectId: string, runId: string, answer: string) {
  return request<GenerationRun>(`/projects/${projectId}/generations/${runId}/clarification`, "POST", { answer });
}

export async function uploadAttachment(projectId: string, file: File): Promise<Attachment> {
  const reserved = await request<Attachment>(`/projects/${projectId}/attachments/init`, "POST", {
    content_type: file.type, size_bytes: file.size,
  });
  if (!reserved.upload_url) throw new Error("Upload reservation did not include a destination");
  const uploaded = await fetch(reserved.upload_url, { method: "PUT", headers: { "content-type": file.type }, body: file });
  if (!uploaded.ok) throw new Error("Image upload failed");
  return request<Attachment>(`/projects/${projectId}/attachments/${reserved.id}/complete`, "POST", {});
}

export function deleteAttachment(projectId: string, attachmentId: string) {
  return request<void>(`/projects/${projectId}/attachments/${attachmentId}`, "DELETE");
}
