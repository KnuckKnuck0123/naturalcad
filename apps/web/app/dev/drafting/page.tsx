import { notFound } from "next/navigation";

import { DevDraftingPreview } from "@/components/workspace/dev-drafting-preview";

export const dynamic = "force-dynamic";

export default function DevDraftingPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <DevDraftingPreview />;
}