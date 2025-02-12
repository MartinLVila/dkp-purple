import os
import logging
import requests
import discord

from discord.ext import commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from event_logic import handle_evento

import data_manager
from data_manager import (
    user_data,
    events_info,
    registered_events,
    score_history,
    PARTYS,
    registrar_cambio_dkp,
    guardar_datos,
    guardar_eventos,
    guardar_eventos_registrados,
    save_partys,
    ZONA_HORARIA
)

import utils
from utils import split_into_chunks, clean_name

from views import (
    EquipoView,
    AusenciaInteractiveView,
    AsistenciaView,
    CrearPartyModal,
    ArmarPartysView
)

logger = logging.getLogger('bot_commands')

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "")
CANAL_ADMIN = int(os.getenv("CANAL_ADMIN", 0))
CANAL_TARDE = int(os.getenv("CANAL_TARDE", 0))
CANAL_AUSENCIAS = int(os.getenv("CANAL_AUSENCIAS", 0))
CANAL_CONSULTA = int(os.getenv("CANAL_CONSULTA", 0))

ADMINS_IDS = set()
if os.getenv("ADMINS_IDS"):
    ADMINS_IDS = set(map(int, os.getenv("ADMINS_IDS").split(',')))

ARMAS_DISPONIBLES = [
    "Greatsword", "Sword", "Crossbow", "Longbow",
    "Staff", "Wand", "Dagger", "Spear"
]
ROLES_DISPONIBLES = [
    "Ranged DPS", "Mid Range DPS", "Melee DPS",
    "Tank", "Healer"
]

def requiere_vinculacion(comando_admin=False):
    def decorator(func):
        @commands.check
        async def wrapper(ctx: commands.Context, *args, **kwargs):
            if comando_admin:
                if ctx.author.id not in ADMINS_IDS:
                    embed = discord.Embed(
                        title="Permiso Denegado",
                        description="No tienes permisos para usar este comando.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    raise commands.CheckFailure("Usuario sin permisos de administrador.")
            else:
                nombre_usuario = None
                for nombre, datos in user_data.items():
                    if datos.get("discord_id") == ctx.author.id:
                        nombre_usuario = nombre
                        break
                if (not nombre_usuario) and (ctx.author.id not in ADMINS_IDS):
                    embed = discord.Embed(
                        title="No Vinculado",
                        description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                        color=discord.Color.red()
                    )
                    await ctx.send(embed=embed)
                    raise commands.CheckFailure("Usuario no vinculado.")
            return True
        return commands.check(wrapper)(func)
    return decorator

class DKPCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dkpdetalle")
    @requiere_vinculacion()
    async def dkp_detalle(self, ctx, *, nombre_usuario: str = None):
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
                    description=f"No se encontró el usuario **{nombre_usuario}**.",
                    color=discord.Color.red()
                ))
                return
            nombre_usuario = found_name
        else:
            user_id = ctx.author.id
            found_name = None
            for nombre, datos in user_data.items():
                if datos.get("discord_id") == user_id:
                    found_name = nombre
                    break
            if found_name is None:
                await ctx.send(embed=discord.Embed(
                    title="No Vinculado",
                    description="No estás vinculado. Pide a un oficial que te vincule.",
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
                    logger.error(f"Formato de fecha inválido en registro DKP de '{nombre_usuario}': {registro['timestamp']}")
                    continue

            if fecha_cambio >= hace_7_dias:
                cambios_7_dias.append((fecha_cambio, registro["delta"], registro.get("razon", "")))

        if not cambios_7_dias:
            await ctx.send(embed=discord.Embed(
                title="DKP Detalle",
                description=f"No hubo cambios de DKP para **{nombre_usuario}** en los últimos 7 días.",
                color=discord.Color.blue()
            ))
            return

        cambios_7_dias.sort(key=lambda x: x[0])  # ordenar por fecha
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

    @commands.command(name="equipo")
    @requiere_vinculacion()
    async def equipo(self, ctx):
        usuario = ctx.author
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None:
            await ctx.send(embed=discord.Embed(
                title="No Vinculado",
                description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule.",
                color=discord.Color.red()
            ))
            return

        view = EquipoView(nombre_usuario)
        embed = discord.Embed(
            title="Configura tu Equipo",
            description="Selecciona tus armas y rol, luego envía para ingresar tu Gear Score.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name="registroevento")
    @requiere_vinculacion(comando_admin=True)
    async def registroevento(self, ctx, nombre_evento: str):
        nombre_evento_lower = nombre_evento.lower()
        for evt in registered_events:
            if evt.lower() == nombre_evento_lower:
                await ctx.send(embed=discord.Embed(
                    title="Evento Ya Registrado",
                    description=f"El evento **{nombre_evento}** ya existe.",
                    color=discord.Color.red()
                ))
                return

        registered_events.add(nombre_evento)
        guardar_eventos_registrados()
        await ctx.send(embed=discord.Embed(
            title="Evento Registrado",
            description=f"Evento permanente **{nombre_evento}** registrado.",
            color=discord.Color.green()
        ))

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
                description=f"No se encontró el evento permanente **{nombre_evento}**.",
                color=discord.Color.red()
            ))
            return

        registered_events.remove(to_remove)
        guardar_eventos_registrados()
        await ctx.send(embed=discord.Embed(
            title="Evento Eliminado",
            description=f"Se eliminó el evento permanente **{to_remove}**.",
            color=discord.Color.green()
        ))

    @commands.command(name="ausencia")
    @requiere_vinculacion()
    async def ausencia(self, ctx, *args):
        if len(args) == 0:
            view = AusenciaInteractiveView(author=ctx.author)
            embed = discord.Embed(
                title="📅 Justificar Ausencia",
                description="¿Para qué eventos o cuántos días deseas justificar?",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, view=view)
            return

        usuario = ctx.author
        if ctx.author.id in ADMINS_IDS:
            if len(args) != 2:
                await ctx.send(embed=discord.Embed(
                    title="Uso Incorrecto",
                    description="Uso (admin): !ausencia <nombre_usuario> <dias> o <nombre_evento>",
                    color=discord.Color.red()
                ))
                return

            nombre_usuario_arg = args[0]
            segundo_arg = args[1]

            if nombre_usuario_arg not in user_data:
                await ctx.send(embed=discord.Embed(
                    title="Usuario no encontrado",
                    description=f"No se encontró el usuario **{nombre_usuario_arg}**.",
                    color=discord.Color.red()
                ))
                return

            try:
                dias = int(segundo_arg)
                if dias < 1 or dias > 3:
                    raise ValueError
                ausencia_until = datetime.utcnow() + timedelta(days=dias)
                user_data[nombre_usuario_arg]["absence_until"] = ausencia_until
                await guardar_datos()

                await ctx.send(embed=discord.Embed(
                    title="Ausencia Justificada",
                    description=(f"Ausencia por **{dias}** día(s) para **{nombre_usuario_arg}**."),
                    color=discord.Color.yellow()
                ))
                return

            except ValueError:
                nombre_evento = segundo_arg
                if not any(evt.lower() == nombre_evento.lower() for evt in registered_events):
                    eventos_disponibles = ", ".join(sorted(registered_events))
                    await ctx.send(embed=discord.Embed(
                        title="Evento No Registrado",
                        description=(
                            f"El evento **{nombre_evento}** no está en la lista.\n\n"
                            f"Eventos disponibles: **{eventos_disponibles}**"
                        ),
                        color=discord.Color.red()
                    ))
                    return
                user_data[nombre_usuario_arg]["justified_events"].add(nombre_evento.upper())
                await guardar_datos()
                await ctx.send(embed=discord.Embed(
                    title="Ausencia Justificada",
                    description=(f"Ausencia para el evento **{nombre_evento}** justificada a **{nombre_usuario_arg}**."),
                    color=discord.Color.yellow()
                ))
                return

        else:
            if len(args) != 1:
                await ctx.send(embed=discord.Embed(
                    title="Uso Incorrecto",
                    description="Uso (usuario): !ausencia <dias> o <nombre_evento>",
                    color=discord.Color.red()
                ))
                return

            primer_arg = args[0]

            nombre_usuario = None
            for n, d in user_data.items():
                if d.get("discord_id") == ctx.author.id:
                    nombre_usuario = n
                    break
            if not nombre_usuario:
                await ctx.send(embed=discord.Embed(
                    title="No Vinculado",
                    description="No se encontró un nombre vinculado a tu usuario.",
                    color=discord.Color.red()
                ))
                return

            try:
                dias = int(primer_arg)
                if dias < 1 or dias > 3:
                    raise ValueError
                ausencia_until = datetime.utcnow() + timedelta(days=dias)
                user_data[nombre_usuario]["absence_until"] = ausencia_until
                await guardar_datos()
                await ctx.send(embed=discord.Embed(
                    title="Ausencia Justificada",
                    description=(f"Ausencia por {dias} día(s) para **{nombre_usuario}**."),
                    color=discord.Color.yellow()
                ))
                return
            except ValueError:
                nombre_evento = primer_arg
                if not any(evt.lower() == nombre_evento.lower() for evt in registered_events):
                    eventos_disponibles = ", ".join(sorted(registered_events))
                    await ctx.send(embed=discord.Embed(
                        title="Evento No Registrado",
                        description=(
                            f"El evento **{nombre_evento}** no está registrado.\n\n"
                            f"Eventos disponibles: **{eventos_disponibles}**\n"
                            "Si falta, pide a un oficial que lo registre."
                        ),
                        color=discord.Color.red()
                    ))
                    return
                user_data[nombre_usuario]["justified_events"].add(nombre_evento.upper())
                await guardar_datos()
                await ctx.send(embed=discord.Embed(
                    title="Ausencia Justificada",
                    description=(f"Ausencia para el evento **{nombre_evento}** justificada a **{nombre_usuario}**."),
                    color=discord.Color.yellow()
                ))
                return

    @commands.command(name="dkp")
    @requiere_vinculacion()
    async def score(self, ctx, nombre: str = None):
        if nombre:
            if ctx.message.mentions:
                member = ctx.message.mentions[0]
                found_name = None
                for nombre_u, datos in user_data.items():
                    if datos.get("discord_id") == member.id:
                        found_name = nombre_u
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
                nombre_usuario_lower = nombre.lower()
                found_name = None
                for nombre_u, datos in user_data.items():
                    if nombre_u.lower() == nombre_usuario_lower:
                        found_name = nombre_u
                        break
                if found_name is None:
                    await ctx.send(embed=discord.Embed(
                        title="Usuario no encontrado",
                        description=f"No se encontró el usuario **{nombre}**.",
                        color=discord.Color.red()
                    ))
                    return
                nombre_usuario = found_name

            equipo = user_data[nombre_usuario].get("equipo", {})
            arma_principal = equipo.get("arma_principal", "N/A")
            arma_secundaria = equipo.get("arma_secundaria", "N/A")
            rol = equipo.get("rol", "N/A")
            gs = equipo.get("gear_score", "N/A")
            puntos = user_data[nombre_usuario]["score"]
            color = discord.Color.green() if puntos >= 0 else discord.Color.red()

            desc = (
                f"**Nombre:** {nombre_usuario}\n"
                f"**DKP:** {puntos}\n"
                f"**Armas:** {arma_principal}/{arma_secundaria}\n"
                f"**Rol:** {rol}\n"
                f"**Gear Score:** {gs}"
            )

            embed = discord.Embed(
                title=f"DKP Detalle: {nombre_usuario}",
                description=desc,
                color=color
            )
            if not equipo:
                embed.add_field(
                    name="⚠️ Equipo No Configurado",
                    value="Usa `!equipo` para establecer tu Arma Principal, Arma Secundaria y Gear Score.",
                    inline=False
                )

            await ctx.send(embed=embed)

        else:
            if not user_data:
                await ctx.send("No hay datos de usuarios aún.")
                return

            all_users = sorted(user_data.items(), key=lambda x: x[0].lower())
            encabezados = (
                f"{'Nombre':<14} {'DKP':<5} {'Armas':<20} {'GS':<4}\n"
                f"{'-'*14} {'-'*5} {'-'*20} {'-'*4}\n"
            )

            embed_title = "Tabla de DKP"
            embed_desc = f"```{encabezados}"
            max_length = 4096 - len(embed_title) - len("```") - 50
            embeds = []

            for nombre_u, datos in all_users:
                puntos = datos["score"]
                equipo = datos.get("equipo", {})
                m_weapon = equipo.get("arma_principal", "N/A")
                s_weapon = equipo.get("arma_secundaria", "N/A")
                gs = equipo.get("gear_score", "N/A")
                armas = f"{m_weapon}/{s_weapon}"

                linea = f"{nombre_u:<14} {puntos:<5} {armas:<20} {gs:<4}\n"
                if len(embed_desc) + len(linea) + len("```") > max_length:
                    embed_desc += "```"
                    embeds.append(discord.Embed(
                        title=embed_title,
                        description=embed_desc,
                        color=discord.Color.blue()
                    ))
                    embed_desc = f"```{encabezados}"

                embed_desc += linea

            if embed_desc != f"```{encabezados}":
                embed_desc += "```"
                embeds.append(discord.Embed(
                    title=embed_title,
                    description=embed_desc,
                    color=discord.Color.blue()
                ))

            for ebd in embeds:
                await ctx.send(embed=ebd)

    @commands.command(name="topdkp")
    @requiere_vinculacion()
    async def topdkp(self, ctx):
        class TopArmasView(discord.ui.View):
            def __init__(self, parent_ctx):
                super().__init__(timeout=300)
                self.parent_ctx = parent_ctx
                for arma in ARMAS_DISPONIBLES:
                    boton = discord.ui.Button(label=arma, style=discord.ButtonStyle.primary)
                    boton.callback = self.generar_callback(arma)
                    self.add_item(boton)

            def generar_callback(self, arma):
                async def callback(interaction: discord.Interaction):
                    usuarios_filtrados = []
                    for nombre, datos in user_data.items():
                        eq = datos.get("equipo", {})
                        if (eq.get("arma_principal") == arma) or (eq.get("arma_secundaria") == arma):
                            usuarios_filtrados.append((nombre, datos["score"], eq))
                    if not usuarios_filtrados:
                        await interaction.response.send_message(
                            f"No hay usuarios con el arma **{arma}**.", ephemeral=True
                        )
                        return
                    usuarios_filtrados.sort(key=lambda x: x[1], reverse=True)
                    top_15 = usuarios_filtrados[:15]

                    desc = f"**Top 15 DKP para {arma}:**\n```\n"
                    desc += "{:<15} {:<5} {:<20}\n".format("Nombre", "DKP", "Armas")
                    desc += "-" * 40 + "\n"
                    for (n, dkp, eq_) in top_15:
                        ap = eq_.get("arma_principal", "N/A")
                        sp = eq_.get("arma_secundaria", "N/A")
                        desc += f"{n:<15} {dkp:<5} {ap}/{sp:<10}\n"
                    desc += "```"

                    emb = discord.Embed(description=desc, color=discord.Color.green())
                    await interaction.message.edit(embed=emb, view=None)
                return callback

        embed = discord.Embed(
            title="Top DKP por Arma",
            description="Selecciona un arma para ver el top 15 DKP.",
            color=discord.Color.blue()
        )
        view = TopArmasView(ctx)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="asistencia")
    @requiere_vinculacion(comando_admin=True)
    async def asistencia(self, ctx):
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
                        "filetype": "PNG"
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
                await ctx.send(f"Error al conectar con OCR.Space: {e}")

        if not nombres_extraidos:
            await ctx.send("No se extrajeron nombres de las imágenes proporcionadas.")
            return

        if not nombres_coincidentes:
            await ctx.send("No hubo coincidencias con user_data en las imágenes.")
            return

        view = AsistenciaView(
            bot=self.bot,
            canal_admin_id=CANAL_ADMIN,
            nombres_extraidos=nombres_extraidos,
            nombres_coincidentes=list(nombres_coincidentes)
        )
        await ctx.send(embed=view.embed, view=view)

    @commands.command(name="evento")
    @requiere_vinculacion(comando_admin=True)
    async def evento(self, ctx, nombre_evento: str, puntaje: int, *usuarios_mencionados):
        noresta = False
        lower_names = [u.lower() for u in usuarios_mencionados]
        if 'noresta' in lower_names:
            noresta = True
            usuarios_mencionados = [u for u in usuarios_mencionados if u.lower() != 'noresta']

        nombre_evento = nombre_evento.upper()
        await handle_evento(
            nombre_evento=nombre_evento,
            puntaje=puntaje,
            noresta=noresta,
            listadenombres=usuarios_mencionados,
            channel=ctx.channel,
            executor=ctx.author
        )

    @commands.command(name="vincular")
    @requiere_vinculacion(comando_admin=True)
    async def vincular(self, ctx, member: discord.Member, nombre: str):
        if nombre in user_data:
            await ctx.send(embed=discord.Embed(
                title="Vinculación Fallida",
                description=f"El nombre **{nombre}** ya está en uso.",
                color=discord.Color.red()
            ))
            return

        user_data[nombre] = {
            "discord_id": member.id,
            "score": 0,
            "justificado": [],
            "justified_events": set(),
            "status": "normal",
            "absence_until": None
        }
        await guardar_datos()
        await ctx.send(embed=discord.Embed(
            title="Vinculación Completada",
            description=f"{member.mention} ha sido vinculado como **{nombre}**.",
            color=discord.Color.green()
        ))

    @commands.command(name="borrarusuario")
    @requiere_vinculacion(comando_admin=True)
    async def borrarusuario(self, ctx, nombre: str):
        if nombre not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario **{nombre}**.",
                color=discord.Color.red()
            ))
            return

        puntos = user_data[nombre]["score"]
        del user_data[nombre]
        await guardar_datos()

        await ctx.send(embed=discord.Embed(
            title="Usuario Borrado",
            description=f"El usuario **{nombre}** con {puntos} DKP ha sido eliminado.",
            color=discord.Color.green()
        ))

    @commands.command(name="revisarvinculacion")
    @requiere_vinculacion(comando_admin=True)
    async def revisar_vinculacion(self, ctx, role_id: int):
        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send(embed=discord.Embed(
                title="Rol no encontrado",
                description=f"No existe rol con ID **{role_id}**.",
                color=discord.Color.red()
            ))
            return

        ids_vinculados = {
            datos.get("discord_id"): nombre
            for nombre, datos in user_data.items() if datos.get("discord_id")
        }

        no_vinculados = []
        for member in role.members:
            if member.id not in ids_vinculados:
                no_vinculados.append(member)

        if not no_vinculados:
            embed = discord.Embed(
                title=f"Rol: {role.name} (ID: {role.id})",
                description="Todos los usuarios de este rol están vinculados.",
                color=discord.Color.green()
            )
        else:
            listado = "\n".join(m.mention for m in no_vinculados)
            embed = discord.Embed(
                title=f"Rol: {role.name} (ID: {role.id})",
                description=f"**No Vinculados:**\n{listado}",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Total: {len(no_vinculados)}")

        await ctx.send(embed=embed)

    @commands.command(name="armarparty")
    @requiere_vinculacion(comando_admin=True)
    async def armarparty(self, ctx, party_name: str = None, *user_names: str):
        if not party_name:
            view = ArmarPartysView()
            embed = discord.Embed(
                title="🛠️ Administrar Partys",
                description="Botones para crear/eliminar/agregar miembros, etc.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, view=view)
            return

        party_name_normalizado = party_name.strip()
        if party_name_normalizado not in PARTYS:
            await ctx.send(embed=discord.Embed(
                title="Party No Encontrada",
                description=f"La party **{party_name_normalizado}** no existe. Usa `!armarparty` sin argumentos para crearla.",
                color=discord.Color.red()
            ))
            return

        usuarios_a_agregar = []
        usuarios_no_encontrados = []
        usuarios_en_otra_party = []

        for nombre in user_names:
            nombre_encontrado = None
            for key in user_data.keys():
                if key.lower() == nombre.lower():
                    nombre_encontrado = key
                    break
            if not nombre_encontrado:
                usuarios_no_encontrados.append(nombre)
                continue

            en_otra = False
            for p_name, miembros in PARTYS.items():
                if nombre_encontrado in miembros and p_name != party_name_normalizado:
                    en_otra = True
                    break
            if en_otra:
                usuarios_en_otra_party.append(nombre_encontrado)
            else:
                usuarios_a_agregar.append(nombre_encontrado)

        if usuarios_no_encontrados or usuarios_en_otra_party:
            desc = ""
            if usuarios_no_encontrados:
                desc += "**No Encontrados:** " + ", ".join(usuarios_no_encontrados) + "\n"
            if usuarios_en_otra_party:
                desc += "**Ya en Otra Party:** " + ", ".join(usuarios_en_otra_party)
            await ctx.send(embed=discord.Embed(
                title="Errores al Agregar Miembros",
                description=desc,
                color=discord.Color.red()
            ))
            return

        if usuarios_a_agregar:
            PARTYS[party_name_normalizado].extend(usuarios_a_agregar)
            save_partys()
            await ctx.send(embed=discord.Embed(
                title="Miembros Agregados",
                description=(
                    f"Agregados a **{party_name_normalizado}**:\n"
                    + ", ".join(usuarios_a_agregar)
                ),
                color=discord.Color.green()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Sin Acciones",
                description="No se agregaron miembros válidos.",
                color=discord.Color.yellow()
            ))

    @commands.command(name="partys")
    @requiere_vinculacion()
    async def partys(self, ctx):
        if not PARTYS:
            await ctx.send("No hay partys definidas todavía.")
            return

        for party_name, miembros in PARTYS.items():
            lines = []
            lines.append(f"{'Nick':<15} {'Armas':<22} {'Rol':<15}")
            lines.append("-" * 55)

            if not miembros:
                lines.append("(Vacío)")
            else:
                for nombre_usuario in miembros:
                    datos = user_data.get(nombre_usuario)
                    if not datos:
                        lines.append(f"{nombre_usuario:<15} {'?':<22} {'?':<15}")
                        continue
                    eq = datos.get("equipo", {})
                    main_weapon = eq.get("arma_principal", "N/A")
                    sec_weapon = eq.get("arma_secundaria", "N/A")
                    rol = eq.get("rol", "N/A")
                    armas = f"{main_weapon}/{sec_weapon}"
                    lines.append(f"{nombre_usuario:<15} {armas:<22} {rol:<15}")

            desc = "```\n" + "\n".join(lines) + "\n```"
            embed = discord.Embed(
                title=party_name,
                description=desc,
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

    @commands.command(name="party")
    @requiere_vinculacion()
    async def party(self, ctx):
        user_id = ctx.author.id
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == user_id:
                nombre_usuario = nombre
                break

        if not nombre_usuario:
            await ctx.send(embed=discord.Embed(
                title="No Vinculado",
                description="No se encontró tu nombre en el sistema DKP.",
                color=discord.Color.red()
            ))
            return

        party_found = None
        for p_name, miembros in PARTYS.items():
            if nombre_usuario in miembros:
                party_found = p_name
                break

        if not party_found:
            await ctx.send(embed=discord.Embed(
                title="Sin Party",
                description="No perteneces a ninguna Party actualmente.",
                color=discord.Color.orange()
            ))
            return

        miembros = PARTYS[party_found]
        lines = []
        lines.append(f"{'Nick':<15} {'Armas':<22} {'Rol':<15}")
        lines.append("-" * 55)
        for miembro in miembros:
            datos = user_data.get(miembro)
            if not datos:
                lines.append(f"{miembro:<15} {'?':<22} {'?':<15}")
                continue
            eq = datos.get("equipo", {})
            main_weapon = eq.get("arma_principal", "N/A")
            sec_weapon = eq.get("arma_secundaria", "N/A")
            rol = eq.get("rol", "N/A")
            armas = f"{main_weapon}/{sec_weapon}"
            lines.append(f"{miembro:<15} {armas:<22} {rol:<15}")

        desc = "```\n" + "\n".join(lines) + "\n```"
        embed = discord.Embed(
            title=f"🛡️ {party_found}",
            description=desc,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="sumardkp")
    @requiere_vinculacion(comando_admin=True)
    async def sumardkp(self, ctx, *args):
        if len(args) != 2:
            await ctx.send("Uso: !sumardkp [usuario] [puntos]")
            return

        nombre_usuario_arg, puntos_str = args
        try:
            puntos_a_sumar = int(puntos_str)
        except ValueError:
            await ctx.send(embed=discord.Embed(
                title="DKP Inválido",
                description="La cantidad de DKP a sumar debe ser un número.",
                color=discord.Color.red()
            ))
            return

        if puntos_a_sumar <= 0:
            await ctx.send(embed=discord.Embed(
                title="DKP Inválido",
                description="La cantidad de DKP a sumar debe ser positiva.",
                color=discord.Color.red()
            ))
            return

        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            found_name = None
            for nombre, datos in user_data.items():
                if datos.get("discord_id") == member.id:
                    found_name = nombre
                    break
            if not found_name:
                await ctx.send(embed=discord.Embed(
                    title="No Vinculado",
                    description="El usuario mencionado no está vinculado al sistema DKP.",
                    color=discord.Color.red()
                ))
                return
            nombre_usuario = found_name
        else:
            nombre_usuario_lower = nombre_usuario_arg.lower()
            found_name = None
            for n, datos in user_data.items():
                if n.lower() == nombre_usuario_lower:
                    found_name = n
                    break
            if not found_name:
                await ctx.send(embed=discord.Embed(
                    title="Usuario no encontrado",
                    description=f"No se encontró el usuario **{nombre_usuario_arg}**.",
                    color=discord.Color.red()
                ))
                return
            nombre_usuario = found_name

        user_data[nombre_usuario]["score"] += puntos_a_sumar
        registrar_cambio_dkp(nombre_usuario, +puntos_a_sumar, f"Comando sumardkp de {ctx.author}")
        await guardar_datos()

        await ctx.send(embed=discord.Embed(
            title="DKP Actualizado",
            description=f"Se han agregado {puntos_a_sumar} DKP a **{nombre_usuario}**. Total: {user_data[nombre_usuario]['score']}",
            color=discord.Color.green()
        ))

    @commands.command(name="restardkp")
    @requiere_vinculacion(comando_admin=True)
    async def restardkp(self, ctx, *args):
        if len(args) != 2:
            await ctx.send(embed=discord.Embed(
                title="Uso Incorrecto",
                description="Uso: !restardkp [usuario] [puntos]",
                color=discord.Color.red()
            ))
            return

        nombre_usuario_arg, puntos_str = args
        try:
            puntos_a_restar = int(puntos_str)
        except ValueError:
            await ctx.send(embed=discord.Embed(
                title="DKP Inválido",
                description="La cantidad de DKP a restar debe ser un número entero.",
                color=discord.Color.red()
            ))
            return

        if puntos_a_restar <= 0:
            await ctx.send(embed=discord.Embed(
                title="DKP Inválido",
                description="La cantidad de DKP a restar debe ser positiva.",
                color=discord.Color.red()
            ))
            return

        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            found_name = None
            for nombre, datos in user_data.items():
                if datos.get("discord_id") == member.id:
                    found_name = nombre
                    break
            if not found_name:
                await ctx.send(embed=discord.Embed(
                    title="No Vinculado",
                    description="El usuario mencionado no está vinculado al sistema DKP.",
                    color=discord.Color.red()
                ))
                return
            nombre_usuario = found_name
        else:
            nombre_usuario_lower = nombre_usuario_arg.lower()
            found_name = None
            for n, datos in user_data.items():
                if n.lower() == nombre_usuario_lower:
                    found_name = n
                    break
            if not found_name:
                await ctx.send(embed=discord.Embed(
                    title="Usuario no encontrado",
                    description=f"No se encontró el usuario **{nombre_usuario_arg}**.",
                    color=discord.Color.red()
                ))
                return
            nombre_usuario = found_name

        if user_data[nombre_usuario]["score"] < puntos_a_restar:
            await ctx.send(embed=discord.Embed(
                title="DKP Insuficiente",
                description=f"El usuario **{nombre_usuario}** no tiene suficientes DKP ({user_data[nombre_usuario]['score']}).",
                color=discord.Color.red()
            ))
            return

        user_data[nombre_usuario]["score"] -= puntos_a_restar
        registrar_cambio_dkp(nombre_usuario, -puntos_a_restar, f"Comando restardkp de {ctx.author}")
        await guardar_datos()

        await ctx.send(embed=discord.Embed(
            title="DKP Actualizado",
            description=f"Se han restado {puntos_a_restar} DKP a **{nombre_usuario}**. Total: {user_data[nombre_usuario]['score']}",
            color=discord.Color.orange()
        ))

    @commands.command(name="vacaciones")
    @requiere_vinculacion(comando_admin=True)
    async def vacaciones(self, ctx, nombre: str):
        nombre = nombre.strip()
        if nombre not in user_data:
            await ctx.send(embed=discord.Embed(
                title="Usuario no encontrado",
                description=f"No se encontró el usuario **{nombre}**.",
                color=discord.Color.red()
            ))
            return

        estado_actual = user_data[nombre].get("status", "normal")
        if estado_actual != "vacaciones":
            user_data[nombre]["status"] = "vacaciones"
            user_data[nombre]["absence_until"] = None
            user_data[nombre]["justified_events"].clear()
            await guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Vacaciones Activadas",
                description=f"El usuario **{nombre}** ahora está en VACACIONES.",
                color=discord.Color.yellow()
            ))
        else:
            user_data[nombre]["status"] = "normal"
            user_data[nombre]["absence_until"] = None
            user_data[nombre]["justified_events"].clear()
            await guardar_datos()
            await ctx.send(embed=discord.Embed(
                title="Vacaciones Desactivadas",
                description=f"El usuario **{nombre}** vuelve a estar ACTIVO.",
                color=discord.Color.green()
            ))

    @commands.command(name="estado")
    @requiere_vinculacion()
    async def estado(self, ctx):
        if not user_data:
            await ctx.send(embed=discord.Embed(
                title="Sin Datos",
                description="No hay usuarios en el sistema DKP.",
                color=discord.Color.blue()
            ))
            return

        lines = []
        lines.append(f"{'Nombre':<20} {'Estado':<40}")
        lines.append("-"*60)
        ahora = datetime.utcnow()

        for nombre, datos in user_data.items():
            status = datos.get("status", "normal")
            if status == "vacaciones":
                estado = "Vacaciones"
            else:
                absence_until = datos.get("absence_until")
                j_events = datos.get("justified_events", set())
                if absence_until and ahora <= absence_until:
                    fecha_str = absence_until.astimezone(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M")
                    estado = f"Hasta {fecha_str} (GMT-3)"
                elif j_events:
                    estado = ", ".join(sorted(j_events))
                else:
                    estado = "Activo"
            lines.append(f"{nombre:<20} {estado:<40}")

        final_text = "\n".join(lines)
        chunks = split_into_chunks(final_text)
        for i, chunk in enumerate(chunks, start=1):
            desc = f"```\n{chunk}\n```"
            embed = discord.Embed(
                title=f"Estado de Usuarios - Parte {i}",
                description=desc,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    @commands.command(name="info")
    @requiere_vinculacion()
    async def info(self, ctx):
        embed = discord.Embed(
            title="Información de Comandos",
            description="Lista de comandos DKP disponibles:",
            color=discord.Color.blue()
        )
        user_cmds = [
            "!dkp [usuario]", 
            "!dkpdetalle [usuario]",
            "!topdkp",
            "!equipo",
            "!ausencia",
            "!llegue <evento>",
            "!estado",
            "!partys",
            "!party",
            "!topgs"
        ]
        admin_cmds = [
            "!vacaciones <nombre>",
            "!registroevento <evento>",
            "!borrarevento <evento>",
            "!evento <evento> <puntaje> [...usuarios] [NORESTA]",
            "!vincular <@miembro> <nombre>",
            "!borrarusuario <nombre>",
            "!sumardkp <nombre> <puntos>",
            "!restardkp <nombre> <puntos>",
            "!asistencia (con imágenes)",
            "!revisarvinculacion <roleID>",
            "!armarparty [partyName]",
        ]

        embed.add_field(
            name="Comandos de Usuario",
            value="\n".join(f"`{c}`" for c in user_cmds),
            inline=False
        )
        embed.add_field(
            name="Comandos de Admin",
            value="\n".join(f"`{c}`" for c in admin_cmds),
            inline=False
        )

        embed.set_footer(text="Usa !dkp para ver tu puntaje. Si eres Admin, tienes comandos adicionales.")
        await ctx.send(embed=embed)

    @commands.command(name="topgs")
    @requiere_vinculacion()
    async def topgs(self, ctx):
        lista_gs = []
        for nombre, datos in user_data.items():
            eq = datos.get("equipo", {})
            gs = eq.get("gear_score")
            if gs is not None:
                arma_p = eq.get("arma_principal", "N/A")
                arma_s = eq.get("arma_secundaria", "N/A")
                dkp = datos["score"]
                lista_gs.append((nombre, gs, arma_p, arma_s, dkp))

        if not lista_gs:
            await ctx.send(embed=discord.Embed(
                title="Top GS",
                description="No hay usuarios con Gear Score configurado.",
                color=discord.Color.red()
            ))
            return

        lista_gs.sort(key=lambda x: x[1], reverse=True)
        top_15 = lista_gs[:15]
        desc = "```\n"
        desc += "{:<3} {:<15} {:<6} {:<20} {:<5}\n".format("#", "Nombre", "GS", "Armas", "DKP")
        desc += "-" * 55 + "\n"
        for i, (nombre, gs, ap, sp, dkp) in enumerate(top_15, start=1):
            armas = f"{ap}/{sp}"
            desc += "{:<3} {:<15} {:<6} {:<20} {:<5}\n".format(i, nombre, gs, armas, dkp)
        desc += "```"

        embed = discord.Embed(
            title="Top 15 Gear Score",
            description=desc,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)


    @commands.command(name="llegue")
    @requiere_vinculacion()
    async def llegue(self, ctx, nombre_evento: str):
        if ctx.channel.id != CANAL_TARDE:
            await ctx.send(embed=discord.Embed(
                title="Canal Incorrecto",
                description="Este comando solo se puede usar en el canal designado para llegadas tardías.",
                color=discord.Color.red()
            ))
            return

        nombre_evento = nombre_evento.upper()
        if nombre_evento not in events_info:
            await ctx.send(embed=discord.Embed(
                title="Evento No Encontrado",
                description=f"No se encontró el evento **{nombre_evento}**.",
                color=discord.Color.red()
            ))
            return

        event = events_info[nombre_evento]
        event_time = event["timestamp"]
        current_time = datetime.utcnow()

        if current_time > event_time + timedelta(minutes=60):
            await ctx.send(embed=discord.Embed(
                title="Tiempo Expirado",
                description="Pasó más de 1 hora para justificar tu llegada tardía.",
                color=discord.Color.red()
            ))
            return

        nombre_usuario = None
        for n, d in user_data.items():
            if d.get("discord_id") == ctx.author.id:
                nombre_usuario = n
                break

        if not nombre_usuario:
            await ctx.send(embed=discord.Embed(
                title="No Vinculado",
                description="No se encontró un nombre vinculado a tu usuario.",
                color=discord.Color.red()
            ))
            return

        if nombre_usuario in event["linked_users"]:
            await ctx.send(embed=discord.Embed(
                title="Estuviste en el evento",
                description="Ya te sumaron DKP para este evento.",
                color=discord.Color.red()
            ))
            return

        if nombre_usuario in event["late_users"]:
            await ctx.send(embed=discord.Embed(
                title="Uso Duplicado",
                description="Ya justificaste tu tardanza para este evento.",
                color=discord.Color.red()
            ))
            return

        puntaje = event["puntaje"]
        penalty_amount = event["penalties"].get(nombre_usuario, 0)
        if penalty_amount > 0:
            user_data[nombre_usuario]["score"] += (penalty_amount + puntaje)
            registrar_cambio_dkp(nombre_usuario, penalty_amount + puntaje,
                                 f"Llegué tarde (penalización devuelta) - {nombre_evento}")
            del event["penalties"][nombre_usuario]
        else:
            user_data[nombre_usuario]["score"] += puntaje
            registrar_cambio_dkp(nombre_usuario, +puntaje,
                                 f"Llegué tarde - {nombre_evento}")

        event["late_users"].add(nombre_usuario)
        await guardar_datos()
        guardar_eventos()

        await ctx.send(embed=discord.Embed(
            title="Llegada Tardía Justificada",
            description=f"Se sumaron **{puntaje} DKP** en **{nombre_evento}** para **{nombre_usuario}**.",
            color=discord.Color.green()
        ))


async def setup(bot):
    await bot.add_cog(DKPCommands(bot))
    logger.info("Cog 'DKPCommands' cargado con setup(bot).")