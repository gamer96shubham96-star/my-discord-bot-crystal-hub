import os
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv
import logging
import random

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
user_selections: dict[tuple[int, int], dict] = {}

quotes = [
    "Tier Is Essential For A Player's Identity!",
    "Get Well Known With Your Tier.",
    "Tier Test In Every One Month!"
]

# ================= READY =================

@client.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    await tree.sync()
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    client.add_view(MainPanel())
    client.add_view(TicketButtons())
    client.add_view(TierTicketView())

    logger.info(f"Logged in as {client.user}")

# ================= TIER RESULT =================

@tree.command(name="tier", guild=discord.Object(id=GUILD_ID))
async def tier(
    interaction: discord.Interaction,
    tester: discord.Member,
    user: discord.Member,
    region: str,
    mode: str,
    account: str,
    previous_tier: str,
    earned_tier: str,
    score: str,
    result: str,
):
    text = f"""|| @everyone ||
## ⛨  Crystal Hub {mode} Tier • OFFICIAL TIER RESULTS  ⛨

### ⚚ Tester
{tester.mention}
### ◈ Candidate
{user.mention}
### :earth_africa: Region
`{region}`
### ⛨ Gamemode
`{mode}`
### ⌬ Account Type
`{account}`
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
## ⛨ RESULT: {result} ⛨

### Think you can outperform this result?  
Test again in 1 month!
"""

    embed = discord.Embed(description=text, color=discord.Color.gold())
    embed.set_image(url="https://media.giphy.com/media/oWWA8hYwrlk8Yrp6lo/giphy.gif")
    await interaction.response.send_message(embed=embed)

# ================= SETUP =================

@tree.command(name="setup_tickets", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    staff_role: discord.Role,
):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    await interaction.response.send_message("Ticket system configured.", ephemeral=True)

# ================= SELECTS =================

class RegionSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select Region",
            options=[
                discord.SelectOption(label="Asia", value="Asia"),
                discord.SelectOption(label="Europe", value="Europe"),
            ],
            custom_id="region_select"
        )

    async def callback(self, interaction: discord.Interaction):
        user_selections[(interaction.user.id, interaction.channel.id)] = {
            "region": self.values[0]
        }
        await interaction.response.defer()

class ModeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select Mode",
            options=[
                discord.SelectOption(label="Crystal PvP", value="Crystal PvP"),
                discord.SelectOption(label="Sword", value="Sword"),
            ],
            custom_id="mode_select"
        )

    async def callback(self, interaction: discord.Interaction):
        user_selections[(interaction.user.id, interaction.channel.id)]["mode"] = self.values[0]
        await interaction.response.defer()

# ================= TICKET VIEW =================

class TierTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegionSelect())
        self.add_item(ModeSelect())

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, custom_id="submit_btn")
    async def submit(self, interaction: discord.Interaction, button: Button):
        data = user_selections.get((interaction.user.id, interaction.channel.id))
        if not data or "mode" not in data:
            await interaction.response.send_message("Select both options.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Request Submitted\nRegion: {data['region']}\nMode: {data['mode']}"
        )

# ================= STAFF BUTTONS =================

class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, custom_id="claim_btn")
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Claimed by {interaction.user.mention}")

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_btn")
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Closing...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

# ================= PANEL =================

class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):
        category = interaction.guild.get_channel(ticket_config["category"])

        channel = await category.create_text_channel(
            f"tier-{interaction.user.name}"
        )

        embed = discord.Embed(
            title="Welcome",
            description=random.choice(quotes),
            color=discord.Color.blue()
        )
        embed.set_image(url="https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif")

        await channel.send(embed=embed, view=TierTicketView())
        await channel.send("Staff Controls:", view=TicketButtons())

        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

# ================= RUN =================

client.run(TOKEN)
