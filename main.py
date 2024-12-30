import os
import discord
import json
import logging
import requests
from discord.ext import commands, tasks
from discord.ext.commands import CommandNotFound
from discord.ui import View, Button, Select, Modal, TextInput, TextInputStyle
from discord import ButtonStyle, SelectOption
from dotenv import load_dotenv
from datetime import datetime, timedelta
from functools import wraps
from typing import List
from zoneinfo import ZoneInfo

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
CANAL_ADMIN = int(os.getenv("CANAL_ADMIN"))
CANAL_AUSENCIAS = int(os.getenv("CANAL_AUSENCIAS"))
CANAL_TARDE = int(os.getenv("CANAL_TARDE"))
CANAL_CONSULTA = int(os.getenv("CANAL_CONSULTA"))
ADMINS_IDS = set(map(int, os.getenv("ADMINS_IDS").split(',')))

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")

ARMAS_DISPONIBLES = [
    "Greatsword", "Sword", "Crossbow", "Longbow",
    "Staff", "Wand", "Dagger", "Spear"
]

ROLES_DISPONIBLES = [
    "Ranged DPS", "Mid Range DPS", "Melee DPS",
    "Tank", "Healer"
]

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

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True
)

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

async def handle_evento(nombre_evento: str, puntaje: int, noresta: bool, listadenombres: List[str], channel: discord.TextChannel, executor: discord.User):
    """
    Procesa el evento y actualiza los datos de los usuarios.
    
    :param nombre_evento: Nombre del evento.
    :param puntaje: Puntos DKP a asignar.
    :param noresta: Si el evento resta DKP.
    :param listadenombres: Lista de nombres de usuarios.
    :param channel: Canal donde se enviarán los resultados.
    :param executor: Usuario que ejecutó el comando.
    """
    if puntaje <= 0:
        embed = discord.Embed(
            title="DKP Inválido",
            description="El DKP debe ser un número positivo.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
        logger.warning(
            f"Administrador '{executor}' intentó crear un evento '{nombre_evento}' con puntaje no positivo: {puntaje}."
        )
        return

    user_data_lower = {ud.lower(): ud for ud in user_data.keys()}

    usuarios_final = set()
    no_encontrados = []
    for user_name in listadenombres:
        nombre_real = user_data_lower.get(user_name.lower())
        if nombre_real:
            usuarios_final.add(nombre_real)
        else:
            no_encontrados.append(user_name)

    event_time = datetime.utcnow()
    linked_users_at_event = set(user_data.keys())
    events_info[nombre_evento] = {
        "timestamp": event_time,
        "linked_users": linked_users_at_event,
        "late_users": set(),
        "puntaje": puntaje,
        "penalties": {}
    }
    logger.info(f"Evento '{nombre_evento}' agregado o actualizado en 'events_info' por administrador '{executor}'.")

    old_scores = {nombre: datos["score"] for nombre, datos in user_data.items()}

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
                logger.debug(f"Usuario '{nombre}' asistió al evento '{nombre_evento}'. DKP +{puntaje}.")

                if nombre_evento in datos.get("justified_events", set()):
                    datos["justified_events"].remove(nombre_evento)
                    logger.debug(f"Evento '{nombre_evento}' removido de 'justified_events' para '{nombre}'.")
            else:
                pass

            if (nombre_evento in datos.get("justified_events", set()) or
                (datos.get("absence_until") and event_time <= datos["absence_until"])):
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
                        await channel.send(embed=discord.Embed(
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
    await channel.send(embed=embed)
    logger.info(f"Evento '{nombre_evento}' procesado y embed enviado por '{executor}'.")

    if no_encontrados:
        mensaje_no_encontrados = "No se encontraron los siguientes usuarios:\n" + ", ".join(no_encontrados)
        await channel.send(embed=discord.Embed(
            title="Usuarios no encontrados",
            description=mensaje_no_encontrados,
            color=discord.Color.red()
        ))
        logger.warning(f"Usuarios no encontrados al crear el evento '{nombre_evento}': {no_encontrados}")

    no_asistieron = [nombre for nombre, estado in estados_usuario.items() if estado == "NO ASISTIÓ"]

    if no_asistieron:
        canal_admin = bot.get_channel(CANAL_ADMIN)
        canal_tarde = bot.get_channel(CANAL_TARDE)

        if not canal_admin or not canal_tarde:
            logger.error(f"No se pudo encontrar el canal de administración ({CANAL_ADMIN}) o el canal de llegadas ({CANAL_TARDE}).")
            return

        members_no_asistieron = []
        for nombre_usuario in no_asistieron:
            discord_id = user_data[nombre_usuario].get("discord_id")
            if not discord_id:
                logger.warning(f"Usuario '{nombre_usuario}' no tiene 'discord_id' registrado.")
                continue

            member = discord.utils.get(channel.guild.members, id=discord_id)
            if not member:
                logger.warning(f"No se pudo encontrar el miembro de Discord con el ID '{discord_id}' para el usuario '{nombre_usuario}'.")
                continue

            members_no_asistieron.append(member)

        if members_no_asistieron:
            menciones = ', '.join([member.mention for member in members_no_asistieron])

            embed_notificacion = discord.Embed(
                title="⏰ Justificación de Ausencia",
                description=(
                    f"{menciones}, no asistieron al evento **{nombre_evento}**.\n"
                    f"Tienen **1 hora** para justificar su ausencia usando el comando `!llegue` en {canal_tarde.mention}.\n"
                    f"**Evidencia de Asistencia:** Por favor, proporcionen evidencia de su presencia si fue un error."
                ),
                color=discord.Color.red()
            )
            embed_notificacion.set_footer(text="Tiempo límite: 1 hora desde el evento.")

            try:
                await canal_admin.send(embed=embed_notificacion)
                logger.info(f"Notificación consolidada enviada a {len(members_no_asistieron)} usuarios en '{nombre_evento}'.")
            except Exception as e:
                logger.error(f"Error al enviar notificación consolidada: {e}")


class EquipoView(View):
    def __init__(self, nombre_usuario: str):
        super().__init__(timeout=300)
        self.nombre_usuario = nombre_usuario
        self.main_weapon = None
        self.secondary_weapon = None
        self.role = None

        self.select_main_weapon = Select(
            placeholder="Selecciona tu Arma Principal",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=arma, value=arma) for arma in ARMAS_DISPONIBLES],
            custom_id="select_main_weapon"
        )
        self.select_main_weapon.callback = self.main_weapon_selected
        self.add_item(self.select_main_weapon)

        self.select_secondary_weapon = Select(
            placeholder="Selecciona tu Arma Secundaria",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=arma, value=arma) for arma in ARMAS_DISPONIBLES],
            custom_id="select_secondary_weapon"
        )
        self.select_secondary_weapon.callback = self.secondary_weapon_selected
        self.add_item(self.select_secondary_weapon)

        self.select_role = Select(
            placeholder="Selecciona tu Rol",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=rol, value=rol) for rol in ROLES_DISPONIBLES],
            custom_id="select_role"
        )
        self.select_role.callback = self.role_selected
        self.add_item(self.select_role)

        self.submit_button = Button(label="Enviar", style=ButtonStyle.green)
        self.submit_button.callback = self.submit
        self.add_item(self.submit_button)

    async def main_weapon_selected(self, interaction: discord.Interaction):
        self.main_weapon = self.select_main_weapon.values[0]
        await interaction.response.send_message(
            f"Arma Principal seleccionada: **{self.main_weapon}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Arma Principal: {self.main_weapon}")

    async def secondary_weapon_selected(self, interaction: discord.Interaction):
        self.secondary_weapon = self.select_secondary_weapon.values[0]
        await interaction.response.send_message(
            f"Arma Secundaria seleccionada: **{self.secondary_weapon}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Arma Secundaria: {self.secondary_weapon}")

    async def role_selected(self, interaction: discord.Interaction):
        self.role = self.select_role.values[0]
        await interaction.response.send_message(
            f"Rol seleccionado: **{self.role}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Rol: {self.role}")

    async def submit(self, interaction: discord.Interaction):
        if not (self.main_weapon and self.secondary_weapon and self.role):
            await interaction.response.send_message(
                "Por favor, selecciona todas las opciones antes de enviar.", ephemeral=True
            )
            logger.warning(f"Usuario '{self.nombre_usuario}' intentó enviar sin completar todas las selecciones.")
            return

        await interaction.response.send_modal(GearScoreModal(
            self.nombre_usuario,
            self.main_weapon,
            self.secondary_weapon,
            self.role,
            self
        ))

class GearScoreModal(Modal):
    def __init__(self, nombre_usuario: str, main_weapon: str, secondary_weapon: str, role: str, view: EquipoView):
        super().__init__(title="Completa tu Equipo")
        self.nombre_usuario = nombre_usuario
        self.main_weapon = main_weapon
        self.secondary_weapon = secondary_weapon
        self.role = role
        self.view = view

        self.gear_score = TextInput(
            label="Gear Score",
            placeholder="Ingresa tu Gear Score (número)",
            style=TextInputStyle.short,
            required=True
        )
        self.add_item(self.gear_score)

    async def on_submit(self, interaction: discord.Interaction):
        gear_score_str = self.gear_score.value.strip()
        if not gear_score_str.isdigit():
            await interaction.response.send_message(
                "El Gear Score debe ser un número válido.", ephemeral=True
            )
            logger.warning(f"Usuario '{self.nombre_usuario}' ingresó Gear Score inválido: {gear_score_str}")
            return

        gear_score = int(gear_score_str)
        if gear_score < 0 or gear_score > 10000:
            await interaction.response.send_message(
                "El Gear Score debe estar entre 0 y 10,000.", ephemeral=True
            )
            logger.warning(f"Usuario '{self.nombre_usuario}' ingresó Gear Score fuera de rango: {gear_score}")
            return

        if self.nombre_usuario not in user_data:
            await interaction.response.send_message(
                "Ocurrió un error: tu usuario no está vinculado al sistema DKP.", ephemeral=True
            )
            logger.error(f"Usuario '{self.nombre_usuario}' no encontrado en 'user_data' al configurar equipo.")
            return

        user_data[self.nombre_usuario]["equipo"] = {
            "arma_principal": self.main_weapon,
            "arma_secundaria": self.secondary_weapon,
            "rol": self.role,
            "gear_score": gear_score
        }
        guardar_datos()

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Equipo Configurado",
                description=(
                    f"**Armas:** {self.main_weapon}/{self.secondary_weapon}\n"
                    f"**Rol:** {self.role}\n"
                    f"**Gear Score:** {gear_score}"
                ),
                color=discord.Color.green()
            ),
            ephemeral=True
        )
        logger.info(f"Equipo configurado para '{self.nombre_usuario}': {self.main_weapon}/{self.secondary_weapon}, Rol: {self.role}, Gear Score: {gear_score}")

        self.view.select_main_weapon.disabled = True
        self.view.select_secondary_weapon.disabled = True
        self.view.select_role.disabled = True
        self.view.submit_button.disabled = True
        await interaction.message.edit(view=self.view)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            "Ocurrió un error al procesar tu Gear Score. Por favor, inténtalo de nuevo más tarde.",
            ephemeral=True
        )
        logger.error(f"Error en GearScoreModal para '{self.nombre_usuario}': {error}")

class AusenciaInteractiveView(View):
    def __init__(self, author: discord.User):
        super().__init__(timeout=300)
        self.author = author

        self.select_tipo = Select(
            placeholder="¿Cómo deseas justificar tu ausencia?",
            min_values=1,
            max_values=1,
            options=[
                SelectOption(label="Por Evento", description="Justificar ausencia en uno o varios eventos."),
                SelectOption(label="Por Duración", description="Justificar ausencia por días o vacaciones.")
            ]
        )
        self.select_tipo.callback = self.tipo_seleccionado
        self.add_item(self.select_tipo)

        self.btn_cancelar = Button(label="Cancelar", style=ButtonStyle.danger)
        self.btn_cancelar.callback = self.cancelar
        self.add_item(self.btn_cancelar)

        self.tipo_justificacion = None
        self.eventos = []
        self.duracion = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Este comando es privado y no puedes interactuar con él.",
                ephemeral=True
            )
            return False
        return True

    async def tipo_seleccionado(self, interaction: discord.Interaction):
        self.tipo_justificacion = self.select_tipo.values[0]
        self.remove_item(self.select_tipo)

        if self.tipo_justificacion == "Por Evento":
            self.select_eventos = Select(
                placeholder="Selecciona los eventos a los que te ausentas...",
                min_values=1,
                max_values=len(registered_events),
                options=[
                    SelectOption(label=evento, description=f"Justificar ausencia en {evento}") for evento in sorted(registered_events)
                ]
            )
            self.select_eventos.callback = self.eventos_seleccionados
            self.add_item(self.select_eventos)

            self.btn_siguiente = Button(label="Siguiente", style=ButtonStyle.primary)
            self.btn_siguiente.callback = self.siguiente_evento
            self.add_item(self.btn_siguiente)

        elif self.tipo_justificacion == "Por Duración":
            self.select_duracion = Select(
                placeholder="Selecciona la duración de tu ausencia...",
                min_values=1,
                max_values=1,
                options=[
                    SelectOption(label="1 Día", description="Ausentarse por 1 día"),
                    SelectOption(label="2 Días", description="Ausentarse por 2 días"),
                    SelectOption(label="Vacaciones", description="Solicitar vacaciones")
                ]
            )
            self.select_duracion.callback = self.duracion_seleccionada
            self.add_item(self.select_duracion)

            self.btn_siguiente = Button(label="Siguiente", style=ButtonStyle.primary)
            self.btn_siguiente.callback = self.siguiente_duracion
            self.add_item(self.btn_siguiente)

        await interaction.response.edit_message(view=self)

    async def eventos_seleccionados(self, interaction: discord.Interaction):
        self.eventos = self.select_eventos.values
        await interaction.response.defer()

    async def siguiente_evento(self, interaction: discord.Interaction):
        if not self.eventos:
            await interaction.response.send_message(
                "Por favor, selecciona al menos un evento.",
                ephemeral=True
            )
            return

        self.select_eventos.disabled = True
        self.btn_siguiente.disabled = True

        resumen = "**Resumen de tu ausencia:**\n"
        resumen += f"**Eventos:** {', '.join(self.eventos)}\n"

        embed = discord.Embed(
            title="Confirmar Ausencia por Evento",
            description=resumen,
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        usuario = interaction.user
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None and usuario.id not in ADMINS_IDS:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Vinculado",
                    description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{usuario}' no está vinculado y trató de justificar ausencia interactiva.")
            self.stop()
            return

        for nombre_evento in self.eventos:
            if nombre_evento not in registered_events:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Evento No Registrado",
                        description=f"El evento **{nombre_evento}** no está registrado.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                logger.warning(f"Evento '{nombre_evento}' no está registrado.")
                continue

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            logger.info(f"Usuario '{nombre_usuario}' justificó ausencia para el evento '{nombre_evento}'.")

        guardar_datos()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has justificado tu ausencia para los eventos: {', '.join(self.eventos)}, **{nombre_usuario}**.",
                color=discord.Color.green()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{nombre_usuario}' justificó ausencia por eventos: {self.eventos}.")
        self.stop()

    async def duracion_seleccionada(self, interaction: discord.Interaction):
        self.duracion = self.select_duracion.values[0]
        await interaction.response.defer()

    async def siguiente_duracion(self, interaction: discord.Interaction):
        if not self.duracion:
            await interaction.response.send_message(
                "Por favor, selecciona una duración.",
                ephemeral=True
            )
            return

        self.select_duracion.disabled = True
        self.btn_siguiente.disabled = True

        resumen = "**Resumen de tu ausencia:**\n"
        resumen += f"**Duración:** {self.duracion}\n"

        embed = discord.Embed(
            title="Confirmar Ausencia por Duración",
            description=resumen,
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        usuario = interaction.user
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None and usuario.id not in ADMINS_IDS:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Vinculado",
                    description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{usuario}' no está vinculado y trató de justificar ausencia interactiva.")
            self.stop()
            return

        if self.duracion.lower() == "vacaciones":
            admins_mencionados = ' '.join([f"<@{admin_id}>" for admin_id in ADMINS_IDS])
            mensaje = f"{admins_mencionados} El usuario **{nombre_usuario or usuario.name}** solicitó irse de vacaciones."

            canal_admin = bot.get_channel(CANAL_ADMIN)
            if not canal_admin:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error",
                        description="No se pudo encontrar el canal de administración para notificar.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                logger.error(f"Canal de administración con ID {CANAL_ADMIN} no encontrado.")
                self.stop()
                return

            await canal_admin.send(mensaje)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Solicitud Enviada",
                    description="Tu solicitud de vacaciones ha sido enviada a los administradores.",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
            logger.info(f"Usuario '{nombre_usuario or usuario.name}' solicitó vacaciones.")
            self.stop()
            return

        try:
            dias = int(self.duracion.split()[0])
            if dias < 1 or dias > 2:
                raise ValueError
        except (ValueError, IndexError):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Duración Inválida",
                    description="La duración seleccionada no es válida. Por favor, intenta nuevamente.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{nombre_usuario or usuario.name}' seleccionó una duración inválida: {self.duracion}")
            self.stop()
            return

        ausencia_until = datetime.utcnow() + timedelta(days=dias)
        user_data[nombre_usuario]["absence_until"] = ausencia_until
        guardar_datos()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado por los próximos **{dias} día(s)**, **{nombre_usuario}**.",
                color=discord.Color.green()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{nombre_usuario}' justificó ausencia por {dias} días.")
        self.stop()

    async def cancelar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()
        await interaction.followup.send(
            embed=discord.Embed(
                title="Proceso Cancelado",
                description="Has cancelado la justificación de ausencia.",
                color=discord.Color.orange()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{interaction.user}' canceló el proceso de justificación de ausencia.")
        self.stop()

class AsistenciaView(View):
    def __init__(self, nombres_extraidos: List[str], nombres_coincidentes: List[str]):
        super().__init__(timeout=1700)
        self.nombres_extraidos = nombres_extraidos.copy()
        self.nombres_filtrados = nombres_coincidentes.copy()
        self.current_page = 0
        self.names_per_page = 25
        self.total_pages = (len(self.nombres_filtrados) - 1) // self.names_per_page + 1
        self.evento_seleccionado = None
        self.dkp_seleccionado = None
        self.resta_dkp = None

        self.embed_initial = discord.Embed(
            title="Asistencia del Evento",
            description=(
                "Lista de nombres extraídos de las imágenes. "
                "Puedes copiarlos manualmente si lo deseas.\n\n"
                "**Elimina los nombres que no están en el lugar:**"
            ),
            color=discord.Color.blue()
        )
        self.update_embed()

        self.prev_button = Button(label="Anterior", style=ButtonStyle.primary, custom_id="prev_page")
        self.next_button = Button(label="Siguiente", style=ButtonStyle.primary, custom_id="next_page")
        self.cancel_button = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.cancel_button.callback = self.cancel_operation

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.cancel_button)

        self.select = Select(
            placeholder="Selecciona los nombres a eliminar",
            min_values=0,
            max_values=self.get_max_values(),
            options=self.get_current_options(),
            custom_id="select_eliminar_nombres"
        )
        self.select.callback = self.remove_names
        self.add_item(self.select)

        self.siguiente_button = Button(label="SIGUIENTE", style=ButtonStyle.green, custom_id="siguiente")
        self.siguiente_button.callback = self.iniciar_evento
        self.add_item(self.siguiente_button)

    def get_current_options(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return [SelectOption(label=nombre, value=nombre) for nombre in current_page_names]

    def get_max_values(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return len(current_page_names) if current_page_names else 1

    def update_embed(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        nombres_str = "\n".join(current_page_names)
        embed = self.embed_initial.copy()
        embed.add_field(
            name=f"Nombres ({self.current_page + 1}/{self.total_pages})",
            value=f"```\n{nombres_str}\n```",
            inline=False
        )
        self.embed = embed

    async def remove_names(self, interaction: discord.Interaction):
        nombres_eliminados = self.select.values
        if nombres_eliminados:
            for nombre in nombres_eliminados:
                if nombre in self.nombres_filtrados:
                    self.nombres_filtrados.remove(nombre)

            self.total_pages = (len(self.nombres_filtrados) - 1) // self.names_per_page + 1

            if self.current_page >= self.total_pages:
                self.current_page = self.total_pages - 1 if self.total_pages > 0 else 0

            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()

            self.update_embed()
            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send(
                f"Se han eliminado los siguientes nombres: {', '.join(nombres_eliminados)}.",
                ephemeral=True
            )

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_embed()
            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()
            await interaction.response.edit_message(embed=self.embed, view=self)
        else:
            await interaction.response.send_message("Ya estás en la primera página.", ephemeral=True)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_embed()
            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()
            await interaction.response.edit_message(embed=self.embed, view=self)
        else:
            await interaction.response.send_message("Ya estás en la última página.", ephemeral=True)

    async def cancelar_y_mostrar_lista(self, interaction: discord.Interaction):
        self.clear_items()
        embed = discord.Embed(
            title="Asistencia del Evento",
            description=(
                "Lista de nombres extraídos de las imágenes para copiar manualmente:\n"
                "```\n" + "\n".join(self.nombres_filtrados) + "\n```"
            ),
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def cancel_operation(self, interaction: discord.Interaction):
        await self.cancelar_y_mostrar_lista(interaction)

    async def iniciar_evento(self, interaction: discord.Interaction):
        self.clear_items()
        embed = discord.Embed(
            title="PARA QUE EVENTO?",
            description="Selecciona el evento al que asistieron los nombres listados.",
            color=discord.Color.green()
        )

        for evento in sorted(registered_events):
            boton = Button(label=evento, style=ButtonStyle.primary, custom_id=f"evento_{evento}")
            boton.callback = self.seleccionar_evento
            self.add_item(boton)

        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_evento(self, interaction: discord.Interaction):
        try:
            evento_seleccionado = interaction.component.custom_id.replace("evento_", "")
        except AttributeError:
            try:
                evento_seleccionado = interaction.data['custom_id'].replace("evento_", "")
            except KeyError:
                await interaction.response.send_message(
                    "No se pudo determinar el evento seleccionado.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id del componente en 'seleccionar_evento'.")
                return

        self.evento_seleccionado = evento_seleccionado
        self.clear_items()
        embed = discord.Embed(
            title="CUANTO DKP?",
            description="Selecciona la cantidad de DKP para asignar al evento.",
            color=discord.Color.orange()
        )

        dkp_valores = [3, 9, 21, 45]
        for dkp in dkp_valores:
            boton = Button(label=str(dkp), style=ButtonStyle.primary, custom_id=f"dkp_{dkp}")
            boton.callback = self.seleccionar_dkp
            self.add_item(boton)

        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_dkp(self, interaction: discord.Interaction):
        try:
            self.dkp_seleccionado = int(interaction.component.custom_id.replace("dkp_", ""))
        except AttributeError:
            try:
                self.dkp_seleccionado = int(interaction.data['custom_id'].replace("dkp_", ""))
            except (KeyError, ValueError):
                await interaction.response.send_message(
                    "No se pudo determinar la cantidad de DKP seleccionada.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id del componente en 'seleccionar_dkp'.")
                return

        self.clear_items()
        embed = discord.Embed(
            title="EL EVENTO RESTA DKP?",
            description="¿El evento resta DKP?",
            color=discord.Color.purple()
        )
        boton_si = Button(label="SI", style=ButtonStyle.danger, custom_id="resta_si")
        boton_no = Button(label="NO", style=ButtonStyle.success, custom_id="resta_no")
        boton_si.callback = self.seleccionar_resta
        boton_no.callback = self.seleccionar_resta
        self.add_item(boton_si)
        self.add_item(boton_no)
        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_resta(self, interaction: discord.Interaction):
        try:
            decision = interaction.component.custom_id.replace("resta_", "").upper()
        except AttributeError:
            try:
                decision = interaction.data['custom_id'].replace("resta_", "").upper()
            except KeyError:
                await interaction.response.send_message(
                    "No se pudo determinar la opción seleccionada.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id en 'seleccionar_resta'.")
                return

        self.resta_dkp = True if decision == "SI" else False
        self.clear_items()
        embed = discord.Embed(
            title="CONFIRMAR",
            description=(
                f"**Evento:** {self.evento_seleccionado}\n"
                f"**DKP:** {self.dkp_seleccionado}\n"
                f"**Resta DKP:** {'SI' if self.resta_dkp else 'NO'}\n\n"
                f"**Nombres:**\n```\n" + "\n".join(self.nombres_filtrados) + "\n```"
            ),
            color=discord.Color.gold()
        )
        confirmar = Button(label="CONFIRMAR", style=ButtonStyle.success, custom_id="confirmar")
        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        confirmar.callback = self.confirmar_operacion
        cancelar.callback = self.cancel_operation
        self.add_item(confirmar)
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirmar_operacion(self, interaction: discord.Interaction):
        noresta = not self.resta_dkp
        noresta_str = "NORESTA" if self.resta_dkp else ""
        listadenombres = self.nombres_filtrados
        comando_evento = f"!evento {self.evento_seleccionado} {self.dkp_seleccionado} {noresta_str} " + " ".join(listadenombres)
        comando_evento = comando_evento.strip()

        canal_admin = bot.get_channel(CANAL_ADMIN)
        if canal_admin is None:
            await interaction.response.send_message(
                "No se pudo encontrar el canal de administración.",
                ephemeral=True
            )
            logger.error(f"No se pudo encontrar el canal con ID {CANAL_ADMIN}.")
            return

        await handle_evento(
            nombre_evento=self.evento_seleccionado,
            puntaje=self.dkp_seleccionado,
            noresta=noresta,
            listadenombres=listadenombres,
            channel=canal_admin,
            executor=interaction.user
        )

        self.clear_items()
        embed_final = discord.Embed(
            title="Asistencia Registrada",
            description="La asistencia ha sido registrada exitosamente en el canal de administración.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed_final, view=self)
        self.stop()
        
@bot.command(name="dkpdetalle")
@requiere_vinculacion()
async def dkp_detalle(ctx, *, nombre_usuario: str = None):
    """
    Muestra los cambios de DKP del usuario en los últimos 7 días.
    - Sin argumentos: muestra el detalle del usuario que ejecuta el comando.
    - Con nombre: muestra el detalle del usuario especificado.
    - Con mención: muestra el detalle del usuario mencionado.
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

    elif nombre_usuario:
        nombre_usuario_lower = nombre_usuario.lower()
        found_name = None
        for nombre, datos in user_data.items():
            if nombre.lower() == nombre_usuario_lower:
                found_name = nombre
                break
        if found_name is None:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario con nombre **{nombre_usuario}**.",
                color=discord.Color.red()
            ))
            return
        nombre_usuario = found_name

    else:
        usuario = ctx.author
        found_name = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                found_name = nombre
                break
        if found_name is None:
            await ctx.send(embed=discord.Embed(
                title="No Vinculado",
                description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                color=discord.Color.red()
            ))
            return
        nombre_usuario = found_name

    if nombre_usuario not in score_history or not score_history[nombre_usuario]:
        await ctx.send(embed=discord.Embed(
            title="Sin Cambios",
            description=f"No hay registros de cambios de DKP para **{nombre_usuario}**.",
            color=discord.Color.blue()
        ))
        return

    ahora = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    hace_7_dias = ahora - timedelta(days=7)

    cambios_usuario = score_history[nombre_usuario]

    cambios_7_dias = []
    for registro in cambios_usuario:
        try:
            fecha_cambio = datetime.strptime(registro["timestamp"], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            try:
                fecha_cambio = datetime.strptime(registro["timestamp"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
            except ValueError:
                logger.error(f"Formato de fecha inválido en registro de DKP para '{nombre_usuario}': {registro['timestamp']}")
                continue

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
        fecha_gmt3 = fecha.astimezone(ZONA_HORARIA)
        fecha_str = fecha_gmt3.strftime("%Y-%m-%d %H:%M")
        desc += f"{fecha_str:<18} | {str(delta):>5} | {razon}\n"
    desc += "```"

    embed = discord.Embed(
        title=f"DKP Detalle: {nombre_usuario}",
        description=desc,
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    logger.info(f"Detalle DKP mostrado para '{nombre_usuario}' por '{ctx.author}'.")

@bot.command(name="equipo")
@requiere_vinculacion()
async def equipo(ctx):
    """
    Configura el equipo del usuario seleccionando armas, rol y Gear Score.
    """
    usuario = ctx.author
    nombre_usuario = None
    for nombre, datos in user_data.items():
        if datos.get("discord_id") == usuario.id:
            nombre_usuario = nombre
            break

    if nombre_usuario is None:
        await ctx.send(embed=discord.Embed(
            title="No Vinculado",
            description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario '{usuario}' intentó usar !equipo sin estar vinculado.")
        return

    view = EquipoView(nombre_usuario)
    embed = discord.Embed(
        title="Configura tu Equipo",
        description="Selecciona tus armas y rol, luego envía para ingresar tu Gear Score.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)
    logger.info(f"Usuario '{nombre_usuario}' inició la configuración de equipo con !equipo.")

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
    if len(args) == 0:
        view = AusenciaInteractiveView(author=ctx.author)
        embed = discord.Embed(
            title="📅 Justificar Ausencia",
            description="¿Para qué eventos o quieres justificar tu ausencia?",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)
        logger.info(f"Usuario '{ctx.author}' inició el proceso interactivo de !ausencia.")
        return

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

            ausencia_until = datetime.utcnow() + timedelta(days=dias)
            user_data[nombre_usuario]["absence_until"] = ausencia_until
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

            ausencia_until = datetime.utcnow() + timedelta(days=dias)
            user_data[nombre_usuario]["absence_until"] = ausencia_until
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
    """
    Muestra el DKP de un usuario específico o una tabla completa de DKP con detalles del equipo.
    - Sin argumentos: Muestra una tabla completa de DKP con detalles del equipo.
    - Con nombre o mención: Muestra detalles del DKP y equipo del usuario especificado.
    """
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

        equipo = user_data[nombre_usuario].get("equipo", {})
        arma_principal = equipo.get("arma_principal", "N/A")
        arma_secundaria = equipo.get("arma_secundaria", "N/A")
        rol = equipo.get("rol", "N/A")
        gear_score = equipo.get("gear_score", "N/A")

        armas = f"{arma_principal}/{arma_secundaria}"

        puntos = user_data[nombre_usuario]["score"]
        color = discord.Color.green() if puntos >= 0 else discord.Color.red()

        desc = (
            f"**Nombre:** {nombre_usuario}\n"
            f"**DKP:** {puntos}\n"
            f"**Armas:** {armas}\n"
            f"**Rol:** {rol}\n"
            f"**Gear Score:** {gear_score}"
        )

        embed = discord.Embed(
            title=f"DKP Detalle: {nombre_usuario}",
            description=desc,
            color=color
        )

        if not equipo:
            embed.add_field(
                name="⚠️ Equipo No Configurado",
                value="Tu equipo aún no está configurado. Usa `!equipo` para establecer tu Arma Principal, Arma Secundaria y Gear Score.",
                inline=False
            )

        await ctx.send(embed=embed)
        logger.info(f"Detalle DKP mostrado para '{nombre_usuario}' por '{ctx.author}'.")
    else:
        if not user_data:
            await ctx.send("No hay datos de usuarios aún.")
            return

        all_users = sorted(user_data.items(), key=lambda x: x[0].lower())

        encabezados = (
            f"{'Nombre':<15} {'DKP':<5} {'Armas':<25} {'GS':<5}\n"
            f"{'-'*15} {'-'*5} {'-'*25} {'-'*5}\n"
        )

        embed_title_base = "Tabla de DKP"
        embed_description = f"```{encabezados}"
        max_length = 4096 - len(embed_title_base) - len("```") - 50
        embeds = []

        for nombre_u, datos in all_users:
            puntos = datos["score"]

            equipo = datos.get("equipo", {})
            arma_principal = equipo.get("arma_principal", "N/A")
            arma_secundaria = equipo.get("arma_secundaria", "N/A")
            gear_score = equipo.get("gear_score", "N/A")

            armas = f"{arma_principal}/{arma_secundaria}"

            linea = f"{nombre_u:<15} {puntos:<5} {armas:<25} {gear_score:<5}\n"

            if len(embed_description) + len(linea) + len("```") > max_length:
                embed_description += "```"
                embeds.append(discord.Embed(
                    title=embed_title_base,
                    description=embed_description,
                    color=discord.Color.blue()
                ))
                embed_description = f"```{encabezados}"

            embed_description += linea

        if embed_description != f"```{encabezados}":
            embed_description += "```"
            embeds.append(discord.Embed(
                title=embed_title_base,
                description=embed_description,
                color=discord.Color.blue()
            ))

        for embed in embeds:
            await ctx.send(embed=embed)

        logger.info(f"Se mostró la tabla completa de DKP a {ctx.author}. Total embeds enviados: {len(embeds)}")

############################
# Comandos Administrativos
############################
def clean_name(line: str) -> str:
    """
    SOLO PARA ESTE PROYECTO TODO: ARREGLARLO
    Reemplaza substrings por nombres esperados:
      - Si la línea contiene 'abyss'  -> 'abyss'
      - Si la línea contiene 'mob'    -> 'mob'
      - Si la línea contiene 'killa'  -> 'Killa'
      - Si la línea contiene 'nebu'   -> 'xNebu'
      - Si la línea contiene 'tinta china' -> 'ャンクス'

    Si no coincide con nada, se retorna tal cual.
    SOLO PARA ESTE PROYECTO TODO: ARREGLARLO
    """
    lower_line = line.lower()

    if "abyss" in lower_line:
        return "abyss"
    if "mob" in lower_line:
        return "mob"
    if "killa" in lower_line:
        return "Killa"
    if "nebu" in lower_line:
        return "xNebu"
    if "tinta china" in lower_line:
        return "ャンクス"

    return line

@bot.command(name="asistencia")
@requiere_vinculacion(comando_admin=True)
async def asistencia(ctx):
    """
    Comando interactivo para registrar asistencia a un evento.
    Uso: !asistencia [adjuntar imágenes con nombres]
    """
    if not ctx.message.attachments:
        await ctx.send("Por favor, adjunta al menos una imagen PNG/JPG con la lista de nombres.")
        return

    nombres_extraidos = []
    nombres_coincidentes = set()
    user_data_lower = {ud.lower(): ud for ud in user_data.keys()}

    for attachment in ctx.message.attachments:
        filename_lower = attachment.filename.lower()
        if not (filename_lower.endswith(".png") or filename_lower.endswith(".jpg") or filename_lower.endswith(".jpeg")):
            await ctx.send(f"Archivo '{attachment.filename}' no es PNG/JPG. Se omite.")
            continue

        image_data = await attachment.read()
        url = "https://api.ocr.space/parse/image"

        try:
            response = requests.post(
                url,
                files={"filename": (attachment.filename, image_data)},
                data={
                    "apikey": OCR_SPACE_API_KEY,
                    "language": "spa",
                    "OCREngine": "2",
                    "filetype": "PNG",
                },
                timeout=60
            )
            result = response.json()

            if not result.get("IsErroredOnProcessing"):
                parsed_results = result.get("ParsedResults", [])
                if parsed_results:
                    ocr_text = parsed_results[0].get("ParsedText", "")
                    lineas = [l.strip() for l in ocr_text.splitlines() if l.strip()]
                    nombres_extraidos.extend(lineas)

                    for linea in lineas:
                        linea_limpia = clean_name(linea)
                        nd_lower = linea_limpia.lower()
                        if nd_lower in user_data_lower:
                            nombres_coincidentes.add(user_data_lower[nd_lower])
                else:
                    await ctx.send(f"OCR.Space no devolvió resultados para {attachment.filename}.")
            else:
                err_msg = result.get("ErrorMessage", ["Desconocido"])[0]
                await ctx.send(f"OCR.Space reportó error en {attachment.filename}: {err_msg}")

        except requests.RequestException as e:
            await ctx.send(f"Error al conectar con OCR.Space para {attachment.filename}: {e}")
            continue

    if not nombres_extraidos:
        await ctx.send("No se extrajeron nombres de las imágenes proporcionadas.")
        return

    if not nombres_coincidentes:
        await ctx.send("No hubo coincidencias con user_data en las imágenes.")
        return

    view = AsistenciaView(nombres_extraidos, list(nombres_coincidentes))
    await ctx.send(embed=view.embed, view=view)
    logger.info(f"Comando !asistencia ejecutado por {ctx.author}. Nombres extraídos: {nombres_extraidos}")

@bot.command(name="evento")
@requiere_vinculacion(comando_admin=True)
async def evento(ctx, nombre_evento: str, puntaje: int, *usuarios_mencionados):
    """
    Comando para registrar un evento y asignar DKP a los usuarios.
    Uso: !evento <nombre_evento> <puntaje> [usuarios] [NORESTA]
    """
    noresta = False
    usuarios_mencionados_lower = [u.lower() for u in usuarios_mencionados]
    if 'noresta' in usuarios_mencionados_lower:
        noresta = True
        usuarios_mencionados = [u for u in usuarios_mencionados if u.lower() != 'noresta']
        logger.info(f"'NORESTA' activado para el evento '{nombre_evento}'.")

    await handle_evento(nombre_evento, puntaje, noresta, list(usuarios_mencionados), ctx.channel, ctx.author)


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
# Comando para Gestionar Vacaciones
############################
@bot.command(name="vacaciones")
@requiere_vinculacion(comando_admin=True)
async def vacaciones(ctx, nombre: str):
    """
    Activa o desactiva el estado de vacaciones para un usuario.
    Uso: !vacaciones <nombre_usuario>
    """
    nombre = nombre.strip()
    
    if nombre not in user_data:
        await ctx.send(embed=discord.Embed(
            title="Usuario no encontrado",
            description=f"No se encontró el usuario con nombre **{nombre}**.",
            color=discord.Color.red()
        ))
        logger.warning(f"Administrador '{ctx.author}' intentó cambiar vacaciones para usuario no existente '{nombre}'.")
        return
    
    estado_actual = user_data[nombre].get("status", "normal")
    
    if estado_actual != "vacaciones":
        user_data[nombre]["status"] = "vacaciones"
        user_data[nombre]["absence_until"] = None
        user_data[nombre]["justified_events"].clear()
        guardar_datos()
        
        await ctx.send(embed=discord.Embed(
            title="Vacaciones Activadas",
            description=f"El usuario **{nombre}** ha sido marcado como **VACACIONES**.",
            color=discord.Color.yellow()
        ))
        logger.info(f"Administrador '{ctx.author}' activó vacaciones para '{nombre}'.")
    else:
        user_data[nombre]["status"] = "normal"
        user_data[nombre]["absence_until"] = None
        user_data[nombre]["justified_events"].clear()
        guardar_datos()
        
        await ctx.send(embed=discord.Embed(
            title="Vacaciones Desactivadas",
            description=f"El usuario **{nombre}** ha vuelto a estar **ACTIVO**.",
            color=discord.Color.green()
        ))
        logger.info(f"Administrador '{ctx.author}' desactivó vacaciones para '{nombre}'.")

############################
#Comando !info
############################
@bot.command(name="info")
@requiere_vinculacion()
async def info(ctx):
    """
    Proporciona una lista de comandos disponibles para el usuario.
    - Usuarios Regulares: Muestra comandos que pueden usar.
    - Administradores: Muestra comandos adicionales de administración.
    """
    embed = discord.Embed(
        title="Información de Comandos",
        description="Aquí tienes una lista de los comandos que puedes utilizar:",
        color=discord.Color.blue()
    )
    
    user_commands = [
        ("!dkp", "Consulta tu DKP o el de otro usuario."),
        ("!dkpdetalle", "Muestra los cambios de DKP en los últimos 7 días."),
        ("!ausencia", "Justifica una ausencia por días o evento."),
        ("!llegue", "Justifica tu llegada tardía a un evento.")
    ]
    
    admin_commands = [
        ("!vacaciones <nombre_usuario>", "Activa o desactiva el estado de vacaciones de un usuario."),
        ("!registroevento <nombre_evento>", "Registra un evento permanente (son los botones de asistencia)."),
        ("!borrarevento <nombre_evento>", "Elimina un evento permanente (son los botones de asistencia)."),
        ("!evento <nombre_evento> <puntaje> [usuarios] [NORESTA]", "Registra un evento y asigna DKP."),
        ("!vincular <miembro> <nombre>", "Vincula un usuario de Discord con un nombre en el sistema DKP."),
        ("!borrarusuario <nombre>", "Elimina un usuario del sistema DKP."),
        ("!sumardkp <nombre> <puntos>", "Suma puntos DKP a un usuario."),
        ("!restardkp <miembro> <puntos>", "Resta puntos DKP a un usuario."),
        ("!asistencia <imagenes>", "Proceso interactivo para generar el DKP")
    ]
    
    embed.add_field(
        name="🔹 Comandos de Usuario",
        value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in user_commands]),
        inline=False
    )
    
    if es_admin(ctx):
        embed.add_field(
            name="🔸 Comandos Administrativos",
            value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in admin_commands]),
            inline=False
        )
    
    embed.set_footer(text="Usa !dkp para más información sobre tus puntos DKP.")
    
    await ctx.send(embed=embed)
    logger.info(f"Comando !info ejecutado por '{ctx.author}' (ID: {ctx.author.id}).")

############################
# Comando !llegue
############################
@bot.command(name="llegue")
@requiere_vinculacion()
async def llegue(ctx, nombre_evento: str):
    """
    Permite a un usuario justificar su llegada tardía a un evento.
    - Solo se puede usar dentro de 1 hora posterior a !evento NOMBREEVENTO.
    - Solo se puede usar una vez por usuario por evento en el canal de ausencias.
    """
    if ctx.channel.id != CANAL_TARDE:
        await ctx.send(embed=discord.Embed(
            title="Canal Incorrecto",
            description="Este comando solo puede usarse en el canal designado para llegadas tardías.",
            color=discord.Color.red()
        ))
        logger.warning(f"Usuario '{ctx.author}' intentó usar !llegue en el canal equivocado.")
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

    if current_time > event_time + timedelta(minutes=60):
        await ctx.send(embed=discord.Embed(
            title="Tiempo Expirado",
            description=f"Ya pasó más de **1 hora** para justificar tu llegada tardía al evento **{nombre_evento}**.",
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
    if isinstance(error, CommandNotFound):
        embed = discord.Embed(
            title="🔍 Comando No Encontrado",
            description=(
                f"El comando `{ctx.message.content}` no existe.\n"
                "Por favor, verifica la lista de comandos disponibles usando `!info`."
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        logger.warning(f"Comando no encontrado: '{ctx.message.content}' usado por '{ctx.author}'.")
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❗ Argumento Faltante",
            description="Faltan argumentos para este comando. Por favor, revisa el uso correcto con `!info`.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' faltando argumentos.")
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="🚫 Permiso Denegado",
            description="No tienes permisos para usar este comando.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' sin permisos.")
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="⚠️ Argumento Inválido",
            description="Tipo de argumento inválido. Por favor, verifica el comando y los argumentos utilizados.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        logger.warning(f"Comando '{ctx.command}' de '{ctx.author}' con argumentos inválidos.")
    else:
        embed = discord.Embed(
            title="❌ Error Interno",
            description="Ocurrió un error al procesar el comando. Por favor, inténtalo de nuevo más tarde.",
            color=discord.Color.dark_red()
        )
        await ctx.send(embed=embed)
        logger.error(f"Error en comando '{ctx.command}' usado por '{ctx.author}' (ID: {ctx.author.id}): {error}")
        print(f"Error: {error}")

@bot.event
async def on_command(ctx):
    nombre_comando = ctx.command.name
    usuario = ctx.author
    argumentos = ctx.message.content
    logger.info(f"Comando: {nombre_comando} | Usuario: {usuario} (ID: {usuario.id}) | Argumentos: {argumentos}")

bot.run(TOKEN)