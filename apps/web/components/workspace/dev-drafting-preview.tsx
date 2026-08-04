"use client";

import { useState } from "react";

import { DraftingViewport2D } from "@/components/workspace/drafting-viewport-2d";
import { PLATE_SCENE, SLOT_SCENE } from "@/lib/drawing-scene.fixtures";
import { ENRICHED_RECT_SCENE } from "@/lib/drawing-scene-enriched-fixture";

const SCENES = [
  { id: "plate", label: "Plate (fixture)", payload: PLATE_SCENE as Record<string, unknown> },
  { id: "slot", label: "Slot (fixture)", payload: SLOT_SCENE as Record<string, unknown> },
  { id: "enriched", label: "Auto-enriched rect", payload: ENRICHED_RECT_SCENE as Record<string, unknown> },
] as const;

export function DevDraftingPreview() {
  const [active, setActive] = useState<(typeof SCENES)[number]["id"]>("plate");
  const [resetToken, setResetToken] = useState(0);
  const current = SCENES.find((option) => option.id === active) ?? SCENES[0];

  return (
    <main className="shell shell--legal">
      <div className="legal-content">
        <h1>Drafting Viewport 2D — dev preview</h1>
        <p className="legal-date">
          Fixture-backed preview of <code>DraftingViewport2D</code>. Scroll to zoom, drag to pan.
          Not wired to live generation. Dev-only — 404s in production.
        </p>

        <div style={{ display: "flex", gap: "0.5rem", margin: "1rem 0" }}>
          {SCENES.map((option) => (
            <button
              key={option.id}
              type="button"
              className={option.id === active ? "viewer-tool viewer-tool--selected" : "viewer-tool"}
              onClick={() => setActive(option.id)}
            >
              {option.label}
            </button>
          ))}
          <button type="button" className="viewer-tool" onClick={() => setResetToken((v) => v + 1)}>Refit</button>
        </div>

        <div className="viewer-shell" style={{ height: 540 }}>
          <DraftingViewport2D scene={current.payload} resetToken={resetToken} />
        </div>
      </div>
    </main>
  );
}