import discord
import io

async def generate_transcript(channel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(f"{msg.author}: {msg.content}")

    transcript_text = "\n".join(messages)
    file = discord.File(
        io.BytesIO(transcript_text.encode()),
        filename=f"{channel.name}-transcript.txt"
    )
    return file
