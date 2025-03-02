import os
import logging
import discord
from datetime import datetime, timedelta

import data_manager
from data_manager import user_data, events_info, registrar_cambio_dkp, guardar_datos, guardar_eventos

logger = logging.getLogger("event_logic")

CANAL_ADMIN = int(os.getenv("CANAL_ADMIN", 0))
CANAL_TARDE = int(os.getenv("CANAL_TARDE", 0))


async def handle_evento(
    nombre_evento: str,
    puntaje: int,
    noresta: bool,
    listadenombres: list,
    channel: discord.TextChannel,
    executor: discord.User
):
    if puntaje <= 0:
        embed = discord.Embed(
            title="DKP Inválido",
            description="El DKP debe ser un número positivo.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
        logger.warning(f"'{executor}' intentó crear un evento con puntaje <= 0: {puntaje}")
        return
    
    if CANAL_ADMIN is None:
    	await interaction.response.send_message(
        	"No se pudo encontrar el canal de administración.",
        	ephemeral=True
    	)
    	logger.error(f"No se pudo encontrar el canal con ID {CANAL_ADMIN}.")
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
    events_info[nombre_evento] = {
        "timestamp": event_time,
        "linked_users": list(usuarios_final),
        "late_users": set(),
        "puntaje": puntaje,
        "penalties": {}
    }
    logger.info(f"Evento '{nombre_evento}' registrado o actualizado por '{executor}'.")

    old_scores = {nombre: datos["score"] for nombre, datos in user_data.items()}
    estados_usuario = {}

    if noresta:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                estados_usuario[nombre] = "VACACIONES"
                continue

            if nombre in usuarios_final:
                datos["score"] += puntaje
                await registrar_cambio_dkp(nombre, +puntaje, f"Evento {nombre_evento}: ASISTIÓ (noresta)")

                if nombre_evento in datos.get("justified_events", []):
                    datos["justified_events"].remove(nombre_evento)

                estados_usuario[nombre] = "ASISTIÓ"
            else:
                estados_usuario[nombre] = "NO ASISTIÓ"
    else:
        for nombre, datos in user_data.items():
            if datos.get("status", "normal") == "vacaciones":
                estados_usuario[nombre] = "VACACIONES"
                continue

            absence_until = datos.get("absence_until")
            justificado_by_absence = (absence_until and event_time <= absence_until)
            justificado_by_event = (nombre_evento in datos.get("justified_events", []))
            justificado_evento = justificado_by_absence or justificado_by_event

            if nombre in usuarios_final:
                datos["score"] += puntaje
                await registrar_cambio_dkp(nombre, +puntaje, f"Evento {nombre_evento}: ASISTIÓ")

                if justificado_by_event:
                    datos["justified_events"].remove(nombre_evento)

                estados_usuario[nombre] = "ASISTIÓ"
            else:
                if justificado_evento:
                    datos["score"] -= puntaje
                    await registrar_cambio_dkp(nombre, -puntaje, f"Evento {nombre_evento}: JUSTIFICADO")

                    if justificado_by_event:
                        datos["justified_events"].remove(nombre_evento)

                    estados_usuario[nombre] = "JUSTIFICADO"
                else:
                    penalizacion = puntaje * 2
                    datos["score"] -= penalizacion
                    await registrar_cambio_dkp(nombre, -penalizacion, f"Evento {nombre_evento}: NO ASISTIÓ")

                    events_info[nombre_evento]["penalties"][nombre] = penalizacion

                    estados_usuario[nombre] = "NO ASISTIÓ"

    await guardar_datos()
    await guardar_eventos()

    all_users = sorted(user_data.items(), key=lambda x: x[0].lower())
    desc = "```\n"
    desc += "{:<15} {:<15} {:<10} {:<10}\n".format("Nombre", "Estado", "Antes", "Después")
    desc += "-"*55 + "\n"
    for nombre, datos in all_users:
        antes = old_scores.get(nombre, 0)
        despues = datos["score"]
        estado = estados_usuario.get(nombre, "ACTIVO")
        desc += "{:<15} {:<15} {:<10} {:<10}\n".format(nombre, estado, str(antes), str(despues))
    desc += "```"

    embed = discord.Embed(
        title=f"Evento: {nombre_evento}",
        color=discord.Color.blurple(),
        description=desc
    )
    await channel.send(embed=embed)

    if no_encontrados:
        mensaje_no_encontrados = "No se encontraron los siguientes usuarios:\n" + ", ".join(no_encontrados)
        await channel.send(embed=discord.Embed(
            title="Usuarios no encontrados",
            description=mensaje_no_encontrados,
            color=discord.Color.red()
        ))
        logger.warning(f"Usuarios no encontrados al procesar '{nombre_evento}': {no_encontrados}.")