# bot.py
import os
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ticket_config: dict[str, int] = {}


@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))

    # Persistent views MUST have custom_id + no timeout
    client.add_view(MainPanel())
    client.add_view(TicketButtons())
    client.add_view(TierTicketViewPlaceholder())

    print(f"✅ Logged in as {client.user}")


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
    await interaction.response.send_message(f"Result: {tester.mention} vs {user.mention}")


@tree.command(name="setup_tickets", description="Setup ticket system", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    staff_role: discord.Role,
):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    await interaction.response.send_message("✅ Configured", ephemeral=True)


# -------------------- PERSISTENT COMPONENTS --------------------

class RegionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Asia"),
            discord.SelectOption(label="Europe"),
            discord.SelectOption(label="North America"),
            discord.SelectOption(label="South America"),
        ]
        super().__init__(
            placeholder="Select Region",
            options=options,
            custom_id="tier_region_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Region: {self.values[0]}", ephemeral=True)


class ModeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Crystal PvP"),
            discord.SelectOption(label="NethPot PvP"),
            discord.SelectOption(label="SMP PvP"),
            discord.SelectOption(label="Sword"),
        ]
        super().__init__(
            placeholder="Select Mode",
            options=options,
            custom_id="tier_mode_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Mode: {self.values[0]}", ephemeral=True)


class TierTicketViewPlaceholder(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegionSelect())
        self.add_item(ModeSelect())

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green, custom_id="tier_submit_btn")
    async def submit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Submitted", ephemeral=True)


class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, custom_id="ticket_claim_btn")
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Claimed", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.delete()


class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Ticket created", ephemeral=True)


@tree.command(name="panel", description="Send ticket panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message("Panel", view=MainPanel())


if __name__ == "__main__":
    client.run(TOKEN)
