# PokeGrinder Setup Guide

This guide is the source of truth for setting up PokeGrinder from a fresh clone.

## What You Get
- Multi-account hunting and fishing automation
- Runtime controls from terminal and dashboard
- Captcha detection with optional auto-answer attempts
- Berry, egg, and world boss automations
- Anti-detection telemetry and controls

## Prerequisites
- Python 3.10+ (3.12 recommended)
- Node.js 18+ and npm
- Git
- Discord Developer Mode enabled (to copy channel/server IDs)

## Fresh Clone Setup

### 1. Clone and enter project
```bash
git clone https://github.com/schrazen/something.git
cd something/PokeGrinder
```

### 2. Create virtual environment
```bash
python -m venv .venv
```

### 3. Activate virtual environment
Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:
```cmd
.venv\Scripts\activate.bat
```

macOS/Linux:
```bash
source .venv/bin/activate
```

### 4. Install Python dependencies
```bash
pip install -r requirements.txt
```

Dependency mode note:
- This setup uses `discord.py-self`.
- Do not install `py-cord` in the same virtual environment.

### 5. Install dashboard dependencies
```bash
cd ui/react-app
npm install
cd ../..
```

## Configuration

### 1. Create local config
Windows:
```powershell
Copy-Item config.example.json config.json
```

macOS/Linux:
```bash
cp config.example.json config.json
```

### 2. Add at least one account in config.json
Replace the placeholder token key under Accounts with your real token and set channels:

```json
{
  "Accounts": {
    "YOUR_DISCORD_TOKEN": {
      "HuntingChannel": 123456789012345678,
      "FishingChannel": 123456789012345678
    }
  }
}
```

Important:
- Keep secrets only in config.json
- Never commit real tokens
- If both HuntingChannel and FishingChannel are 0, that account will not run

### 3. Optional global keys
- RequiredServerID: lock runtime to one server (0 disables lock)
- CaptchaAnswerer.AutoAnswerEnabled: enables auto answer attempts
- CaptchaAnswerer.MaxAutoAttempts: max automatic attempts before manual required
- CaptchaAnswerer.ManualAnswerAllowedUserIDs: optional allowlist for manual answer command
- AntiDetection and HumanBreaks: reduce repetitive behavior patterns

## Start the System

### Option A: One-click launcher (Windows)
Run:
```cmd
run_pokegrinder.bat
```

Default behavior:
- Prompts for Desktop app mode or Browser mode.
- Desktop mode launches a hidden app-mode process (build + backend + Electron).
- Browser mode starts backend + React dev server.

Additional launcher modes:
```cmd
run_pokegrinder.bat desktop
run_pokegrinder.bat desktop-debug
run_pokegrinder.bat desktop-dev-debug
run_pokegrinder.bat web
```

### Option B: Start manually (any OS)
Terminal 1:
```bash
python main.py
```

Terminal 2:
```bash
cd ui/react-app
npm run dev
```

Optional desktop app mode (no Vite required):
```bash
cd ui/react-app
npm run desktop:app
```

## URLs
- Dashboard UI (dev mode): http://127.0.0.1:5173
- Dashboard UI (desktop app mode): http://127.0.0.1:8787
- Backend API: http://127.0.0.1:8787

Note: in desktop app mode, Flask serves the built React app from 8787 root.

## Runtime Controls

### Current startup behavior
- Accounts are OFF by default when app boots
- Start/stop is user-driven from Runtime tab

### Dashboard controls
Runtime tab includes:
- Start All / Stop All
- Per-account Start/Stop in Configured Accounts
- Per-running-bot pause/resume hunt/fish
- Automation toggles

### Terminal controls (when running main.py)
- help
- status
- pause
- resume
- pause hunt
- resume hunt
- pause fish
- resume fish
- clear limit
- start all
- exit

### AutoFight command reference
- ;autofight on
  - Start AutoFight watcher mode.
- ;autofight run <count> <battle_mode> [STRATEGY]
  - Run N battles with cooldown-aware restart.
  - Example: ;autofight run 10 npc 1 EV
- ;autofight once [battle_mode] [STRATEGY]
  - Run exactly one battle.
  - Example: ;autofight once npc 13 LEVEL
- ;autofight stop
  - Stop current AutoFight run immediately.
- ;autofight off
  - Disable AutoFight.

Strategy modes:
- STANDARD (default): balanced battle decisions
- EV: no voluntary switching (first mon focus)
- LEVEL: stronger mon softens, weaker mon finishes for EXP

Automation coordination:
- When AutoFight starts, hunt/fish automation is paused.
- When AutoFight stops or completes, previous hunt/fish pause state is restored.

## Captcha Answering

Config block:
```json
"CaptchaAnswerer": {
  "AutoAnswerEnabled": true,
  "MaxAutoAttempts": 3,
  "ManualAnswerAllowedUserIDs": []
}
```

Manual answer command in captcha channel:
- answer 12345

Behavior:
- Auto-answer retries up to MaxAutoAttempts
- Manual answers are limited to prevent endless spam loops
- Captcha has a 90-second timeout window
- If attempts are exhausted or timeout is reached, captcha enters terminal failure: reminders stop and the affected module is paused until manually resumed
- Attempts/outcomes are logged under assets/captcha_samples

## Quick Troubleshooting

### Module errors for discord
If import errors mention discord variants or auth mode mismatch, ensure environment is pyself-only:
```bash
pip uninstall -y py-cord discord.py
pip install -r requirements.txt
pip install --force-reinstall --no-cache-dir discord.py-self==2.1.0
```

Why this matters:
- Mixed installs (`py-cord` + `discord.py-self`) can override the `discord` import target and break token auth mode.

### Runtime stuck on Starting/Connecting
- Open Runtime status and check account `last_error`.
- If you see `Improper token has been passed.` while using known-working self tokens, your environment is likely importing the wrong discord package.
- Re-run the pyself-only dependency steps above, then restart.

### Dashboard not reachable
- Confirm UI dev server is running on 5173
- If API calls fail in UI, ensure main.py is running on 8787

### Runtime says Not ready
- Recheck token and channel IDs in config.json
- Verify account can access configured channels
- Check startup logs for LoginFailure or permissions

### Added account but it does not run
- New accounts do not auto-start
- Start it from Runtime tab or use Start All

## Files You Should Know
- main.py: runtime process and bot lifecycle
- config.example.json: template config for new clones
- config.json: local private config (do not commit)
- requirements.txt: Python dependencies
- run_pokegrinder.bat: Windows launcher (backend + UI)
- ui/server.py: Flask API layer
- ui/react-app: React dashboard source
