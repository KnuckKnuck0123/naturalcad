import { useEffect, useRef } from "react";

type ViewerTone = "studio" | "light" | "black";

const backgrounds: Record<ViewerTone, string> = {
  studio: "linear-gradient(180deg, #131519 0%, #050505 100%)",
  light: "linear-gradient(180deg, #d7dbe0 0%, #9ea6af 100%)",
  black: "linear-gradient(180deg, #080808 0%, #000000 100%)",
};

const exposures: Record<ViewerTone, string> = {
  studio: "0.85",
  light: "1.15",
  black: "0.65",
};

export function CADViewport({
  url,
  autoRotate,
  tone,
  resetToken,
}: {
  url: string | null;
  autoRotate: boolean;
  tone: ViewerTone;
  resetToken: number;
}) {
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const handleLoad = () => {
      try {
        const material = viewer.model?.materials?.[0];
        if (material) {
          // Tactical Gunmetal Grey
          material.pbrMetallicRoughness.setBaseColorFactor([0.15, 0.16, 0.18, 1.0]);
          material.pbrMetallicRoughness.setMetallicFactor(0.7);
          material.pbrMetallicRoughness.setRoughnessFactor(0.3);
        }
      } catch (e) {
        console.warn("Could not apply tactical material:", e);
      }
    };

    viewer.addEventListener('load', handleLoad);
    return () => viewer.removeEventListener('load', handleLoad);
  }, [url]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.autoRotate = autoRotate;
  }, [autoRotate]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.exposure = exposures[tone];
    viewer.style.background = backgrounds[tone];
  }, [tone]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !url) return;
    if (typeof viewer.jumpCameraToGoal === "function") viewer.jumpCameraToGoal();
    if (typeof viewer.dismissPoster === "function") viewer.dismissPoster();
  }, [resetToken, url]);

  if (!url) {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#555", fontFamily: "var(--font-mono)", fontSize: "0.7rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>
        WAITING FOR PREVIEW GLB...
      </div>
    );
  }

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 10 }}>
      {/* @ts-ignore - model-viewer is a web component */}
      <model-viewer
        ref={viewerRef}
        src={url}
        camera-controls
        shadow-intensity="1.5"
        shadow-softness="0.5"
        exposure={exposures[tone]}
        environment-image="neutral"
        camera-orbit="-45deg 60deg auto"
        style={{ width: "100%", height: "100%", background: backgrounds[tone], outline: "none" }}
      />
    </div>
  );
}
