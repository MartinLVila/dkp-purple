import discord
from discord.ext import commands
from utils import requiere_vinculacion
from data_manager import handle_evento, user_data, events_info, registered_events, CANAL_ADMIN, CANAL_TARDE, guardar_eventos, guardar_datos, logger
from views import AsistenciaView
from main import bot

class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="asistencia")
    @requiere_vinculacion(comando_admin=True)
    async def asistencia(self, ctx):
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

    @commands.command(name="llegue_tarde")
    @requiere_vinculacion()
    async def llegue_tarde(self, ctx, nombre_evento: str):
        """
        Permite a un usuario justificar su llegada tardía a un evento.
        - Solo se puede usar dentro de los 20 minutos posteriores a !evento NOMBREEVENTO.
        - Solo se puede usar una vez por usuario por evento en el canal de ausencias.
        """
        if ctx.channel.id != CANAL_TARDE:
            await ctx.send(embed=discord.Embed(
                title="Canal Incorrecto",
                description="Este comando solo puede usarse en el canal designado para llegadas tardías.",
                color=discord.Color.red()
            ))
            logger.warning(f"Usuario '{ctx.author}' intentó usar !llegue_tarde en el canal equivocado.")
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

        if current_time > event_time + timedelta(minutes=20):
            await ctx.send(embed=discord.Embed(
                title="Tiempo Expirado",
                description=f"Ya pasaron más de 20 minutos para justificar llegada tardía al evento **{nombre_evento}**.",
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
            logger.info(f"Usuario '{nombre_usuario}' justificó tardanza y recibió {puntaje} en el evento '{nombre_evento}'.")

        event["late_users"].add(nombre_usuario)
        guardar_datos()
        guardar_eventos()

        await ctx.send(embed=discord.Embed(
            title="Llegada Tardía Justificada",
            description=f"Se han sumado **{puntaje} DKP** en el evento **{nombre_evento}** para ti, **{nombre_usuario}**.",
            color=discord.Color.green()
        ))

def setup(bot):
    bot.add_cog(Attendance(bot))