# PokeGrinder

Automated, multi-account PokéMeow automation suite equipped with an intelligent battle engine, neural network captcha solver, humanized anti-detection pacing, and a modern Electron/React desktop dashboard.

---

> [!WARNING]
> ### Disclaimer & Terms of Service Notice
> **This repository is an archived hobby/educational project and may be outdated.** Discord API policies, `discord.py-self` behavior, and PokéMeow bot mechanics or command structures may have changed since this project was maintained. 
> 
> Self-botting violates **Discord's Terms of Service** and can result in permanent account termination. Use this software strictly at your own discretion and risk. The authors and contributors assume no liability for account suspensions, bans, or data loss.

---

## ✨ Key Features

### 👥 Multi-Account Orchestration
- **Simultaneous Grinding**: Run multiple Discord tokens concurrently without cross-account interference.
- **Granular Controls**: Configure independent hunting/fishing channels, delay profiles, ball rules, and webhook alerts per account.
- **Dynamic Runtime Controls**: Start, pause, resume, or stop individual accounts on the fly directly from the dashboard.

### 🎮 Automated PokéMeow Modules
- **Wild Hunting**: Automatic encounter resolution with customizable ball priorities (Common, Uncommon, Rare, Super Rare, Legendary, Shiny, Event, Full-odds).
- **Target Ball Exceptions**: Specify distinct Pokéball choices for target Pokémon (e.g. Master Ball on Shiny/Legendary encounters, Ultra Ball on specific rares).
- **Auto-Restock**: Automatically purchase necessary Pokéballs when inventory runs low.
- **Fishing Automation**: Timed rod casting, cooldown tracking, and automated catch loops.
- **Smart AutoFight (Battle Bot)**: Real-time embed battle state parsing with PokéAPI type-effectiveness evaluations, HP threshold heuristics, switch strategies, and optimal move selection.
- **Berry Garden & CatchBot**: Periodic garden inspections with auto-watering for dry slots, CatchBot loot collection, and egg incubation.

### 🛡️ Humanized Anti-Detection Engine
- **Humanizer & Break Coordinator**: Simulates human behavior with randomized micro-delays and configurable short/long break cycles to eliminate robotic patterns.
- **Cloudflare & Gateway Awareness**: Automatically detects Discord API rate limits and gateway slowdowns to dynamically pace requests.
- **Suspicion Avoidance**: Intelligent spacing and randomized jitter between Discord button interactions and message dispatches.

### 🤖 AI-Powered Captcha Solver
- **YOLO Neural Network Solver**: Integrated object-detection model (`assets/Solver100k.pt`) that auto-crops, removes noise, and predicts captcha digit challenges.
- **Multi-Variant Image Filtering**: Applies adaptive thresholding and morphological operations to maximize recognition accuracy on distorted text.
- **Safety Guardrails**: Configurable attempt limits, Discord Webhook alerts with ping notifications, and automatic session pause when manual completion is required.

### 🌸 Modern Dashboard (Web & Desktop)
- **Standalone Electron App**: Run as a sleek native desktop application or access via browser.
- **Sakura Theme UI**: Built with React, Vite, and Tailwind CSS for real-time telemetry, catch logs, and performance tracking.
- **Live Flask API**: Serves session statistics, account statuses, and system diagnostics over local REST endpoints.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technology |
|---|---|
| **Bot Core** | Python 3.10+, `discord.py-self` |
| **Machine Learning** | PyTorch, Ultralytics YOLOv8, OpenCV, Pillow |
| **Backend API** | Flask, Werkzeug, SQLite3 (caching) |
| **Frontend UI** | React 18, Vite, Tailwind CSS, Lucide Icons |
| **Desktop Wrapper** | Electron |

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10 - 3.12**
- **Node.js 18+** & `npm`
- **Git**

> [!NOTE]
> This project relies on `discord.py-self`. Do **not** install `py-cord` or standard `discord.py` in the same environment, as library namespace conflicts will break token authentication.

---

### Installation

#### 1. Set up Python environment
**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Install Dashboard UI dependencies
```bash
cd ui/react-app
npm install
cd ../..
```

---

## ⚙️ Configuration

1. Copy the example configuration template:
   ```bash
   cp config.example.json config.json
   ```
2. Open `config.json` in your editor and configure your accounts:
   ```json
   {
     "Accounts": {
       "PASTE_DISCORD_TOKEN_HERE": {
         "HuntingChannel": 123456789012345678,
         "FishingChannel": 123456789012345678,
         "Balls": {
           "Common": "pb",
           "Uncommon": "pb",
           "Rare": "gb",
           "Super Rare": "ub",
           "Legendary": "mb",
           "Shiny": "mb"
         }
       }
     }
   }
   ```
> [!IMPORTANT]
> Keep your real tokens **only** in `config.json`. The repository's `.gitignore` is configured to prevent `config.json` and runtime logs from ever being tracked by git. Full documentation is in [SETUP.md](SETUP.md).

---

## 🖥️ Running PokeGrinder

### Quick Launch (Windows)
Double-click [`run_pokegrinder.bat`](run_pokegrinder.bat) to launch both backend services and the Electron desktop window.

### Command Line Modes

| Command | Description |
|---|---|
| `run_pokegrinder.bat desktop` | Starts backend + hidden background Electron desktop window |
| `run_pokegrinder.bat desktop-debug` | Starts backend + visible Electron desktop console logs |
| `run_pokegrinder.bat web` | Starts backend on `http://127.0.0.1:8787` and opens React UI in your browser (`http://127.0.0.1:5173`) |

### Manual Launch (All Platforms)
```bash
# Terminal 1: Backend
python main.py

# Terminal 2: UI
cd ui/react-app
npm run dev
```

---

## 📄 License & Code of Conduct

- Distributed under the terms in [LICENSE](LICENSE).
- Community guidelines: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## 🙏 Acknowledgements & Credits

- **Original Project**: Built upon the foundational bot concepts and command automation from [MehulKhanna/PokeGrinder](https://github.com/MehulKhanna/PokeGrinder).
- **Pokémon Data & Assets**: Sprites and game data provided by [PokéAPI](https://pokeapi.co/) and [PokemonDB](https://pokemondb.net/).
- **AI & Captcha Detection**: Powered by [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics).
- **Discord Gateway Interface**: Powered by [`discord.py-self`](https://github.com/dolfies/discord.py-self).
