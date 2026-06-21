import { useEffect, useRef } from "react";

export function CADViewport({ url }: { url: string | null }) {
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

  if (!url) {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#555", fontFamily: "var(--font-mono)", fontSize: "0.7rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>
        WAITING FOR GEOMETRY KERNEL...
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
        auto-rotate
        shadow-intensity="1.5"
        shadow-softness="0.5"
        exposure="0.75"
        environment-image="neutral"
        camera-orbit="-45deg 60deg auto"
        style={{ width: "100%", height: "100%", backgroundColor: "transparent", outline: "none" }}
      />
    </div>
  );
}
