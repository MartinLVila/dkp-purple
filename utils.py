from functools import wraps
import discord
from discord.ext import commands
from data_manager import user_data, ADMINS_IDS, logger

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
