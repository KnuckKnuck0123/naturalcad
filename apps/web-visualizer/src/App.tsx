import { useCallback, useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

const SAMPLE_SNIPPET = `from build123d import *

# Simple parametric puck
radius = 15
height = 8

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Circle(radius)
        PolarLocations(radius / 2, 6)
        Circle(radius / 6)
    extrude(amount=height)

result = bp.part`;

type LogEntry = {
  id: string;
  message: string;
  level: 'info' | 'error';
};

const loader = new STLLoader();

export default function App() {
  const [code, setCode] = useState(SAMPLE_SNIPPET);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [artifactUrl, setArtifactUrl] = useState<string | null>(null);
  const [stepUrl, setStepUrl] = useState<string | null>(null);
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  const appendLog = useCallback((message: string, level: 'info' | 'error' = 'info') => {
    setLogs((prev) => [...prev, { id: crypto.randomUUID(), message, level }]);
  }, []);

  useEffect(() => {
    if (!viewerRef.current) return;

    const width = viewerRef.current.clientWidth;
    const height = viewerRef.current.clientHeight;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020617);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(60, 45, 60);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(50, 80, 30);

    const grid = new THREE.GridHelper(120, 20, 0x172554, 0x1e293b);

    scene.add(ambient);
    scene.add(dir);
    scene.add(grid);

    viewerRef.current.appendChild(renderer.domElement);

    sceneRef.current = scene;
    rendererRef.current = renderer;
    cameraRef.current = camera;
    controlsRef.current = controls;

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };
    animate();

    const handleResize = () => {
      if (!viewerRef.current || !rendererRef.current || !cameraRef.current) return;
      const newWidth = viewerRef.current.clientWidth;
      const newHeight = viewerRef.current.clientHeight;
      rendererRef.current.setSize(newWidth, newHeight);
      cameraRef.current.aspect = newWidth / newHeight;
      cameraRef.current.updateProjectionMatrix();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      controls.dispose();
    };
  }, []);

  useEffect(() => {
    if (!artifactUrl || !sceneRef.current) return;

    loader.load(
      artifactUrl,
      (geometry) => {
        if (meshRef.current) {
          sceneRef.current!.remove(meshRef.current);
          meshRef.current.geometry.dispose();
        }
        geometry.center();
        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({
          color: 0x38bdf8,
          metalness: 0.1,
          roughness: 0.4
        });
        const mesh = new THREE.Mesh(geometry, material);
        meshRef.current = mesh;
        sceneRef.current!.add(mesh);
        appendLog('STL loaded in viewer.');
        setStatus('done');
      },
      undefined,
      (error) => {
        appendLog(`Viewer load error: ${error.message}`, 'error');
        setStatus('error');
      }
    );
  }, [artifactUrl, appendLog]);

  const handleRun = () => {
    if (!code.trim()) {
      appendLog('Add some build123d code before running.', 'error');
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setLogs([]);
    setStatus('running');
    setArtifactUrl(null);
    setStepUrl(null);

    const url = `/api/run?ts=${Date.now()}&code=${encodeURIComponent(code)}`;
    const source = new EventSource(url);
    eventSourceRef.current = source;

    source.addEventListener('log', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { message: string; level?: 'info' | 'error' };
      appendLog(payload.message, payload.level ?? 'info');
    });

    source.addEventListener('complete', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { success: boolean; stlPath?: string; stepPath?: string; error?: string };
      if (payload.success && payload.stlPath) {
        const finalUrl = `${payload.stlPath}?v=${Date.now()}`;
        appendLog('Runner completed; STL ready.');
        if (payload.stepPath) {
          appendLog('STEP export ready.');
          setStepUrl(`${payload.stepPath}?v=${Date.now()}`);
        }
        setArtifactUrl(finalUrl);
      } else {
        appendLog(payload.error ?? 'Runner failed.', 'error');
        setStatus('error');
      }
      source.close();
    });

    source.onerror = () => {
      appendLog('Connection interrupted.', 'error');
      setStatus('error');
      source.close();
    };
  };

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      appendLog('Stream closed by user.');
      setStatus('idle');
    }
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (rendererRef.current) {
        rendererRef.current.dispose();
      }
      if (controlsRef.current) {
        controlsRef.current.dispose();
      }
    };
  }, []);

  return (
    <div className="app-shell layout-landscape">
      <section className="panel panel-editor">
        <h2>build123d Prompt</h2>
        <div className="controls">
          <button onClick={handleRun} disabled={status === 'running'}>
            {status === 'running' ? 'Running…' : 'Run & Stream'}
          </button>
          <button onClick={handleStop}>Stop</button>
        </div>
        <textarea
          className="editor"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
        />
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.5rem' }}>
          Tip: assign your geometry to a variable named <code>result</code> so the runner can export it.
        </p>
      </section>

      <section className="panel panel-viewer">
        <div className="panel-header-row">
          <h2>Live Model</h2>
          <div className="status-inline">
            <span>Status: {status}</span>
          </div>
        </div>
        <div className="viewer-container viewer-container-large">
          <div className="viewer-canvas" ref={viewerRef} />
        </div>
        {(artifactUrl || stepUrl) && (
          <div className="status-row">
            <span>Exports Ready</span>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              {artifactUrl && (
                <a href={artifactUrl} download="model.stl" style={{ color: '#38bdf8' }}>
                  Download STL
                </a>
              )}
              {stepUrl && (
                <a href={stepUrl} download="model.step" style={{ color: '#f59e0b' }}>
                  Download STEP
                </a>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="panel panel-logs">
        <div className="panel-header-row">
          <h2>Runner Logs</h2>
          <span className="log-count">{logs.length} entries</span>
        </div>
        <div className="logs">
          {logs.length === 0 ? 'Awaiting output…' : logs.map((log) => `${log.level === 'error' ? '✖' : '•'} ${log.message}`).join('\n')}
        </div>
      </section>
    </div>
  );
}
