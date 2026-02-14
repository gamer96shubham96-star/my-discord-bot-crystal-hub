import discord
from discord.ext import commands
from discord import app_commands
from config import BRAND_COLOR, SUCCESS_COLOR, ERROR_COLOR
from utils.database import create_ticket, claim_ticket, close_ticket
from utils.transcript import generate_transcript
import asyncio

STAFF_ROLE_IDS = [123456789]  # replace with your staff role ID
LOG_CHANNEL_ID = 123456789    # replace with your logs channel ID

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can claim tickets.",
                ephemeral=True
            )

        claim_ticket(interaction.channel.id, interaction.user.id)

        embed = interaction.message.embeds[0]
        embed.set_field_at(
            1,
            name="Claimed By",
            value=interaction.user.mention,
            inline=True
        )

        button.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can close tickets.",
                ephemeral=True
            )

        await interaction.response.send_message("Closing ticket in 2 seconds...")
        await asyncio.sleep(2)

        transcript = await generate_transcript(interaction.channel)

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(
            f"📁 Ticket closed by {interaction.user.mention}",
            file=transcript
        )

        close_ticket(interaction.channel.id)
        await interaction.channel.delete()

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="panel", description="Send ticket panel")
    async def panel(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🎫 Crystal Hub • Support Panel",
            description="Click below to create a support ticket.",
            color=BRAND_COLOR
        )

        view = CreateTicketView()
        await interaction.response.send_message(embed=embed, view=view)

class CreateTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.success)
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category
        )

        ticket_id = create_ticket(interaction.user.id, channel.id)

        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id}",
            color=BRAND_COLOR
        )

        embed.add_field(name="Status", value="🟢 OPEN", inline=True)
        embed.add_field(name="Claimed By", value="None", inline=True)
        embed.set_footer(text="Crystal Hub • Enterprise Ticket System")

        await channel.send(
            interaction.user.mention,
            embed=embed,
            view=TicketView()
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

async def auto_close():
    await asyncio.sleep(1800)  # 30 minutes

    if channel:
        try:
            await channel.send("⏳ Ticket closed due to inactivity.")
            await channel.delete()
        except:
            pass

interaction.client.loop.create_task(auto_close())

async def setup(bot):
    await bot.add_cog(Tickets(bot))
