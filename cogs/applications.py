import discord
from discord.ext import commands
from discord import app_commands
from config import BRAND_COLOR, SUCCESS_COLOR, ERROR_COLOR
from utils.database import (
    create_application,
    update_application_status,
    has_application
)

STAFF_ROLE_IDS = [123456789]  # replace
APPLICATION_LOG_CHANNEL_ID = 123456789  # replace
STAFF_ROLE_TO_GIVE = 123456789  # role given on accept

# ------------------ MODAL ------------------

class ApplicationModal(discord.ui.Modal, title="Crystal Hub • Staff Application"):

    experience = discord.ui.TextInput(
        label="Previous Experience",
        style=discord.TextStyle.paragraph,
        required=True
    )

    availability = discord.ui.TextInput(
        label="Daily Availability",
        placeholder="Hours per day",
        required=True
    )

    reason = discord.ui.TextInput(
        label="Why should we accept you?",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        if has_application(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You already have a pending application.",
                ephemeral=True
            )

        app_id = create_application(
            interaction.user.id,
            self.experience.value,
            self.availability.value,
            self.reason.value
        )

        embed = discord.Embed(
            title=f"📋 Staff Application #{app_id}",
            color=BRAND_COLOR,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="Applicant", value=interaction.user.mention, inline=False)
        embed.add_field(name="Experience", value=self.experience.value, inline=False)
        embed.add_field(name="Availability", value=self.availability.value, inline=False)
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        embed.add_field(name="Status", value="🟡 PENDING", inline=False)

        embed.set_footer(text="Crystal Hub • Recruitment System")

        log_channel = interaction.guild.get_channel(APPLICATION_LOG_CHANNEL_ID)

        view = ReviewView(app_id, interaction.user)

        await log_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            "✅ Application submitted successfully!",
            ephemeral=True
        )

# ------------------ REVIEW BUTTONS ------------------

class ReviewView(discord.ui.View):
    def __init__(self, app_id, applicant):
        super().__init__(timeout=None)
        self.app_id = app_id
        self.applicant = applicant

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can review applications.",
                ephemeral=True
            )

        update_application_status(self.app_id, "ACCEPTED", interaction.user.id)

        role = interaction.guild.get_role(STAFF_ROLE_TO_GIVE)
        member = interaction.guild.get_member(self.applicant.id)

        if role and member:
            await member.add_roles(role)

        embed = interaction.message.embeds[0]
        embed.set_field_at(
            4,
            name="Status",
            value=f"🟢 ACCEPTED\nReviewed by {interaction.user.mention}",
            inline=False
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id in STAFF_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message(
                "❌ Only staff can review applications.",
                ephemeral=True
            )

        update_application_status(self.app_id, "REJECTED", interaction.user.id)

        embed = interaction.message.embeds[0]
        embed.set_field_at(
            4,
            name="Status",
            value=f"🔴 REJECTED\nReviewed by {interaction.user.mention}",
            inline=False
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

# ------------------ PANEL COMMAND ------------------

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="applicationpanel", description="Send application panel")
    async def application_panel(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="💼 Crystal Hub • Staff Recruitment",
            description="Click below to apply for staff.",
            color=BRAND_COLOR
        )

        view = ApplyButtonView()

        await interaction.response.send_message(embed=embed, view=view)

class ApplyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.primary)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal())
    @app_commands.command(name="appstats", description="View application statistics")
    async def appstats(self, interaction: discord.Interaction):

    stats = get_application_stats()

    embed = discord.Embed(
        title="📋 Recruitment Statistics",
        color=BRAND_COLOR
    )

    for status, count in stats:
        embed.add_field(name=status, value=f"{count}", inline=False)

    await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Applications(bot))
