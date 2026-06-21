export type SessionKind = "guest" | "user";

export type JobStatus =
  | "submitted"
  | "validated"
  | "queued"
  | "running"
  | "completed"
  | "failed";

export type CadModeType = "part" | "assembly" | "sketch";
export type OutputType = "3d_solid" | "surface" | "2d_vector" | "1d_path";

export type GuestSession = {
  session_id: string;
  actor_type: SessionKind;
  created_at: string;
  quotas: Record<string, number>;
};

export type Project = {
  id: string;
  title: string;
  mode: CadModeType;
  output_type: OutputType;
  owner_session_id: string;
  created_at: string;
  updated_at: string;
};

export type ParameterControl = {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
};

export type Version = {
  id: string;
  project_id: string;
  parent_version_id?: string | null;
  prompt: string;
  profile: string;
  model: string;
  artifacts: Record<string, string>;
  generated_code: string;
  parameters: ParameterControl[];
  status: "completed" | "failed";
  error?: string | null;
  created_at: string;
};

export type CreateGuestSessionResponse = GuestSession;

export type CreateProjectRequest = {
  title: string;
  mode?: CadModeType;
  output_type?: OutputType;
};

export type CreateProjectResponse = Project;

export type GenerateProjectRequest = {
  prompt: string;
  profile?: "fast" | "balanced" | "quality";
  image_urls?: string[];
};

export type VersionResponse = Version;

export type ProjectDetailResponse = {
  project: Project;
  versions: Version[];
};

export type UpdateParametersRequest = {
  updates: Record<string, number>;
};
