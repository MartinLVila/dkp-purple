import discord
from discord.ext import commands
from utils import requiere_vinculacion
from data_manager import user_data, events_info, registered_events, guardar_eventos, guardar_eventos_registrados, registrar_cambio_dkp, logger
from typing import List

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="evento")
    @requiere_vinculacion(comando_admin=True)
    async def evento(self, ctx, nombre_evento: str, puntaje: int, *usuarios_mencionados):
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

        await handle_evento(
            nombre_evento=nombre_evento,
            puntaje=puntaje,
            noresta=noresta,
            listadenombres=list(usuarios_mencionados),
            channel=ctx.channel,
            executor=ctx.author
        )

    @commands.command(name="registroevento")
    @requiere_vinculacion(comando_admin=True)
    async def registroevento(self, ctx, nombre_evento: str):
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

    @commands.command(name="borrarevento")
    @requiere_vinculacion(comando_admin=True)
    async def borrarevento(self, ctx, nombre_evento: str):
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

def setup(bot):
    bot.add_cog(Events(bot))