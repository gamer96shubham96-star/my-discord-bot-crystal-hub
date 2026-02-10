import os
import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv
import logging

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
    # Create an embed for a professional look
    embed = discord.Embed(
        title="🏆 Tier Test Result",
        color=discord.Color.blue()
    )
    embed.add_field(name="Tester", value=tester.mention, inline=True)
    embed.add_field(name="Player", value=user.mention, inline=True)
    embed.add_field(name="Region", value=region.value, inline=True)
    embed.add_field(name="Mode", value=mode.value, inline=True)
    embed.add_field(name="Account Type", value=account.value, inline=True)
    embed.add_field(name="Previous Tier", value=previous_tier, inline=True)
    embed.add_field(name="Earned Tier", value=earned_tier, inline=True)
    embed.add_field(name="Score", value=score, inline=True)
    embed.add_field(name="Result", value=result.value, inline=True)
    embed.set_footer(text=f"Posted by {interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

    await interaction.response.send_message(embed=embed)

@tree.command(name="setup_tickets", description="Setup ticket system", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    staff_role: discord.Role,
):
    ticket_config["category"] = category.id
    ticket_config["staff_role"] = staff_role.id
    embed = discord.Embed(
        title="✅ Ticket System Configured",
        description=f"Category: {category.mention}\nStaff Role: {staff_role.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
        # Store the selection in the interaction's custom data or a temp store
        # For simplicity, we'll use a dict keyed by user/channel
        if not hasattr(interaction, 'temp_data'):
            interaction.temp_data = {}
        interaction.temp_data['region'] = self.values[0]
        await interaction.response.defer()  # Acknowledge without message

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
        if not hasattr(interaction, 'temp_data'):
            interaction.temp_data = {}
        interaction.temp_data['mode'] = self.values[0]
        await interaction.response.defer()

class TierTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegionSelect())
        self.add_item(ModeSelect())

    @discord.ui.button(label="Submit Request", style=discord.ButtonStyle.green, custom_id="tier_submit_btn")
    async def submit(self, interaction: discord.Interaction, button: Button):
        # Check if selections are made
        region = getattr(interaction, 'temp_data', {}).get('region')
        mode = getattr(interaction, 'temp_data', {}).get('mode')
        if not region or not mode:
            await interaction.response.send_message("Please select both Region and Mode before submitting.", ephemeral=True)
            return

        # Send a message to the channel with the request details
        embed = discord.Embed(
            title="🎫 Tier Test Request Submitted",
            description=f"**Requester:** {interaction.user.mention}\n**Region:** {region}\n**Mode:** {mode}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
        # Optionally, notify staff (if staff_role is set)
        if "staff_role" in ticket_config:
            staff_role = interaction.guild.get_role(ticket_config["staff_role"])
            if staff_role:
                await interaction.followup.send(f"{staff_role.mention}, a new tier test request has been submitted!", ephemeral=True)

class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, custom_id="ticket_claim_btn")
    async def claim(self, interaction: discord.Interaction, button: Button):
        # Check if user has staff role
        if "staff_role" not in ticket_config or not interaction.user.get_role(ticket_config["staff_role"]):
            await interaction.response.send_message("You do not have permission to claim this ticket.", ephemeral=True)
            return
        embed = discord.Embed(
            title="✅ Ticket Claimed",
            description=f"Claimed by {interaction.user.mention}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close_btn")
    async def close(self, interaction: discord.Interaction, button: Button):
        # Check permissions
        if "staff_role" not in ticket_config or not interaction.user.get_role(ticket_config["staff_role"]):
            await interaction.response.send_message("You do not have permission to close this ticket.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description="This ticket has been closed.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)  # Give time to read
        await interaction.channel.delete()

class MainPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="♛ Tier Test", style=discord.ButtonStyle.blurple, custom_id="panel_tier_btn")
    async def tier(self, interaction: discord.Interaction, button: Button):
        # Check if ticket system is configured
        if "category" not in ticket_config or "staff_role" not in ticket_config:
            await interaction.response.send_message("Ticket system is not configured. Please ask an admin to run `/setup_tickets`.", ephemeral=True)
            return

        category = interaction.guild.get_channel(ticket_config["category"])
        if not category:
            await interaction.response.send_message("Configured category not found.", ephemeral=True)
            return

        # Create a ticket channel
        channel_name = f"tier-test-{interaction.user.name}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(ticket_config["staff_role"]): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        channel = await category.create_text_channel(channel_name, overwrites=overwrites)

        # Send the tier request view in the new channel
        embed = discord.Embed(
            title="🎫 Tier Test Request",
            description="Please select your Region and Mode, then submit your request.",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed, view=TierTicketView())

        # Send ticket buttons for staff
        ticket_embed = discord.Embed(
            title="Staff Controls",
            description="Use the buttons below to manage this ticket.",
            color=discord.Color.grey()
        )
        await channel.send(embed=ticket_embed, view=TicketButtons())

        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

@tree.command(name="panel", description="Send ticket panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket Panel",
        description="Click the button below to create a tier test ticket.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=MainPanel())

if __name__ == "__main__":
    client.run(TOKEN)
