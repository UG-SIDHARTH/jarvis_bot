# ===== COMBINED TELEGRAM + DISCORD BOT =====
# Run this on your own computer - YOU control everything

import asyncio
import threading
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ===== TELEGRAM SETUP =====
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  Telegram library not installed. Run: pip install python-telegram-bot")

# ===== DISCORD SETUP =====
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("⚠️  Discord library not installed. Run: pip install discord.py")

# ===== CONFIGURATION =====
# Read tokens strictly from environment variables (.env file)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ===== TELEGRAM BOT FUNCTIONS =====
if TELEGRAM_AVAILABLE:
    async def telegram_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Combined Bot Active!\n"
            "Telegram commands:\n"
            "/start - Show this message\n"
            "/help - Get help\n"
            "/echo <text> - I'll repeat your text\n"
            "/ping - Check if I'm alive\n\n"
            "Discord commands work in your Discord server!"
        )

    async def telegram_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📚 **Telegram Help**\n"
            "/start - Start the bot\n"
            "/help - Show this help\n"
            "/echo <text> - Echo your message\n"
            "/ping - Pong! (latency test)\n"
            "/info - Bot information"
        )

    async def telegram_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = ' '.join(context.args) if context.args else ""
        if text:
            await update.message.reply_text(f"🔊 Echo: {text}")
        else:
            await update.message.reply_text("Usage: /echo <your message>")

    async def telegram_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏓 Pong! Bot is responsive.")

    async def telegram_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 **Combined Bot Info**\n"
            "Platform: Telegram + Discord\n"
            "Status: Running ✅\n"
            "Creator: You!\n"
            "Commands: /start, /help, /echo, /ping, /info"
        )

    async def telegram_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❓ Unknown command. Try /help for available commands.\n"
            "Note: Discord commands work in your Discord server!"
        )

    def run_telegram_bot():
        """Run Telegram bot in separate thread"""
        print("🤖 Starting Telegram bot...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", telegram_start))
        application.add_handler(CommandHandler("help", telegram_help))
        application.add_handler(CommandHandler("echo", telegram_echo))
        application.add_handler(CommandHandler("ping", telegram_ping))
        application.add_handler(CommandHandler("info", telegram_info))
        application.add_handler(MessageHandler(filters.COMMAND, telegram_unknown))
        
        # Run the bot (stop_signals=None is required when running in a worker thread)
        application.run_polling(stop_signals=None)
        print("✅ Telegram bot stopped")

# ===== DISCORD BOT FUNCTIONS =====
if DISCORD_AVAILABLE:
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    @bot.event
    async def on_ready():
        print(f'🤖 Discord bot logged in as {bot.user} (ID: {bot.user.id})')
        print('------')
        activity = discord.Game(name="with combined bot | !help")
        await bot.change_presence(activity=activity)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ Unknown command. Type `!help` for available commands.")
        else:
            await ctx.send(f"⚠️ An error occurred: {str(error)}")
            print(f"Discord error: {error}")

    @bot.command(name='help')
    async def discord_help(ctx):
        help_text = """
📚 **Discord Bot Help**
!help - Show this help message
!hello - Get a friendly greeting
!echo <text> - I'll repeat your text
!ping - Check bot latency
!info - Bot information
!status - Check both platforms
        """
        await ctx.send(help_text)

    @bot.command(name='hello')
    async def discord_hello(ctx):
        await ctx.send(f'👋 Hello {ctx.author.mention}! I\'m your combined bot!')

    @bot.command(name='echo')
    async def discord_echo(ctx, *, text: str):
        await ctx.send(f'🔊 Echo: {text}')

    @bot.command(name='ping')
    async def discord_ping(ctx):
        latency = round(bot.latency * 1000)
        await ctx.send(f'🏓 Pong! Latency: {latency}ms')

    @bot.command(name='info')
    async def discord_info(ctx):
        info_text = f"""
🤖 **Combined Bot Info**
Platform: Telegram + Discord
Discord Latency: {round(bot.latency * 1000)}ms
Servers: {len(bot.guilds)}
Users: {len(set(bot.get_all_members()))}
        """
        await ctx.send(info_text)

    @bot.command(name='status')
    async def discord_status(ctx):
        status_text = "✅ **Bot Status**\n"
        status_text += "Discord: Online 🟢\n"
        status_text += "Telegram: Check your chat 💬\n"
        status_text += "Prefix: !\n"
        status_text += "Use !help for commands"
        await ctx.send(status_text)

    def run_discord_bot():
        """Run Discord bot in separate thread"""
        print("🤖 Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
        print("✅ Discord bot stopped")

# ===== MAIN EXECUTION =====
def main():
    print("=" * 50)
    print("🚀 COMBINED TELEGRAM + DISCORD BOT")
    print("=" * 50)
    
    # Check library installations
    print("\n📋 SETUP STATUS:")
    print(f"Telegram Library: {'✅ Installed' if TELEGRAM_AVAILABLE else '❌ Not installed'}")
    print(f"Discord Library:  {'✅ Installed' if DISCORD_AVAILABLE else '❌ Not installed'}")
    
    if not TELEGRAM_AVAILABLE and not DISCORD_AVAILABLE:
        print("\n🔧 TO INSTALL MISSING LIBRARIES:")
        print("   pip install -r requirements.txt")
        return

    # Check token readiness
    telegram_ready = TELEGRAM_AVAILABLE and bool(TELEGRAM_TOKEN) and TELEGRAM_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    discord_ready = DISCORD_AVAILABLE and bool(DISCORD_TOKEN) and DISCORD_TOKEN != "YOUR_DISCORD_BOT_TOKEN_HERE"

    if not telegram_ready:
        print("⚠️  Telegram token is not configured or python-telegram-bot is missing.")
    else:
        print("✅ Telegram token configured.")

    if not discord_ready:
        print("⚠️  DISCORD_TOKEN is not set or still set to placeholder in .env / code.")
        print("   Get it from: https://discord.com/developers/applications")
    else:
        print("✅ Discord token configured.")

    if not telegram_ready and not discord_ready:
        print("\n❌ Neither bot is ready to start. Please configure at least one token.")
        return

    print("\n🔧 STARTING BOTS...")
    if telegram_ready:
        print("   • Telegram bot will respond to /commands in your chat")
    if discord_ready:
        print("   • Discord bot will respond to !commands in your server")
    print("   Press Ctrl+C to stop the bot(s)\n")
    
    # Start configured bots in separate threads
    if telegram_ready:
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
    
    if discord_ready:
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
    
    try:
        # Keep main thread alive without busy-waiting
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bots...")
        print("✅ Bots stopped. Goodbye!")

if __name__ == "__main__":
    main()
