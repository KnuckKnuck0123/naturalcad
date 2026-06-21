import { publicConfig } from "@/lib/config";
import type {
  CreateGuestSessionResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  GenerateProjectRequest,
  ProjectDetailResponse,
  UpdateParametersRequest,
  VersionResponse,
} from "@/lib/api-types";

async function request<TResponse>(
  path: string,
  method: "GET" | "POST" | "PATCH",
  body?: unknown,
  sessionId?: string,
): Promise<TResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (sessionId) {
    headers["x-session-id"] = sessionId;
  }

  // Use the development key for local testing
  headers["x-api-key"] = "naturalcad_dev_4f8c2c91b7a64e2d";

  const response = await fetch(`${publicConfig.apiBaseUrl}/v1${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail?.error || `Request failed: ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as TResponse;
}

export function createGuestSession() {
  return request<CreateGuestSessionResponse>("/auth/guest", "POST", {});
}

export function createProject(input: CreateProjectRequest, sessionId: string) {
  return request<CreateProjectResponse>("/projects", "POST", input, sessionId);
}

export function getProject(projectId: string, sessionId: string) {
  return request<ProjectDetailResponse>(`/projects/${projectId}`, "GET", undefined, sessionId);
}

export function generateVersion(
  projectId: string,
  input: GenerateProjectRequest,
  sessionId: string,
) {
  return request<VersionResponse>(
    `/projects/${projectId}/generate`,
    "POST",
    input,
    sessionId,
  );
}

export function updateParameters(
  projectId: string,
  versionId: string,
  input: UpdateParametersRequest,
  sessionId: string,
) {
  return request<VersionResponse>(
    `/projects/${projectId}/versions/${versionId}/parameters`,
    "PATCH",
    input,
    sessionId,
  );
}

// Higher-level bootstrap for the guest workspace
export async function bootstrapGuestWorkspace() {
  const session = await createGuestSession();
  const project = await createProject(
    {
      title: "Untitled Project",
      mode: "part",
      output_type: "3d_solid",
    },
    session.session_id,
  );

  return {
    session,
    project,
    source: "remote" as const,
  };
}
