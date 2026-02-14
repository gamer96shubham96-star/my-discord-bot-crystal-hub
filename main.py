import os
import io
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv
import datetime
import json
import logging
logger = logging.getLogger("crystalhub")
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.all()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

CONFIG_FILE = "config.json"

ticket_config = {}
application_config = {}
ticket_owners = {}
warn_waiting = {}
tier_filled = {}
APPLICATION_COOLDOWN = 86400
application_times = {}
active_applications = {}
last_activity = {}
MAX_TICKETS = 2
TICKET_COOLDOWN = 60
user_ticket_cooldown = {}
claimed_by = {}

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "ticket": ticket_config,
            "application": application_config
        }, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            data = json.load(f)
            ticket_config.update(data.get("ticket", {}))
            application_config.update(data.get("application", {}))

# -------------------- FUNCTIONS --------------------

async def generate_transcript(channel: discord.TextChannel) -> str:
    lines = []
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{msg.author} ({msg.author.id})"
        content = msg.content or ""
        if msg.attachments:
            content += " " + " ".join(a.url for a in msg.attachments)
        lines.append(f"[{timestamp}] {author}: {content}")
    return "\n".join(lines)

def find_existing_ticket(guild: discord.Guild, user_id: int) -> discord.TextChannel | None:
    for channel_id, owner_id in ticket_owners.items():
        if owner_id == user_id:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel
    return None

def count_user_tickets(user_id: int):
    return sum(1 for owner in ticket_owners.values() if owner == user_id)

async def auto_close_task():
    while True:
        await asyncio.sleep(60)
        now = discord.utils.utcnow().timestamp()
        to_close = [cid for cid, ts in last_activity.items() if now - ts > 1200]

        for cid in to_close:
            channel = client.get_channel(cid)
            if not channel:
                continue

            logs_id = ticket_config.get("logs_channel")
            if not logs_id:
                continue

            logs_channel = client.get_channel(logs_id)

            try:
                transcript_text = await generate_transcript(channel)

                transcript_file = discord.File(
                    fp=io.BytesIO(transcript_text.encode()),
                    filename=f"transcript-{channel.name}.txt"
                )

                owner_id = ticket_owners.get(cid, "Unknown")

                embed = discord.Embed(
                    title="📝 Ticket Transcript",
                    description=f"**Channel:** {channel.name}\n"
                                f"**Closed by:** Auto-close (inactive)\n"
                                f"**Owner ID:** {owner_id}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )

                if logs_channel:
                    await logs_channel.send(embed=embed, file=transcript_file)

            except Exception as e:
                logger.error(f"Failed to create transcript: {e}")

            ticket_owners.pop(cid, None)
            last_activity.pop(cid, None)
            await channel.delete()

# -------------------- PERSISTENT COMPONENTS --------------------
class MainPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎫Tier Test",
        style=discord.ButtonStyle.blurple,
        custom_id="crystalhub_tier_start"
    )
    async def start_tier(self, interaction: discord.Interaction, button: discord.ui.Button):

        if "category" not in ticket_config:
            await interaction.response.send_message(
                "❌ Ticket system is not configured yet.\nRun /setup_tickets",
                ephemeral=True
            )
            return

        category = interaction.guild.get_channel(ticket_config["category"])
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])

        existing = find_existing_ticket(interaction.guild, interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"❌ You already have a ticket: {existing.mention}",
                ephemeral=True
            )
            return

        if count_user_tickets(interaction.user.id) >= MAX_TICKETS:
            await interaction.response.send_message(
                "❌ You reached maximum open tickets.",
                ephemeral=True
            )
            return

        now = discord.utils.utcnow().timestamp()
        last = user_ticket_cooldown.get(interaction.user.id)

        if last and now - last < TICKET_COOLDOWN:
            await interaction.response.send_message(
                "⏳ Please wait before opening another ticket.",
                ephemeral=True
            )
            return

        user_ticket_cooldown[interaction.user.id] = now

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await category.create_text_channel(
            name=f"tier-{interaction.user.name}".lower().replace(" ", "-"),
            overwrites=overwrites
        )

        ticket_owners[channel.id] = interaction.user.id
        last_activity[channel.id] = discord.utils.utcnow().timestamp()

             embed = discord.Embed(
             title="🎫 Crystal Hub • Tier Evaluation Ticket",
             description=(
             f"Welcome {interaction.user.mention},\n\n"
             "Your private evaluation channel has been created.\n"
             "Please complete the tier form below to begin the assessment process."
            ),
             color=discord.Color.from_rgb(40, 120, 255),
             timestamp=discord.utils.utcnow()
        )

             embed.add_field(name="📌 Ticket Status", value="🟢 Open", inline=True)
             embed.add_field(name="👤 Assigned Staff", value="Not Assigned", inline=True)

             embed.set_footer(text="Crystal Hub • Competitive Evaluation System")
             embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
             embed.set_image(url="https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif")

        await channel.send(embed=embed, view=TierFormView(channel.id))
        await channel.send(view=TicketButtons())

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )
#---------------------------------------------------------------
class TierFormView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(
        label="📝Tier Form ➠",
        style=discord.ButtonStyle.success,
        custom_id="tier_form_open"
    )
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):

        if tier_filled.get(self.channel_id):
            await interaction.response.send_message("Form already submitted.", ephemeral=True)
            return

        await interaction.response.send_modal(TierModal(self))

class TierModal(discord.ui.Modal, title="Tier Test Form"):

    def __init__(self, parent_view: TierFormView):
        super().__init__()
        self.parent_view = parent_view

        self.username = TextInput(label="Minecraft + Discord Username")
        self.age = TextInput(label="Age")
        self.region = TextInput(label="Region")
        self.gamemode = TextInput(label="Gamemode")

        self.add_item(self.username)
        self.add_item(self.age)
        self.add_item(self.region)
        self.add_item(self.gamemode)

    async def on_submit(self, interaction: discord.Interaction):
        tier_filled[self.parent_view.channel_id] = True

         # Remove button AFTER submit
         await interaction.message.edit(view=None)

        for child in self.parent_view.children:
            child.disabled = True

        await interaction.message.edit(view=self.parent_view)

        embed = discord.Embed(
            title="📋 Tier Test Submission",
            color=discord.Color.green()
        )
        embed.add_field(name="Username", value=self.username.value, inline=False)
        embed.add_field(name="Age", value=self.age.value, inline=False)
        embed.add_field(name="Region", value=self.region.value, inline=False)
        embed.add_field(name="Gamemode", value=self.gamemode.value, inline=False)

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(
            "✅ Tier form submitted.",
            ephemeral=True
        )

#---------------------------------------------------------------------------------------
class StaffApplicationModal(discord.ui.Modal, title="Crystal Hub • Staff Application"):

    def __init__(self):
        super().__init__()

        self.username = TextInput(label="Minecraft Username & Discord Tag", max_length=60)
        self.age = TextInput(label="Age", max_length=3)
        self.region = TextInput(label="Region / Timezone", max_length=40)
        self.gamemodes = TextInput(label="Gamemodes You Can Professionally Test", max_length=80)
        self.staff_exp = TextInput(label="Previous Staff Experience", style=discord.TextStyle.paragraph)

        self.add_item(self.username)
        self.add_item(self.age)
        self.add_item(self.region)
        self.add_item(self.gamemodes)
        self.add_item(self.staff_exp)

    async def on_submit(self, interaction: discord.Interaction):

        if "logs_channel" not in application_config:
            await interaction.response.send_message(
                "Applications are not configured yet.",
                ephemeral=True
            )
            return

        if active_applications.get(interaction.user.id):
            await interaction.response.send_message(
                "You already have a pending application.",
                ephemeral=True
            )
            return

        now = discord.utils.utcnow().timestamp()
        last_time = application_times.get(interaction.user.id)

        if last_time and now - last_time < APPLICATION_COOLDOWN:
            remaining = int((APPLICATION_COOLDOWN - (now - last_time)) / 3600)
            await interaction.response.send_message(
                f"You can apply again in {remaining} hours.",
                ephemeral=True
            )
            return

        application_times[interaction.user.id] = now
        active_applications[interaction.user.id] = True

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📝 Crystal Hub • Staff Application",
            description="A new professional staff application has been submitted.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Applicant", value=interaction.user.mention, inline=False)

        for item in self.children:
            embed.add_field(name=item.label, value=item.value, inline=False)

        embed.set_image(url="https://media.giphy.com/media/c9P1lz0XJsjwQh0L6U/giphy.gif")


        logs = interaction.guild.get_channel(application_config["logs_channel"])
        view = ApplicationReviewView(interaction.user.id)

        await logs.send(embed=embed, view=view)

        await interaction.followup.send(
            "✅ Your application has been submitted to Crystal Hub Staff Team.",
            ephemeral=True
        )

# ================= REJECT REASON MODAL =================

class RejectReasonModal(discord.ui.Modal, title="Application Rejection Reason"):

    reason = discord.ui.TextInput(
        label="Reason for rejection",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, applicant_id: int):
        super().__init__()
        self.applicant_id = applicant_id

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.guild.get_member(self.applicant_id)

        # remove application lock
        active_applications.pop(self.applicant_id, None)

        try:
            await user.send(
                    "❌ **Application Update**\n\n"
                    "Thank you for taking the time to apply for the Crystal Hub Tester Team.\n\n"
                    "After careful review, we regret to inform you that your application "
                    "has not been approved at this time.\n\n"
                    f"**Reason Provided by Staff:**\n{self.reason.value}\n\n"
                    "This decision is not permanent. You are welcome to reapply after improving "
                    "your experience and activity.\n\n"
                    "We appreciate your interest in Crystal Hub."
   
            )
        except:
            pass

        await interaction.response.send_message(
            "Rejection reason sent to applicant.",
            ephemeral=True
        )

# ================= REVIEW BUTTONS =================

class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.handled = False

    async def disable_all(self, interaction):
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept_unique")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.handled:
            await interaction.response.send_message("Already handled.", ephemeral=True)
            return

        self.handled = True
        active_applications.pop(self.applicant_id, None)

user = interaction.guild.get_member(self.applicant_id)
if not user:
    try:
        user = await client.fetch_user(self.applicant_id)
    except:
        user = None

        tester_role = discord.utils.get(interaction.guild.roles, name="Tester")

        if tester_role and user:
            try:
                await user.add_roles(tester_role)
            except:
                pass

            try:
                await user.send(
                    "🎉 **Application Status: APPROVED**\n\n"
                    "After a full review by the Crystal Hub Administration Team, "
                    "your Tester Application has been **successfully approved**.\n\n"
                    "We believe you have the skill level and professionalism required "
                    "to represent our competitive standards.\n\n"
                    "⚜ Please maintain high integrity and fairness in all evaluations.\n\n"
                    "Welcome to Crystal Hub."
                )
            except:
                pass

        await self.disable_all(interaction)
        await interaction.response.send_message("Applicant accepted.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="app_reject_unique")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.handled:
            await interaction.response.send_message("Already handled.", ephemeral=True)
            return

        self.handled = True
        active_applications.pop(self.applicant_id, None)

        await self.disable_all(interaction)
        await interaction.response.send_modal(RejectReasonModal(self.applicant_id))
# ================= APPLICATION PANEL =================

class ApplicationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply for Staff", style=discord.ButtonStyle.primary, custom_id="apply_tester_button")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):

        if "logs_channel" not in application_config:
            await interaction.response.send_message("Applications not setup.", ephemeral=True)
            return

        if active_applications.get(interaction.user.id):
            await interaction.response.send_message("You already have a pending application.", ephemeral=True)
            return

        await interaction.response.send_modal(StaffApplicationModal())

class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 Claim", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

    staff_role = interaction.guild.get_role(ticket_config["staff_role"])

    if staff_role not in interaction.user.roles:
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return

    if interaction.channel.id in claimed_by:
        await interaction.response.send_message(
            f"Already claimed by <@{claimed_by[interaction.channel.id]}>",
            ephemeral=True
        )
        return

    claimed_by[interaction.channel.id] = interaction.user.id

    # Update embed professionally
    message = interaction.channel.history(limit=5)
    async for msg in message:
        if msg.embeds:
            embed = msg.embeds[0]
            embed.set_field_at(0, name="📌 Ticket Status", value="🟡 Claimed", inline=True)
            embed.set_field_at(1, name="👤 Assigned Staff", value=interaction.user.mention, inline=True)
            await msg.edit(embed=embed)
            break

    button.disabled = True
    await interaction.message.edit(view=self)

    await interaction.response.send_message("✅ Ticket successfully claimed.", ephemeral=True)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        staff_role = interaction.guild.get_role(ticket_config["staff_role"])

        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff can close tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=ConfirmCloseView(),
            ephemeral=True
        )

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing...", ephemeral=True)

        transcript = await generate_transcript(interaction.channel)
        file = discord.File(io.BytesIO(transcript.encode()), filename="transcript.txt")

        logs = interaction.guild.get_channel(ticket_config["logs_channel"])
        if logs:
            await logs.send(f"Transcript of {interaction.channel.name}", file=file)

        await asyncio.sleep(2)
        await interaction.channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)

# -------------------- EVENTS --------------------

@client.event
async def on_ready():
    load_config()

    # REGISTER ALL PERSISTENT VIEWS
    client.add_view(MainPanel())
    client.add_view(TicketButtons())
    client.add_view(ApplicationPanel())

    asyncio.create_task(auto_close_task())
    asyncio.create_task(warn_checker())

    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Crystal Hub Bot Ready")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # update ticket activity
    if message.channel.id in ticket_owners:
        last_activity[message.channel.id] = discord.utils.utcnow().timestamp()

    # warn system
    if message.channel.id in warn_waiting:
        data = warn_waiting[message.channel.id]
        if message.author.id == data["user"]:
            del warn_waiting[message.channel.id]
            await message.channel.send("✅ User replied. Warning cleared.")

# -------------------- COMMANDS --------------------
@tree.command(
    name="warn",
    description="Warn user in ticket",
    guild=discord.Object(id=GUILD_ID)
)
async def warn(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str):

    channel = find_existing_ticket(interaction.guild, user.id)
    if not channel:
        await interaction.response.send_message("No ticket found.", ephemeral=True)
        return

    await channel.send(
        f"{user.mention}⚠️ {reason}\nReply within **{minutes} minutes** or ticket closes."
    )

    warn_waiting[channel.id] = {
        "user": user.id,
        "end": discord.utils.utcnow().timestamp() + (minutes * 60)
    }

    await interaction.response.send_message("Warn sent.", ephemeral=True)

async def warn_checker():
    while True:
        await asyncio.sleep(15)
        now = discord.utils.utcnow().timestamp()

        for cid, data in list(warn_waiting.items()):
            if now > data["end"]:
                channel = client.get_channel(cid)
                if not channel:
                    del warn_waiting[cid]
                    continue

                member = channel.guild.get_member(data["user"])
                if not member:
                    del warn_waiting[cid]
                    continue

                await channel.send("⏰ No response. Ticket closing and user timed out.")

                await member.timeout(datetime.timedelta(hours=1))
                await channel.delete()

                del warn_waiting[cid]

@tree.command(name="tier", description="Post official tier result", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    tester="Tester",
    user="Player",
    region="Region",
    mode="Gamemode",
    account="Account type",
    previous_tier="Previous tier",
    earned_tier="Tier achieved",
    score="Match score",
    result="Match result"
)
@app_commands.choices(
    region=[
        app_commands.Choice(name="Asia", value="Asia"),
        app_commands.Choice(name="Europe", value="Europe"),
        app_commands.Choice(name="North America", value="North America"),
        app_commands.Choice(name="South America", value="South America"),
    ],
    mode=[
        app_commands.Choice(name="Crystal PvP", value="Crystal PvP"),
        app_commands.Choice(name="NethPot PvP", value="NethPot PvP"),
        app_commands.Choice(name="SMP PvP", value="SMP PvP"),
        app_commands.Choice(name="Sword", value="Sword"),
    ],
    account=[
        app_commands.Choice(name="Premium", value="Premium"),
        app_commands.Choice(name="Cracked", value="Cracked"),
    ],
    result=[
        app_commands.Choice(name="WON", value="WON"),
        app_commands.Choice(name="LOST", value="LOST"),
    ],
)
async def tier(
    interaction: discord.Interaction,
    tester: discord.Member,
    user: discord.Member,
    region: app_commands.Choice[str],
    mode: app_commands.Choice[str],
    account: app_commands.Choice[str],
    previous_tier: str,
    earned_tier: str,
    score: str,
    result: app_commands.Choice[str],
):
    # Exact custom formatted result message as requested, with enhanced markdown
    result_text = f"""
|| @everyone ||

## ⛨ Crystal Hub {mode.value} Tier • OFFICIAL TIER RESULTS ⛨

### ⚚ Tester
{tester.mention}

### ◈ Candidate
{user.mention}

### 🌍 Region
{region.value}

### ⛨ Gamemode
{mode.value}

### ⌬ Account Type
{account.value}

━━━━━━━━━━━━━━━━━━

### ⬖ Previous Tier
**{previous_tier}**

### ⬗ Tier Achieved
**{earned_tier}**

### ✦ Match Score
**{score}**

━━━━━━━━━━━━━━━━━━

## ⛨ RESULT: **{result.value}** ⛨

**Think you can outperform this result?**  
Test again in **1 month!**
"""
    # Create embed with the text as description and GIF as image
    embed = discord.Embed(description=result_text, color=discord.Color.gold())
    embed.set_image(url="https://media.giphy.com/media/oWWA8hYwrlk8Yrp6lo/giphy.gif")
    await interaction.response.send_message(embed=embed)
    # Log the action
    logger.info(f"Tier result posted by {interaction.user}: Tester {tester}, User {user}, Result {result.value}")

@tree.command(name="setup_tickets", description="Setup ticket system", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    staff_role: discord.Role,
    logs_channel: discord.TextChannel,
):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    ticket_config["logs_channel"] = logs_channel.id
    save_config()

    embed = discord.Embed(
        title="✅ Ticket System Configured",
        description=(
            f"Category: {category.mention}\n"
            f"Staff Role: {staff_role.mention}\n"
            f"Logs Channel: {logs_channel.mention}"
        ),
        color=discord.Color.green()
    )

    embed.set_footer(text="✅ Configuration completed", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Log the setup
    logger.info(f"Ticket system configured by {interaction.user}: Category {category.name}, Staff Role {staff_role.name}, Logs Channel {logs_channel.name}")

@tree.command(name="stats", description="Bot statistics", guild=discord.Object(id=GUILD_ID))
async def stats(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📊 Crystal Hub Bot Stats",
        color=discord.Color.purple()
    )

    embed.add_field(name="Open Tickets", value=str(len(ticket_owners)))
    embed.add_field(name="Claimed Tickets", value=str(len(claimed_by)))
    embed.add_field(name="Pending Applications", value=str(len(active_applications)))
    embed.add_field(name="Warnings Active", value=str(len(warn_waiting)))

    await interaction.response.send_message(embed=embed)
    
@tree.command(name="application_panel", description="Send staff application panel", guild=discord.Object(id=GUILD_ID))
async def application_panel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📝 Crystal Hub • Staff Tester Application",
        description=(
            "Thank you for your interest in joining **Crystal Hub's Official Testing Team**.\n\n"
            "We are looking for dedicated and experienced players to assist in "
            "testing and evaluating competitive PvP performance.\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "**Available Testing Divisions**\n"
            "• Crystal PvP\n"
            "• NethPot PvP\n"
            "• SMP PvP\n"
            "• Sword PvP\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "**Minimum Requirements**\n"
            "• Mature & professional attitude\n"
            "• Consistent activity\n"
            "• Strong understanding of PvP mechanics\n"
            "• Ability to provide fair and unbiased evaluations\n\n"
            "If you meet these standards, submit your application below."
        ),
        color=discord.Color.from_rgb(30, 144, 255)
    )

    embed.set_footer(text="Crystal Hub • Professional Recruitment System")
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_image(url="https://media.giphy.com/media/c9P1lz0XJsjwQh0L6U/giphy.gif")

    await interaction.channel.send(embed=embed, view=ApplicationPanel())
    await interaction.response.send_message("Panel sent.", ephemeral=True)

@tree.command(name="setup_applications", description="Setup application logs", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_applications(interaction: discord.Interaction, logs_channel: discord.TextChannel):
    application_config["logs_channel"] = logs_channel.id
    save_config()
    await interaction.response.send_message(
        f"✅ Application logs channel set to {logs_channel.mention}",
        ephemeral=True
    )

@tree.command(name="panel", description="Send ticket panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):

    crazy_text = (
        "**🚀 Test Your Tier! 🚀**\n\n"
        "**CRYSTAL PVP • NETHPOT • SMP • SWORD AVAILABLE — TEST NOW!**\n\n"
        "**💥 Give Your Absolute Best Performance! 💥**\n\n"
        "Select your region, choose your mode, and let's get started.\n\n"
        "**🔥 WARNING:** Do NOT waste staff time. Provide correct details only."
    )

    embed = discord.Embed(
        title="🎫 Crystal Hub • Tier Test Panel",
        description=crazy_text,
        color=discord.Color.blurple()
    )

    embed.set_image(url="https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif")

    await interaction.channel.send(embed=embed, view=MainPanel())
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)
    
client.run(TOKEN)
