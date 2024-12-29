import discord
from discord.ext import commands
from utils import requiere_vinculacion
from data_manager import user_data, score_history, ZONA_HORARIA, logger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dkpdetalle")
    @requiere_vinculacion()
    async def dkp_detalle(self, ctx, *, nombre_usuario: str = None):
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
                fecha_cambio = datetime.fromisoformat(registro["timestamp"]).replace(tzinfo=ZoneInfo("UTC"))
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

    @commands.command(name="dkp")
    @requiere_vinculacion()
    async def score(self, ctx, nombre: str = None):
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

def setup(bot):
    bot.add_cog(General(bot))