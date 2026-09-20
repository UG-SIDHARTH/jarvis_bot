# 🤖 Jarvis Bot — Combined Telegram + Discord Bot

A powerful, self-hosted bot that runs both **Telegram** and **Discord** bots concurrently in a single Python application. Built for full control, easy server administration, interactive role menus, and rich presence customization.

---

## 🌟 Key Features

### 🧠 AI Assistant (J.A.R.V.I.S.)
- **Powered by Google Gemini**: Lightning-fast, intelligent, and refined conversational AI.
- **Sophisticated Persona**: Inspired by Tony Stark's J.A.R.V.I.S.—helpful, witty, and polite.
- **Discord AI Interaction**:
  - `/ask <prompt>` (and `!ask <prompt>`) or `/ai <prompt>` — Ask anything via slash or prefix command.
  - `@Jarvis <prompt>` — Mention Jarvis directly in any channel for an instant AI response.
- **Telegram AI Interaction**:
  - `/ask <prompt>` or `/ai <prompt>` — Ask questions in group or direct chats.
  - Direct 1-on-1 private messages automatically routed to Jarvis AI.
- **Smart Formatting & Chunking**: Automatic character limit management (2,000 for Discord, 4,096 for Telegram) and markdown preservation.

### 🎮 Discord Bot
- **Hybrid Commands**: Every command works seamlessly as a Slash Command (`/command`) and as a Prefix Command (`!command`).
- **Channel & Category Management**:
  - `/createchannel <name> [type] [category]` — Create text or voice channels.
  - `/createmultichannel <layout>` — Bulk-create multiple channels across different categories in one command.
  - `/createcategory <name>` — Create new categories.
  - `/deletechannel [#channel]` — Delete a channel.
- **Bulk Channel Creation Function**:
  - Programmatic `create_multiple_channels()` Python function supporting shorthand strings, simple dicts, nested dicts, and list formats.
  - Automatic duplicate prevention and rate limit protection.
- **Role Management**:
  - `/giverole @user <role>` & `/removerole @user <role>` — Assign or remove roles with hierarchy checks.
  - `/createrole <name> [color]` — Create roles with optional hex color codes (e.g. `#ff0000`).
  - `/roles` — List all server roles and member counts.
  - `/rolemenu <title> @role1 [@role2...]` — Generate interactive Discord UI button panels for self-assignable roles.
- **One-Click Server Setup**:
  - `/setup_server` — Automatically creates standard categories (`📌 INFORMATION`, `💬 COMMUNITY`, `🔊 VOICE CHANNELS`), essential channels, starter roles (`Admin`, `Moderator`, `Member`), and publishes server rules.
- **Rules & Moderation**:
  - `/rules [#channel]` — Post a sleek community rules embed.
  - `/postrules <Title> | <Rule 1> | <Rule 2>...` — Post custom formatted rules.
- **Dynamic Rich Presence**:
  - Custom status activities (`/setpresence playing|streaming|listening|watching|competing <name> [| state]`).
  - Default presence: *Competing in Competitive (Playing Solo)*.

### 💬 Telegram Bot
- Run simultaneously alongside Discord.
- Supported commands:
  - `/start` — Welcome message and instructions.
  - `/help` — Overview of available commands.
  - `/ask <prompt>` — Ask Jarvis AI anything.
  - `/echo <text>` — Echo input text.
  - `/ping` — Latency and responsiveness check.
  - `/info` — Bot runtime status.

### 🖥️ Desktop Discord RPC (Optional)
- Standalone zero-dependency Discord IPC client (`discord_rpc.py`) for custom Discord Rich Presence on your desktop.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Google Gemini API Key (free from [Google AI Studio](https://aistudio.google.com/))

### 2. Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/UG-SIDHARTH/jarvis_bot.git
   cd jarvis_bot
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuration

Copy the example environment file:
```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux / macOS
```

Edit `.env` with your credentials:
```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Discord Bot Token (from Discord Developer Portal)
DISCORD_TOKEN=your_discord_bot_token_here

# Enable Privileged Gateway Intents (Message Content & Server Members)
DISCORD_PRIVILEGED_INTENTS=true

# Discord Client / Application ID (Optional, for Discord Rich Presence / RPC)
DISCORD_CLIENT_ID=your_client_id_here

# Google Gemini API Key (for Jarvis AI Assistant)
# Get a free key at https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
AI_MODEL=gemini-1.5-flash
```

> [!IMPORTANT]
> **Discord Privileged Intents**:
> If `DISCORD_PRIVILEGED_INTENTS=true`, ensure **Message Content Intent** and **Server Members Intent** are enabled in the [Discord Developer Portal](https://discord.com/developers/applications) under **Bot > Privileged Gateway Intents**.

---

## 🏃 Running the Bot

### Running Directly with Python
```bash
python bot.py
```

### Running with Docker & Docker Compose
```bash
# Start in the background
docker-compose up -d

# View live logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

### Running Desktop Rich Presence (Optional)
```bash
python discord_rpc.py
```

---

## 📖 Command Reference

### Discord Commands

| Command | Description | Required Permissions |
| :--- | :--- | :--- |
| `/ask <prompt>` or `!ask <prompt>` | Ask Jarvis AI anything | Everyone |
| `/ai <prompt>` | Alias for `/ask` | Everyone |
| `@Jarvis <prompt>` | Mention Jarvis anywhere to chat directly | Everyone |
| `/help` or `!help` | Display interactive help menu | Everyone |
| `/hello` or `!hello` | Friendly greeting | Everyone |
| `/echo <text>` or `!echo <text>` | Echo a message | Everyone |
| `/ping` or `!ping` | Check bot latency | Everyone |
| `/info` or `!info` | Show server and bot statistics | Everyone |
| `/status` or `!status` | Show operational status of both bots | Everyone |
| `/giverole @user <role>` | Assign a role to a member | Manage Roles |
| `/removerole @user <role>` | Remove a role from a member | Manage Roles |
| `/createrole <name> [color]` | Create a new role with optional hex color | Manage Roles |
| `/roles` | List all server roles and member counts | Everyone |
| `/rolemenu <title> @role1 [@role2...]` | Create self-assignable role buttons | Manage Roles |
| `/createchannel <name> [type] [category]` | Create a text or voice channel | Manage Channels |
| `/createmultichannel <layout>` | Bulk create channels across categories | Manage Channels |
| `/deletechannel [#channel]` | Delete a channel (defaults to current) | Manage Channels |
| `/createcategory <name>` | Create a category | Manage Channels |
| `/rules [#channel]` | Post official server rules embed | Administrator |
| `/postrules <Title> \| <Rule 1>...` | Post custom formatted rules | Administrator |
| `/setup_server` | Automated 1-click server setup | Administrator |
| `/setpresence <type> <name> [\| state]` | Update bot activity dynamically | Administrator |
| `/resetpresence` | Reset bot activity to default | Administrator |

### Telegram Commands

| Command | Description |
| :--- | :--- |
| `/start` | Start the bot and view welcome info |
| `/help` | View available Telegram commands |
| `/ask <prompt>` | Ask Jarvis AI anything |
| `/ai <prompt>` | Alias for `/ask` |
| Direct Message | Chat 1-on-1 with Jarvis AI directly in private chat |
| `/echo <text>` | Repeat provided text |
| `/ping` | Check bot responsiveness |
| `/info` | View platform & bot status |

---

## 🛠️ Bulk Channel Creation API

The bot includes a Python function `create_multiple_channels` to programmatically build channel hierarchies in a Discord server:

```python
import bot

# Example 1: Shorthand String Layout
await bot.create_multiple_channels(
    guild=guild,
    structure="📌 INFO: rules, announcements | 💬 CHAT: general, memes, voice:Lounge"
)

# Example 2: Dictionary with Lists (use 'voice:' prefix for voice channels)
await bot.create_multiple_channels(
    guild=guild,
    structure={
        "📌 INFORMATION": ["welcome", "announcements"],
        "💬 COMMUNITY": ["general", "bot-commands", "voice:Lounge"],
        "🔊 VOICE": ["voice:Duo 1", "voice:Squad 1"]
    }
)

# Example 3: Nested Dictionary
await bot.create_multiple_channels(
    guild=guild,
    structure={
        "Community": {
            "text": ["general", "clips"],
            "voice": ["Hangout"]
        }
    }
)
```

---

## 📄 License

This project is open-source and free to use. Modify and customize it to fit your community's needs!
