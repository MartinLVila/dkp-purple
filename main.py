import os
import logging
import discord

from discord.ext import commands
from dotenv import load_dotenv

import data_manager
import tasks

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No se encontró DISCORD_BOT_TOKEN en el archivo .env")

logging.basicConfig(
    filename='bot_commands.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("main")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True
)

@bot.event
async def on_ready():
    data_manager.cargar_todos_los_datos()
    logger.info("Datos cargados correctamente.")

    tasks.iniciar_tareas(bot)
    logger.info("Tareas iniciadas.")

    await bot.load_extension("commands")
    logger.info("Extensión 'commands' cargada exitosamente.")

    print(f"Bot conectado como {bot.user} (ID: {bot.user.id})")

bot.run(TOKEN)