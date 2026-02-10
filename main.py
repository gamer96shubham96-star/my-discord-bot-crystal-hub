import os
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv
import logging
import random  # For adding some "interesting" random elements, like quotes

# Set up logging for better debugging and professionalism
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "1466825673384394824"))
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ticket_config: dict[str, int] = {}
user_selections: dict[tuple[int, int], dict] = {}  # Key: (user_id, channel_id), Value: {'region': str, 'mode': str}

# List of interesting quotes for flair in tickets
interesting_quotes = [
    "Skill is not just about winning, it's about growth.",
    "Every challenge is an opportunity to rise.",
    "PvP is not a game, it's a battlefield of wits.",
    "Tier up or step down – the choice is yours.",
    "In the world of PvP, only the strong survive... or adapt."
]

@client.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    # Sync commands globally first, then to the specific guild for faster updates
    await tree.sync()
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    # Add persistent views to handle interactions even after restart
    client.add_view(MainPanel())
    client.add_view(TicketButtons())
    client.add_view(TierTicketView())

    logger.info(f"✅ Logged in as {client.user}")

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
    result_text = f"""|| @everyone ||
## ⛨  Crystal Hub {mode.value} Tier • OFFICIAL TIER RESULTS  ⛨

### ⚚ Tester
{tester.mention}
### ◈ Candidate
{user.mention}
### :earth_africa: Region
`{region.value}`
### ⛨ Gamemode
`{mode.value}`
### ⌬ Account Type
`{account.value}`
------------------
### ⬖ Previous Tier
**{previous_tier}**
---
### ⬗ Tier Achieved
**{earned_tier}**
---
### ✦ Match Score
`{score}`
------------------
## ⛨ RESULT: {result.value} ⛨

### Think you can outperform this result?  
Test again in 1 month!

[https://giphy.com/gifs/intresting-MScmyZctK91GfATYob]"""

    # Send the formatted message
    await interaction.response.send_message(result_text)

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

# -------------------- PERSISTENT COMPONENTS --------------------

class RegionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Asia", value="Asia"),
            discord.SelectOption(label="Europe", value="Europe"),
            discord.SelectOption(label="North America", value="North America"),
            discord.SelectOption(label="South America", value="South America"),
        ]
        super().__init__(
            placeholder="Select Region",
            options=options,
            custom_id="tier_region_select"
        )

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
        super().__init__(
            placeholder="Select Mode",
            options=options,
            custom_id="tier_mode_select"
        )

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
        super().__init__(label="Claim", style=discord.ButtonStyle.blurple, custom_id="ticket_claim_btn")

    async def callback(self, interaction: discord.Interaction):
        if "staff_role" not in ticket_config or not interaction.user.get_role(ticket_config["staff_role"]):
            await interaction.response.send_message("You do not have permission to claim this ticket.", ephemeral=True)
            return
        embed = discord.Embed(
            title="✅ Ticket Claimed",
            description=f"Claimed by: {interaction.user.mention}\n\n{random.choice(interesting_quotes)}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Ticket claimed", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.send_message(embed=embed)

        logger.info(f"Ticket claimed by {interaction.user} in channel {interaction.channel.name}")

class CloseButton(Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")

    async def callback(self, interaction: discord.Interaction):
        if "staff_role" not in ticket_config or not interaction.user.get_role(ticket_config["staff_role"]):
            await interaction.response.send_message("You do not have permission to close this ticket.", ephemeral=True)
            return

        logs_channel = interaction.guild.get_channel(ticket_config.get("logs_channel"))
        if logs_channel:
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                content = message.content or "[Embed/Attachment]"
                messages.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author}: {content}")
            transcript = "\n".join(messages)

            embed = discord.Embed(
                title=f"📜 Ticket Transcript - {interaction.channel.name}",
                description=f"Closed by: {interaction.user.mention}\n\nTranscript:\n```\n{transcript[:4000]}\n```",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Transcript logged", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            await logs_channel.send(embed=embed)

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Closed by: {interaction.user.mention}\n\n{random.choice(interesting_quotes)}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Ticket closed", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.send_message(embed=embed)

        logger.info(f"Ticket closed by {interaction.user} in channel {interaction.channel.name}")

        await asyncio.sleep(5)
        await interaction.channel.delete()

class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):
        if "category" not in ticket_config or "staff_role" not in ticket_config or "logs_channel" not in ticket_config:
            await interaction.response.send_message("Ticket system is not fully configured. Please ask an admin to run `/setup_tickets` with category, staff role, and logs channel.", ephemeral=True)
            return

        category = interaction.guild.get_channel(ticket_config["category"])
        if not category:
            await interaction.response.send_message("Configured category not found.", ephemeral=True)
            return

        channel_name = f"tier-test-{interaction.user.name}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(ticket_config["staff_role"]): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            client.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # Ensure bot can send messages
        }
        try:
            channel = await category.create_text_channel(channel_name, overwrites=overwrites)
        except Exception as e:
            logger.error(f"Error creating ticket channel: {e}")
            await interaction.response.send_message("Failed to create ticket channel. Check permissions or try again.", ephemeral=True)
            return

        try:
            welcome_embed = discord.Embed(
                title="🎫 Welcome to Your Tier Test Ticket!",
                description=f"Hello {interaction.user.mention}! We're excited to help you with your tier test.\n\n{random.choice(interesting_quotes)}\n\nPlease select your Region and Mode below, then submit your request.\n\nNote: Selections are one-time only after submission.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            welcome_embed.set_footer(text="Ticket created", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            await channel.send(embed=welcome_embed, view=TierTicketView())

            ticket_embed = discord.Embed(
                title="Staff Controls",
                description="Use the buttons below to manage this ticket.\n\nRemember, every ticket is a step towards mastery!",
                color=discord.Color.grey(),
                timestamp=discord.utils.utcnow()
            )
            ticket_embed.set_footer(text="Staff panel", icon_url=client.user.avatar.url if client.user.avatar else None)
            await channel.send(embed=ticket_embed, view=TicketButtons())

            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}\n\nHead over to the channel to proceed!", ephemeral=True)

            logger.info(f"Ticket created by {interaction.user}: Channel {channel_name}")
        except Exception as e:
            logger.error(f"Error sending messages to ticket channel: {e}")
            await channel.delete()  # Clean up if sending fails
            await interaction.response.send_message("Failed to set up ticket. Please try again.", ephemeral=True)

@tree.command(name="panel", description="Send ticket panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket Panel",
        description="Click the button below to create a tier test ticket.\n\nReady to prove your skills? Let's begin!",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Panel sent", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    await interaction.response.send_message(embed=embed, view=MainPanel())

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except discord.HTTPException as e:
        if e.status == 429:
            logger.error("Rate limit hit. Waiting before retry...")
            asyncio.run(asyncio.sleep(60))  # Wait 60 seconds before retrying
            client.run(TOKEN)
        else:
            raise
