const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { randomUUID } = require('crypto');

const PYTHON_BIN = process.env.BUILD123D_PYTHON || '/Users/noahk/.openclaw/workspace/skills/build123d-cad/.venv/bin/python';
const PORT = process.env.PORT || 4000;
const ARTIFACT_DIR = path.join(__dirname, '..', 'artifacts');
const RUNNER_PATH = path.join(__dirname, 'runner.py');
const DIST_PATH = path.join(__dirname, '..', 'dist');

fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use('/artifacts', express.static(ARTIFACT_DIR));

if (fs.existsSync(DIST_PATH)) {
  app.use(express.static(DIST_PATH));
}

const sendSse = (res, event, data) => {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
};

app.get('/api/run', (req, res) => {
  const code = req.query.code;
  if (typeof code !== 'string' || !code.trim()) {
    res.status(400).json({ error: 'Missing code parameter.' });
    return;
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const jobId = randomUUID();
  const codeFile = path.join(ARTIFACT_DIR, `${jobId}.py`);
  const stlFile = path.join(ARTIFACT_DIR, `${jobId}.stl`);
  const stepFile = path.join(ARTIFACT_DIR, `${jobId}.step`);

  fs.writeFileSync(codeFile, code);
  sendSse(res, 'log', { message: `Job ${jobId} accepted.` });

  const pythonArgs = [RUNNER_PATH, '--source', codeFile, '--stl-output', stlFile, '--step-output', stepFile];
  const child = spawn(PYTHON_BIN, pythonArgs, { env: process.env });

  req.on('close', () => {
    if (!child.killed) {
      child.kill('SIGINT');
    }
  });

  child.stdout.on('data', (chunk) => {
    sendSse(res, 'log', { message: chunk.toString().trim() });
  });

  child.stderr.on('data', (chunk) => {
    sendSse(res, 'log', { message: chunk.toString().trim(), level: 'error' });
  });

  child.on('error', (error) => {
    sendSse(res, 'log', { message: `Runner error: ${error.message}`, level: 'error' });
    sendSse(res, 'complete', { success: false, error: error.message });
    res.end();
  });

  child.on('close', (code) => {
    const success = code === 0;
    if (success) {
      sendSse(res, 'complete', {
        success: true,
        stlPath: `/artifacts/${path.basename(stlFile)}`,
        stepPath: `/artifacts/${path.basename(stepFile)}`
      });
    } else {
      sendSse(res, 'complete', { success: false, error: `Runner exited with ${code}` });
    }
    res.end();
  });
});

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', python: PYTHON_BIN });
});

app.listen(PORT, () => {
  console.log(`build123d live runner listening on http://localhost:${PORT}`);
});
