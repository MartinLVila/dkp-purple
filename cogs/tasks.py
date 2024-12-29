import discord
from discord.ext import commands, tasks
from data_manager import events_info, guardar_eventos, user_data, guardar_datos, logger
from datetime import datetime, timedelta

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.limpiar_eventos_expirados.start()
        self.limpiar_absences_expiradas.start()
        self.limpiar_eventos_justificados_expirados.start()

    def cog_unload(self):
        self.limpiar_eventos_expirados.cancel()
        self.limpiar_absences_expiradas.cancel()
        self.limpiar_eventos_justificados_expirados.cancel()

    @tasks.loop(minutes=10)
    async def limpiar_eventos_expirados(self):
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
    async def limpiar_absences_expiradas(self):
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
    async def limpiar_eventos_justificados_expirados(self):
        ahora = datetime.utcnow()
        modificados = False
        for nombre_evento, info in list(events_info.items()):
            evento_time = info["timestamp"]
            if ahora > evento_time + timedelta(minutes=20):
                del events_info[nombre_evento]
                modificados = True
                logger.info(f"Evento '{nombre_evento}' (justificado) eliminado por limpieza.")
        if modificados:
            guardar_eventos()

def setup(bot):
    bot.add_cog(Tasks(bot))