import { app, BrowserWindow, shell } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import http from "node:http";
import https from "node:https";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appDir = path.resolve(__dirname, "..");
const projectRoot = path.resolve(appDir, "..", "..");
const preloadPath = path.join(__dirname, "preload.cjs");
const iconIcoPath = path.join(__dirname, "assets", "pokemon_icon.ico");
const iconPngPath = path.join(__dirname, "assets", "pokemon_icon.png");
// Desktop backend mode must load Flask (8787). Default 5173 is only for Vite dev + proxy.
const uiUrl =
  process.env.ELECTRON_UI_URL ||
  (process.env.ELECTRON_MANAGE_BACKEND === "1"
    ? "http://127.0.0.1:8787"
    : "http://127.0.0.1:5173");

let backendProc = null;
let gpuRecoveryAttempted = false;
let startupIssueMessage = "";

// Reduce blank-window / GPU black-screen issues on some Windows setups.
app.disableHardwareAcceleration();

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function probeUiUrlOnce() {
  return new Promise((resolve) => {
    let parsed;
    try {
      parsed = new URL(uiUrl);
    } catch {
      resolve(false);
      return;
    }

    const client = parsed.protocol === "https:" ? https : http;
    const port =
      parsed.port || (parsed.protocol === "https:" ? 443 : 80);
    const req = client.request(
      {
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port,
        path: parsed.pathname || "/",
        method: "GET",
        timeout: 1200,
      },
      (res) => {
        res.resume();
        resolve((res.statusCode || 0) > 0);
      },
    );

    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });

    req.on("error", () => {
      resolve(false);
    });

    req.end();
  });
}

async function waitForUiReady(maxAttempts, intervalMs) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (await probeUiUrlOnce()) {
      return true;
    }
    if (attempt < maxAttempts) {
      await delay(intervalMs);
    }
  }
  return false;
}

function getHelpHtml() {
  const distPath = path.join(appDir, "dist", "index.html");
  const distExists = existsSync(distPath);
  const backendManaged = process.env.ELECTRON_MANAGE_BACKEND === "1";
  const looksLikeFlask = uiUrl.includes("8787");

  if (backendManaged || looksLikeFlask) {
    const extra = startupIssueMessage
      ? `<p style="margin:0 0 12px 0;line-height:1.5;color:#fecaca;"><b>Detected issue:</b> ${startupIssueMessage}</p>`
      : "";
    return `
      <html>
        <body style="margin:0;background:#030000;color:#fee2e2;font-family:Segoe UI,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;">
          <div style="max-width:760px;padding:32px;border:1px solid #4c0519;border-radius:16px;background:#0f0305;">
            <h2 style="margin:0 0 12px 0;color:#f43f5e;">Dashboard server not reachable</h2>
            ${extra}
            <p style="margin:0 0 10px 0;line-height:1.5;">Nothing responded at <b>${uiUrl}</b>.</p>
            <p style="margin:0 0 16px 0;line-height:1.5;">If you launched Electron alone, run the full stack from repo root:</p>
            <pre style="white-space:pre-wrap;background:#140205;border:1px solid #4c0519;padding:12px;border-radius:10px;margin:0;">cd ui/react-app &amp;&amp; npm run desktop:app</pre>
            <p style="margin:12px 0 0 0;font-size:12px;color:#fda4af;">Or use browser mode: run_pokegrinder.bat web</p>
          </div>
        </body>
      </html>
    `;
  }

  if (!distExists) {
    return `
      <html>
        <body style="margin:0;background:#030000;color:#fee2e2;font-family:Segoe UI,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;">
          <div style="max-width:760px;padding:32px;border:1px solid #4c0519;border-radius:16px;background:#0f0305;">
            <h2 style="margin:0 0 12px 0;color:#f43f5e;">React app not built</h2>
            <p style="margin:0 0 10px 0;line-height:1.5;">Run in <b>ui/react-app</b>:</p>
            <pre style="white-space:pre-wrap;background:#140205;border:1px solid #4c0519;padding:12px;border-radius:10px;margin:0;">npm install
npm run build
npm run desktop:app</pre>
          </div>
        </body>
      </html>
    `;
  }

  return `
    <html>
      <body style="margin:0;background:#030000;color:#fee2e2;font-family:Segoe UI,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;">
        <div style="max-width:760px;padding:32px;border:1px solid #4c0519;border-radius:16px;background:#0f0305;">
          <h2 style="margin:0 0 12px 0;color:#f43f5e;">Dev server not reachable</h2>
          <p style="margin:0;line-height:1.5;">Expected Vite at <b>${uiUrl}</b>. Run: <b>npm run desktop:dev</b></p>
        </div>
      </body>
    </html>
  `;
}

function probeServerIdentity() {
  return new Promise((resolve) => {
    let parsed;
    try {
      parsed = new URL(uiUrl);
    } catch {
      resolve({ ok: false, message: "Invalid dashboard URL." });
      return;
    }

    const client = parsed.protocol === "https:" ? https : http;
    const port = parsed.port || (parsed.protocol === "https:" ? 443 : 80);
    const req = client.request(
      {
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port,
        path: "/api/health",
        method: "GET",
        timeout: 1500,
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          try {
            const payload = JSON.parse(body || "{}");
            const buildHeader = String(res.headers["x-pokegrinder-build"] || "").trim();
            const buildField = String(payload?.server_build || "").trim();
            if (buildHeader || buildField) {
              resolve({ ok: true, message: "" });
              return;
            }
            resolve({
              ok: false,
              message:
                "Another service is responding on this port (missing X-PokeGrinder-Build/server_build). " +
                "Stop old main.py processes and relaunch desktop mode.",
            });
          } catch {
            resolve({
              ok: false,
              message:
                "A non-PokeGrinder service responded with invalid health payload. " +
                "Stop conflicting process on port 8787 and relaunch.",
            });
          }
        });
      },
    );

    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, message: "Health probe timed out." });
    });

    req.on("error", () => {
      resolve({ ok: false, message: "Health probe failed." });
    });

    req.end();
  });
}

async function showUiUnavailableHelp(win) {
  await win.loadURL(`data:text/html;charset=UTF-8,${encodeURIComponent(getHelpHtml())}`);
}

async function showStartupLoading(win) {
  const loading = `
    <html>
      <body style="margin:0;background:#030000;color:#fecdd3;font-family:Segoe UI,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;">
        <div style="width:min(560px,90vw);padding:28px;border:1px solid #4c0519;border-radius:16px;background:#0f0305;">
          <h2 style="margin:0 0 12px 0;color:#fb7185;font-size:20px;">Starting YveltalGo</h2>
          <p style="margin:0;line-height:1.5;">Waiting for dashboard at ${uiUrl} …</p>
        </div>
      </body>
    </html>
  `;
  await win.loadURL(`data:text/html;charset=UTF-8,${encodeURIComponent(loading)}`);
}

async function loadUiWithRetry(win) {
  const shouldWait = process.env.ELECTRON_MANAGE_BACKEND === "1";

  if (shouldWait) {
    await showStartupLoading(win);
    const ready = await waitForUiReady(120, 500);
    if (!ready) {
      await showUiUnavailableHelp(win);
      return;
    }

    const identity = await probeServerIdentity();
    if (!identity.ok) {
      startupIssueMessage = identity.message;
      await showUiUnavailableHelp(win);
      return;
    }
  }

  const maxAttempts = shouldWait ? 2 : 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      await win.loadURL(uiUrl);
      return;
    } catch {
      if (attempt === maxAttempts) break;
      await delay(350);
    }
  }

  await showUiUnavailableHelp(win);
}

function createWindow() {
  const iconPath = existsSync(iconIcoPath)
    ? iconIcoPath
    : (existsSync(iconPngPath) ? iconPngPath : undefined);

  const win = new BrowserWindow({
    width: 1460,
    height: 940,
    minWidth: 1100,
    minHeight: 760,
    backgroundColor: "#030000",
    autoHideMenuBar: true,
    title: "YveltalGo",
    icon: iconPath,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.webContents.on("did-fail-load", async (_event, errorCode, errorDescription) => {
    console.error(`[Electron] Failed loading UI (${errorCode}): ${errorDescription}`);
    await showUiUnavailableHelp(win);
  });

  win.webContents.on("render-process-gone", async (_event, details) => {
    console.error(`[Electron] Renderer process gone: ${details?.reason || "unknown"}`);
    if (!gpuRecoveryAttempted) {
      gpuRecoveryAttempted = true;
      try {
        app.relaunch({ args: process.argv.slice(1).concat(["--disable-gpu"]) });
        app.exit(0);
        return;
      } catch {
        // fall through
      }
    }
    await showUiUnavailableHelp(win);
  });

  void loadUiWithRetry(win);
}

function startBackendIfRequested() {
  if (process.env.ELECTRON_MANAGE_BACKEND !== "1") {
    return;
  }

  const isWindows = process.platform === "win32";
  const repoRoot = path.resolve(projectRoot, "..");
  const venvCandidates = isWindows
    ? [
        path.join(projectRoot, ".venv", "Scripts", "python.exe"),
        path.join(repoRoot, ".venv", "Scripts", "python.exe"),
      ]
    : [
        path.join(projectRoot, ".venv", "bin", "python"),
        path.join(repoRoot, ".venv", "bin", "python"),
      ];

  const command = venvCandidates.find((c) => existsSync(c));
  if (!command) {
    startupIssueMessage =
      "Python virtual environment not found (.venv). Run from repository root and ensure .venv exists.";
    console.error("[Electron] Backend start skipped: .venv Python not found.");
    return;
  }
  const args = ["main.py"];

  backendProc = spawn(command, args, {
    cwd: projectRoot,
    stdio: "inherit",
    shell: false,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      POKEGRINDER_ROOT: projectRoot,
      // Python must not use interactive `input()` — Electron's inherited stdio is not a TTY.
      POKEGRINDER_SKIP_TERMINAL: "1",
      ELECTRON_MANAGE_BACKEND: "1",
    },
  });

  backendProc.on("error", (err) => {
    console.error(`[Electron] Failed to start backend with '${command}': ${err?.message || err}`);
  });

  backendProc.on("exit", () => {
    backendProc = null;
  });
}

function stopBackendIfManaged() {
  if (!backendProc) {
    return;
  }
  try {
    backendProc.kill();
  } catch {
    // ignore
  }
  backendProc = null;
}

app.whenReady().then(() => {
  startBackendIfRequested();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackendIfManaged();
});
