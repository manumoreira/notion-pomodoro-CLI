# 🍅 Notion Pomodoro CLI

A lightweight, beautiful Command Line Interface (CLI) Pomodoro timer built in Python with `typer`, `rich`, and `notion-client`. It tracks your focus sessions with terminal progress bars and automatically logs completed work blocks directly to your Notion database.

---

## ✨ Features

- **Visual Terminal Timer**: Rich live display with real-time countdown, animated progress bar, cycle indicators, and session stats.
- **Automatic Notion Logging**: Prompts for task name/tags upon completion and creates structured entries in your Notion database.
- **Configurable Durations**: Default 25 min work, 5 min short break, 15 min long break, 4 cycles (all customizable via flags or config).
- **Interactive Controls**: Press `Ctrl+C` at any time to pause, resume, finish early (logging actual time worked), or skip breaks.
- **Audio & Terminal Notifications**: Terminal audio chime and prominent completion alert panels right in the console (optional desktop notifications via `--os-notify`).
- **Direct Logging**: Manually log sessions anytime with `pomodoro log`.
- **Flexible Notion Schema**: Automatically resolves common column names (`Task`/`Name`, `Date`, `Duration`, `Tags`/`Category`, `Status`).

---

## 📋 Notion Database Setup

### Your Database Properties
The CLI is designed to work seamlessly with your existing Notion Task database:

| Property Name | Property Type | Description | Required? |
| :--- | :--- | :--- | :--- |
| **Task** *(or Name)* | `title` | Task description or name | **Yes** |
| **Status** | `status` or `select` | Task status (e.g. `In Progress`, `Done`) | Optional |
| **Project/client** | `select`, `multi_select`, `relation` | Project or client category | Optional |
| **Deadline** | `date` | Target due date (*preserved, never overwritten*) | Optional |
| **Parent item** | `relation` | Sub-item parent relation (*preserved*) | Optional |
| **Pomodoros** *(or 🍅)* | `number` | Counter incremented with every completed Pomodoro (+1) | **Recommended** |
| **Time Spent (min)** | `number` | Total minutes accumulated on this task (+25m) | **Recommended** |
| **Date** | `date` | Optional last worked timestamp (distinct from `Deadline`) | Optional |

---

## 🔒 Security & Credentials (For Users & Contributors)

### ⚠️ Never Commit Secrets
This repository is configured to protect your sensitive credentials:
- All `.env`, `*.env`, `.env.*`, `*.key`, `*.pem`, `token.json`, and `credentials.json` files are **ignored by Git** in `.gitignore`.
- **Never commit your personal Notion API key (`ntn_...` or `secret_...`) or Database ID** to version control.
- Only the sanitized template file [`.env.example`](.env.example) should be committed to Git.

---

## 🚀 Installation & Setup (Using `venv`)

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
# or
source .venv/bin/activate
```

### 2. Configure Credentials

#### Method A: Interactive Wizard (Recommended)
Run the guided setup:
```bash
pomodoro init
```
*Prompts for your Notion API Key and Database ID/URL, validates the connection with Notion, and automatically saves your configuration to a protected local `.env`.*

#### Method B: Manual Configuration with `.env.example`
1. Copy the example template:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your values:
   ```env
   NOTION_API_KEY=secret_your_notion_api_key_here
   NOTION_DATABASE_ID=your_32_character_database_id_here
   ```

#### Method C: Global System Configuration (For Any Directory)
If you want to use the CLI from anywhere on your system without local project files:
```bash
pomodoro init --global
```
*Stores credentials securely in your home directory at `~/.config/notion-pomodoro/.env`.*

#### 🔑 How to Get Your Notion Credentials:
1. Go to [Notion Integrations](https://www.notion.so/profile/integrations) and click **"+ New integration"**.
2. Copy the **Internal Integration Secret** (`secret_...` or `ntn_...`).
3. In Notion, open your database page, click the `...` menu (top right) ➔ **Connections** ➔ add your integration.
4. Copy your **Database ID** (the 32-character string in the database URL before `?v=`).
---

## 💻 CLI Usage

### Start a Focus Session & Select Active Task
```bash
# Start Pomodoro (fetches your active Notion tasks so you can select one from a menu!)
pomodoro start

# Start directly on a specific task
pomodoro start --task "Prepare Client Proposal" --tag "Acme Corp"

# Custom durations (30 min work, 10 min break, 4 cycles)
pomodoro start -w 30 -s 10 -l 20 -c 4
```

> **Task Validation**: If a task name is entered that doesn't exist in Notion, the CLI prompts you:
> - **[1]** Pick an existing task from Notion
> - **[2]** Create it as a new task in Notion upon completion
> - **[3]** Continue timer untracked (runs locally without logging to Notion)
> - **[q]** Cancel session


When the timer completes:
1. It chimes and displays a completion alert in your terminal.
2. Prompts: `Did you finish this task? (Mark status as Done in Notion) [y/N]`.
3. Automatically increments **`Pomodoros` (+1)** and adds to **`Time Spent (min)` (+25m)** directly on the task in Notion.

### View Active Tasks from Notion
```bash
pomodoro tasks
# or
pomodoro list
```

### Take an Independent Break
```bash
pomodoro break          # 5-min short break
pomodoro break --long   # 15-min long break
pomodoro break -m 10    # custom 10-min break
```

### Manually Add / Increment Pomodoros
```bash
pomodoro log --task "Refactor Auth" --pomodoros 2 --duration 50 --tag "Engineering" --done
```

### Inspect Configuration & Notion Database Mapping
```bash
pomodoro status
```

### Help & Options
```bash
pomodoro --help
pomodoro start --help
```

---

## ⌨️ Timer Controls

During a live timer session, you can press **`Ctrl+C`** to pause:
- **`[r]esume`**: Unpauses and continues the countdown.
- **`[f]inish early & log`**: Ends the session immediately and logs the actual minutes elapsed.
- **`[s]kip break`**: Skips the rest of a break timer.
- **`[q]uit/cancel`**: Aborts the session.

---

## 🧪 Running Tests

```bash
# Ensure venv is active
pytest
```

---

## 📄 License
MIT
