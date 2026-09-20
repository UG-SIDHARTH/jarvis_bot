# ===== COMBINED TELEGRAM + DISCORD BOT =====
# Run this on your own computer - YOU control everything

import asyncio
import threading
import time
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ===== TELEGRAM SETUP =====
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    import telegram.error
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
DISCORD_PRIVILEGED_INTENTS = os.getenv("DISCORD_PRIVILEGED_INTENTS", "true").lower() in ("true", "1", "yes")

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

    async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in Telegram bot and prevent infinite conflict loop."""
        error = context.error
        if isinstance(error, telegram.error.Conflict):
            print("\n" + "=" * 60)
            print("⚠️  [TELEGRAM CONFLICT DETECTED]")
            print("   Terminated by another getUpdates request.")
            print("   Make sure only ONE bot instance is running with this token!")
            print("   Check for other Docker containers (`docker ps`) or local processes.")
            print("=" * 60)
            if context.application.updater and context.application.updater.running:
                print("🛑 Stopping Telegram polling loop to prevent spamming the API...")
                await context.application.updater.stop()
        elif isinstance(error, telegram.error.NetworkError):
            print(f"⚠️ Telegram network error: {error}")
        else:
            print(f"⚠️ Telegram error: {error}")

    def run_telegram_bot():
        """Run Telegram bot in separate thread"""
        print("🤖 Starting Telegram bot...")
        try:
            application = Application.builder().token(TELEGRAM_TOKEN).build()
            
            # Add handlers
            application.add_handler(CommandHandler("start", telegram_start))
            application.add_handler(CommandHandler("help", telegram_help))
            application.add_handler(CommandHandler("echo", telegram_echo))
            application.add_handler(CommandHandler("ping", telegram_ping))
            application.add_handler(CommandHandler("info", telegram_info))
            application.add_handler(MessageHandler(filters.COMMAND, telegram_unknown))
            
            # Register error handler to avoid unhandled exception spam
            application.add_error_handler(telegram_error_handler)
            
            # Run the bot (drop_pending_updates flushes queued updates from old runs)
            application.run_polling(drop_pending_updates=True, stop_signals=None)
        except Exception as e:
            print(f"❌ Telegram bot crashed: {e}")
        print("✅ Telegram bot stopped")

# ===== DISCORD BOT FUNCTIONS =====
if DISCORD_AVAILABLE:
    intents = discord.Intents.default()
    if DISCORD_PRIVILEGED_INTENTS:
        intents.message_content = True  # Required to read message content for prefix commands
        intents.members = True          # Required for role assignment and member management
    else:
        print("ℹ️  Discord privileged intents disabled (DISCORD_PRIVILEGED_INTENTS=false).")
        print("   Prefix commands (!help, !ping) in servers will require mentioning the bot.")

    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # --- Interactive Self-Role UI Components ---
    class SelfRoleButton(discord.ui.Button):
        def __init__(self, role: discord.Role):
            super().__init__(label=role.name, style=discord.ButtonStyle.primary, custom_id=f"self_role_{role.id}")
            self.role_id = role.id

        async def callback(self, interaction: discord.Interaction):
            role = interaction.guild.get_role(self.role_id)
            if not role:
                await interaction.response.send_message("❌ This role no longer exists.", ephemeral=True)
                return

            if role in interaction.user.roles:
                try:
                    await interaction.user.remove_roles(role, reason="Self-assigned role toggle")
                    await interaction.response.send_message(f"➖ Removed role **{role.name}** from you.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("⚠️ I don't have permission to remove that role. Check my role hierarchy!", ephemeral=True)
            else:
                try:
                    await interaction.user.add_roles(role, reason="Self-assigned role toggle")
                    await interaction.response.send_message(f"➕ Added role **{role.name}** to you!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("⚠️ I don't have permission to assign that role. Check my role hierarchy!", ephemeral=True)

    class SelfRoleView(discord.ui.View):
        def __init__(self, roles):
            super().__init__(timeout=None)  # Persistent view
            for role in roles[:25]:  # Discord limit: max 25 components
                self.add_item(SelfRoleButton(role))

    @bot.event
    async def on_ready():
        print(f'🤖 Discord bot logged in as {bot.user} (ID: {bot.user.id})')
        print('------')
        # Sync slash commands with Discord
        try:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} slash command(s) with Discord!")
        except Exception as e:
            print(f"⚠️ Failed to sync slash commands: {e}")

        # Default Rich Presence: Competing in Competitive (Playing Solo)
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="Competitive",
            state="Playing Solo"
        )
        await bot.change_presence(activity=activity)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ Unknown command. Type `!help` for available commands.")
        elif isinstance(error, commands.MissingPermissions):
            missing = ", ".join(f"`{perm}`" for perm in error.missing_permissions)
            await ctx.send(f"⛔ You don't have permission to use this command! Missing: {missing}")
        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(f"`{perm}`" for perm in error.missing_permissions)
            await ctx.send(f"⚠️ I don't have the required permissions to do that! Missing: {missing}")
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send(f"❌ Role `{error.argument}` not found. Check the name or mention.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"❌ Member `{error.argument}` not found. Please mention them or use their ID.")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send(f"❌ Channel `{error.argument}` not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing required argument: `{error.param.name}`. Check `!help` for usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"⚠️ Invalid argument: {str(error)}")
        else:
            await ctx.send(f"⚠️ An error occurred: {str(error)}")
            print(f"Discord error: {error}")

    # ==================== GENERAL COMMANDS ====================

    @bot.hybrid_command(name='help', description="Show the Discord bot help menu")
    async def discord_help(ctx):
        embed = discord.Embed(
            title="📚 Discord Bot Help Menu",
            description="All commands work with both `/command` (Slash) and `!command` (Prefix):",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🤖 General",
            value=(
                "`/help` or `!help` - Show this menu\n"
                "`/hello` or `!hello` - Friendly greeting\n"
                "`/echo <text>` - Repeat your message\n"
                "`/ping` or `!ping` - Latency check\n"
                "`/info` or `!info` - Bot information\n"
                "`/status` or `!status` - Bot operational status"
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ Role Management (Requires Manage Roles)",
            value=(
                "`/giverole @user <role>` - Assign a role to a member\n"
                "`/removerole @user <role>` - Remove a role from a member\n"
                "`/createrole <name> [color]` - Create a new role (e.g. `/createrole Gamer #ff0000`)\n"
                "`/roles` - List all server roles and member counts\n"
                "`/rolemenu <title> <@role1> [@role2...]` - Create an interactive self-role button panel"
            ),
            inline=False
        )
        embed.add_field(
            name="📁 Channel Management (Requires Manage Channels)",
            value=(
                "`/createchannel <name> [type] [category]` - Create a channel\n"
                "`/deletechannel [#channel]` - Delete a channel (defaults to current)\n"
                "`/createcategory <name>` - Create a new category"
            ),
            inline=False
        )
        embed.add_field(
            name="📜 Rules & Server Setup (Requires Admin)",
            value=(
                "`/rules [#channel]` - Post a sleek pre-configured rules embed\n"
                "`/postrules <Title> | <Rule 1> | <Rule 2>...` - Post custom rules\n"
                "`/setup_server` - One-click server setup (channels, categories, roles)"
            ),
            inline=False
        )
        embed.add_field(
            name="🎮 Presence Management (Requires Admin)",
            value=(
                "`/setpresence <type> <name> [| state]` - Set custom bot activity\n"
                "`/resetpresence` - Reset activity to Competitive (Playing Solo)"
            ),
            inline=False
        )
        embed.set_footer(text="Tip: Ensure the bot's role is positioned high in Server Settings > Roles!")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='hello', description="Friendly greeting")
    async def discord_hello(ctx):
        await ctx.send(f'👋 Hello {ctx.author.mention}! Ready to customize your server? Type `/help` to see commands.')

    @bot.hybrid_command(name='echo', description="Repeat your message")
    async def discord_echo(ctx, *, text: str):
        await ctx.send(f'🔊 Echo: {text}')

    @bot.hybrid_command(name='ping', description="Check bot latency")
    async def discord_ping(ctx):
        latency = round(bot.latency * 1000)
        await ctx.send(f'🏓 Pong! Latency: {latency}ms')

    @bot.hybrid_command(name='info', description="Show bot information and stats")
    async def discord_info(ctx):
        embed = discord.Embed(title="🤖 Combined Bot Info", color=discord.Color.teal())
        embed.add_field(name="Platform", value="Telegram + Discord", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Total Users", value=str(len(set(bot.get_all_members()))), inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='status', description="Show bot operational status")
    async def discord_status(ctx):
        status_text = "✅ **Bot Status**\n"
        status_text += "Discord: Online 🟢\n"
        if bot.activity:
            act_type = bot.activity.type.name.capitalize()
            act_name = getattr(bot.activity, "name", "")
            act_state = getattr(bot.activity, "state", "")
            status_text += f"Activity: {act_type} {act_name}"
            if act_state:
                status_text += f" ({act_state})"
            status_text += "\n"
        status_text += "Telegram: Check your chat 💬\n"
        status_text += "Prefix: `/` (Slash) or `!`\n"
        status_text += "Use `/help` for commands"
        await ctx.send(status_text)

    # ==================== PRESENCE MANAGEMENT ====================

    @bot.hybrid_command(name='setpresence', description="Dynamically update bot presence (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_setpresence(ctx, activity_type: str, *, text: str):
        """
        Dynamically update bot presence.
        Usage:
          /setpresence competing Competitive | Playing Solo
          /setpresence playing Overwatch 2
          /setpresence watching Tournaments
          /setpresence listening Chill Beats
        """
        parts = [p.strip() for p in text.split('|', 1)]
        name = parts[0]
        state = parts[1] if len(parts) > 1 else None

        type_map = {
            'playing': discord.ActivityType.playing,
            'streaming': discord.ActivityType.streaming,
            'listening': discord.ActivityType.listening,
            'watching': discord.ActivityType.watching,
            'competing': discord.ActivityType.competing,
            'custom': discord.ActivityType.custom,
        }

        act_type = type_map.get(activity_type.lower())
        if act_type is None:
            valid = ", ".join(f"`{k}`" for k in type_map.keys())
            await ctx.send(f"❌ Invalid activity type. Valid types: {valid}")
            return

        activity = discord.Activity(type=act_type, name=name, state=state)
        await bot.change_presence(activity=activity)

        embed = discord.Embed(title="🎮 Presence Updated", color=discord.Color.green())
        embed.add_field(name="Type", value=activity_type.capitalize(), inline=True)
        embed.add_field(name="Name", value=name, inline=True)
        if state:
            embed.add_field(name="State", value=state, inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='resetpresence', description="Reset presence to default (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_resetpresence(ctx):
        """Reset bot presence to default (Competitive | Playing Solo)."""
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="Competitive",
            state="Playing Solo"
        )
        await bot.change_presence(activity=activity)
        await ctx.send("✅ Presence reset to default: **Competing in Competitive (Playing Solo)**.")

    # ==================== ROLE MANAGEMENT ====================

    @bot.hybrid_command(name='giverole', description="Assign an existing role to a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_giverole(ctx, member: discord.Member, role: discord.Role):
        """Assign an existing role to a member."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign that role because it is higher than or equal to my highest role!")
            return
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot assign a role that is higher than or equal to your own highest role!")
            return
        if role in member.roles:
            await ctx.send(f"ℹ️ {member.mention} already has the **{role.name}** role.")
            return

        await member.add_roles(role, reason=f"Given by {ctx.author}")
        embed = discord.Embed(
            title="✅ Role Assigned",
            description=f"Successfully added **{role.name}** to {member.mention}.",
            color=role.color if role.color.value != 0 else discord.Color.green()
        )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='removerole', description="Remove a role from a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_removerole(ctx, member: discord.Member, role: discord.Role):
        """Remove a role from a member."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot remove that role because it is higher than or equal to my highest role!")
            return
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot remove a role that is higher than or equal to your own highest role!")
            return
        if role not in member.roles:
            await ctx.send(f"ℹ️ {member.mention} does not have the **{role.name}** role.")
            return

        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        embed = discord.Embed(
            title="✅ Role Removed",
            description=f"Successfully removed **{role.name}** from {member.mention}.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='createrole', description="Create a new role with optional hex color")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_createrole(ctx, name: str, color: Optional[str] = None):
        """Create a new role with an optional hex color (e.g. /createrole Gamer #ff0000)."""
        role_color = discord.Color.default()
        if color:
            clean_color = color.lstrip('#')
            try:
                role_color = discord.Color(int(clean_color, 16))
            except ValueError:
                await ctx.send("⚠️ Invalid hex color code. Creating role with default color instead.")

        new_role = await ctx.guild.create_role(
            name=name,
            color=role_color,
            reason=f"Created by {ctx.author}"
        )
        embed = discord.Embed(
            title="✅ Role Created",
            description=f"Role **{new_role.name}** was created successfully.",
            color=new_role.color if new_role.color.value != 0 else discord.Color.green()
        )
        embed.add_field(name="Role ID", value=f"`{new_role.id}`", inline=True)
        embed.add_field(name="Color", value=f"`{str(new_role.color)}`", inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='roles', description="List all server roles and their member counts")
    async def discord_roles(ctx):
        """List all server roles and their member counts."""
        roles = [r for r in ctx.guild.roles if not r.is_default()]
        roles.reverse()  # Highest hierarchy first

        if not roles:
            await ctx.send("ℹ️ No custom roles found in this server.")
            return

        lines = [f"• **{role.name}** ({len(role.members)} members) - `{role.id}`" for role in roles[:30]]
        embed = discord.Embed(
            title=f"🛡️ Server Roles ({len(roles)} total)",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        if len(roles) > 30:
            embed.set_footer(text=f"Showing top 30 of {len(roles)} roles")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='rolemenu', description="Create an interactive self-role button panel")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_rolemenu(
        ctx,
        title: str,
        role1: discord.Role,
        role2: Optional[discord.Role] = None,
        role3: Optional[discord.Role] = None,
        role4: Optional[discord.Role] = None,
        role5: Optional[discord.Role] = None
    ):
        """Create an interactive button menu for self-assignable roles.
        Usage: /rolemenu "Pick Your Roles" @Gamer @Developer
        """
        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        if not roles:
            await ctx.send("⚠️ Please specify at least one role.")
            return

        # Check bot hierarchy for all roles
        unassignable = [r.name for r in roles if r >= ctx.guild.me.top_role]
        if unassignable:
            await ctx.send(f"❌ I cannot manage these roles because they are higher than or equal to my highest role: {', '.join(unassignable)}")
            return

        view = SelfRoleView(roles)
        embed = discord.Embed(
            title=f"🎭 {title}",
            description="Click the buttons below to add or remove roles from yourself!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Click once to get the role, click again to remove it.")
        await ctx.send(embed=embed, view=view)

    # ==================== CHANNEL MANAGEMENT ====================

    @bot.hybrid_command(name='createchannel', description="Create a text or voice channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_createchannel(ctx, name: str, channel_type: str = "text", category_name: Optional[str] = None):
        """Create a text or voice channel.
        Usage: /createchannel lounge text Community
        """
        category = None
        if category_name:
            category = discord.utils.find(lambda c: c.name.lower() == category_name.lower(), ctx.guild.categories)
            if not category:
                await ctx.send(f"⚠️ Category `{category_name}` not found. Creating channel without category.")

        if channel_type.lower() in ["voice", "vc"]:
            new_channel = await ctx.guild.create_voice_channel(name=name, category=category, reason=f"Created by {ctx.author}")
            channel_icon = "🔊"
        else:
            new_channel = await ctx.guild.create_text_channel(name=name, category=category, reason=f"Created by {ctx.author}")
            channel_icon = "💬"

        embed = discord.Embed(
            title="✅ Channel Created",
            description=f"{channel_icon} Successfully created {new_channel.mention}!",
            color=discord.Color.green()
        )
        if category:
            embed.add_field(name="Category", value=category.name, inline=True)
        embed.add_field(name="Type", value=channel_type.capitalize(), inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='deletechannel', description="Delete a channel (defaults to current channel)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_deletechannel(ctx, channel: Optional[discord.TextChannel] = None):
        """Delete a channel. Defaults to current channel if none specified.
        Usage: /deletechannel #spam
        """
        target_channel = channel or ctx.channel
        channel_name = target_channel.name

        # If deleting the current channel, we won't be able to reply after delete
        is_current = target_channel.id == ctx.channel.id

        await target_channel.delete(reason=f"Deleted by {ctx.author}")

        if not is_current:
            embed = discord.Embed(
                title="🗑️ Channel Deleted",
                description=f"Channel **#{channel_name}** has been deleted.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @bot.hybrid_command(name='createcategory', description="Create a new category for organizing channels")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_createcategory(ctx, *, name: str):
        """Create a new category for organizing channels.
        Usage: /createcategory Gaming
        """
        category = await ctx.guild.create_category(name=name, reason=f"Created by {ctx.author}")
        embed = discord.Embed(
            title="✅ Category Created",
            description=f"📁 Successfully created category **{category.name}**!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # ==================== RULES & SERVER SETUP ====================

    @bot.hybrid_command(name='rules', description="Post a sleek community rules embed (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_rules(ctx, channel: Optional[discord.TextChannel] = None):
        """Post a professionally formatted community rules embed.
        Usage: /rules or /rules #rules
        """
        target_channel = channel or ctx.channel
        embed = discord.Embed(
            title="📜 Official Server Rules & Guidelines",
            description="Welcome to our server! To ensure an enjoyable and safe environment for everyone, please follow these rules:",
            color=discord.Color.dark_teal()
        )
        embed.add_field(
            name="1️⃣ Be Respectful & Kind",
            value="Treat all members with respect. Harassment, hate speech, bullying, toxicity, and discrimination will not be tolerated.",
            inline=False
        )
        embed.add_field(
            name="2️⃣ No Spam or Advertising",
            value="Avoid spamming messages, emojis, mentions, or images. Self-promotion and server invites are only allowed in designated channels.",
            inline=False
        )
        embed.add_field(
            name="3️⃣ Keep Content Appropriate (SFW)",
            value="No NSFW, explicit, gore, or illegal content. Keep profile pictures, nicknames, and statuses clean.",
            inline=False
        )
        embed.add_field(
            name="4️⃣ Use Channels Appropriately",
            value="Post topics in their respective channels (e.g. memes in #memes, bot commands in #bot-commands).",
            inline=False
        )
        embed.add_field(
            name="5️⃣ Follow Discord's Terms of Service",
            value="All members must adhere to [Discord's Community Guidelines](https://discord.com/guidelines) and [Terms of Service](https://discord.com/terms).",
            inline=False
        )
        embed.add_field(
            name="6️⃣ Respect Staff & Moderation",
            value="Moderators have the final say. If you have an issue, please open a ticket or DM a staff member privately.",
            inline=False
        )
        embed.set_footer(text="By remaining in this server, you agree to follow these rules.")
        await target_channel.send(embed=embed)
        if target_channel != ctx.channel:
            await ctx.send(f"✅ Rules have been posted to {target_channel.mention}!")

    @bot.hybrid_command(name='postrules', description="Post custom rules formatted with pipes (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_postrules(ctx, *, content: str):
        """Post custom rules formatted with pipes.
        Usage: /postrules Server Rules | 1. Be kind | 2. No spam | 3. Have fun
        """
        parts = [p.strip() for p in content.split('|')]
        if len(parts) < 2:
            await ctx.send("⚠️ Format: `/postrules Title | Rule 1 | Rule 2 | ...`")
            return

        title = parts[0]
        rules_list = parts[1:]

        embed = discord.Embed(
            title=f"📜 {title}",
            description="Please read and abide by the rules below:",
            color=discord.Color.dark_purple()
        )
        for i, rule in enumerate(rules_list, 1):
            embed.add_field(name=f"Rule {i}", value=rule, inline=False)

        embed.set_footer(text="Thank you for keeping our community safe!")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='setup_server', description="One-click server setup (Admin only)")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(administrator=True, manage_channels=True, manage_roles=True)
    async def discord_setup_server(ctx):
        """Automated one-click server setup with categories, channels, roles, and rules."""
        await ctx.defer()
        status_msg = await ctx.send("⚙️ Starting automated server setup... This may take a few seconds.")

        guild = ctx.guild

        # 1. Create Default Roles if they don't exist
        created_roles = []
        role_definitions = [
            ("Admin", discord.Color.red()),
            ("Moderator", discord.Color.blue()),
            ("Member", discord.Color.green())
        ]
        for role_name, role_color in role_definitions:
            existing = discord.utils.get(guild.roles, name=role_name)
            if not existing:
                try:
                    new_r = await guild.create_role(name=role_name, color=role_color, reason="Automated Server Setup")
                    created_roles.append(new_r.name)
                except discord.Forbidden:
                    pass

        # 2. Create Categories & Channels
        structure = [
            {
                "category": "📌 INFORMATION",
                "text": ["welcome-and-rules", "announcements"],
                "voice": []
            },
            {
                "category": "💬 COMMUNITY",
                "text": ["general", "bot-commands", "memes"],
                "voice": []
            },
            {
                "category": "🔊 VOICE CHANNELS",
                "text": [],
                "voice": ["General Voice", "Gaming Lounge"]
            }
        ]

        rules_channel = None

        for group in structure:
            cat_name = group["category"]
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                category = await guild.create_category(name=cat_name, reason="Automated Server Setup")

            for t_name in group["text"]:
                ch = discord.utils.get(guild.text_channels, name=t_name, category=category)
                if not ch:
                    ch = await guild.create_text_channel(name=t_name, category=category, reason="Automated Server Setup")
                if t_name == "welcome-and-rules":
                    rules_channel = ch

            for v_name in group["voice"]:
                vc = discord.utils.get(guild.voice_channels, name=v_name, category=category)
                if not vc:
                    await guild.create_voice_channel(name=v_name, category=category, reason="Automated Server Setup")

        # 3. Post Rules in the rules channel if found
        if rules_channel:
            rules_embed = discord.Embed(
                title="📜 Welcome to the Server!",
                description="Welcome! Please take a moment to review our server rules:",
                color=discord.Color.dark_teal()
            )
            rules_embed.add_field(name="1️⃣ Be Respectful", value="Treat all members with courtesy and kindness.", inline=False)
            rules_embed.add_field(name="2️⃣ No Spam or Self-Promo", value="Keep channels clean and free of unsolicited advertisements.", inline=False)
            rules_embed.add_field(name="3️⃣ SFW Server", value="Keep all conversations, media, and profiles appropriate.", inline=False)
            rules_embed.add_field(name="4️⃣ Follow Discord ToS", value="Adhere to Discord's Terms of Service at all times.", inline=False)
            rules_embed.set_footer(text="Enjoy your stay!")
            await rules_channel.send(embed=rules_embed)

        summary_embed = discord.Embed(
            title="🎉 Server Setup Complete!",
            description="Your server has been customized with essential channels, categories, and roles.",
            color=discord.Color.green()
        )
        summary_embed.add_field(
            name="📁 Categories Created",
            value="• 📌 INFORMATION\n• 💬 COMMUNITY\n• 🔊 VOICE CHANNELS",
            inline=True
        )
        summary_embed.add_field(
            name="🛡️ Roles Created",
            value=", ".join(created_roles) if created_roles else "Existing roles retained",
            inline=True
        )
        if rules_channel:
            summary_embed.add_field(name="📜 Rules Channel", value=rules_channel.mention, inline=False)

        await status_msg.edit(content=None, embed=summary_embed)

    def run_discord_bot():
        """Run Discord bot in separate thread"""
        print("🤖 Starting Discord bot...")
        try:
            bot.run(DISCORD_TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "=" * 60)
            print("❌ DISCORD ERROR: Privileged Intents Not Enabled!")
            print("=" * 60)
            print("Your bot is configured to use Privileged Gateway Intents (Message Content & Server Members),")
            print("but they have not been enabled in the Discord Developer Portal.")
            print("\nTo fix this:")
            print("  1. Visit: https://discord.com/developers/applications")
            print("  2. Select your bot application -> Click 'Bot' in the left menu")
            print("  3. Scroll down to 'Privileged Gateway Intents'")
            print("  4. Enable:")
            print("     • MESSAGE CONTENT INTENT")
            print("     • SERVER MEMBERS INTENT")
            print("  5. Click 'Save Changes'")
            print("\nAlternatively, set DISCORD_PRIVILEGED_INTENTS=false in your .env to run without them.")
            print("=" * 60 + "\n")
        except discord.errors.LoginFailure:
            print("❌ DISCORD ERROR: Improper or invalid token passed. Check DISCORD_TOKEN in .env.")
        except Exception as e:
            print(f"❌ Discord bot error: {e}")
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
        print("   • Discord bot will respond to /commands (Slash) and !commands in your server")
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
