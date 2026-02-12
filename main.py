import os
import io
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv
import logging
import random
import datetime

# Set up logging for better debugging and professionalism
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "1466825673384394824"))

# Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Client and tree
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Global configurations and data
ticket_config: dict[str, int] = {}
application_config: dict[str, int] = {}
ticket_owners: dict[int, int] = {}  # channel_id -> user_id
user_selections: dict[tuple[int, int], dict] = {}  # Key: (user_id, channel_id), Value: {'region': str, 'mode': str}
ticket_counter = 1
last_activity: dict[int, float] = {}  # channel_id -> timestamp
application_states: dict[int, dict] = {}  # user_id -> {'step': int, 'answers': list[str]}

# List of interesting quotes for flair in tickets
interesting_quotes = [
    "Shubham96 Is The Best Cpvp Tester!",
    "qbhishekyt_11 is The Best Nethpot Tester!",
    "Tier Is A Identity Of A Fighter!",
    "Test Tier Wake Earlier!",
    "Subscribe-https://www.youtube.com/@Shubham96Official"
]

# Questions for staff applications
questions = [
    "Username (Minecraft + Discord)?",
    "How old are you?",
    "What is your Region / Timezone?",
    "What gamemodes can you test? (Crystal, NethPot, SMP, Sword)",
    "How many hours can you give daily?",
    "How long have you been doing PvP?",
    "Rate your PvP skill from 1-10",
    "Do you have previous staff experience? If yes, where?",
    "Why do you want to become a Tester?",
    "What makes you different from other applicants?",
    "How would you handle toxic players during tests?",
    "How would you handle false tier accusations?",
    "Can you record your tests? (Yes/No)",
    "Do you understand abuse = instant removal? (Yes/No)",
    "Any additional information?"
]

CONFIG_FILE = "config.json"

import json

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "ticket_config": ticket_config,
            "application_config": application_config
        }, f)

def load_config():
    global ticket_config, application_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            ticket_config.update(data.get("ticket_config", {}))
            application_config.update(data.get("application_config", {}))

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

class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):

        if "category" not in ticket_config:
            await interaction.response.send_message("Ticket system not configured.", ephemeral=True)
            return

        existing = find_existing_ticket(interaction.guild, interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True
            )
            return

        category = interaction.guild.get_channel(ticket_config["category"])

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(ticket_config["staff_role"]): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            client.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        try:
            channel = await category.create_text_channel(
                f"tier-test-{interaction.user.name}".lower().replace(" ", "-"),
                overwrites=overwrites
            )

            ticket_owners[channel.id] = interaction.user.id

            await channel.send(view=TicketButtons())

await interaction.response.send_message(
    "✅ Ticket created. Please fill the form below.",
    ephemeral=True
)
await channel.send(view=TierFormButton())

            welcome_embed = discord.Embed(
                title="🎫 Welcome to Your Tier Test Ticket!",
                description=(
                    f"Hello {interaction.user.mention}!\n\n"
                    f"{random.choice(interesting_quotes)}\n\n"
                    "Please select your Region and Mode below, then submit your request."
                ),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            await channel.send("", view=TicketButtons())

            await interaction.response.send_message(
                f"✅ Ticket created: {channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(e)
            await interaction.response.send_message(
                "Failed to create ticket.",
                ephemeral=True
            )

            # Test sending a simple message first to check permissions
            test_msg = await channel.send("Testing permissions...")
            await test_msg.delete()

            ticket_owners[channel.id] = interaction.user.id

            welcome_embed = discord.Embed(
                title="🎫 Welcome to Your Tier Test Ticket!",
                description=f"Hello {interaction.user.mention}!\n\nPlease select your Region and Mode below and submit.\n\n{random.choice(interesting_quotes)}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            await channel.send(embed=welcome_embed, view=TierTicketView())
            await channel.send("", view=TicketButtons())

            await interaction.response.send_message(
                f"✅ Ticket created: {channel.mention}\n\nHead over to the channel to proceed!",
                ephemeral=True
            )

            logger.info(f"Ticket created by {interaction.user}: Channel {channel_name}")

        except Exception as e:
            logger.error(f"Error creating or setting up ticket channel: {e}")
            await interaction.response.send_message(
                "Ticket channel created, but setup failed. Check bot permissions.",
                ephemeral=True
            )

class TierRequestModal(discord.ui.Modal, title="Tier Test Request Form"):

    mc_discord = TextInput(label="Minecraft & Discord Username", max_length=50)
    age = TextInput(label="Age", max_length=3)
    region = TextInput(label="Region (Asia / EU / NA / SA)", max_length=20)
    mode = TextInput(label="Gamemode (Crystal / NethPot / SMP / Sword)", max_length=20)
    hours = TextInput(label="Hours Available Daily", max_length=10)

async def on_submit(self, interaction: discord.Interaction):
    embed = discord.Embed(
        title="📋 Tier Test Request",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(name="User", value=interaction.user.mention, inline=False)
    embed.add_field(name="MC + Discord", value=self.mc_discord.value, inline=False)
    embed.add_field(name="Age", value=self.age.value, inline=True)
    embed.add_field(name="Region", value=self.region.value, inline=True)
    embed.add_field(name="Gamemode", value=self.mode.value, inline=True)
    embed.add_field(name="Daily Hours", value=self.hours.value, inline=True)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Form submitted.", ephemeral=True)
        # Clear selections
        # Open modal for detailed questions
        await interaction.response.send_modal(TierTestModal())

        embed = discord.Embed(
            title="🎫 Tier Test Request Submitted",
            description=f"Requester: {interaction.user.mention}\nRegion: {region}\nMode: {mode}\n\n{random.choice(interesting_quotes)}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Request submitted", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.send_message(embed=embed)
        # Disable the view after submission to prevent further changes
        self.clear_items()
        await interaction.message.edit(view=self)
        # Clean up selections
        user_selections.pop(key, None)
        logger.info(f"Tier test request submitted by {interaction.user}: Region {region}, Mode {mode}")
        if "staff_role" in ticket_config:
            staff_role = interaction.guild.get_role(ticket_config["staff_role"])
            if staff_role:
                await interaction.followup.send(f"{staff_role.mention}, a new tier test request has been submitted!", ephemeral=True)

class StaffApplicationModal(discord.ui.Modal, title="Crystal Hub • Tester Staff Application"):

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

    experience = discord.ui.TextInput(
        label="PvP Experience (Years)",
        max_length=20
    )

    staff_exp = discord.ui.TextInput(
        label="Previous Staff Experience",
        style=discord.TextStyle.paragraph
    )

    reason = discord.ui.TextInput(
        label="Why Should Crystal Hub Select You As Tester?",
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

    @discord.ui.button(label="Fill Tier Test Form", style=discord.ButtonStyle.blurple)
    async def open_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TierRequestModal())
    
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

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
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

    @discord.ui.button(label="Apply for Tester", style=discord.ButtonStyle.blurple)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StaffApplicationModal())


class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClaimButton())
        self.add_item(CloseButton())

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
    guild = discord.Object(id=GUILD_ID)
    # Sync commands globally first, then to the specific guild for faster updates
    await tree.sync()
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    # Add persistent views to handle interactions even after restart
    client.add_view(MainPanel())
    client.add_view(TicketButtons())
    asyncio.create_task(auto_close_task())
    logger.info(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Track ticket activity in servers
    if message.guild and message.channel.id in ticket_owners:
        last_activity[message.channel.id] = message.created_at.timestamp()

    # If NOT DM → allow slash commands to work
    if not isinstance(message.channel, discord.DMChannel):
        await client.process_commands(message)
        return

    user_id = message.author.id

    # Not in application flow
    if user_id not in application_states:
        return

    state = application_states[user_id]
    step = state['step']
    answers = state['answers']

    # Save answer
    answers.append(message.content.strip())
    step += 1

    # Ask next question
    if step < len(questions):
        state['step'] = step
        await message.channel.send(f"**Question {step + 1}:** {questions[step]}")
        return

    # Application finished
    del application_states[user_id]

    embed = discord.Embed(
        title="📝 New Staff Application",
        description=f"Submitted by {message.author} ({user_id})",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    # Add Q/A safely
    for i in range(len(questions)):
        answer = answers[i] if answers[i] else "No response"
        embed.add_field(
            name=f"Q{i+1}: {questions[i]}",
            value=answer,
            inline=False
        )

    embed.set_footer(
        text=f"Applicant ID: {user_id}",
        icon_url=message.author.avatar.url if message.author.avatar else None
    )

    # Send to logs safely
    logs_id = application_config.get("logs_channel")
    role_id = application_config.get("staff_role")

    if logs_id:
        logs_channel = client.get_channel(logs_id)
        guild = client.get_guild(GUILD_ID)
        staff_role = guild.get_role(role_id) if guild and role_id else None

        if logs_channel:
            await logs_channel.send(
                content=staff_role.mention if staff_role else None,
                embed=embed
            )

    await message.channel.send("✅ Your staff application has been submitted successfully.")
    await client.process_commands(message)

# -------------------- COMMANDS --------------------
@tree.command(name="warn", description="Warn a user in a ticket and auto-close the ticket after time.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    user="The user to warn",
    duration="Time in minutes for timeout",
    reason="Reason for warning"
)
@app_commands.checks.has_permissions(administrator=True)
async def warn(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str):
    # Ensure ticket exists
    ticket_channel = find_existing_ticket(interaction.guild, user.id)
    if not ticket_channel:
        await interaction.response.send_message(f"❌ {user.mention} has no active ticket.", ephemeral=True)
        return

    # Notify user in ticket
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"You have been warned by {interaction.user.mention} for: **{reason}**\nTicket will close in {duration} minutes.",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    await ticket_channel.send(content=user.mention, embed=embed)

    await interaction.response.send_message(f"✅ {user.mention} warned and ticket will close in {duration} minutes.", ephemeral=True)

    # Timeout user in guild
    await user.timeout(duration=datetime.timedelta(minutes=duration), reason=reason)

    # Wait duration and then delete ticket
    await asyncio.sleep(duration * 60)
    if ticket_channel.id in ticket_owners:
        logs_channel = interaction.guild.get_channel(ticket_config.get("logs_channel"))
        transcript = await generate_transcript(ticket_channel)
        file = discord.File(io.StringIO(transcript), filename=f"transcript-{ticket_channel.name}.txt")
        if logs_channel:
            await logs_channel.send(embed=discord.Embed(
                title="📝 Ticket Closed (Auto)",
                description=f"Ticket for {user.mention} closed after warning timeout.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            ), file=file)
        ticket_owners.pop(ticket_channel.id)
        await ticket_channel.delete()

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
    embed = discord.Embed(
        title="✅ Ticket System Configured",
        description=f"Category: {category.mention}\nStaff Role: {staff_role.mention}\nLogs Channel: {logs_channel.mention}",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Configuration completed", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
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

@tree.command(name="application_panel", description="Send staff application panel", guild=discord.Object(id=GUILD_ID))
async def application_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Crystal Hub • Staff Applications",
        description=(
            "Interested in becoming a **Crystal Hub Staff?**\n\n"
            "Click the button below and fill the form.\n"
            "Ensure all details are accurate before submitting."
        ),
        color=discord.Color.purple()
    )

    await interaction.response.send_message(embed=embed, view=ApplicationPanel())
# -------------------- START BOT --------------------

if __name__ == "__main__":
    client.run(TOKEN)
