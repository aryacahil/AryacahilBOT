import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class AryaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        await self.load_extension("cogs.werewolf")
        await self.load_extension("cogs.wowocash")
        await self.load_extension("cogs.casino")
        await self.load_extension("cogs.roulette")
        await self.tree.sync()
        print("✅ Commands synced.")

    async def on_ready(self):
        print(f"🐺 Logged in as {self.user} (ID: {self.user.id})")

async def main():
    bot = AryaBot()
    await bot.start(TOKEN)

asyncio.run(main())