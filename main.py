import os
import io
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv
import logging
import random

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
    "What is your Minecraft username?",
    "How old are you?",
    "What region are you from?",
    "What gamemodes can you test? (Crystal, NethPot, SMP, Sword)",
    "How much experience do you have in PvP?",
    "Why do you want to become a staff tester?",
    "How many hours can you give daily?",
    "Have you been staff before? If yes, where?"
]

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
            if channel:
                logs_channel = client.get_channel(ticket_config["logs_channel"])
                try:
                    transcript_text = await generate_transcript(channel)
                    transcript_file = discord.File(fp=io.StringIO(transcript_text), filename=f"transcript-{channel.name}.txt")
                    owner_id = ticket_owners.get(cid, "Unknown")
                    embed = discord.Embed(
                        title="📝 Ticket Transcript",
                        description=f"**Channel:** {channel.name}\n**Closed by:** Auto-close (inactive)\n**Owner ID:** {owner_id}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
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
        # Assuming this is the main ticket panel; add buttons as needed
        # For example, a button to create a ticket
        self.add_item(Button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn"))

class RegionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Asia", value="Asia"),
            discord.SelectOption(label="Europe", value="Europe"),
            discord.SelectOption(label="North America", value="North America"),
            discord.SelectOption(label="South America", value="South America"),
        ]
        super().__init__(placeholder="Select Region", options=options, custom_id="tier_region_select")

    async def callback(self, interaction: discord.Interaction):
        key = (interaction.user.id, interaction.channel.id)
        if key not in user_selections:
            user_selections[key] = {}
        user_selections[key]['region'] = self.values[0]
        await interaction.response.defer()

class ModeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Crystal PvP", value="Crystal PvP"),
            discord.SelectOption(label="NethPot PvP", value="NethPot PvP"),
            discord.SelectOption(label="SMP PvP", value="SMP PvP"),
            discord.SelectOption(label="Sword", value="Sword"),
        ]
        super().__init__(placeholder="Select Mode", options=options, custom_id="tier_mode_select")

    async def callback(self, interaction: discord.Interaction):
        key = (interaction.user.id, interaction.channel.id)
        if key not in user_selections:
            user_selections[key] = {}
        user_selections[key]['mode'] = self.values[0]
        await interaction.response.defer()

class TierTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegionSelect())
        self.add_item(ModeSelect())

    @discord.ui.button(label="Submit Request", style=discord.ButtonStyle.green, custom_id="tier_submit_btn")
    async def submit(self, interaction: discord.Interaction, button: Button):
        key = (interaction.user.id, interaction.channel.id)
        region = user_selections.get(key, {}).get('region')
        mode = user_selections.get(key, {}).get('mode')
        if not region or not mode:
            await interaction.response.send_message("Please select both Region and Mode before submitting.", ephemeral=True)
            return
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
    guild = discord.Object(id=GUILD_ID)
    # Sync commands globally first, then to the specific guild for faster updates
    await tree.sync()
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    # Add persistent views to handle interactions even after restart
    client.add_view(MainPanel())
    client.add_view(TierTicketView())
    asyncio.create_task(auto_close_task())
    logger.info(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id in ticket_owners:
        last_activity[message.channel.id] = message.created_at.timestamp()

    user_id = message.author.id

    if user_id in application_states:
        state = application_states[user_id]
        step = state['step']
        answers = state['answers']
        answers.append(message.content)
        step += 1

        if step < len(questions):
            state['step'] = step
            await message.channel.send(f"**Question {step + 1}:** {questions[step]}")
        else:
            del application_states[user_id]
            # (rest of your embed code)

    # 🔥 THIS IS THE MISSING LINE
    await client.process_commands(message)

            embed = discord.Embed(
                title="📝 New Staff Application",
                description=f"Submitted by {message.author.mention}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Minecraft Username", value=answers[0], inline=False)
            embed.add_field(name="Age", value=answers[1], inline=False)
            embed.add_field(name="Region", value=answers[2], inline=False)
            embed.add_field(name="Gamemodes", value=answers[3], inline=False)
            embed.add_field(name="PvP Experience", value=answers[4], inline=False)
            embed.add_field(name="Why Become Tester", value=answers[5], inline=False)
            embed.add_field(name="Daily Hours", value=answers[6], inline=False)
            embed.add_field(name="Previous Staff Experience", value=answers[7], inline=False)
            embed.set_footer(text=f"Applicant ID: {user_id}", icon_url=message.author.avatar.url if message.author.avatar else None)
            # Send to logs
            logs_channel = client.get_channel(application_config["logs_channel"])
            staff_role = client.get_role(application_config["staff_role"])
            if logs_channel and staff_role:
                await logs_channel.send(f"{staff_role.mention}", embed=embed)
            await message.channel.send("✅ Your staff application has been submitted successfully.")

# -------------------- COMMANDS --------------------

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
    result_text = f"""|| @everyone || ## ⛨ Crystal Hub {mode.value} Tier • TIER RESULTS ⛨ ### ⚚ Tester {tester.mention} ### ◈ Candidate {user.mention} ### :earth_africa: Region {region.value} ### ⛨ Gamemode {mode.value} ### ⌬ Account Type {account.value} ------------------ ### ⬖ Previous Tier **{previous_tier}** --- ### ⬗ Tier Achieved **{earned_tier}** --- ### ✦ Match Score {score} ------------------ ## ⛨ RESULT: {result.value} ⛨ ### Think you can outperform this result? Test again in 1 month! """
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

@tree.command(name="setup_applications", description="Setup application system", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_applications(
    interaction: discord.Interaction,
    logs_channel: discord.TextChannel,
    staff_role: discord.Role,
):
    application_config["logs_channel"] = logs_channel.id
    application_config["staff_role"] = staff_role.id
    embed = discord.Embed(
        title="✅ Application System Configured",
        description=f"Logs Channel: {logs_channel.mention}\nStaff Role: {staff_role.mention}",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Configuration completed", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    # Log the setup
    logger.info(f"Application system configured by {interaction.user}: Logs Channel {logs_channel.name}, Staff Role {staff_role.name}")

@tree.command(name="applications", description="Start staff application", guild=discord.Object(id=GUILD_ID))
async def applications(interaction: discord.Interaction):
    if "logs_channel" not in application_config or "staff_role" not in application_config:
        await interaction.response.send_message("Application system is not configured by admins.", ephemeral=True)
        return

    user_id = interaction.user.id

    if user_id in application_states:
        await interaction.response.send_message("You already have a pending application.", ephemeral=True)
        return

    application_states[user_id] = {'step': 0, 'answers': []}
    await interaction.response.send_message(f"**Question 1:** {questions[0]}")
