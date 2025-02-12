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
    await data_manager.init_db()
    await data_manager.cargar_todos_los_datos()
    logger.info("Datos cargados correctamente.")

    tasks.iniciar_tareas(bot)
    logger.info("Tareas iniciadas.")

    await bot.load_extension("dkp_commands")
    logger.info("Extensión 'dkp_commands' cargada exitosamente.")

    print("Comandos registrados:", [cmd.name for cmd in bot.commands])
    print(f"Bot conectado como {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("El comando no existe.")
    else:
        raise error

bot.run(TOKEN)