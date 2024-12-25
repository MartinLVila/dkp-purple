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
REGISTERED_EVENTS_FILE = "registered_events.json"
HISTORY_FILE = "score_history.json"

user_data = {}
events_info = {}
registered_events = set()
score_history = {}

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
                            datos["absence_until"] = datetime.strptime(
                                datos["absence_until"], "%Y-%m-%dT%H:%M:%S.%f"
                            )
                        except ValueError:
                            datos["absence_until"] = None
                            logger.error(
                                f"Error al parsear 'absence_until' para el usuario '{nombre}'. Asignando como None."
                            )
                    else:
                        datos["absence_until"] = None

                    if "justified_events" in datos:
                        datos["justified_events"] = set(datos["justified_events"])
                    else:
                        datos["justified_events"] = set()

                    if "justificado" not in datos or not isinstance(datos["justificado"], list):
                        datos["justificado"] = []
                        logger.warning(f"'justificado' inicializado para el usuario '{nombre}'.")

                user_data = data
                logger.info(f"Se cargaron {len(user_data)} usuarios desde '{DATA_FILE}'.")
        except json.JSONDecodeError as jde:
            user_data = {}
            logger.error(f"Error al decodificar '{DATA_FILE}': {jde}. Inicializando 'user_data' como diccionario vacío.")
    else:
        user_data = {}
        logger.info(f"'{DATA_FILE}' no existe. Inicializando 'user_data' como diccionario vacío.")


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

    try:
        with open(DATA_FILE, "w") as f:
            json.dump(serializable_data, f, indent=4)
        logger.info(f"Datos de usuarios guardados correctamente en '{DATA_FILE}'.")
    except Exception as e:
        logger.error(f"Error al guardar datos en '{DATA_FILE}': {e}")


def cargar_eventos():
    global events_info
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r") as f:
                data = json.load(f)
                for evento, info in data.items():
                    try:
                        info["timestamp"] = datetime.strptime(
                            info["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"
                        )
                    except ValueError as ve:
                        logger.error(
                            f"Error al parsear 'timestamp' para el evento '{evento}': {ve}. Asignando la hora actual."
                        )
                        info["timestamp"] = datetime.utcnow()

                    if isinstance(info.get("linked_users"), list):
                        info["linked_users"] = set(info["linked_users"])
                    else:
                        logger.warning(
                            f"'linked_users' para el evento '{evento}' no es una lista. Inicializando como conjunto vacío."
                        )
                        info["linked_users"] = set()

                    if isinstance(info.get("late_users"), list):
                        info["late_users"] = set(info["late_users"])
                    else:
                        logger.warning(
                            f"'late_users' para el evento '{evento}' no es una lista. Inicializando como conjunto vacío."
                        )
                        info["late_users"] = set()

                    if isinstance(info.get("penalties"), dict):
                        info["penalties"] = info.get("penalties", {})
                    else:
                        logger.warning(
                            f"'penalties' para el evento '{evento}' no es un diccionario. Inicializando como diccionario vacío."
                        )
                        info["penalties"] = {}
                events_info = data
                logger.info(f"Se cargaron {len(events_info)} eventos desde '{EVENTS_FILE}'.")
        except json.JSONDecodeError as jde:
            events_info = {}
            logger.error(f"Error al decodificar '{EVENTS_FILE}': {jde}. Inicializando 'events_info' como diccionario vacío.")
    else:
        events_info = {}
        logger.info(f"'{EVENTS_FILE}' no existe. Inicializando 'events_info' como diccionario vacío.")


def guardar_eventos():
    try:
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
        logger.info(f"Eventos guardados correctamente en '{EVENTS_FILE}'.")
    except Exception as e:
        logger.error(f"Error al guardar eventos en '{EVENTS_FILE}': {e}")


def cargar_eventos_registrados():
    global registered_events
    if os.path.exists(REGISTERED_EVENTS_FILE):
        try:
            with open(REGISTERED_EVENTS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    registered_events = set(data)
                else:
                    registered_events = set()
                logger.info(f"Se cargaron {len(registered_events)} eventos registrados desde '{REGISTERED_EVENTS_FILE}'.")
        except json.JSONDecodeError as jde:
            registered_events = set()
            logger.error(f"Error al decodificar '{REGISTERED_EVENTS_FILE}': {jde}. Se inicializa 'registered_events' vacío.")
    else:
        registered_events = set()
        logger.info(f"No existe '{REGISTERED_EVENTS_FILE}'. Se inicializa 'registered_events' vacío.")


def guardar_eventos_registrados():
    try:
        with open(REGISTERED_EVENTS_FILE, "w") as f:
            json.dump(list(registered_events), f, indent=4)
        logger.info(f"Eventos registrados guardados correctamente en '{REGISTERED_EVENTS_FILE}'.")
    except Exception as e:
        logger.error(f"Error al guardar eventos registrados en '{REGISTERED_EVENTS_FILE}': {e}")


HISTORY_FILE = "score_history.json"
score_history = {}


def cargar_historial_dkp():
    global score_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    score_history = data
                else:
                    score_history = {}
            logger.info(f"Historial de DKP cargado desde '{HISTORY_FILE}'.")
        except json.JSONDecodeError as jde:
            score_history = {}
            logger.error(f"Error al decodificar '{HISTORY_FILE}': {jde}. Se inicializa 'score_history' vacío.")
    else:
        score_history = {}
        logger.info(f"No existe '{HISTORY_FILE}'. Se inicializa 'score_history' vacío.")


def guardar_historial_dkp():
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(score_history, f, indent=4)
        logger.info(f"Historial de DKP guardado en '{HISTORY_FILE}'.")
    except Exception as e:
        logger.error(f"Error al guardar historial de DKP en '{HISTORY_FILE}': {e}")


def registrar_cambio_dkp(nombre_usuario, delta, razon=""):
    """
    Registra en 'score_history' el cambio de DKP de 'nombre_usuario',
    con timestamp, el delta (positivo/negativo) y una razón opcional.
    """
    global score_history
    if nombre_usuario not in score_history:
        score_history[nombre_usuario] = []

    registro = {
        "timestamp": datetime.utcnow().isoformat(),
        "delta": delta,
        "razon": razon
    }
    score_history[nombre_usuario].append(registro)
    guardar_historial_dkp()

    logger.debug(f"Registrado cambio de {delta} DKP a '{nombre_usuario}' por '{razon}'.")


@bot.event
async def on_ready():
    cargar_datos()
    cargar_eventos()
    cargar_eventos_registrados()
    cargar_historial_dkp()
    
    print(f"Bot conectado como {bot.user}")
    logger.info(f"Bot conectado como {bot.user} (ID: {bot.user.id})")

    limpiar_eventos_expirados.start()
    limpiar_absences_expiradas.start()
    limpiar_eventos_justificados_expirados.start()


def es_admin(ctx):
    return (ctx.author.id in ADMINS_IDS)


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
                    logger.warning(f"Usuario {ctx.author} intentó usar un comando administrativo sin permisos.")
                    return
            else:
                if nombre_usuario is None and usuario.id not in ADMINS_IDS:
                    await ctx.send(embed=discord.Embed(
                        title="No Vinculado",
                        description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                        color=discord.Color.red()
                    ))
                    logger.warning(f"Usuario {ctx.author} no está vinculado y intentó usar un comando sin permisos.")
                    return

            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

@bot.command(name="dkpdetalle")
@requiere_vinculacion()
async def dkp_detalle(ctx, *, nombre_usuario: str):
    """
    Muestra los cambios de DKP del usuario (nombre_usuario) en los últimos 7 días.
    - Se puede también mencionar @usuario en vez de poner el nombre.
    """
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
        found_name = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == member.id:
                found_name = nombre
                break
        if found_name is None:
            await ctx.send(embed=discord.Embed(
                title="No Vinculado",
                description="El usuario mencionado no está vinculado al sistema DKP.",
                color=discord.Color.red()
            ))
            return
        nombre_usuario = found_name
    else:
        if nombre_usuario not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                color=discord.Color.red()
            ))
            return

    if nombre_usuario not in score_history or not score_history[nombre_usuario]:
        await ctx.send(embed=discord.Embed(
            title="Sin Cambios",
            description=f"No hay registros de cambios de DKP para **{nombre_usuario}**.",
            color=discord.Color.blue()
        ))
        return

    ahora = datetime.utcnow()
    hace_7_dias = ahora - timedelta(days=7)

    cambios_usuario = score_history[nombre_usuario]

    cambios_7_dias = []
    for registro in cambios_usuario:
        try:
            fecha_cambio = datetime.strptime(registro["timestamp"], "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            fecha_cambio = datetime.strptime(registro["timestamp"], "%Y-%m-%dT%H:%M:%S")

        if fecha_cambio >= hace_7_dias:
            delta = registro["delta"]
            razon = registro.get("razon", "")
            cambios_7_dias.append((fecha_cambio, delta, razon))

    if not cambios_7_dias:
        await ctx.send(embed=discord.Embed(
            title="DKP Detalle",
            description=f"No hubo cambios para **{nombre_usuario}** en los últimos 7 días.",
            color=discord.Color.blue()
        ))
        return

    cambios_7_dias.sort(key=lambda x: x[0])

    desc = "```\nFecha               |  ΔDKP  | Razón\n"
    desc += "-"*50 + "\n"
    for (fecha, delta, razon) in cambios_7_dias:
        fecha_str = fecha.strftime("%Y-%m-%d %H:%M")
        desc += f"{fecha_str:<18} | {str(delta):>5} | {razon}\n"
    desc += "```"

    embed = discord.Embed(
        title=f"DKP Detalle: {nombre_usuario}",
        description=desc,
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name="registroevento")
@requiere_vinculacion(comando_admin=True)
async def registroevento(ctx, nombre_evento: str):
    nombre_evento_lower = nombre_evento.lower()
    for evt in registered_events:
        if evt.lower() == nombre_evento_lower:
            await ctx.send(embed=discord.Embed(
                title="Evento Ya Registrado",
                description=f"El evento **{nombre_evento}** ya estaba registrado.",
                color=discord.Color.red()
            ))
            logger.warning(f"Administrador '{ctx.author}' intentó registrar un evento ya existente '{nombre_evento}'.")
            return

    registered_events.add(nombre_evento)
    guardar_eventos_registrados()

    await ctx.send(embed=discord.Embed(
        title="Evento Registrado",
        description=f"Se ha registrado el evento permanente **{nombre_evento}**.",
        color=discord.Color.green()
    ))
    logger.info(f"Evento permanente '{nombre_evento}' registrado por administrador '{ctx.author}'.")


@bot.command(name="borrarevento")
@requiere_vinculacion(comando_admin=True)
async def borrarevento(ctx, nombre_evento: str):
    to_remove = None
    for evt in registered_events:
        if evt.lower() == nombre_evento.lower():
            to_remove = evt
            break

    if to_remove is None:
        await ctx.send(embed=discord.Embed(
            title="Evento No Encontrado",
            description=f"No se encontró el evento permanente **{nombre_evento}** para borrar.",
            color=discord.Color.red()
        ))
        logger.warning(f"Administrador '{ctx.author}' intentó borrar un evento permanente no existente '{nombre_evento}'.")
        return

    registered_events.remove(to_remove)
    guardar_eventos_registrados()

    await ctx.send(embed=discord.Embed(
        title="Evento Eliminado",
        description=f"Se eliminó el evento permanente **{to_remove}** de la lista.",
        color=discord.Color.green()
    ))
    logger.info(f"Evento permanente '{to_remove}' fue eliminado por administrador '{ctx.author}'.")


############################
# Comando de Ausencia
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
            logger.warning(f"Usuario {ctx.author} usó !ausencia con argumentos incorrectos.")
            return

        nombre_usuario = args[0]
        segundo_arg = args[1]

        if nombre_usuario not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                color=discord.Color.red()
            ))
            logger.warning(f"Usuario {nombre_usuario} no encontrado al intentar justificar ausencia.")
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
            logger.info(f"Ausencia justificada por {dias} días para el usuario '{nombre_usuario}' por administrador '{ctx.author}'.")
            return

        except ValueError:
            nombre_evento = segundo_arg
            if not any(evt.lower() == nombre_evento.lower() for evt in registered_events):
                eventos_disponibles = ", ".join(sorted(registered_events))
                await ctx.send(embed=discord.Embed(
                    title="Evento No Registrado",
                    description=(
                        f"El evento **{nombre_evento}** no está en la lista de eventos permanentes.\n\n"
                        f"Eventos disponibles:\n**{eventos_disponibles}**\n\n"
                        "Si corresponde, regístralo antes con !registroevento."
                    ),
                    color=discord.Color.red()
                ))
                logger.warning(f"El evento '{nombre_evento}' no está registrado. No se puede justificar ausencia.")
                return

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"La ausencia para el evento **{nombre_evento}** ha sido justificada para el usuario **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            logger.info(f"Ausencia justificada para el evento '{nombre_evento}' del usuario '{nombre_usuario}' por administrador '{ctx.author}'.")
            return

    else:
        if len(args) != 1:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso correcto para usuarios:\n!ausencia dias\n!ausencia nombreevento",
                color=discord.Color.red()
            ))
            logger.warning(f"Usuario {ctx.author} usó !ausencia con argumentos incorrectos.")
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
                logger.warning(f"Usuario {ctx.author} no está vinculado y quiso justificar ausencia.")
                return

            absence_until = datetime.utcnow() + timedelta(days=dias)
            user_data[nombre_usuario]["absence_until"] = absence_until
            guardar_datos()

            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado por los próximos **{dias} día(s)**, **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            logger.info(f"Usuario '{nombre_usuario}' justificó ausencia por {dias} días.")
            return

        except ValueError:
            nombre_evento = primer_arg
            if not any(evt.lower() == nombre_evento.lower() for evt in registered_events):
                eventos_disponibles = ", ".join(sorted(registered_events))
                await ctx.send(embed=discord.Embed(
                    title="Evento No Registrado",
                    description=(
                        f"El evento **{nombre_evento}** no está en la lista de eventos permanentes.\n\n"
                        f"Eventos disponibles:\n**{eventos_disponibles}**\n\n"
                        "Si corresponde, pide a un oficial que lo registre con !registroevento."
                    ),
                    color=discord.Color.red()
                ))
                logger.warning(f"Usuario '{ctx.author}' intentó justificar ausencia a un evento no registrado '{nombre_evento}'.")
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
                logger.warning(f"Usuario {ctx.author} no está vinculado y quiso justificar ausencia por evento.")
                return

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado para el evento **{nombre_evento}**, **{nombre_usuario}**.",
                color=discord.Color.yellow()
            ))
            logger.info(f"Usuario '{nombre_usuario}' justificó ausencia para el evento '{nombre_evento}'.")
            return


############################
# Comando de Consulta de DKP
############################
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
                logger.warning(f"Usuario mencionado '{member}' no está vinculado en 'user_data'.")
                return
        else:
            nombre_usuario = nombre
            if nombre_usuario not in user_data:
                await ctx.send(embed=discord.Embed(
                    title="Usuario no encontrado",
                    description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                    color=discord.Color.red()
                ))
                logger.warning(f"Usuario '{nombre_usuario}' no encontrado al consultar DKP.")
                return

        puntos = user_data[nombre_usuario]["score"]
        status = user_data[nombre_usuario].get("status", "normal")
        estado = "VACACIONES" if status == "vacaciones" else "ACTIVO"
        color = discord.Color.green() if puntos >= 0 else discord.Color.red()

        embed = discord.Embed(title=f"DKP de {nombre_usuario}", color=color)
        embed.add_field(name="DKP", value=str(puntos), inline=True)
        embed.add_field(name="Estado", value=estado, inline=True)
        await ctx.send(embed=embed)
        logger.info(f"Usuario '{nombre_usuario}' consultó su DKP.")
    else:
        if not user_data:
            await ctx.send("No hay datos de usuarios aún.")
            logger.info("Comando !dkp ejecutado pero no hay datos de usuarios.")
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
        logger.info(f"Se mostró la tabla completa de DKP a {ctx.author}.")


############################
# Comandos Administrativos
############################
@bot.command(name="evento")
@requiere_vinculacion(comando_admin=True)
async def evento(ctx, nombre_evento: str, puntaje: int, *usuarios_mencionados):
    if puntaje <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP inválido",
            description="El DKP debe ser un número positivo.",
            color=discord.Color.red()
        ))
        logger.warning(
            f"Administrador '{ctx.author}' intentó crear un evento '{nombre_evento}' con puntaje no positivo: {puntaje}."
        )
        return

    usuarios_mencionados = list(usuarios_mencionados)
    logger.debug(f"Usuarios mencionados (original): {usuarios_mencionados}")

    noresta = False
    usuarios_mencionados_lower = [u.lower() for u in usuarios_mencionados]
    if 'noresta' in usuarios_mencionados_lower:
        noresta = True
        usuarios_mencionados = [u for u in usuarios_mencionados if u.lower() != 'noresta']
        logger.info(f"'noresta' activado para el evento '{nombre_evento}'.")

    usuarios_final = set()
    no_encontrados = []

    for user_name_in_command in usuarios_mencionados:
        nombre_real = next(
            (nombre_registrado for nombre_registrado in user_data
             if nombre_registrado.lower() == user_name_in_command.lower()),
            None
        )
        if nombre_real is None:
            no_encontrados.append(user_name_in_command)
            logger.warning(f"Usuario mencionado '{user_name_in_command}' no encontrado en 'user_data'.")
        else:
            usuarios_final.add(nombre_real)
            logger.debug(f"'{user_name_in_command}' coincide con '{nombre_real}' en user_data.")

    logger.debug(f"Usuarios finales (match en user_data): {usuarios_final}")

    old_scores = {nombre: datos["score"] for nombre, datos in user_data.items()}
    old_justificado = {nombre: (nombre_evento in datos["justified_events"]) for nombre, datos in user_data.items()}

    event_time = datetime.utcnow()
    linked_users_at_event = set(user_data.keys())
    events_info[nombre_evento] = {
        "timestamp": event_time,
        "linked_users": linked_users_at_event,
        "late_users": set(),
        "puntaje": puntaje,
        "penalties": {}
    }
    logger.info(f"Evento '{nombre_evento}' agregado o actualizado en 'events_info' por administrador '{ctx.author}'.")

    estados_usuario = {}

    if noresta:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                estados_usuario[nombre] = "VACACIONES"
                logger.debug(f"Usuario '{nombre}' está de vacaciones. Estado: VACACIONES.")
                continue

            if nombre in usuarios_final:
                datos["score"] += puntaje
                registrar_cambio_dkp(nombre, +puntaje, f"Evento {nombre_evento}: ASISTIÓ (noresta)")
                logger.debug(
                    f"Usuario '{nombre}' asistió al evento '{nombre_evento}'. DKP +{puntaje}."
                )

                if nombre_evento in datos.get("justified_events", set()):
                    datos["justified_events"].remove(nombre_evento)
                    logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para '{nombre}'.")
            else:
                pass

            if (nombre_evento in datos.get("justified_events", set())
                or (datos.get("absence_until") and event_time <= datos["absence_until"])):
                estados_usuario[nombre] = "JUSTIFICADO"
            elif nombre in usuarios_final:
                estados_usuario[nombre] = "ASISTIÓ"
            else:
                estados_usuario[nombre] = "NO ASISTIÓ"

    else:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                estados_usuario[nombre] = "VACACIONES"
                logger.debug(f"Usuario '{nombre}' de vacaciones. Estado: VACACIONES.")
                continue

            absence_until = datos.get("absence_until")
            justificado_by_days = absence_until and event_time <= absence_until
            justificado_by_event = (nombre_evento in datos.get("justified_events", set()))
            justificado_evento = justificado_by_days or justificado_by_event

            if justificado_evento:
                estado = "JUSTIFICADO"
            elif nombre in usuarios_final:
                estado = "ASISTIÓ"
            else:
                estado = "NO ASISTIÓ"

            estados_usuario[nombre] = estado

            if nombre in usuarios_final:
                datos["score"] += puntaje
                registrar_cambio_dkp(nombre, +puntaje, f"Evento {nombre_evento}: ASISTIÓ")
                logger.debug(f"Usuario '{nombre}' asistió. DKP +{puntaje}.")

                if justificado_by_event:
                    datos["justified_events"].remove(nombre_evento)
                    logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para '{nombre}'.")

            else:
                if justificado_evento:
                    datos["score"] -= puntaje
                    registrar_cambio_dkp(nombre, -puntaje, f"Evento {nombre_evento}: JUSTIFICADO")
                    logger.debug(f"Usuario '{nombre}' justificado. DKP -{puntaje}.")

                    if justificado_by_event:
                        datos["justified_events"].remove(nombre_evento)
                else:
                    penalizacion = puntaje * 2
                    datos["score"] -= penalizacion
                    registrar_cambio_dkp(nombre, -penalizacion, f"Evento {nombre_evento}: NO ASISTIÓ")
                    logger.debug(f"Usuario '{nombre}' no asistió sin justificación. DKP -{penalizacion}.")

                    if nombre_evento in events_info:
                        events_info[nombre_evento]["penalties"][nombre] = penalizacion
                    else:
                        logger.error(f"Evento '{nombre_evento}' no existe al asignar penalización.")
                        await ctx.send(embed=discord.Embed(
                            title="Error Interno",
                            description="Ocurrió un error al asignar penalizaciones. Contacta al administrador.",
                            color=discord.Color.red()
                        ))
                        return

    guardar_datos()
    guardar_eventos()

    all_users = sorted(user_data.items(), key=lambda x: x[0].lower())
    desc = "```\n"
    desc += "{:<15} {:<15} {:<10} {:<10}\n".format("Nombre", "Estado", "Antes", "Después")
    desc += "-"*55 + "\n"
    for nombre, datos in all_users:
        antes = old_scores.get(nombre, 0)
        despues = datos["score"]
        estado = estados_usuario.get(nombre, "ACTIVO")
        desc += "{:<15} {:<15} {:<10} {:<10}\n".format(nombre, estado, str(antes), str(despues))
    desc += "```"

    embed = discord.Embed(
        title=f"Evento: {nombre_evento}",
        color=discord.Color.blurple(),
        description=desc
    )
    await ctx.send(embed=embed)
    logger.info(f"Evento '{nombre_evento}' procesado y embed enviado por '{ctx.author}'.")

    if no_encontrados:
        mensaje_no_encontrados = "No se encontraron los siguientes usuarios:\n" + ", ".join(no_encontrados)
        await ctx.send(embed=discord.Embed(
            title="Usuarios no encontrados",
            description=mensaje_no_encontrados,
            color=discord.Color.red()
        ))
        logger.warning(f"Usuarios no encontrados al crear el evento '{nombre_evento}': {no_encontrados}")


@bot.command(name="vincular")
@requiere_vinculacion(comando_admin=True)
async def vincular(ctx, member: discord.Member, nombre: str):
    if nombre in user_data:
        await ctx.send(embed=discord.Embed(
            title="Vinculación Fallida",
            description=f"El nombre **{nombre}** ya está vinculado a otro usuario.",
            color=discord.Color.red()
        ))
        logger.warning(f"Intento de vincular usuario '{member}' con nombre ya existente '{nombre}'.")
        return

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
        title="Vinculación Completada",
        description=f"El usuario {member.mention} ha sido vinculado al nombre **{nombre}** con estado **ACTIVO**.",
        color=discord.Color.green()
    ))
    logger.info(f"Usuario {member} vinculado al nombre '{nombre}' por administrador '{ctx.author}'.")


@bot.command(name="borrarusuario")
@requiere_vinculacion(comando_admin=True)
async def borrarusuario(ctx, nombre: str):
    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        logger.warning(f"Intento de borrar usuario no existente '{nombre}' por '{ctx.author}'.")
        return

    puntos = user_data[nombre]["score"]
    del user_data[nombre]
    guardar_datos()

    await ctx.send(embed=discord.Embed(
        title="Usuario Borrado",
        description=f"El usuario **{nombre}** con {puntos} DKP ha sido eliminado.",
        color=discord.Color.green()
    ))
    logger.info(f"Usuario '{nombre}' eliminado por '{ctx.author}'. DKP: {puntos}.")


@bot.command(name="sumardkp")
@requiere_vinculacion(comando_admin=True)
async def sumardkp(ctx, nombre: str, puntos_a_sumar: int):
    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        logger.warning(f"Intento de sumar DKP a usuario no existente '{nombre}' por '{ctx.author}'.")
        return

    if puntos_a_sumar <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP Inválido",
            description="La cantidad de DKP a sumar debe ser un número positivo.",
            color=discord.Color.red()
        ))
        logger.warning(f"Administrador '{ctx.author}' intentó sumar DKP no válido: {puntos_a_sumar} a '{nombre}'.")
        return

    user_data[nombre]["score"] += puntos_a_sumar
    registrar_cambio_dkp(nombre, +puntos_a_sumar, f"Comando sumardkp usado por {ctx.author}")
    guardar_datos()

    await ctx.send(embed=discord.Embed(
        title="DKP Actualizado",
        description=f"Se han agregado {puntos_a_sumar} DKP a **{nombre}**. Total: {user_data[nombre]['score']}",
        color=discord.Color.green()
    ))
    logger.info(f"Administrador '{ctx.author}' sumó {puntos_a_sumar} DKP a '{nombre}'. Total: {user_data[nombre]['score']}.")


@bot.command(name="restardkp")
@requiere_vinculacion(comando_admin=True)
async def restardkp(ctx, member: discord.Member, puntos_a_restar: int):
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
        logger.warning(f"Usuario '{member}' no está vinculado en 'user_data'.")
        return

    if puntos_a_restar <= 0:
        await ctx.send(embed=discord.Embed(
            title="DKP Inválido",
            description="La cantidad de DKP a restar debe ser un número positivo.",
            color=discord.Color.red()
        ))
        logger.warning(f"Administrador '{ctx.author}' intentó restar DKP no válido: {puntos_a_restar} a '{nombre_usuario}'.")
        return

    user_data[nombre_usuario]["score"] -= puntos_a_restar
    registrar_cambio_dkp(nombre_usuario, -puntos_a_restar, f"Comando restardkp usado por {ctx.author}")
    guardar_datos()

    await ctx.send(embed=discord.Embed(
        title="DKP Actualizado",
        description=f"Se han restado {puntos_a_restar} DKP a **{nombre_usuario}**. Total: {user_data[nombre_usuario]['score']}",
        color=discord.Color.orange()
    ))
    logger.info(f"Administrador '{ctx.author}' restó {puntos_a_restar} DKP a '{nombre_usuario}'. Total: {user_data[nombre_usuario]['score']}.")


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
        logger.warning(f"Administrador '{ctx.author}' intentó marcar vacaciones a '{nombre}' no existente.")
        return

    user_data[nombre]["status"] = "vacaciones"
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Estado Actualizado",
        description=f"El usuario **{nombre}** ha sido marcado como **VACACIONES**.",
        color=discord.Color.yellow()
    ))
    logger.info(f"Administrador '{ctx.author}' marcó a '{nombre}' como VACACIONES.")


@bot.command(name="ausencia_volvio")
@requiere_vinculacion(comando_admin=True)
async def ausencia_volvio(ctx, nombre: str):
    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        logger.warning(f"Administrador '{ctx.author}' intentó marcar activo a usuario '{nombre}' no existente.")
        return

    user_data[nombre]["status"] = "normal"
    user_data[nombre]["absence_until"] = None
    user_data[nombre]["justified_events"].clear()
    guardar_datos()
    await ctx.send(embed=discord.Embed(
        title="Estado Actualizado",
        description=f"El usuario **{nombre}** ha vuelto de **VACACIONES** y ahora está **ACTIVO**.",
        color=discord.Color.green()
    ))
    logger.info(f"Administrador '{ctx.author}' marcó a '{nombre}' como ACTIVO tras vacaciones.")


############################
# Comando !llegue_tarde
############################
@bot.command(name="llegue_tarde")
@requiere_vinculacion()
async def llegue_tarde(ctx, nombre_evento: str):
    """
    Permite a un usuario justificar su llegada tardía a un evento.
    - Solo se puede usar dentro de los 20 minutos posteriores a !evento NOMBREEVENTO.
    - Solo se puede usar una vez por usuario por evento en el canal de ausencias.
    """
    if ctx.channel.id != CANAL_TARDE:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description="Este comando solo puede usarse en el canal designado para llegadas tardías.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario '{ctx.author}' intentó usar !llegue_tarde en el canal equivocado.")
        return

    if nombre_evento not in events_info:
        await ctx.send(embed=discord.Embed(
            title="Evento No Encontrado",
            description=f"No se encontró el evento **{nombre_evento}**. Usa !evento primero.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario '{ctx.author}' intentó justificar tardanza en evento inexistente '{nombre_evento}'.")
        return

    event = events_info[nombre_evento]
    event_time = event["timestamp"]
    current_time = datetime.utcnow()

    if current_time > event_time + timedelta(minutes=20):
        await ctx.send(embed=discord.Embed(
            title="Tiempo Expirado",
            description=f"Ya pasaron más de 20 minutos para justificar llegada tardía al evento **{nombre_evento}**.",
            color=discord.Color.red()
        ))
        logger.info(f"Usuario '{ctx.author}' tardó más de 20 mins para justificar tardanza en '{nombre_evento}'.")
        return

    nombre_usuario = None
    for nombre, datos in user_data.items():
        if datos.get("discord_id") == ctx.author.id:
            nombre_usuario = nombre
            break

    if nombre_usuario is None:
        await ctx.send(embed=discord.Embed(
            title="No Vinculado",
            description="No se encontró un nombre vinculado a tu usuario. Pide a un oficial que te vincule.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario '{ctx.author}' quiso justificar tardanza sin estar vinculado.")
        return

    if nombre_usuario in event["late_users"]:
        await ctx.send(embed=discord.Embed(
            title="Uso Duplicado",
            description="Ya has justificado tu llegada tardía para este evento.",
            color=discord.Color.red()
        ))
        logger.info(f"Usuario '{nombre_usuario}' intentó llegar tarde dos veces al evento '{nombre_evento}'.")
        return

    if nombre_usuario not in event["linked_users"]:
        await ctx.send(embed=discord.Embed(
            title="No Necesitas Justificación",
            description="Estabas vinculado al momento del evento, tus puntos ya fueron ajustados.",
            color=discord.Color.red()
        ))
        logger.info(f"Usuario '{nombre_usuario}' no necesita tardanza en '{nombre_evento}' (ya estaba vinculado).")
        return

    puntaje = event["puntaje"]
    if nombre_usuario not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario No Vinculado",
            description="Tu usuario no está en el sistema DKP. Pide a un oficial que te vincule.",
            color=discord.Color.red()
        ))
        logger.error(f"'{nombre_usuario}' no está en user_data al justificar tardanza.")
        return

    penalty_amount = event["penalties"].get(nombre_usuario, 0)
    if penalty_amount > 0:
        user_data[nombre_usuario]["score"] += (penalty_amount + puntaje)
        registrar_cambio_dkp(
            nombre_usuario,
            penalty_amount + puntaje,
            f"Llegue tarde: Se elimina penalización y se otorga {puntaje}."
        )
        del event["penalties"][nombre_usuario]
        logger.info(f"Usuario '{nombre_usuario}' recibió devolución de penalización + {puntaje} por llegada tarde en '{nombre_evento}'.")
    else:
        user_data[nombre_usuario]["score"] += puntaje
        registrar_cambio_dkp(
            nombre_usuario,
            +puntaje,
            f"Llegue tarde: Se otorga {puntaje}."
        )
        logger.info(f"Usuario '{nombre_usuario}' justificó tardanza y recibió {puntaje} en '{nombre_evento}'.")

    event["late_users"].add(nombre_usuario)
    guardar_datos()
    guardar_eventos()

    await ctx.send(embed=discord.Embed(
        title="Llegada Tardía Justificada",
        description=f"Se han sumado **{puntaje} DKP** en el evento **{nombre_evento}** para ti, **{nombre_usuario}**.",
        color=discord.Color.green()
    ))


############################
# Tareas para Limpieza
############################
@tasks.loop(minutes=10)
async def limpiar_eventos_expirados():
    global events_info
    ahora = datetime.utcnow()
    eventos_a_eliminar = [
        evento for evento, info in events_info.items()
        if ahora > info["timestamp"] + timedelta(minutes=20)
    ]
    for evento in eventos_a_eliminar:
        del events_info[evento]
        logger.info(f"Evento '{evento}' eliminado por limpieza de eventos expirados.")
    if eventos_a_eliminar:
        guardar_eventos()


@tasks.loop(minutes=10)
async def limpiar_absences_expiradas():
    global user_data
    ahora = datetime.utcnow()
    modificados = False
    for nombre, datos in user_data.items():
        if "absence_until" in datos and datos["absence_until"]:
            if ahora > datos["absence_until"]:
                user_data[nombre]["absence_until"] = None
                modificados = True
                logger.info(f"Ausencia de '{nombre}' ha expirado (limpiada).")
    if modificados:
        guardar_datos()


@tasks.loop(minutes=10)
async def limpiar_eventos_justificados_expirados():
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
            logger.info(f"Evento '{nombre_evento}' (justificado) eliminado por limpieza.")
    if modificados:
        guardar_eventos()


############################
# Manejo de Errores
############################
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Faltan argumentos para este comando.")
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' faltando argumentos.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("No tienes permisos para usar este comando.")
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' sin permisos.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Tipo de argumento inválido.")
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' con argumentos inválidos.")
    else:
        await ctx.send("Ocurrió un error al procesar el comando.")
        logger.error(f"Error en comando '{ctx.command}' usado por '{ctx.author}' (ID: {ctx.author.id}): {error}")
        print(f"Error: {error}")

@bot.event
async def on_command(ctx):
    nombre_comando = ctx.command.name
    usuario = ctx.author
    argumentos = ctx.message.content
    logger.info(f"Comando: {nombre_comando} | Usuario: {usuario} (ID: {usuario.id}) | Argumentos: {argumentos}")

bot.run(TOKEN)