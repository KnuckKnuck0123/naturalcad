"use client";

import dynamic from "next/dynamic";
import { ChangeEvent, useEffect, useRef, useState } from "react";

import { Topbar } from "@/components/chrome/topbar";
import {
  answerClarification, createGuestSession, createProject, deleteAttachment,
  getGeneration, getProject, startGeneration, uploadAttachment,
} from "@/lib/api-client";
import type { Attachment, GenerationRun, ProjectDetail, Version } from "@/lib/api-types";
import { exportFormats } from "@/lib/product-copy";

const CADViewport = dynamic(() => import("./cad-viewport").then((module) => module.CADViewport), {
  ssr: false,
  loading: () => <div className="viewer-empty">Initializing viewer</div>,
});

const projectStorageKey = "naturalcad.project.v2";
const terminalStatuses = new Set(["completed", "failed", "awaiting_clarification"]);

export function WorkspacePage() {
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<GenerationRun | null>(null);
  const [prompt, setPrompt] = useState("");
  const [selectedAttachmentIds, setSelectedAttachmentIds] = useState<string[]>([]);
  const [bootStatus, setBootStatus] = useState<"booting" | "ready" | "failed">("booting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function refresh(id: string) {
    const next = await getProject(id);
    setDetail(next);
    if (!selectedVersionId && next.versions[0]) setSelectedVersionId(next.versions[0].id);
    return next;
  }

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        let id = window.localStorage.getItem(projectStorageKey);
        if (id) {
          try {
            const existing = await getProject(id);
            if (cancelled) return;
            setDetail(existing);
            setProjectId(id);
            setSelectedVersionId(existing.versions[0]?.id || null);
            const resumable = existing.runs.find((run) => !terminalStatuses.has(run.status));
            if (resumable) setActiveRun(resumable);
            setBootStatus("ready");
            return;
          } catch {
            window.localStorage.removeItem(projectStorageKey);
          }
        }
        await createGuestSession();
        const project = await createProject();
        id = project.id;
        window.localStorage.setItem(projectStorageKey, id);
        if (cancelled) return;
        setProjectId(id);
        await refresh(id);
        setBootStatus("ready");
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Unable to initialize workspace");
          setBootStatus("failed");
        }
      }
    }
    void bootstrap();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!projectId || !activeRun || terminalStatuses.has(activeRun.status)) return;
    let cancelled = false;
    let delay = 1000;
    async function poll() {
      try {
        const run = await getGeneration(projectId!, activeRun!.id);
        if (cancelled) return;
        setActiveRun(run);
        if (terminalStatuses.has(run.status)) {
          const next = await refresh(projectId!);
          if (run.version_id) setSelectedVersionId(run.version_id);
          setBusy(false);
          if (run.status === "failed") setError(run.error || "Generation failed");
          if (run.status === "completed") setSelectedAttachmentIds([]);
          setDetail(next);
          return;
        }
        delay = Math.min(Math.round(delay * 1.5), 5000);
        window.setTimeout(poll, delay);
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Unable to check generation");
          setBusy(false);
        }
      }
    }
    const timer = window.setTimeout(poll, delay);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeRun?.id, activeRun?.status, projectId]);

  async function submit() {
    if (!projectId || !prompt.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const run = activeRun?.status === "awaiting_clarification"
        ? await answerClarification(projectId, activeRun.id, prompt.trim())
        : await startGeneration(projectId, prompt.trim(), selectedVersionId, selectedAttachmentIds);
      setActiveRun(run);
      setPrompt("");
      await refresh(projectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start generation");
      setBusy(false);
    }
  }

  async function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    if (!projectId || !event.target.files?.length) return;
    const available = Math.max(0, 3 - (detail?.attachments.filter((item) => item.status !== "deleted").length || 0));
    const files = Array.from(event.target.files).slice(0, available);
    setBusy(true);
    setError(null);
    try {
      const uploaded: Attachment[] = [];
      for (const file of files) uploaded.push(await uploadAttachment(projectId, file));
      setSelectedAttachmentIds((current) => [...current, ...uploaded.map((item) => item.id)]);
      await refresh(projectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Image upload failed");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function removeAttachment(attachmentId: string) {
    if (!projectId || busy) return;
    setBusy(true);
    try {
      await deleteAttachment(projectId, attachmentId);
      setSelectedAttachmentIds((current) => current.filter((id) => id !== attachmentId));
      await refresh(projectId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to remove image");
    } finally {
      setBusy(false);
    }
  }

  function resetProject() {
    if (busy || !window.confirm("Start a new project? Current project history will remain on the server.")) return;
    window.localStorage.removeItem(projectStorageKey);
    window.location.reload();
  }

  const selectedVersion: Version | undefined = detail?.versions.find((version) => version.id === selectedVersionId);
  const status = activeRun?.status || "idle";
  const clarification = activeRun?.status === "awaiting_clarification";

  return (
    <main className="shell shell--workspace">
      <div className="screen-frame">
        <Topbar brand="NATURALCAD / GUEST" status={bootStatus === "ready" ? "LINK_ESTABLISHED" : bootStatus === "failed" ? "LINK_OFFLINE" : "HANDSHAKE_INIT"} />
        <div className="workspace-commandbar">
          <span>{projectId ? `Project ${projectId.slice(0, 12)}` : "Connecting"}</span>
          <button type="button" onClick={resetProject} disabled={busy}>New project</button>
        </div>

        <section className="workspace-grid">
          <section className="panel">
            <div className="panel-heading">
              <p className="section-tag">Conversation</p>
              <h2>Describe, inspect, refine</h2>
              <p className="workspace-subtitle">Reference images guide form. Add dimensions in chat when fit matters.</p>
            </div>

            <div className="conversation-log" aria-live="polite">
              {detail?.messages.length ? detail.messages.map((message) => (
                <div key={message.id} className={message.role === "assistant" ? "conversation-entry conversation-entry--assistant" : "conversation-entry"}>
                  <span className="conversation-entry__role">{message.role === "assistant" ? "NaturalCAD" : "You"}</span>
                  <p>{message.content}</p>
                </div>
              )) : <div className="conversation-entry conversation-entry--assistant"><span className="conversation-entry__role">NaturalCAD</span><p>Describe the part or attach up to three reference images.</p></div>}
              {!terminalStatuses.has(status) && status !== "idle" && <div className="conversation-entry conversation-entry--assistant"><span className="conversation-entry__role">NaturalCAD</span><p>{status.replaceAll("_", " ")}...</p></div>}
            </div>

            <div className="composer-shell">
              {clarification && <div className="clarification-banner">Answer the questions above to continue this generation.</div>}
              <div className="attachment-strip">
                {detail?.attachments.filter((item) => item.status === "ready").map((attachment) => (
                  <div key={attachment.id} className="attachment-item">
                    <button type="button" className={selectedAttachmentIds.includes(attachment.id) ? "attachment-thumb attachment-thumb--selected" : "attachment-thumb"} onClick={() => setSelectedAttachmentIds((current) => current.includes(attachment.id) ? current.filter((id) => id !== attachment.id) : [...current, attachment.id].slice(-3))}>
                      {attachment.preview_url && <img src={attachment.preview_url} alt="Uploaded part reference" />}
                      <span>{selectedAttachmentIds.includes(attachment.id) ? "Selected" : "Reference"}</span>
                    </button>
                    <button type="button" className="attachment-remove" title="Remove image" aria-label="Remove image" onClick={() => void removeAttachment(attachment.id)}>×</button>
                  </div>
                ))}
              </div>
              <textarea className="prompt-box" value={prompt} placeholder={clarification ? "Answer the clarification questions" : "Describe the part or the next change"} disabled={busy || bootStatus !== "ready"} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); void submit(); } }} />
              <div className="action-row action-row--split">
                <input ref={fileInput} className="file-input" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={chooseFiles} />
                <button className="button button--ghost" type="button" onClick={() => fileInput.current?.click()} disabled={busy || (detail?.attachments.length || 0) >= 3}>Attach images</button>
                <button className="button button--primary" type="button" onClick={() => void submit()} disabled={busy || !prompt.trim() || bootStatus !== "ready"}>{busy ? "Working" : clarification ? "Answer" : "Generate"}</button>
              </div>
              {error && <div className="workspace-note workspace-note--danger">{error}</div>}
            </div>
          </section>

          <section className="panel workspace-sidebar">
            <div className="panel-heading">
              <p className="section-tag">Viewport</p>
              <h2>{selectedVersion?.change_summary || "Generated geometry"}</h2>
            </div>
            <div className="viewer-shell">
              <div className="viewer-grid" />
              <CADViewport url={selectedVersion?.artifacts.glb || selectedVersion?.artifacts.stl || null} />
              <div className="viewer-overlay"><span>{selectedVersion ? selectedVersion.id.slice(0, 12) : "No version"}</span><span>{status}</span></div>
            </div>
            <section className="history-panel">
              <div className="panel-heading"><p className="section-tag">Version branches</p><h2>Select a parent to refine</h2></div>
              <div className="version-list">
                {detail?.versions.map((version) => (
                  <button key={version.id} type="button" className={version.id === selectedVersionId ? "version-row version-row--selected" : "version-row"} onClick={() => setSelectedVersionId(version.id)}>
                    <div><strong>{version.id.slice(0, 10)}</strong><p>{version.change_summary || version.prompt}</p></div><span className="pill pill--completed">completed</span>
                  </button>
                ))}
                {!detail?.versions.length && <div className="version-empty">No generated versions yet</div>}
              </div>
              <div className="export-row">
                {exportFormats.map((format) => {
                  const key = format === "Preview GLB" ? "glb" : format.toLowerCase();
                  const url = selectedVersion?.artifacts[key];
                  return <button key={format} className="button button--ghost" type="button" disabled={!url} onClick={() => url && window.open(url, "_blank", "noopener,noreferrer")}>{format}</button>;
                })}
              </div>
            </section>
          </section>
        </section>
      </div>
    </main>
  );
}
