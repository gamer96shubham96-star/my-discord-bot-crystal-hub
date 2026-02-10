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
ticket_owners: dict[int, int] = {}  # channel_id -> user_id

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
    await tree.sync()
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    client.add_view(MainPanel())
    client.add_view(TierTicketView())
    logger.info(f"✅ Logged in as {client.user}")

# -------------------- SELECTS --------------------

class RegionSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select Region",
            options=[
                discord.SelectOption(label="Asia", value="Asia"),
                discord.SelectOption(label="Europe", value="Europe"),
                discord.SelectOption(label="North America", value="North America"),
                discord.SelectOption(label="South America", value="South America"),
            ],
            custom_id="tier_region_select"
        )

    async def callback(self, interaction: discord.Interaction):
        key = (interaction.user.id, interaction.channel.id)
        user_selections.setdefault(key, {})['region'] = self.values[0]
        await interaction.response.defer()

class ModeSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select GameMode",
            options=[
                discord.SelectOption(label="Crystal PvP", value="Crystal PvP"),
                discord.SelectOption(label="NethPot PvP", value="NethPot PvP"),
                discord.SelectOption(label="SMP PvP", value="SMP PvP"),
                discord.SelectOption(label="Sword", value="Sword"),
            ],
            custom_id="tier_mode_select"
        )

    async def callback(self, interaction: discord.Interaction):
        key = (interaction.user.id, interaction.channel.id)
        user_selections.setdefault(key, {})['mode'] = self.values[0]
        await interaction.response.defer()

# -------------------- VIEWS --------------------

class TierTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegionSelect())
        self.add_item(ModeSelect())

    @discord.ui.button(label="Submit Request", style=discord.ButtonStyle.green, custom_id="tier_submit_btn")
    async def submit(self, interaction: discord.Interaction, button: Button):
        key = (interaction.user.id, interaction.channel.id)
        data = user_selections.get(key, {})
        if 'region' not in data or 'mode' not in data:
            await interaction.response.send_message("Select Region and Mode first.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎫 Tier Test Request Submitted",
            description=f"Requester: {interaction.user.mention}\nRegion: {data['region']}\nMode: {data['mode']}\n\n{random.choice(interesting_quotes)}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
        self.clear_items()
        await interaction.message.edit(view=self)
        user_selections.pop(key, None)

class ClaimButton(Button):
    def __init__(self):
        super().__init__(label="Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim_btn")

    async def callback(self, interaction: discord.Interaction):
        if "staff_role" not in ticket_config or not interaction.user.get_role(ticket_config["staff_role"]):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        channel = interaction.channel
        owner_id = ticket_owners.get(channel.id)
        owner = interaction.guild.get_member(owner_id)
        claimer = interaction.user
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])

        await channel.edit(name=f"claimed-by-{claimer.name}".lower().replace(" ", "-"))
        await channel.set_permissions(staff_role, overwrite=discord.PermissionOverwrite(view_channel=False))
        await channel.set_permissions(owner, overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True))
        await channel.set_permissions(claimer, overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True))

        for item in self.view.children:
            if item.custom_id == "ticket_claim_btn":
                item.disabled = True

        await interaction.message.edit(view=self.view)
        await interaction.response.send_message(f"✅ Claimed by {claimer.mention}")

class CloseButton(Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Closing ticket...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClaimButton())
        self.add_item(CloseButton())

class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):
        category = interaction.guild.get_channel(ticket_config["category"])
        staff_role = interaction.guild.get_role(ticket_config["staff_role"])

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            client.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await category.create_text_channel(
            f"tier-test-{interaction.user.name}",
            overwrites=overwrites
        )

        ticket_owners[channel.id] = interaction.user.id

        embed = discord.Embed(
            title="🎫 Welcome to Your Tier Test Ticket!",
            description="Select Region and Mode, then submit."
        )

        await channel.send(embed=embed, view=TierTicketView())
        await channel.send(view=TicketButtons())
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

@tree.command(name="setup_tickets", guild=discord.Object(id=GUILD_ID))
async def setup_tickets(interaction: discord.Interaction, category: discord.CategoryChannel, staff_role: discord.Role):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    await interaction.response.send_message("Setup complete", ephemeral=True)

@tree.command(name="panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message("🎫 Tier Panel", view=MainPanel())

client.run(TOKEN)
