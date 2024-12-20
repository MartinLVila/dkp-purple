import os
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

CANAL_ADMIN = 647611825172774934
CANAL_AUSENCIAS = 647611825172774934
CANAL_CONSULTA = 647611825172774934

ADMINS_IDS = {154770363081949184, 1122334455}

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "scores.json"
user_data = {}

def cargar_datos():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                user_data = data
        except json.JSONDecodeError:
            user_data = {}
    else:
        user_data = {}

def guardar_datos():
    with open(DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

@bot.event
async def on_ready():
    cargar_datos()
    print(f"Bot conectado como {bot.user}")

def es_admin(ctx):
    return (ctx.author.id in ADMINS_IDS)

############################
# Comando para ausencia en un evento (justificado)
############################
@bot.command(name="ausencia")
async def ausencia(ctx, nombre_evento: str):
    if ctx.channel.id != CANAL_AUSENCIAS:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para ausencias.",
            color=discord.Color.red()
        ))
        return

    nombre_usuario = None
    for nombre, datos in user_data.items():
        if datos.get("discord_id") == ctx.author.id:
            nombre_usuario = nombre
            break

    if nombre_usuario is None:
        await ctx.send(embed=discord.Embed(
            title="No vinculado",
            description="No se encontró un nombre vinculado a tu usuario. Pide a un oficial que te vincule primero.",
            color=discord.Color.red()
        ))
        return

    if "justificado" not in user_data[nombre_usuario]:
        user_data[nombre_usuario]["justificado"] = []
    if nombre_evento not in user_data[nombre_usuario]["justificado"]:
        user_data[nombre_usuario]["justificado"].append(nombre_evento)

    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Ausencia Justificada",
        description=f"Has quedado justificado para el evento **{nombre_evento}**, {nombre_usuario}.",
        color=discord.Color.yellow()
    ))

@bot.command(name="dkp")
async def score(ctx, nombre: str = None):
    if nombre:
        if nombre not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre}**.",
                color=discord.Color.red()
            ))
            return

        puntos = user_data[nombre]["score"]
        color = discord.Color.green() if puntos >= 0 else discord.Color.red()
        embed = discord.Embed(title=f"DKP de {nombre}", color=color)
        embed.add_field(name="DKP", value=str(puntos), inline=True)
        await ctx.send(embed=embed)
    else:
        if not user_data:
            await ctx.send("No hay datos de usuarios aún.")
            return

        all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

        desc = "```\n{:<15} {:<10}\n".format("Nombre", "DKP")
        desc += "-"*25 + "\n"
        for nombre_u, datos in all_users:
            puntos = datos["score"]
            desc += "{:<15} {:<10}\n".format(nombre_u, str(puntos))
        desc += "```"

        embed = discord.Embed(
            title="Tabla de DKP",
            description=desc,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

############################
# Solo Admins               #
############################

@bot.command(name="evento")
async def evento(ctx, nombre_evento: str, puntaje: int, *usuarios_mencionados):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        return

    if puntaje <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP inválido",
            description="El dkp debe ser un número positivo.",
            color=discord.Color.red()
        ))
        return

    usuarios_mencionados = set(usuarios_mencionados)

    for nombre, datos in user_data.items():
        if "justificado" not in datos or not isinstance(datos["justificado"], list):
            user_data[nombre]["justificado"] = []

    no_encontrados = []

    for nombre in usuarios_mencionados:
        if nombre not in user_data:
            no_encontrados.append(nombre)

    old_scores = {nombre: datos["score"] for nombre, datos in user_data.items()}
    old_justificado = {nombre: (nombre_evento in datos["justificado"]) for nombre, datos in user_data.items()}

    for nombre, datos in user_data.items():
        justificado_evento = (nombre_evento in datos["justificado"])

        if nombre in usuarios_mencionados:
            datos["score"] += puntaje

            if justificado_evento:
                datos["justificado"].remove(nombre_evento)
        else:
            if justificado_evento:
                datos["score"] -= puntaje
                datos["justificado"].remove(nombre_evento)
            else:
                datos["score"] -= (puntaje * 2)

    guardar_datos()

    all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

    desc = "```\n"
    desc += "{:<15} {:<12} {:<7} {:<8}\n".format("Nombre", "Estado", "Antes", "Después")
    desc += "-"*50 + "\n"
    for nombre, datos in all_users:
        antes = old_scores.get(nombre, 0)
        despues = datos["score"]
        justificado_prev = old_justificado.get(nombre, False)

        if justificado_prev:
            estado = "JUSTIFICADO"
        elif nombre not in usuarios_mencionados:
            estado = "NO ASISTIO"
        else:
            estado = "ASISTIO"

        desc += "{:<15} {:<12} {:<7} {:<8}\n".format(
            nombre, estado, str(antes), str(despues)
        )
    desc += "```"

    embed = discord.Embed(
        title=f"Evento: {nombre_evento}",
        color=discord.Color.blurple(),
        description=desc
    )
    await ctx.send(embed=embed)

    if no_encontrados:
        mensaje_no_encontrados = "No se encontraron los siguientes usuarios:\n"
        mensaje_no_encontrados += ", ".join(no_encontrados)
        await ctx.send(embed=discord.Embed(
            title="Usuarios no encontrados",
            description=mensaje_no_encontrados,
            color=discord.Color.red()
        ))

@bot.command(name="vincular")
async def vincular(ctx, member: discord.Member, nombre: str):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        return
    
    if ctx.channel.id != CANAL_ADMIN:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para administración.",
            color=discord.Color.red()
        ))
        return

    user_data[nombre] = {
        "discord_id": member.id,
        "score": user_data.get(nombre, {}).get("score", 0),
        "justificado": user_data.get(nombre, {}).get("justificado", [])
    }
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Vinculación completada",
        description=f"El usuario {member.mention} ha sido vinculado al nombre **{nombre}**",
        color=discord.Color.green()
    ))

@bot.command(name="borrarusuario")
async def borrarusuario(ctx, nombre: str):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        return
        
    if ctx.channel.id != CANAL_ADMIN:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para administración.",
            color=discord.Color.red()
        ))
        return

    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        return

    puntos = user_data[nombre]["score"]

    del user_data[nombre]
    guardar_datos()

    await ctx.send(embed=discord.Embed(
        title="Usuario Borrado",
        description=f"El usuario **{nombre}** con {puntos} DKP ha sido eliminado de la lista.",
        color=discord.Color.green()
    ))

@bot.command(name="sumardkp")
async def sumardkp(ctx, nombre: str, puntos_a_sumar: int):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        return

    if ctx.channel.id != CANAL_ADMIN:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para administración.",
            color=discord.Color.red()
        ))
        return

    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        return

    user_data[nombre]["score"] += puntos_a_sumar
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="DKP Actualizado",
        description=f"Se han agregado {puntos_a_sumar} DKP a **{nombre}**. Total: {user_data[nombre]['score']}",
        color=discord.Color.green()
    ))

@bot.command(name="restardkp")
@commands.has_permissions(administrator=True)
async def restardkp(ctx, nombre: str, puntos_a_restar: int):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        return

    if ctx.channel.id != CANAL_ADMIN:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para administración.",
            color=discord.Color.red()
        ))
        return

    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        return

    user_data[nombre]["score"] -= puntos_a_restar
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="DKP Actualizado",
        description=f"Se han restado {puntos_a_restar} DKP a **{nombre}**. Total: {user_data[nombre]['score']}",
        color=discord.Color.orange()
    ))

############################
# Manejo de errores       #
############################
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Faltan argumentos para este comando.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("No tienes permisos para usar este comando.")
    else:
        await ctx.send("Ocurrió un error al procesar el comando.")
        print(f"Error: {error}")

bot.run(TOKEN)
