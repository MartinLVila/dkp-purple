import discord
from discord.ext import commands
from utils import requiere_vinculacion
from data_manager import user_data, guardar_datos, registrar_cambio_dkp, logger

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="vincular")
    @requiere_vinculacion(comando_admin=True)
    async def vincular(self, ctx, member: discord.Member, nombre: str):
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

    @commands.command(name="borrarusuario")
    @requiere_vinculacion(comando_admin=True)
    async def borrarusuario(self, ctx, nombre: str):
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

    @commands.command(name="sumardkp")
    @requiere_vinculacion(comando_admin=True)
    async def sumardkp(self, ctx, nombre: str, puntos_a_sumar: int):
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

    @commands.command(name="restardkp")
    @requiere_vinculacion(comando_admin=True)
    async def restardkp(self, ctx, member: discord.Member, puntos_a_restar: int):
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == member.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None:
            await ctx.send(embed=discord.Embed(
                title="Usuario No Vinculado",
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

def setup(bot):
    bot.add_cog(Admin(bot))