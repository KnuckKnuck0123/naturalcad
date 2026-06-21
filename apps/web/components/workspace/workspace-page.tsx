"use client";

import { useEffect, useState, useRef } from "react";
import dynamic from "next/dynamic";

import { publicConfig } from "@/lib/config";
import { Topbar } from "@/components/chrome/topbar";

// Dynamically import the CAD viewport so it doesn't break SSR
const CADViewport = dynamic(
  () => import("./cad-viewport").then(m => m.CADViewport),
  { 
    ssr: false, 
    loading: () => <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#555", fontFamily: "var(--font-mono)", fontSize: "0.7rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>INITIALIZING WEBG...</div> 
  }
);
import { bootstrapGuestWorkspace, generateVersion, getProject } from "@/lib/api-client";
import type { JobStatus, Version } from "@/lib/api-types";
import { exportFormats } from "@/lib/product-copy";

type ConversationEntry = {
  role: "You" | "NaturalCAD";
  text: string;
};

type VersionEntry = {
  id: string;
  label: string;
  state: "completed" | "failed";
  artifacts?: Record<string, string>;
};

const snapshotStorageKey = "naturalcad.guest-workspace.v1";
const initialConversation: ConversationEntry[] = [
  {
    role: "NaturalCAD",
    text: "Describe the part you want to make. Then keep prompting until the geometry looks right.",
  },
];

export function WorkspacePage() {
  const [prompt, setPrompt] = useState(
    "Design a wall-mounted tool bracket with a reinforced back plate, a tapered arm, and a cable relief notch.",
  );
  const [bootStatus, setBootStatus] = useState<
    "booting" | "ready" | "failed"
  >("booting");
  const [workspaceSource, setWorkspaceSource] = useState<
    "remote" | "local-fallback" | null
  >(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [requestSource, setRequestSource] = useState<"remote" | "local-fallback" | null>(
    null,
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [conversation, setConversation] =
    useState<ConversationEntry[]>(initialConversation);
  const [generateStatus, setGenerateStatus] = useState<"completed" | "failed" | "submitted" | "idle">(
    "idle",
  );
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Recovery and Initialization
  useEffect(() => {
    if (!isClient) return;
    let cancelled = false;

    async function initialize() {
      console.log("[BOOT] Starting sequence...");
      if (typeof publicConfig !== "undefined") {
        console.log("[BOOT] API Target:", publicConfig.apiBaseUrl);
      }
      
      // 1. Try recovery
      const raw = window.localStorage.getItem(snapshotStorageKey);
      if (raw) {
        try {
          const snapshot = JSON.parse(raw);
          console.log("[BOOT] Found local snapshot:", snapshot.sessionId);
          if (cancelled) return;

          setSessionId(snapshot.sessionId);
          setProjectId(snapshot.projectId);
          setWorkspaceSource(snapshot.workspaceSource);
          setRequestSource(snapshot.requestSource);
          setJobId(snapshot.jobId);
          setVersionId(snapshot.versionId);
          setConversation(snapshot.conversation || initialConversation);
          setGenerateStatus(snapshot.generateStatus || "idle");
          setVersions(snapshot.versions || []);
          
          // Verify session is still valid on backend
          try {
            console.log("[BOOT] Verifying session on backend...");
            if (snapshot.projectId && snapshot.sessionId) {
              await getProject(snapshot.projectId, snapshot.sessionId);
              console.log("[BOOT] Session verified.");
            }
            setBootStatus("ready");
            return;
          } catch (e) {
            console.warn("[BOOT] Session verification failed, starting fresh:", e);
          }
        } catch (e) {
          console.error("[BOOT] Recovery failed:", e);
          window.localStorage.removeItem(snapshotStorageKey);
        }
      }

      // 2. Fresh bootstrap
      try {
        console.log("[BOOT] Fetching fresh session...");
        const result = await bootstrapGuestWorkspace();
        console.log("[BOOT] Bootstrap success:", result.session.session_id);
        if (cancelled) return;

        setSessionId(result.session.session_id);
        setProjectId(result.project.id);
        setWorkspaceSource(result.source);
        setBootStatus("ready");
      } catch (err) {
        console.error("[BOOT] Bootstrap error:", err);
        if (cancelled) return;
        setBootStatus("failed");
        setLastError(err instanceof Error ? err.message : "Initialization failed.");
      }
    }

    void initialize();

    // Emergency timeout (15s)
    const timeout = setTimeout(() => {
      setBootStatus((currentStatus) => {
        if (currentStatus === "booting") {
          console.warn("[BOOT] Timeout reached.");
          setLastError("CONNECTION_TIMEOUT: Backend not responding at " + (typeof publicConfig !== 'undefined' ? publicConfig.apiBaseUrl : 'UNKNOWN_URL'));
          return "failed";
        }
        return currentStatus;
      });
    }, 15000);

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [isClient]);

  // Persistence
  useEffect(() => {
    if (bootStatus !== "ready") return;

    const snapshot = {
      sessionId,
      projectId,
      workspaceSource,
      requestSource,
      jobId,
      versionId,
      conversation,
      generateStatus,
      versions,
    };

    window.localStorage.setItem(snapshotStorageKey, JSON.stringify(snapshot));
  }, [
    bootStatus,
    conversation,
    generateStatus,
    jobId,
    projectId,
    requestSource,
    sessionId,
    versionId,
    versions,
    workspaceSource,
  ]);

  async function handleReset() {
    if (isGenerating) return;
    if (!confirm("Are you sure you want to start a new project? Current history will be cleared.")) return;
    
    setBootStatus("booting");
    setLastError(null);
    window.localStorage.removeItem(snapshotStorageKey);
    window.location.reload();
  }

  async function handleGenerate() {
    if (!projectId || !sessionId || !prompt.trim() || isGenerating) {
      return;
    }

    setIsGenerating(true);
    setLastError(null);
    setGenerateStatus("submitted");

    try {
      const result = await generateVersion(
        projectId,
        {
          prompt: prompt.trim(),
          profile: "balanced",
        },
        sessionId,
      );

      setConversation((current) => [
        ...current,
        { role: "You", text: prompt.trim() },
        {
          role: "NaturalCAD",
          text:
            result.status === "completed"
              ? "VERSION QUEUED. ANALYZING GEOMETRY CONSTRAINTS."
              : `GENERATION FAILED: ${result.error || "UNKNOWN ERROR"}`,
        },
      ]);
      setVersionId(result.id);
      setGenerateStatus(result.status);
      setVersions((current) => [
        {
          id: result.id,
          label: prompt.trim(),
          state: result.status,
          artifacts: result.artifacts,
        },
        ...current.filter((v) => v.id !== result.id),
      ]);
      setPrompt("");
    } catch (error) {
      setGenerateStatus("failed");
      const message = error instanceof Error ? error.message : "GENERATION FAILED.";
      setLastError(message);
    } finally {
      setIsGenerating(false);
    }
  }

  const currentVersion = versions.find(v => v.id === versionId);
  const currentArtifacts = currentVersion?.artifacts || {};

  return (
    <main className="shell shell--workspace">
      <div className="screen-frame">
          <Topbar
            brand="NATURALCAD / GUEST"
            status={
              !isClient
                ? "SYNC_PENDING"
                : bootStatus === "ready"
                  ? "LINK_ESTABLISHED"
                  : bootStatus === "failed"
                    ? "LINK_OFFLINE"
                    : "HANDSHAKE_INIT"
            }
          />

          <div style={{ padding: '4px 40px', background: '#050505', borderBottom: '1px solid #111', display: 'flex', justifyContent: 'flex-end' }}>
            <button 
              onClick={handleReset}
              disabled={bootStatus !== "ready" || isGenerating}
              style={{ background: 'transparent', border: 'none', color: '#444', fontSize: '0.55rem', textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '0.15em' }}
            >
              [ NEW_PROJECT ]
            </button>
          </div>

        {bootStatus === "failed" && (
          <div style={{ padding: '4px 40px', background: '#100', borderBottom: '1px solid #1a0000', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ color: '#600', fontSize: '0.55rem', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              [SYSTEM_LINK_FAILURE]: {lastError || "REMOTE_TIMEOUT"}
            </span>
            <button 
              onClick={() => { window.localStorage.removeItem(snapshotStorageKey); window.location.reload(); }}
              style={{ background: 'transparent', border: 'none', color: '#444', fontSize: '0.55rem', textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '0.1em' }}
            >
              / REBOOT_CORE
            </button>
          </div>
        )}

        <section className="workspace-grid">
          {/* CONTROL PANEL */}
          <section className="panel">
            <div className="panel-heading">
              <p className="section-tag">INPUT_BUS_01</p>
              <h2>Command Console</h2>
              <p className="workspace-subtitle">
                INPUT PARAMETRIC COMMANDS TO OPERATE THE GEOMETRY KERNEL.
              </p>
            </div>

            <div className="workspace-meta-strip">
                <div>
                  <span className="workspace-meta-strip__label">SESSION:</span>
                  <strong>{bootStatus !== "ready" ? "OFFLINE" : (sessionId ? sessionId.slice(0, 8) : "---")}</strong>
                </div>
                <div>
                  <span className="workspace-meta-strip__label">KERNEL:</span>
                  <strong>{bootStatus !== "ready" ? "BUSY" : (versionId ? generateStatus : "IDLE")}</strong>
                </div>
                <div>
                  <span className="workspace-meta-strip__label">PROJECT:</span>
                  <strong>{bootStatus !== "ready" ? "OFFLINE" : (projectId ? projectId.slice(0, 8) : "---")}</strong>
                </div>
            </div>

            <div className="conversation-log">
              {conversation.map((entry, index) => (
                <div
                  key={`${entry.role}-${index}`}
                  className={
                    entry.role === "NaturalCAD"
                      ? "conversation-entry conversation-entry--assistant"
                      : "conversation-entry"
                  }
                >
                  <span className="conversation-entry__role">
                    {entry.role === "NaturalCAD" ? "NaturalCAD" : "You"}
                  </span>
                  <p>{entry.text}</p>
                </div>
              ))}
            </div>

            <div className="composer-shell">
              <label className="field-label">Command Entry</label>
              <textarea
                className="prompt-box"
                value={prompt}
                placeholder="INPUT PARAMETRIC COMMAND..."
                disabled={isGenerating}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void handleGenerate();
                  }
                }}
              />

              <div className="action-row">
                <button
                  className="button button--primary"
                  type="button"
                  onClick={handleGenerate}
                  disabled={bootStatus !== "ready" || isGenerating}
                >
                  {isGenerating ? "EXECUTING..." : "EXECUTE"}
                </button>
              </div>
            </div>

            {lastError && (
              <div className="workspace-note workspace-note--danger">
                [ERR_KERNEL_CRASH]: {lastError}
              </div>
            )}
          </section>

          {/* VIEWPORT PANEL */}
          <section className="panel workspace-sidebar">
            <div className="panel-heading">
              <p className="section-tag">DISPLAY_PORT_01</p>
              <h2>Orthographic Viewport</h2>
            </div>

            <div className="viewer-shell">
              <div className="viewer-grid" />
              <div className="viewer-crosshair" style={{ inset: '0 0 0 50%', width: '1px', background: 'rgba(255, 255, 255, 0.1)' }} />
              <div className="viewer-crosshair" style={{ inset: '50% 0 0 0', height: '1px', background: 'rgba(255, 255, 255, 0.1)' }} />
              <div className="viewer-reticle" style={{ position: 'absolute', top: '50%', left: '50%', width: '40px', height: '40px', border: '1px solid rgba(255,255,255,0.2)', transform: 'translate(-50%, -50%)', borderRadius: '50%', pointerEvents: 'none', zIndex: 10 }} />
              
              <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
                <CADViewport url={currentArtifacts["glb"] || null} />
              </div>

              <div className="viewer-overlay" style={{ zIndex: 20 }}>
                <span>VER: {versionId ?? "N/A"}</span>
                <span>STATE: {generateStatus}</span>
              </div>
            </div>

            <section className="history-panel">
              <div className="panel-heading" style={{ borderTop: '1px solid #333' }}>
                <p className="section-tag">LOG_HISTORY</p>
                <h2>Version Stack</h2>
              </div>

              <div className="version-list">
                {versions.map((v) => (
                  <div key={v.id} className="version-row">
                    <div>
                      <strong>{v.id.slice(0, 8)}</strong>
                      <p>{v.label}</p>
                    </div>
                    <span className={`pill pill--${v.state}`}>{v.state}</span>
                  </div>
                ))}
                {versions.length === 0 && (
                  <div style={{ padding: '16px', fontSize: '0.7rem', color: '#555' }}>
                    NO DATA IN STACK
                  </div>
                )}
              </div>

              <div className="export-row">
                {exportFormats.map((f) => {
                  const formatKey = f === "Preview GLB" ? "glb" : f.toLowerCase();
                  const downloadUrl = currentArtifacts[formatKey];
                  
                  return (
                    <button
                      key={f}
                      className="button button--ghost"
                      type="button"
                      disabled={!versionId || !downloadUrl}
                      onClick={() => {
                        if (downloadUrl) {
                          window.open(downloadUrl, "_blank");
                        }
                      }}
                    >
                      {f}
                    </button>
                  );
                })}
              </div>
            </section>
          </section>
        </section>
      </div>
    </main>
  );
}
