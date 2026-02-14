import discord
from discord.ext import commands
from discord import app_commands
from config import BRAND_COLOR, GOLD_COLOR
from utils.database import save_tier_result

STAFF_ROLE_IDS = [123456789]  # replace
TIER_LOG_CHANNEL_ID = 123456789  # replace

class TierModal(discord.ui.Modal, title="Crystal Hub • Tier Result"):

    region = discord.ui.TextInput(
        label="Region",
        placeholder="EU / NA / ASIA",
        required=True
    )

    gamemode = discord.ui.TextInput(
        label="Gamemode",
        placeholder="NoDebuff / Crystal / SMP",
        required=True
    )

    result = discord.ui.TextInput(
        label="Final Tier",
        placeholder="Tier 1 / Tier 2 / Tier 3",
        required=True
    )

    def __init__(self, candidate: discord.Member):
        super().__init__()
        self.candidate = candidate

    async def on_submit(self, interaction: discord.Interaction):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can submit tier results.",
                ephemeral=True
            )

        save_tier_result(
            interaction.user.id,
            self.candidate.id,
            self.region.value,
            self.gamemode.value,
            self.result.value
        )

        embed = discord.Embed(
            title="⛨ Crystal Hub • Official Tier Result",
            color=GOLD_COLOR,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Tester", value=interaction.user.mention, inline=True)
        embed.add_field(name="Candidate", value=self.candidate.mention, inline=True)
        embed.add_field(name="Region", value=self.region.value, inline=True)
        embed.add_field(name="Gamemode", value=self.gamemode.value, inline=True)
        embed.add_field(name="Tier Achieved", value=f"**{self.result.value}**", inline=False)

        embed.set_thumbnail(url=self.candidate.display_avatar.url)
        embed.set_footer(text="Crystal Hub • Competitive Testing Network")

        await interaction.response.send_message(embed=embed)

        log_channel = interaction.guild.get_channel(TIER_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)

class Tier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.checks.cooldown(1, 10)(name="tier", description="Submit a tier result")
    async def tier(self, interaction: discord.Interaction, member: discord.Member):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can use this command.",
                ephemeral=True
            )

        await interaction.response.send_modal(TierModal(member))

    @app_commands.command(name="tierstats", description="View tier statistics")
    async def tierstats(self, interaction: discord.Interaction):

    stats = get_tier_stats()

    embed = discord.Embed(
        title="📊 Crystal Hub • Tier Statistics",
        color=GOLD_COLOR
    )

    for gamemode, count in stats:
        embed.add_field(name=gamemode, value=f"{count} tests", inline=False)

    await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Tier(bot))
