import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List
import discord

logger = logging.getLogger('bot_commands')

DATA_FILE = "scores.json"
EVENTS_FILE = "events.json"
REGISTERED_EVENTS_FILE = "registered_events.json"
HISTORY_FILE = "score_history.json"

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")

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
                            datos["absence_until"] = datetime.fromisoformat(datos["absence_until"])
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
                        info["timestamp"] = datetime.fromisoformat(info["timestamp"])
                    except ValueError as ve:
                        logger.error(f"Error al parsear 'timestamp' para el evento '{evento}': {ve}. Asignando la hora actual.")
                        info["timestamp"] = datetime.utcnow()
    
                    if isinstance(info.get("linked_users"), list):
                        info["linked_users"] = set(info["linked_users"])
                    else:
                        logger.warning(f"'linked_users' para el evento '{evento}' no es una lista. Inicializando como conjunto vacío.")
                        info["linked_users"] = set()
    
                    if isinstance(info.get("late_users"), list):
                        info["late_users"] = set(info["late_users"])
                    else:
                        logger.warning(f"'late_users' para el evento '{evento}' no es una lista. Inicializando como conjunto vacío.")
                        info["late_users"] = set()
    
                    if isinstance(info.get("penalties"), dict):
                        info["penalties"] = info.get("penalties", {})
                    else:
                        logger.warning(f"'penalties' para el evento '{evento}' no es un diccionario. Inicializando como diccionario vacío.")
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

async def handle_evento(nombre_evento: str, puntaje: int, noresta: bool, listadenombres: List[str], channel, executor):
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
                        embed_error = discord.Embed(
                            title="Error Interno",
                            description="Ocurrió un error al asignar penalizaciones. Contacta al administrador.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed_error)
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
        desc += "{:<15} {:<15} 