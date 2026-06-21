export const landingFeatures = [
  "Prompt-driven geometry creation with a real workspace behind it",
  "Versioned iteration instead of one-shot dead ends",
  "Export-ready STEP, STL, and preview artifacts when the model is ready",
];

export const landingLanes = [
  {
    label: "Prompt",
    value: "Describe the object, system, or assembly.",
  },
  {
    label: "Generate",
    value: "Create the first model and preview the result.",
  },
  {
    label: "Iterate",
    value: "Refine through versions without losing history.",
  },
  {
    label: "Export",
    value: "Ship files downstream when the geometry is ready.",
  },
];

export const stackCards = [
  {
    label: "Frontend",
    value: "Next.js + TypeScript",
  },
  {
    label: "Hosting",
    value: "Vercel + Cloudflare",
  },
  {
    label: "Execution",
    value: "Modal Worker Path",
  },
  {
    label: "Data",
    value: "Supabase Sessions + Versions",
  },
];

export const versionFixtures = [
  {
    id: "V-003",
    label: "Bracket with filleted armature and wider base",
    state: "ready",
  },
  {
    id: "V-002",
    label: "Reduced wall thickness and cleaner underside clearance",
    state: "queued",
  },
  {
    id: "V-001",
    label: "Initial prompt generation",
    state: "exported",
  },
] as const;

export const exportFormats = ["STEP", "STL", "Preview GLB"] as const;

export const workspaceThread = [
  {
    role: "USER",
    text: "Make the back plate taller and soften the arm transition.",
  },
  {
    role: "SYSTEM",
    text: "Updated version queued with wider anchor spacing and a filleted junction for print durability.",
  },
] as const;
