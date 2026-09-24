# 🤖 Jarvis Bot — Combined Telegram + Discord Bot

A powerful, self-hosted bot that runs both **Telegram** and **Discord** bots concurrently in a single Python application. Built for full control, easy server administration, interactive role menus, and rich presence customization.

---

## 🌟 Key Features

### 🧠 AI Assistant (J.A.R.V.I.S.) — [Admin Only]
- **Admin-Only Access**: J.A.R.V.I.S. AI cognitive systems are strictly reserved for Server Administrators and Bot Owners. Normal users attempting to interact with the AI receive an access denied notice.
- **Powered by Google Gemini**: Lightning-fast, intelligent, and refined conversational AI.
- **Sophisticated Persona**: Inspired by Tony Stark's J.A.R.V.I.S.—helpful, witty, and polite.
- **Multi-Turn Conversation Memory**: Retains the last 10 messages of conversation context so you can have natural follow-up conversations without repeating details. Use `/reset` anytime to start fresh.
- **Image & Vision Support (Multimodal)**: Upload screenshots, images (PNG, JPEG, WEBP, GIF), or code snippets alongside your prompt. Jarvis will analyze, explain, or debug them.
- **Discord AI Interactions (Admin Only)**:
  - `/ask <prompt> [image]` (and `!ask`) or `/ai` — Ask questions with optional image attachments.
  - `/reset` — Clear conversation memory.
  - `@Jarvis <prompt>` — Mention Jarvis anywhere (with or without images) for an instant response.
  - **Discord DM Auto-Chat**: Send private 1-on-1 messages or images directly to Jarvis on Discord—no commands needed! (Requires user to be an administrator in a mutual server).
  - **Right-Click App Command**: Right-click any message anywhere on Discord -> Apps -> **"Explain with Jarvis"** to summarize, explain, or debug messages.
- **Telegram AI Interactions**:
  - `/ask <prompt>` or `/ai <prompt>` — Ask questions in group or direct chats.
  - `/reset` — Clear conversation memory.
  - **Photos**: Send or forward photos with captions directly for vision analysis.
  - **Direct Messages**: 1-on-1 private messages are automatically routed to Jarvis AI.
- **Smart Formatting & Chunking**: Automatic character limit management (2,000 for Discord, 4,096 for Telegram) with markdown preservation.
- **AI Rate Limiting**:
  - Protects your Gemini API quota from spam and abuse.
  - Applies to `/ask`, `@Jarvis` server mentions, right-click app commands, and private DMs.

### 🏆 Leveling & XP System (Discord)
- **Separate Text & Voice Tracking**:
  - **Text XP**: Earn 15–25 XP per message (with a 60-second cooldown to discourage spam).
  - **Voice XP**: Earn 10 XP per minute spent actively in voice channels (AFK and deafened members are excluded).
- **Embedded Rank Cards (`/rank`)**:
  - Displays user avatar, Text LVL, Text Rank, Voice LVL, Voice Rank, total XP, and graphical progress bars (`[████████░░░░]`).
- **Server Leaderboards (`/leaderboard`)**:
  - Top 10 users per page with medals (🥇, 🥈, 🥉) and pagination (`/leaderboard [page]`).
  - Sort by total XP, text XP, or voice XP (`/leaderboard page:1 sort_by:voice`).
- **Automated Level Up Announcements**:
  - Automatically announces when a member levels up with a festive celebration card (`🎉 Level Up! @User has reached level X!`).
- **Persistent SQLite Storage**: Zero-setup local `levels.db` database.

### 🛡️ AutoMod & Moderation System
- **Automated Rules & Filters**:
  - **Anti-Caps**: Detects messages with $\ge 70\%$ uppercase characters (messages $\ge 8$ characters).
  - **Anti-Invites**: Blocks unauthorized Discord invite links (`discord.gg/...`, `discord.com/invite/...`).
  - **Mass Mentions**: Prevents ping spam ($> 4$ mentions per message).
  - **Anti-Spam**: Flags rapid message spam ($> 4$ messages in 3 seconds).
  - **Bad Words / Profanity**: Filters toxic language and profanities using word-boundary matching (prevents false positives on words like "classic").
- **Graduated Strike Sanctions**:
  - **Strikes 1–2**: Warning alert DM (`⚠️ AutoMod Alert: Warn`).
  - **Strikes 3–4**: **10-Minute Timeout** applied immediately with DM alert (`⚠️ AutoMod Alert: Timeout`).
  - **Strike 5**: **24-Hour Temporary Ban** applied with DM alert (`⛔ AutoMod Alert: Temporary Ban`).
  - **Auto-Unban Loop**: Background worker automatically unbans members when their temporary ban expires.
  - **Admin Cancel Controls**: Administrators can cancel or reverse any punishment at any time using `/untimeout`, `/unban`, or `/clearstrikes`.
- **Direct Message (DM) Alerts**:
  - Offending users immediately receive an AutoMod alert embed via DM matching modern moderation bots (`⚠️ AutoMod Alert: Warn`, server name, `Violation: <Rule>`).
- **Channel Cleanup & Mod-Logging**:
  - Removes offending messages instantly and leaves a 5-second self-deleting notice.
  - Automatically sends detailed incident alerts to `#mod-logs` or your designated logging channel (`/setmodlog`).
- **Staff Exemption & Moderation Commands**:
  - Administrators and moderators bypass all AutoMod filters.
  - `/warn @user [reason]` — Manually issue a warning with the same alert DM sent to the member.
  - `/warnings [@user]` — View warning history for a user or server.
  - `/strikes [@user]` — View strike count, active punishment tier, and warning history.
  - `/untimeout @user [reason]` — Cancel an active timeout.
  - `/unban <user_id> [reason]` — Cancel a temporary or permanent ban.
  - `/clearstrikes @user` — Reset and clear all strikes for a member.
  - `/automod [rule] [enabled]` — View or toggle AutoMod filter rules (`anticaps`, `antiinvites`, `massmentions`, `antispam`, `badwords`).
  - `/badwords <add|remove|list> [word]` — Manage custom server bad words blacklist.

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
  - `/claimlink @role [member] [max_uses] [expires_hours]` — Generate a web link that awards a role when clicked/accessed in any browser.
  - `/inviterole @role [channel] [max_uses] [max_age_hours]` — Create a Discord invite link that automatically grants a role to anyone who joins with it.
  - `/claimrole @role [options]` — Create an embed with a persistent 1-click button for members to claim a role (survives bot restarts).
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
AI_MODEL=gemini-3.6-flash
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
| `/ask <prompt> [image]` or `!ask` | Ask Jarvis AI anything (supports vision & multi-turn memory) | Administrator |
| `/ai <prompt>` | Alias for `/ask` | Administrator |
| `/reset` | Clear conversation memory with Jarvis | Administrator |
| `@Jarvis <prompt>` | Mention Jarvis anywhere (supports attachments) to chat directly | Administrator |
| Direct Message (DM) | Chat 1-on-1 with Jarvis in private DMs (no commands needed) | Administrator |
| Apps > Explain with Jarvis | Right-click any message to summarize or explain it | Administrator |
| `/rank [@user]` | View Text & Voice rank, level, and progress bar card | Everyone |
| `/leaderboard [page] [sort_by]` | View server XP rankings with medals (🥇🥈🥉) | Everyone |
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
| `/claimlink @role [options]` | Generate a web link to claim a role in a browser | Manage Roles |
| `/inviterole @role [options]` | Create a Discord invite that auto-grants a role on join | Manage Roles |
| `/claimrole @role [options]` | Create a 1-click button embed for members to claim a role | Manage Roles |
| `/rolemenu <title> @role1 [@role2...]` | Create self-assignable role buttons | Manage Roles |
| `/createchannel <name> [type] [category]` | Create a text or voice channel | Manage Channels |
| `/createmultichannel <layout>` | Bulk create channels across categories | Manage Channels |
| `/deletechannel [#channel]` | Delete a channel (defaults to current) | Manage Channels |
| `/createcategory <name>` | Create a category | Manage Channels |
| `/rules [#channel]` | Post official server rules embed | Administrator |
| `/postrules <Title> \| <Rule 1>...` | Post custom formatted rules | Administrator |
| `/warn @user [reason]` | Warn a member and send an AutoMod alert DM | Manage Messages |
| `/warnings [@user]` | View warning history for a user or server | Manage Messages |
| `/strikes [@user]` | View member strike count and current sanction tier | Manage Messages |
| `/untimeout @user [reason]` | Cancel and remove an active timeout | Moderate Members |
| `/unban <user_id> [reason]` | Cancel and reverse a ban | Ban Members |
| `/clearstrikes @user` | Reset and clear all strikes for a member | Administrator |
| `/automod [rule] [enabled]` | View or toggle AutoMod filter rules | Administrator |
| `/badwords <action> [word]` | Add, remove, or list custom server bad words | Administrator |
| `/setmodlog [#channel]` | Set designated mod-log channel for alerts | Administrator |
| `/setup_server` | Automated 1-click server setup | Administrator |
| `/setwelcome [#channel]` | Set welcome channel for new member greetings | Administrator |
| `/testwelcome [@user]` | Preview the welcome greeting embed | Administrator |
| `/setpresence <type> <name> [\| state]` | Update bot activity dynamically | Administrator |
| `/resetpresence` | Reset bot activity to default | Administrator |

### Telegram Commands

| Command | Description |
| :--- | :--- |
| `/start` | Start the bot and view welcome info |
| `/help` | View available Telegram commands |
| `/ask <prompt>` | Ask Jarvis AI anything (with multi-turn memory) |
| `/ai <prompt>` | Alias for `/ask` |
| `/reset` | Clear conversation memory with Jarvis |
| Direct Message | Chat 1-on-1 with Jarvis AI directly in private chat |
| Send Photo | Send or forward photos with captions for visual analysis |
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
