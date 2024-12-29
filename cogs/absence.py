import discord
from discord.ext import commands
from utils import requiere_vinculacion, es_admin
from data_manager import user_data, guardar_datos, registered_events, logger
from datetime import datetime, timedelta

class Absence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ausencia")
    @requiere_vinculacion()
    async def ausencia(self, ctx, *args):
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

    @commands.command(name="ausencia_vacaciones")
    @requiere_vinculacion(comando_admin=True)
    async def ausencia_vacaciones(self, ctx, nombre: str):
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

    @commands.command(name="ausencia_volvio")
    @requiere_vinculacion(comando_admin=True)
    async def ausencia_volvio(self, ctx, nombre: str):
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

def setup(bot):
    bot.add_cog(Absence(bot))