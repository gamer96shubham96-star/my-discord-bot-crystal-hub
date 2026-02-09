# bot.py
import os
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv

# Load environment variables from a .env file (if present)
load_dotenv()

# -------------------- CONFIG --------------------
TOKEN = os.getenv("TOKEN")  # Your Discord bot token from env
GUILD_ID = int(os.getenv("GUILD_ID", 1466825673384394824))

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ticket_config: dict[str, int] = {}

# -------------------- READY --------------------
@client.event
async def on_ready():
    guild = client.get_guild(GUILD_ID)
    if guild is None:
        guild = discord.Object(id=GUILD_ID)

    # Clear old guild commands
    await tree.clear_commands(guild=guild)

    # Optional: clear global commands if needed
    # await tree.clear_commands(guild=None)

    # Sync new commands
    await tree.sync(guild=guild)

    # Add persistent views
    client.add_view(MainPanel())
    client.add_view(TicketButtons())

    print(f"✅ Logged in as {client.user} - Commands reset and synced!")

# -------------------- TIER RESULT COMMAND --------------------
@tree.command(name="tier", description="Post official tier result")
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
        app_commands.Choice(name="NethPot PvP", value="NethPot"),
        app_commands.Choice(name="SMP PvP", value="SMP PvP"),
        app_commands.Choice(name="Sword", value="Sword"),  # Added Sword
    ],
    account=[
        app_commands.Choice(name="Premium", value="Premium"),
        app_commands.Choice(name="Cracked", value="Cracked"),
    ],
    result=[
        app_commands.Choice(name="WON", value="WON"),
        app_commands.Choice(name="LOST", value="LOST"),  # Changed LOSE → LOST
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
    msg = f"""
|| @everyone ||

## ⛨ Crystal Hub • OFFICIAL Tier RESULT ⛨

### Tester
{tester.mention}
### Candidate
{user.mention}
### Region
`{region.value}`
### Gamemode
`{mode.value}`
### Account
`{account.value}`
---
### Previous Tier
**{previous_tier.upper()}**
### Tier Achieved
**{earned_tier.upper()}**
### Score
`{score}`
---

# RESULT: **{result.value}**
"""
    await interaction.response.send_message(msg)

# -------------------- TICKET SETUP COMMAND --------------------
@tree.command(name="setup_tickets", description="Setup ticket system")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    staff_role: discord.Role,
):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    await interaction.response.send_message("✅ Ticket system configured", ephemeral=True)

# -------------------- REGION & MODE SELECTS --------------------
class RegionSelect(Select):
    def __init__(self, view):
        options = [
            discord.SelectOption(label="Asia"),
            discord.SelectOption(label="Europe"),
            discord.SelectOption(label="North America"),
            discord.SelectOption(label="South America"),
        ]
        super().__init__(placeholder="Select your Region", options=options, custom_id="region_select")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.region = self.values[0]
        await self.view_ref.refresh(interaction)

class ModeSelect(Select):
    def __init__(self, view):
        options = [
            discord.SelectOption(label="Crystal PvP"),
            discord.SelectOption(label="NethPot PvP"),
            discord.SelectOption(label="SMP PvP"),
            discord.SelectOption(label="Sword"),  # Added Sword
        ]
        super().__init__(placeholder="Select your Gamemode", options=options, custom_id="mode_select")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.mode = self.values[0]
        await self.view_ref.refresh(interaction)

# -------------------- TIER TEST VIEW --------------------
class TierTicketView(View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        self.member = member
        self.region = "Not Selected"
        self.mode = "Not Selected"

        self.add_item(RegionSelect(self))
        self.add_item(ModeSelect(self))

    async def refresh(self, interaction: discord.Interaction):
        content = f"""
# ⛨ TIER TEST TICKET ⛨

Welcome {self.member.mention}

### Region
`{self.region}`

### Gamemode
`{self.mode}`
"""
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Submit Details", style=discord.ButtonStyle.green, custom_id="tier_submit")
    async def submit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"✅ Details Submitted\nRegion: `{self.region}`\nGamemode: `{self.mode}`",
            ephemeral=True
        )

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="tier_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.delete()

# -------------------- NORMAL TICKET BUTTONS --------------------
class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Claimed by {interaction.user.mention}")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: Button):
        await asyncio.sleep(2)
        await interaction.channel.delete()

# -------------------- PANEL BUTTONS --------------------
class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, reason: str):
        guild = interaction.guild
        member = interaction.user
        category = guild.get_channel(ticket_config["category"])
        staff_role = guild.get_role(ticket_config["staff_role"])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True),
            staff_role: discord.PermissionOverwrite(view_channel=True),
        }

        channel = await guild.create_text_channel(
            name=f"{reason}-{member.name}",
            category=category,
            overwrites=overwrites,
        )

        if reason == "tier-test":
            await channel.send(
                f"# ⛨ Tier Test Ticket ⛨\nWelcome {member.mention}",
                view=TierTicketView(member)
            )
        else:
            await channel.send(
                f"# Ticket: {reason}\n{member.mention}",
                view=TicketButtons()
            )

        await interaction.response.send_message("✅ Ticket created", ephemeral=True)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier")
    async def tier(self, interaction: discord.Interaction, button: Button):
        await self.create_ticket(interaction, "tier-test")

# -------------------- PANEL COMMAND --------------------
@tree.command(name="panel", description="Send ticket panel")
async def panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)  # defers the interaction
    embed = discord.Embed(
        title="⛨ Tier-Test Panel ⛨",
        description="### Click the button below to test your tier.",
        color=discord.Color.blue()
    )
    embed.set_image(url="https://media.giphy.com/media/IkSLbEzqgT9LzS1NKH/giphy.gif")
    await interaction.followup.send(embed=embed, view=MainPanel())
# -------------------- RUN --------------------
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("Bot token not found! Set TOKEN in environment variables.")
    client.run(TOKEN)
