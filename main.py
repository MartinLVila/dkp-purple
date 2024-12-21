import os
import discord
import json
import logging
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
from functools import wraps

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CANAL_ADMIN = int(os.getenv("CANAL_ADMIN"))
CANAL_AUSENCIAS = int(os.getenv("CANAL_AUSENCIAS"))
CANAL_TARDE = int(os.getenv("CANAL_TARDE"))
CANAL_CONSULTA = int(os.getenv("CANAL_CONSULTA"))
ADMINS_IDS = set(map(int, os.getenv("ADMINS_IDS").split(',')))

logging.basicConfig(
    filename='bot_commands.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)

logger = logging.getLogger('bot_commands')

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
                    
                    if "absence_until" in datos and datos["absence_until"]:
                        try:
                            datos["absence_until"] = datetime.strptime(datos["absence_until"], "%Y-%m-%dT%H:%M:%S.%f")
                        except ValueError:
                            datos["absence_until"] = None
                    else:
                        datos["absence_until"] = None
                    
                    if "justified_events" in datos:
                        datos["justified_events"] = set(datos["justified_events"])
                    else:
                        datos["justified_events"] = set()
                    
                    if "justificado" not in datos or not isinstance(datos["justificado"], list):
                        datos["justificado"] = []
                    
                user_data = data
        except json.JSONDecodeError:
            user_data = {}
    else:
        user_data = {}

def guardar_datos():
    serializable_data = {}
    for nombre, datos in user_data.items():
        serializable_data[nombre] = datos.copy()
        
        if "absence_until" in serializable_data[nombre] and serializable_data[nombre]["absence_until"]:
            serializable_data[nombre]["absence_until"] = serializable_data[nombre]["absence_until"].isoformat()
        else:
            serializable_data[nombre]["absence_until"] = None
        
        if "justified_events" in serializable_data[nombre]:
            serializable_data[nombre]["justified_events"] = list(serializable_data[nombre]["justified_events"])
        else:
            serializable_data[nombre]["justified_events"] = []
        
    with open(DATA_FILE, "w") as f:
        json.dump(serializable_data, f, indent=4)

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
                    info["penalties"] = info.get("penalties", {})
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
                "puntaje": info["puntaje"],
                "penalties": info.get("penalties", {})
            }
            for evento, info in events_info.items()
        }
        json.dump(serializable_events, f, indent=4)


@bot.event
async def on_ready():
    cargar_datos()
    cargar_eventos()
    print(f"Bot conectado como {bot.user}")
    logger.info(f"Bot conectado como {bot.user} (ID: {bot.user.id})")
    limpiar_eventos_expirados.start()
    limpiar_absences_expiradas.start()
    limpiar_eventos_justificados_expirados.start()


def es_admin(ctx):
    return (ctx.author.id in ADMINS_IDS)

############################
# Decorador de Verificación
############################
def requiere_vinculacion(comando_admin=False):
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            usuario = ctx.author
            nombre_usuario = None
            for nombre, datos in user_data.items():
                if datos.get("discord_id") == usuario.id:
                    nombre_usuario = nombre
                    break

            if comando_admin:
                if usuario.id not in ADMINS_IDS:
                    await ctx.send(embed=discord.Embed(
                        title="Permiso Denegado",
                        description="No tienes permisos para usar este comando.",
                        color=discord.Color.red()
                    ))
                    return
            else:
                if nombre_usuario is None and usuario.id not in ADMINS_IDS:
                    await ctx.send(embed=discord.Embed(
                        title="No Vinculado",
                        description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                        color=discord.Color.red()
                    ))
                    return

            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

############################
# Comando para ausencia con duración o por evento
############################
@bot.command(name="ausencia")
@requiere_vinculacion()
async def ausencia(ctx, *args):
    """
    Permite justificar una ausencia.
    - Usuarios Regulares:
        - Por días: !ausencia <dias>
        - Por evento: !ausencia <nombre_evento>
    - Administradores:
        - Por días: !ausencia <nombre_usuario> <dias>
        - Por evento: !ausencia <nombre_usuario> <nombre_evento>
    """
    if es_admin(ctx):
        if len(args) != 2:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso correcto para administradores:\n!ausencia nombreusuario dias\n!ausencia nombreusuario nombreevento",
                color=discord.Color.red()
            ))
            return

        nombre_usuario = args[0]
        segundo_arg = args[1]

        if nombre_usuario not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                color=discord.Color.red()
            ))
            return

        try:
            dias = int(segundo_arg)
            if dias < 1 or dias > 3:
                raise ValueError

            absence_until = datetime.utcnow() + timedelta(days=dias)
            user_data[nombre_usuario]["absence_until"] = absence_until
            guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"La ausencia para los próximos **{dias} día(s)** ha sido justificada para el usuario **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            return
        except ValueError:

            nombre_evento = segundo_arg

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"La ausencia para el evento **{nombre_evento}** ha sido justificada para el usuario **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            return

    else:
        if len(args) != 1:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso correcto para usuarios:\n!ausencia dias\n!ausencia nombreevento",
                color=discord.Color.red()
            ))
            return

        primer_arg = args[0]

        try:
            dias = int(primer_arg)
            if dias < 1 or dias > 3:
                raise ValueError
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

            absence_until = datetime.utcnow() + timedelta(days=dias)
            user_data[nombre_usuario]["absence_until"] = absence_until
            guardar_datos()

            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado por los próximos **{dias} día(s)**, **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            return
        except ValueError:
            nombre_evento = primer_arg
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

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado para el evento **{nombre_evento}**, **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            return

@bot.command(name="dkp")
@requiere_vinculacion()
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
    global events_info, user_data

    logger.info(f"Comando !evento invocado por {ctx.author} para el evento '{nombre_evento}' con puntaje {puntaje} y usuarios {usuarios_mencionados}")

    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario {ctx.author} intentó usar !evento sin permisos.")
        return

    if puntaje <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP inválido",
            description="El DKP debe ser un número positivo.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario {ctx.author} intentó crear un evento con puntaje no positivo: {puntaje}.")
        return

    usuarios_mencionados = list(usuarios_mencionados)
    noresta = False
    usuarios_mencionados_lower = [u.lower() for u in usuarios_mencionados]
    if 'noresta' in usuarios_mencionados_lower:
        noresta = True
        usuarios_mencionados = [u for u in usuarios_mencionados if u.lower() != 'noresta']
        logger.info(f"'noresta' activado para el evento '{nombre_evento}'.")

    usuarios_mencionados = set(usuarios_mencionados)

    for nombre, datos in user_data.items():
        if "justificado" not in datos or not isinstance(datos["justificado"], list):
            user_data[nombre]["justificado"] = []
            logger.debug(f"'justificado' inicializado para el usuario '{nombre}'.")

    no_encontrados = []

    for nombre in usuarios_mencionados:
        if nombre not in user_data:
            no_encontrados.append(nombre)
            logger.warning(f"Usuario mencionado '{nombre}' no encontrado en 'user_data'.")

    old_scores = {nombre: datos["score"] for nombre, datos in user_data.items()}
    old_justificado = {nombre: (nombre_evento in datos["justificado"]) for nombre, datos in user_data.items()}

    event_time = datetime.utcnow()
    linked_users_at_event = set(user_data.keys())

    events_info[nombre_evento] = {
        "timestamp": event_time,
        "linked_users": set(linked_users_at_event),
        "late_users": set(),
        "puntaje": puntaje,
        "penalties": {}
    }
    logger.info(f"Evento '{nombre_evento}' agregado a 'events_info'.")

    if noresta:
        logger.info(f"Aplicando lógica 'noresta' para el evento '{nombre_evento}'.")
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                logger.debug(f"Usuario '{nombre}' está de vacaciones. Omitiendo.")
                continue

            if nombre in usuarios_mencionados:
                datos["score"] += puntaje
                logger.debug(f"Usuario '{nombre}' asistió al evento '{nombre_evento}'. DKP incrementado en {puntaje}.")
                if nombre_evento in datos.get("justified_events", set()):
                    datos["justified_events"].remove(nombre_evento)
                    logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para el usuario '{nombre}'.")
    else:
        logger.info(f"Aplicando lógica estándar para el evento '{nombre_evento}'.")
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                logger.debug(f"Usuario '{nombre}' está de vacaciones. Omitiendo.")
                continue

            absence_until = datos.get("absence_until")
            justified_by_days = absence_until and event_time <= absence_until
            justified_by_event = nombre_evento in datos.get("justified_events", set())
            justificado_evento = justified_by_days or justified_by_event

            if nombre in usuarios_mencionados:
                datos["score"] += puntaje
                logger.debug(f"Usuario '{nombre}' asistió al evento '{nombre_evento}'. DKP incrementado en {puntaje}.")
                if justificado_evento:
                    datos["justified_events"].remove(nombre_evento)
                    logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para el usuario '{nombre}'.")
            else:
                if justificado_evento:
                    datos["score"] -= puntaje
                    logger.debug(f"Usuario '{nombre}' justificado para el evento '{nombre_evento}'. DKP decrementado en {puntaje}.")
                    if nombre_evento in datos.get("justified_events", set()):
                        datos["justified_events"].remove(nombre_evento)
                        logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para el usuario '{nombre}'.")
                else:
                    datos["score"] -= (puntaje * 2)
                    if nombre_evento in events_info:
                        events_info[nombre_evento]["penalties"][nombre] = puntaje * 2
                        logger.debug(f"Penalización de {puntaje * 2} DKP asignada a '{nombre}' para el evento '{nombre_evento}'.")
                    else:
                        logger.error(f"Evento '{nombre_evento}' no existe en 'events_info' al asignar penalización.")
                        await ctx.send(embed=discord.Embed(
                            title="Error Interno",
                            description="Ocurrió un error al asignar penalizaciones. Por favor, contacta al administrador.",
                            color=discord.Color.red()
                        ))
                        return

    try:
        guardar_datos()
        guardar_eventos()
        logger.info(f"Datos y eventos guardados correctamente tras el comando '!evento {nombre_evento}'.")
    except Exception as e:
        logger.error(f"Error al guardar datos/eventos tras el comando '!evento {nombre_evento}': {e}")
        await ctx.send(embed=discord.Embed(
            title="Error Interno",
            description="Ocurrió un error al guardar los datos del evento. Por favor, contacta al administrador.",
            color=discord.Color.red()
        ))
        return

    all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

    desc = "```\n"
    desc += "{:<15} {:<15} {:<10} {:<10}\n".format("Nombre", "Estado", "Antes", "Después")
    desc += "-"*55 + "\n"
    for nombre, datos in all_users:
        antes = old_scores.get(nombre, 0)
        despues = datos["score"]

        if datos.get("status", "normal") == "vacaciones":
            estado = "VACACIONES"
        else:
            absence_until = datos.get("absence_until")
            justified_by_days = absence_until and event_time <= absence_until
            justified_by_event = nombre_evento in datos.get("justified_events", set())
            if justified_by_days or justified_by_event:
                estado = "JUSTIFICADO"
            elif nombre in usuarios_mencionados:
                estado = "ASISTIÓ"
            else:
                estado = "NO ASISTIÓ"

        desc += "{:<15} {:<15} {:<10} {:<10}\n".format(
            nombre, estado, str(antes), str(despues)
        )
    desc += "```"

    embed = discord.Embed(
        title=f"Evento: {nombre_evento}",
        color=discord.Color.blurple(),
        description=desc
    )
    await ctx.send(embed=embed)
    logger.info(f"Embed para el evento '{nombre_evento}' enviado a {ctx.author}.")

    if no_encontrados:
        mensaje_no_encontrados = "No se encontraron los siguientes usuarios:\n"
        mensaje_no_encontrados += ", ".join(no_encontrados)
        await ctx.send(embed=discord.Embed(
            title="Usuarios no encontrados",
            description=mensaje_no_encontrados,
            color=discord.Color.red()
        ))
        logger.warning(f"Usuarios no encontrados al crear el evento '{nombre_evento}': {no_encontrados}")

@bot.command(name="vincular")
@requiere_vinculacion(comando_admin=True)
async def vincular(ctx, member: discord.Member, nombre: str):
    user_data[nombre] = {
        "discord_id": member.id,
        "score": user_data.get(nombre, {}).get("score", 0),
        "justificado": user_data.get(nombre, {}).get("justificado", []),
        "justified_events": set(user_data.get(nombre, {}).get("justified_events", [])),
        "status": "normal",
        "absence_until": None
    }
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Vinculación completada",
        description=f"El usuario {member.mention} ha sido vinculado al nombre **{nombre}** con estado **ACTIVO**.",
        color=discord.Color.green()
    ))

@bot.command(name="borrarusuario")
@requiere_vinculacion(comando_admin=True)
async def borrarusuario(ctx, nombre: str):
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
@requiere_vinculacion(comando_admin=True)
async def sumardkp(ctx, nombre: str, puntos_a_sumar: int):
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
async def restardkp(ctx, member: discord.Member, puntos_a_restar: int):
    global user_data

    if not es_admin(ctx):
        await ctx.send(embed=discord.Embed(
            title="Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario {ctx.author} intentó usar !restardkp sin permisos.")
        return

    nombre_usuario = None
    for nombre, datos in user_data.items():
        if datos.get("discord_id") == member.id:
            nombre_usuario = nombre
            break

    if nombre_usuario is None:
        await ctx.send(embed=discord.Embed(
            title="Usuario no Vinculado",
            description="El usuario mencionado no está vinculado al sistema DKP.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario mencionado '{member}' no está vinculado en 'user_data'.")
        return

    if puntos_a_restar <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP Inválido",
            description="La cantidad de DKP a restar debe ser un número positivo.",
            color=discord.Color.red()
        ))
        logger.warning(f"Intento de restar DKP no válido: {puntos_a_restar} a '{nombre_usuario}'.")
        return

    user_data[nombre_usuario]["score"] -= puntos_a_restar
    guardar_datos()
    logger.info(f"Se han restado {puntos_a_restar} DKP a '{nombre_usuario}' (ID Discord: {member.id}).")
    
    await ctx.send(embed=discord.Embed(
        title="DKP Actualizado",
        description=f"Se han restado **{puntos_a_restar} DKP** a **{nombre_usuario}**. Total: **{user_data[nombre_usuario]['score']} DKP**.",
        color=discord.Color.orange()
    ))

############################
# Comandos para Gestionar Vacaciones
############################

@bot.command(name="ausencia_vacaciones")
@requiere_vinculacion(comando_admin=True)
async def ausencia_vacaciones(ctx, nombre: str):
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
@requiere_vinculacion(comando_admin=True)
async def ausencia_volvio(ctx, nombre: str):
    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        return

    user_data[nombre]["status"] = "normal"
    user_data[nombre]["absence_until"] = None
    user_data[nombre]["justified_events"].clear()
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
@requiere_vinculacion()
async def llegue_tarde(ctx, nombre_evento: str):
    """
    Permite a un usuario justificar su llegada tardía a un evento.
    - Solo se puede usar dentro de los 20 minutos posteriores a que se emitió el comando !evento NOMBREEVENTO.
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
            description=f"No se encontró el evento **{nombre_evento}**. Asegúrate de haberlo registrado con !evento.",
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

    penalty_amount = event["penalties"].get(nombre_usuario, 0)

    if penalty_amount > 0:
        user_data[nombre_usuario]["score"] += penalty_amount + puntaje
        del event["penalties"][nombre_usuario]
    else:
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
# Tareas para Limpieza    #
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

@tasks.loop(minutes=5)
async def limpiar_absences_expiradas():
    """
    Limpia las ausencias que han expirado.
    """
    global user_data
    ahora = datetime.utcnow()
    modificados = False
    for nombre, datos in user_data.items():
        if "absence_until" in datos and datos["absence_until"]:
            if ahora > datos["absence_until"]:
                user_data[nombre]["absence_until"] = None
                modificados = True
    if modificados:
        guardar_datos()

@tasks.loop(minutes=5)
async def limpiar_eventos_justificados_expirados():
    """
    Limpia los eventos justificados específicos que ya han ocurrido.
    """
    global user_data, events_info
    ahora = datetime.utcnow()
    modificados = False
    for nombre_evento, info in list(events_info.items()):
        evento_time = info["timestamp"]
        if ahora > evento_time + timedelta(minutes=20):
            for nombre in list(info["penalties"].keys()):
                if nombre in user_data:
                    pass
            del events_info[nombre_evento]
            modificados = True
    if modificados:
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
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Tipo de argumento inválido.")
    else:
        await ctx.send("Ocurrió un error al procesar el comando.")
        logger.error(f"Error en comando {ctx.command} usado por {ctx.author} (ID: {ctx.author.id}): {error}")
        print(f"Error: {error}")


@bot.event
async def on_command(ctx):
    nombre_comando = ctx.command.name
    usuario = ctx.author
    argumentos = ctx.message.content
    logger.info(f"Comando: {nombre_comando} | Usuario: {usuario} (ID: {usuario.id}) | Argumentos: {argumentos}")

bot.run(TOKEN)