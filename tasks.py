import logging
from datetime import datetime, timedelta
from discord.ext import tasks

import data_manager
from data_manager import events_info, user_data
from data_manager import guardar_eventos, guardar_datos

logger = logging.getLogger('bot_tasks')

@tasks.loop(minutes=10)
async def limpiar_eventos_expirados():
    ahora = datetime.utcnow()
    eventos_a_eliminar = [
        evento for evento, info in events_info.items()
        if ahora > info["timestamp"] + timedelta(minutes=60)
    ]
    if eventos_a_eliminar:
        for evento in eventos_a_eliminar:
            del events_info[evento]
            logger.info(f"Evento '{evento}' eliminado por limpieza de eventos expirados.")
        guardar_eventos()

@tasks.loop(minutes=10)
async def limpiar_absences_expiradas():
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
    ahora = datetime.utcnow()
    modificados = False
    for nombre_evento, info in list(events_info.items()):
        evento_time = info["timestamp"]
        if ahora > evento_time + timedelta(minutes=60):
            del events_info[nombre_evento]
            modificados = True
            logger.info(f"Evento '{nombre_evento}' eliminado por limpieza.")
    if modificados:
        guardar_eventos()

def iniciar_tareas(bot):
    limpiar_eventos_expirados.start()
    limpiar_absences_expiradas.start()
    limpiar_eventos_justificados_expirados.start()
    logger.info("Tareas de limpieza iniciadas.")
