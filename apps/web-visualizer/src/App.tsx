import { FormEvent, useMemo, useState } from 'react';

type SpecPreview = {
  intent: string;
  mode: 'part' | 'assembly' | 'sketch';
  output: '3d_solid' | 'surface' | '2d_vector' | '1d_path';
  notes: string[];
};

const defaultPrompt = 'A modular steel bracket with 4 bolt holes and a cable channel';

const features = [
  {
    title: 'Prompt to geometry in one flow',
    body: 'Natural-language input, generated build123d logic, and export-ready CAD artifacts in one run.'
  },
  {
    title: 'Export-first workflow',
    body: 'STEP and STL for fabrication, DXF for linework and laser workflows, with lineage per run.'
  },
  {
    title: 'Enterprise controls ready',
    body: 'Structured API boundaries, auth gates, observability, and path to RBAC and tenant isolation.'
  }
];

const steps = [
  'Describe the object in plain language.',
  'NaturalCAD resolves intent into CAD-safe generation logic.',
  'Review the model, then download STEP/STL/DXF artifacts.'
];

function inferSpec(prompt: string): SpecPreview {
  const text = prompt.toLowerCase();
  const is2d = /dxf|profile|laser|plate|outline/.test(text);
  const is1d = /route|centerline|path|wire/.test(text);
  const output = is1d ? '1d_path' : is2d ? '2d_vector' : '3d_solid';

  return {
    intent: prompt.trim() || defaultPrompt,
    mode: output === '3d_solid' ? 'part' : 'sketch',
    output,
    notes: [
      'Dimension constraints inferred from prompt language.',
      'Geometry kept bounded for stable generation latency.',
      'Artifacts prepared for downstream CAD handoff.'
    ]
  };
}

export default function App() {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [submittedPrompt, setSubmittedPrompt] = useState(defaultPrompt);

  const spec = useMemo(() => inferSpec(submittedPrompt), [submittedPrompt]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSubmittedPrompt(prompt);
  };

  return (
    <main className="site-shell">
      <header className="topbar">
        <div className="brand">NaturalCAD</div>
        <nav>
          <a href="#product">Product</a>
          <a href="#workflow">Workflow</a>
          <a href="#pilot">Pilot</a>
        </nav>
      </header>

      <section className="hero" id="product">
        <div>
          <p className="eyebrow">NaturalCAD • Website Prototype v0</p>
          <h1>Design with words. Ship real CAD artifacts.</h1>
          <p className="hero-copy">
            This is a first-pass front end for your domain launch. It positions NaturalCAD as a product,
            not just a demo, while keeping a live prompt-to-spec interaction on the page.
          </p>
          <div className="cta-row">
            <a className="btn btn-primary" href="https://huggingface.co/spaces/kNOWare/naturalcad" target="_blank" rel="noreferrer">
              Open current Space
            </a>
            <a className="btn btn-ghost" href="#pilot">Request pilot access</a>
          </div>
        </div>

        <form className="spec-card" onSubmit={handleSubmit}>
          <label htmlFor="prompt">Try a concept prompt</label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={5}
          />
          <button className="btn btn-primary" type="submit">Preview inferred spec</button>

          <pre>{JSON.stringify(spec, null, 2)}</pre>
        </form>
      </section>

      <section className="feature-grid" aria-label="key features">
        {features.map((feature) => (
          <article key={feature.title} className="feature-card">
            <h2>{feature.title}</h2>
            <p>{feature.body}</p>
          </article>
        ))}
      </section>

      <section className="workflow" id="workflow">
        <h2>How the production flow lands</h2>
        <ol>
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="pilot" id="pilot">
        <h2>Enterprise pilot</h2>
        <p>
          Start with one team, one artifact lane, and traceability from prompt to export. Then scale by
          domain, policy, and workload.
        </p>
        <div className="pilot-tags">
          <span>API-first</span>
          <span>Audit trail</span>
          <span>STEP/STL/DXF</span>
          <span>Private deployment path</span>
        </div>
      </section>
    </main>
  );
}
