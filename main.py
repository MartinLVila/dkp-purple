import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import ssl

load_dotenv()

import data_manager
import tasks

from aiohttp import web

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No se encontró DISCORD_BOT_TOKEN en el archivo .env")

WEB_PORT = int(os.getenv("WEB_PORT", 5000))

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

def serialize_history(history):
    serialized = []
    for record in history:
        new_record = record.copy()
        ts = new_record.get("timestamp")
        if isinstance(ts, datetime):
            new_record["timestamp"] = ts.isoformat()
        serialized.append(new_record)
    return serialized

async def handle_users(request):
    users_list = []
    for name, data in data_manager.user_data.items():
        let_equipo = data.get("equipo", {})
        history = data_manager.score_history.get(name, [])
        serialized_history = serialize_history(history)
        users_list.append({
            "name": name,
            "arma_principal": let_equipo.get("arma_principal", "N/A"),
            "arma_secundaria": let_equipo.get("arma_secundaria", "N/A"),
            "rol": let_equipo.get("rol", "N/A"),
            "score": data.get("score", 0),
            "history": serialized_history
        })
    response = web.json_response(users_list)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

async def start_web_server():
    app = web.Application()
    app.router.add_get('/api/users', handle_users)
    runner = web.AppRunner(app)
    await runner.setup()
    
    constCert = os.getenv("SSL_CERT_PATH")
    constKey = os.getenv("SSL_KEY_PATH")
    ssl_context = None
    if constCert and constKey:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=constCert, keyfile=constKey)
    
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT, ssl_context=ssl_context)
    await site.start()
    print(f"Servidor web iniciado en el puerto {WEB_PORT} con SSL: {ssl_context is not None}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("El comando no existe.")
    else:
        raise error

@bot.event
async def on_ready():
    await data_manager.init_db()
    await data_manager.cargar_todos_los_datos()
    logger.info("Datos cargados correctamente.")

    tasks.iniciar_tareas(bot)
    logger.info("Tareas iniciadas.")

    await bot.load_extension("dkp_commands")
    logger.info("Extensión 'dkp_commands' cargada exitosamente.")

    asyncio.create_task(start_web_server())
    
    print("Comandos registrados:", [cmd.name for cmd in bot.commands])
    print(f"Bot conectado como {bot.user} (ID: {bot.user.id})")

bot.run(TOKEN)