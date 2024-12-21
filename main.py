import os
import discord
import json
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CANAL_ADMIN = int(os.getenv("CANAL_ADMIN"))
CANAL_AUSENCIAS = int(os.getenv("CANAL_AUSENCIAS"))
CANAL_TARDE = int(os.getenv("CANAL_TARDE"))
CANAL_CONSULTA = int(os.getenv("CANAL_CONSULTA"))
ADMINS_IDS = set(map(int, os.getenv("ADMINS_IDS").split(',')))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "scores.json"
EVENTS_FILE = "events.json"
user_data = {}
events_info = {}

def cargar_datos():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)

                for nombre, datos in data.items():
                    if "status" not in datos:
                        datos["status"] = "normal"
                user_data = data
        except json.JSONDecodeError:
            user_data = {}
    else:
        user_data = {}

def guardar_datos():
    with open(DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

def cargar_eventos():
    global events_info
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r") as f:
                data = json.load(f)
                for evento, info in data.items():
                    info["timestamp"] = datetime.strptime(info["timestamp"], "%Y-%m-%dT%H:%M:%S.%f")
                    info["linked_users"] = set(info["linked_users"])
                    info["late_users"] = set(info["late_users"])
                events_info = data
        except json.JSONDecodeError:
            events_info = {}
    else:
        events_info = {}

def guardar_eventos():
    with open(EVENTS_FILE, "w") as f:
        serializable_events = {
            evento: {
                "timestamp": info["timestamp"].isoformat(),
                "linked_users": list(info["linked_users"]),
                "late_users": list(info["late_users"]),
                "puntaje": info["puntaje"]
            }
            for evento, info in events_info.items()
        }
        json.dump(serializable_events, f, indent=4)

@bot.event
async def on_ready():
    cargar_datos()
    cargar_eventos()
    print(f"Bot conectado como {bot.user}")
    limpiar_eventos_expirados.start()

def es_admin(ctx):
    return (ctx.author.id in ADMINS_IDS)

############################
# Comando para ausencia en un evento (justificado)
############################
@bot.command(name="ausencia")
async def ausencia(ctx, nombre_usuario: str = None, nombre_evento: str = None):
    """
    Permite justificar una ausencia.
    - Usuarios Regulares: !ausencia nombreevento
    - Administradores: !ausencia nombreusuario nombreevento
    """

    if es_admin(ctx):
        if nombre_usuario is None or nombre_evento is None:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso correcto para administradores: `!ausencia nombreusuario nombreevento`",
                color=discord.Color.red()
            ))
            return

        if nombre_usuario not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                color=discord.Color.red()
            ))
            return
    else:
        if nombre_evento is None:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso correcto para usuarios: `!ausencia nombreevento`",
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
                title="No Vinculado",
                description="No se encontró un nombre vinculado a tu usuario. Pide a un oficial que te vincule primero.",
                color=discord.Color.red()
            ))
            return

    if es_admin(ctx) and nombre_usuario:
        target_user = nombre_usuario
    else:
        target_user = nombre_usuario

    if target_user not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{target_user}**.",
            color=discord.Color.red()
        ))
        return

    if nombre_evento not in user_data[target_user].get("justificado", []):
        user_data[target_user].setdefault("justificado", []).append(nombre_evento)

    guardar_datos()
    if es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Ausencia Justificada",
            description=f"La ausencia para el evento **{nombre_evento}** ha sido justificada para el usuario **{target_user}**.",
            color=discord.Color.yellow()
        ))
    else:
        await ctx.send(embed=discord.Embed(
            title="Ausencia Justificada",
            description=f"Has quedado justificado para el evento **{nombre_evento}**, {target_user}.",
            color=discord.Color.yellow()
        ))

@bot.command(name="dkp")
async def score(ctx, nombre: str = None):
    if nombre:
        member = ctx.message.mentions[0] if ctx.message.mentions else None

        if member:
            nombre_usuario = None
            for nombre_u, datos in user_data.items():
                if datos.get("discord_id") == member.id:
                    nombre_usuario = nombre_u
                    break

            if nombre_usuario is None:
                await ctx.send(embed=discord.Embed(
                    title="No Vinculado",
                    description="El usuario mencionado no está vinculado al sistema DKP.",
                    color=discord.Color.red()
                ))
                return
        else:
            nombre_usuario = nombre

            if nombre_usuario not in user_data:
                await ctx.send(embed=discord.Embed(
                    title="Usuario no encontrado",
                    description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                    color=discord.Color.red()
                ))
                return

        # Obtener DKP y Estado
        puntos = user_data[nombre_usuario]["score"]
        status = user_data[nombre_usuario].get("status", "normal")
        estado = "VACACIONES" if status == "vacaciones" else "ACTIVO"
        color = discord.Color.green() if puntos >= 0 else discord.Color.red()

        embed = discord.Embed(title=f"DKP de {nombre_usuario}", color=color)
        embed.add_field(name="DKP", value=str(puntos), inline=True)
        embed.add_field(name="Estado", value=estado, inline=True)
        await ctx.send(embed=embed)
    else:
        if not user_data:
            await ctx.send("No hay datos de usuarios aún.")
            return

        all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

        desc = "```\n{:<15} {:<10} {:<10}\n".format("Nombre", "DKP", "Estado")
        desc += "-"*40 + "\n"
        for nombre_u, datos in all_users:
            puntos = datos["score"]
            status = datos.get("status", "normal")
            estado = "VACACIONES" if status == "vacaciones" else "ACTIVO"
            desc += "{:<15} {:<10} {:<10}\n".format(nombre_u, str(puntos), estado)
        desc += "```"

        embed = discord.Embed(
            title="Tabla de DKP",
            description=desc,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

############################
# Comandos Administrativos  #
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

    usuarios_mencionados = list(usuarios_mencionados)
    noresta = False
    usuarios_mencionados_lower = [u.lower() for u in usuarios_mencionados]
    if 'noresta' in usuarios_mencionados_lower:
        noresta = True
        usuarios_mencionados = [u for u in usuarios_mencionados if u.lower() != 'noresta']

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

    event_time = datetime.utcnow()
    linked_users_at_event = set(user_data.keys())
    events_info[nombre_evento] = {
        "timestamp": event_time,
        "linked_users": linked_users_at_event,
        "late_users": set(),
        "puntaje": puntaje
    }

    if noresta:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                continue

            if nombre in usuarios_mencionados:
                datos["score"] += puntaje

                if nombre_evento in datos.get("justificado", []):
                    datos["justificado"].remove(nombre_evento)
            else:
                pass
    else:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                continue

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
    guardar_eventos()

    all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

    desc = "```\n"
    desc += "{:<15} {:<12} {:<10} {:<10}\n".format("Nombre", "Estado", "Antes", "Después")
    desc += "-"*50 + "\n"
    for nombre, datos in all_users:
        antes = old_scores.get(nombre, 0)
        despues = datos["score"]

        # Determinar el estado para este evento
        if datos.get("status", "normal") == "vacaciones":
            estado = "VACACIONES"
        elif nombre in usuarios_mencionados:
            estado = "ASISTIO"
        elif nombre_evento in datos.get("justificado", []):
            estado = "JUSTIFICADO"
        else:
            estado = "NO ASISTIO"

        desc += "{:<15} {:<12} {:<10} {:<10}\n".format(
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

    user_data[nombre] = {
        "discord_id": member.id,
        "score": user_data.get(nombre, {}).get("score", 0),
        "justificado": user_data.get(nombre, {}).get("justificado", []),
        "status": "normal"  # Estado por defecto
    }
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Vinculación completada",
        description=f"El usuario {member.mention} ha sido vinculado al nombre **{nombre}** con estado **ACTIVO**.",
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
async def restardkp(ctx, nombre: str, puntos_a_restar: int):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
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
# Comandos para Gestionar Vacaciones
############################

@bot.command(name="ausencia_vacaciones")
async def ausencia_vacaciones(ctx, nombre: str):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
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

    user_data[nombre]["status"] = "vacaciones"
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Estado Actualizado",
        description=f"El usuario **{nombre}** ha sido marcado como **VACACIONES**.",
        color=discord.Color.yellow()
    ))

@bot.command(name="ausencia_volvio")
async def ausencia_volvio(ctx, nombre: str):
    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
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

    user_data[nombre]["status"] = "normal"
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Estado Actualizado",
        description=f"El usuario **{nombre}** ha vuelto de **VACACIONES** y está nuevamente en estado **ACTIVO**.",
        color=discord.Color.green()
    ))

############################
# Comando !llegue_tarde
############################

@bot.command(name="llegue_tarde")
async def llegue_tarde(ctx, nombre_evento: str):
    """
    Permite a un usuario justificar su llegada tardía a un evento.
    - Solo se puede usar dentro de los 10 minutos posteriores a que se emitió el comando !evento NOMBREEVENTO.
    - Solo se puede usar una vez por usuario por evento en el canal de ausencias.
    """

    if ctx.channel.id != CANAL_TARDE:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description=f"Este comando solo puede usarse en el canal designado para llegadas tardías.",
            color=discord.Color.red()
        ))
        return

    if nombre_evento not in events_info:
        await ctx.send(embed=discord.Embed(
            title="Evento No Encontrado",
            description=f"No se encontró el evento **{nombre_evento}**. Asegúrate de haberlo registrado con `!evento`.",
            color=discord.Color.red()
        ))
        return

    event = events_info[nombre_evento]
    event_time = event["timestamp"]
    current_time = datetime.utcnow()

    if current_time > event_time + timedelta(minutes=20):
        await ctx.send(embed=discord.Embed(
            title="Tiempo Expirado",
            description=f"El tiempo para justificar tu llegada tardía al evento **{nombre_evento}** ha expirado.",
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
            title="No Vinculado",
            description="No se encontró un nombre vinculado a tu usuario. Pide a un oficial que te vincule primero.",
            color=discord.Color.red()
        ))
        return

    if nombre_usuario in event["late_users"]:
        await ctx.send(embed=discord.Embed(
            title="Uso Duplicado",
            description="Ya has justificado tu llegada tardía para este evento.",
            color=discord.Color.red()
        ))
        return

    if nombre_usuario not in event["linked_users"]:
        await ctx.send(embed=discord.Embed(
            title="No Necesitas Justificación",
            description="Estabas vinculado al momento del evento y tus puntos ya fueron ajustados.",
            color=discord.Color.red()
        ))
        return

    puntaje = event["puntaje"]

    if nombre_usuario not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario No Vinculado",
            description="Tu usuario no está vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
            color=discord.Color.red()
        ))
        return

    user_data[nombre_usuario]["score"] += puntaje

    event["late_users"].add(nombre_usuario)

    guardar_datos()
    guardar_eventos()

    await ctx.send(embed=discord.Embed(
        title="Llegada Tardía Justificada",
        description=f"Se han sumado **{puntaje} DKP** al evento **{nombre_evento}** para ti, **{nombre_usuario}**.",
        color=discord.Color.green()
    ))

############################
# Tarea para Limpiar Eventos Expirados
############################

@tasks.loop(minutes=5)
async def limpiar_eventos_expirados():
    """
    Limpia los eventos que han expirado (más de 20 minutos desde su creación).
    """
    global events_info
    ahora = datetime.utcnow()
    eventos_a_eliminar = [
        evento for evento, info in events_info.items()
        if ahora > info["timestamp"] + timedelta(minutes=20)
    ]
    for evento in eventos_a_eliminar:
        del events_info[evento]
    if eventos_a_eliminar:
        guardar_eventos()

############################
# Manejo de Errores       #
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