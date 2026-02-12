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
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

CONFIG_FILE = "config.json"

ticket_config = {}
application_config = {}
ticket_owners = {}
warn_waiting = {}
last_activity = {}

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
                    fp=io.StringIO(transcript_text),
                    filename=f"transcript-{channel.name}.txt"
                )

                owner_id = ticket_owners.get(cid, "Unknown")

                embed = discord.Embed(
                    title="📝 Ticket Transcript",
                    description=f"**Channel:** {channel.name}\n**Closed by:** Auto-close (inactive)\n**Owner ID:** {owner_id}",
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
        label="🎫 Start Tier Test",
        style=discord.ButtonStyle.blurple,
        custom_id="crystalhub_tier_start"
    )
    async def start_tier(self, interaction: discord.Interaction, button: discord.ui.Button):

        existing = find_existing_ticket(interaction.guild, interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True
            )
            return

        category = interaction.guild.get_channel(ticket_config["category"])
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])

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

        # PROFESSIONAL TICKET EMBED
        embed = discord.Embed(
            title="🎫 Crystal Hub • Tier Test Ticket",
            description=(
                f"Welcome {interaction.user.mention}\n\n"
                "**Please click the button below and fill your Tier Test Form carefully.**\n\n"
                "⚠️ Do not waste staff time.\n"
                "⚠️ Provide correct information."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )

        embed.set_image(url="https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif")
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        await channel.send(embed=embed, view=TierFormButton())
        await channel.send(view=TicketButtons())

        await interaction.response.send_message(
            f"✅ Your Tier Test ticket has been created: {channel.mention}",
            ephemeral=True
        )

class TierModal(Modal, title="Tier Test Form"):
    mc = TextInput(label="Minecraft + Discord Username")
    age = TextInput(label="Age")
    region = TextInput(label="Region")
    mode = TextInput(label="Gamemode")

async def on_submit(self, interaction: discord.Interaction):
    if interaction.channel.id not in ticket_owners:
        await interaction.response.send_message(
            "This form can only be used inside a ticket.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📋 Tier Test Submission",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )

    for item in self.children:
        embed.add_field(name=item.label, value=item.value, inline=False)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Tier form submitted.", ephemeral=True)

class StaffApplicationModal(discord.ui.Modal, title="Crystal Hub • Staff Application"):

    username = discord.ui.TextInput(
        label="Minecraft Username & Discord Tag",
        placeholder="Example: Shubham96 | qbhsihekyt_11",
        max_length=60
    )

    age = discord.ui.TextInput(
        label="Age",
        max_length=3
    )

    region = discord.ui.TextInput(
        label="Region / Timezone",
        placeholder="Example: Asia / IST",
        max_length=40
    )

    gamemodes = discord.ui.TextInput(
        label="Gamemodes You Can Professionally Test",
        placeholder="Crystal, NethPot, SMP, Sword",
        max_length=80
    )

    staff_exp = discord.ui.TextInput(
        label="Previous Staff Experience",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="📝 Crystal Hub • New Staff Application",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Applicant", value=interaction.user.mention, inline=False)

        for item in self.children:
            embed.add_field(name=item.label, value=item.value, inline=False)

        embed.set_footer(
            text=f"Applicant ID: {interaction.user.id}",
            icon_url=interaction.user.display_avatar.url
        )

        logs = interaction.guild.get_channel(application_config["logs_channel"])
        view = ApplicationReviewView(interaction.user.id)

        await logs.send(embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Your application has been submitted to Crystal Hub Staff Team.",
            ephemeral=True
        )

class TierFormButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📝 Fill Tier Test Form",
        style=discord.ButtonStyle.success,
        custom_id="tier_form_btn"
    )
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TierModal())
    
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
        
    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="app_reject_btn")
    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.guild.get_member(self.applicant_id)

        try:
            await user.send(
                f"❌ Your Tester Application at **Crystal Hub** was rejected.\n\n"
                f"**Reason:**\n{self.reason.value}"
            )
        except:
            pass

        await interaction.response.send_message("Rejection reason sent to applicant.", ephemeral=True)


# ================= REVIEW BUTTONS =================

class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.guild.get_member(self.applicant_id)

        try:
            await user.send(
                "🎉 Congratulations!\n\n"
                "Your Tester Application at **Crystal Hub** has been **ACCEPTED**.\n"
                "A staff member will contact you shortly."
            )
        except:
            pass

        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Applicant accepted and notified.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectReasonModal(self.applicant_id))


# ================= APPLICATION PANEL =================

class ApplicationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Apply for Staff",
        style=discord.ButtonStyle.primary,
        custom_id="apply_tester_button"  # REQUIRED
    )
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StaffApplicationModal())


class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return

        await interaction.channel.edit(name=f"claimed-{interaction.user.name}")
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("✅ Ticket claimed.", ephemeral=True)

    @discord.ui.button(label="⚠️ Warn User", style=discord.ButtonStyle.secondary, custom_id="warn_user")
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use `/warn @user minutes reason`", ephemeral=True)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.delete()

class ClaimButton(Button):
    def __init__(self):
        super().__init__(label="Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])
        if not staff_role or staff_role not in interaction.user.roles:
            await interaction.followup.send("You do not have permission to claim this ticket.", ephemeral=True)
            return
        channel = interaction.channel
        owner_id = ticket_owners.get(channel.id)
        if not owner_id:
            await interaction.followup.send("Ticket owner not found.", ephemeral=True)
            return
        # If already claimed, stop
        if channel.name.startswith("claimed-by-"):
            await interaction.followup.send("This ticket is already claimed.", ephemeral=True)
            return
        owner = interaction.guild.get_member(owner_id)
        claimer = interaction.user
        # Rename
        await channel.edit(name=f"✅claimed-by-{claimer.name}".lower().replace(" ", "-"))
        # Remove ALL staff access
        await channel.set_permissions(staff_role, overwrite=discord.PermissionOverwrite(view_channel=False))
        # Allow only owner and claimer
        await channel.set_permissions(owner, overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True))
        await channel.set_permissions(claimer, overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True))
        # Disable button
        for item in self.view.children:
            if isinstance(item, Button) and item.custom_id == "ticket_claim_btn":
                item.disabled = True
        await interaction.message.edit(view=self.view)
        await interaction.followup.send(f"✅ Ticket claimed by {claimer.mention}")

class CloseButton(Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])
        if not staff_role or staff_role not in interaction.user.roles:
            await interaction.followup.send("You do not have permission to close this ticket.", ephemeral=True)
            return
        channel = interaction.channel
        logs_channel = interaction.guild.get_channel(ticket_config["logs_channel"])
        await interaction.followup.send("🔒 Closing ticket and saving transcript...")
        try:
            # Generate transcript
            transcript_text = await generate_transcript(channel)
            # Create a text file from transcript
            transcript_file = discord.File(fp=io.StringIO(transcript_text), filename=f"transcript-{channel.name}.txt")
            # Send to logs channel
            owner_id = ticket_owners.get(channel.id, "Unknown")
            embed = discord.Embed(
                title="📝 Ticket Transcript",
                description=f"**Channel:** {channel.name}\n**Closed by:** {interaction.user.mention}\n**Owner ID:** {owner_id}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await logs_channel.send(embed=embed, file=transcript_file)
        except Exception as e:
            logger.error(f"Failed to create transcript: {e}")
        ticket_owners.pop(channel.id, None)
        await asyncio.sleep(2)
        await channel.delete()

# -------------------- EVENTS --------------------

@client.event
async def on_ready():
    load_config()

    client.add_view(MainPanel())
    client.add_view(TierFormButton())
    client.add_view(TicketButtons())
    client.add_view(ApplicationPanel())
    client.add_view(ApplicationReviewView(0))

    asyncio.create_task(auto_close_task())
    asyncio.create_task(warn_checker())

    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Crystal Hub Bot Ready")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id in warn_waiting:
        data = warn_waiting[message.channel.id]
        if message.author.id == data["user"]:
            del warn_waiting[message.channel.id]
            await message.channel.send("✅ User replied. Warning cleared.")

# -------------------- COMMANDS --------------------
@tree.command(name="warn", description="Warn user in ticket")
async def warn(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str):

    channel = find_existing_ticket(interaction.guild, user.id)
    if not channel:
        await interaction.response.send_message("No ticket found.", ephemeral=True)
        return

    await channel.send(
        f"{user.mention} ⚠️ {reason}\nReply within **{minutes} minutes** or ticket closes."
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
    save_config()
    
@tree.command(name="panel", description="Send ticket panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    # Crazy hype text for the description
    crazy_text = "**🚀 Test Your Tier! 🚀**\n\n**CRYSTAL PVP,NETHPOT,SMP,SWORD ARE AVAILABLE,TEST NOW!**\n\n**💥 TEST & Give Your Best! 💥**\n\n**Select your region, choose your mode, and LET'S GET THIS PARTY STARTED!**\n\n**🔥 WARNING: DON'T WASTE STAFF TIME! 🔥**"
    
    # Fun PvP/Gaming GIF URL (replace with a working one if needed)
    gif_url = "https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif"  # Example: Replace with a real GIF URL like a fighting or gaming one
    
    embed = discord.Embed(
        title="🎫 **TIER TEST PANEL** 🎫",
        description=crazy_text,
        color=discord.Color.purple(),  # Crazy color
        timestamp=discord.utils.utcnow()
    )
    embed.set_image(url=gif_url)  # GIF as image
    embed.set_footer(text="Test Your Tier ⤵︎", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    
    await interaction.response.send_message(embed=embed, view=MainPanel())

@tree.command(name="setup_applications", description="Setup application logs", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_applications(
    interaction: discord.Interaction,
    logs_channel: discord.TextChannel,
):
    application_config["logs_channel"] = logs_channel.id
    save_config()

    await interaction.response.send_message(
        f"✅ Application system configured.\nLogs: {logs_channel.mention}",
        ephemeral=True
    )

@tree.command(name="application_panel", guild=discord.Object(id=GUILD_ID))
async def application_panel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🛡️ Crystal Hub • Tester Staff Application",
        description=(
            "Become a part of the **Crystal Hub Staff Team**.\n\n"
            "Click below and submit your application carefully."
        ),
        color=discord.Color.blurple(),
    )

    embed.set_image(url="https://media.giphy.com/media/oWWA8hYwrlk8Yrp6lo/giphy.gif")

    await interaction.response.send_message(embed=embed, view=ApplicationPanel())

# -------------------- START BOT --------------------

if __name__ == "__main__":
    client.run(TOKEN)
