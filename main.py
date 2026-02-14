import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    # Load all cogs
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            await bot.load_extension(f"cogs.{file[:-3]}")

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(e)

    print("Crystal Hub Enterprise Bot Ready")
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                "Something went wrong. Staff have been notified.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Something went wrong. Staff have been notified.",
                ephemeral=True
            )
    except:
        pass

    print(f"[ERROR] {error}")
bot.run(TOKEN)
