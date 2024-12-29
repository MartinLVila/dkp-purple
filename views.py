import discord
from discord.ui import View, Button, Select
from discord import ButtonStyle, SelectOption
from data_manager import handle_evento, user_data, registered_events, logger
from datetime import datetime
from data_manager import CANAL_ADMIN, logger
from main import bot

class AsistenciaView(View):
    def __init__(self, nombres_extraidos, nombres_coincidentes):
        super().__init__(timeout=1700)
        self.nombres_extraidos = nombres_extraidos.copy()
        self.nombres_filtrados = nombres_coincidentes.copy()
        self.current_page = 0
        self.names_per_page = 25
        self.total_pages = (len(self.nombres_filtrados) - 1) // self.names_per_page + 1
        self.evento_seleccionado = None
        self.dkp_seleccionado = None
        self.resta_dkp = None

        self.embed_initial = discord.Embed(
            title="Asistencia del Evento",
            description=(
                "Lista de nombres extraídos de las imágenes. "
                "Puedes copiarlos manualmente si lo deseas.\n\n"
                "**Elimina los nombres que no están en el lugar:**"
            ),
            color=discord.Color.blue()
        )
        self.update_embed()

        self.prev_button = Button(label="Anterior", style=ButtonStyle.primary, custom_id="prev_page")
        self.next_button = Button(label="Siguiente", style=ButtonStyle.primary, custom_id="next_page")
        self.cancel_button = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.cancel_button.callback = self.cancel_operation

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.cancel_button)

        self.select = Select(
            placeholder="Selecciona los nombres a eliminar",
            min_values=0,
            max_values=self.get_max_values(),
            options=self.get_current_options(),
            custom_id="select_eliminar_nombres"
        )
        self.select.callback = self.remove_names
        self.add_item(self.select)

        self.siguiente_button = Button(label="SIGUIENTE", style=ButtonStyle.green, custom_id="siguiente")
        self.siguiente_button.callback = self.iniciar_evento
        self.add_item(self.siguiente_button)

    def get_current_options(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return [SelectOption(label=nombre, value=nombre) for nombre in current_page_names]

    def get_max_values(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return len(current_page_names) if current_page_names else 1

    def update_embed(self):
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        nombres_str = "\n".join(current_page_names)
        embed = self.embed_initial.copy()
        embed.add_field(
            name=f"Nombres ({self.current_page + 1}/{self.total_pages})",
            value=f"```\n{nombres_str}\n```",
            inline=False
        )
        self.embed = embed

    async def remove_names(self, interaction: discord.Interaction):
        nombres_eliminados = self.select.values
        if nombres_eliminados:
            for nombre in nombres_eliminados:
                if nombre in self.nombres_filtrados:
                    self.nombres_filtrados.remove(nombre)

            self.total_pages = (len(self.nombres_filtrados) - 1) // self.names_per_page + 1

            if self.current_page >= self.total_pages:
                self.current_page = self.total_pages - 1 if self.total_pages > 0 else 0

            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()

            self.update_embed()
            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send(
                f"Se han eliminado los siguientes nombres: {', '.join(nombres_eliminados)}.",
                ephemeral=True
            )

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_embed()
            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()
            await interaction.response.edit_message(embed=self.embed, view=self)
        else:
            await interaction.response.send_message("Ya estás en la primera página.", ephemeral=True)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_embed()
            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()
            await interaction.response.edit_message(embed=self.embed, view=self)
        else:
            await interaction.response.send_message("Ya estás en la última página.", ephemeral=True)

    async def cancelar_y_mostrar_lista(self, interaction: discord.Interaction):
        self.clear_items()
        embed = discord.Embed(
            title="Asistencia del Evento",
            description=(
                "Lista de nombres extraídos de las imágenes para copiar manualmente:\n"
                "```\n" + "\n".join(self.nombres_filtrados) + "\n```"
            ),
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def cancel_operation(self, interaction: discord.Interaction):
        await self.cancelar_y_mostrar_lista(interaction)

    async def iniciar_evento(self, interaction: discord.Interaction):
        self.clear_items()
        embed = discord.Embed(
            title="PARA QUE EVENTO?",
            description="Selecciona el evento al que asistieron los nombres listados.",
            color=discord.Color.green()
        )

        for evento in sorted(registered_events):
            boton = Button(label=evento, style=ButtonStyle.primary, custom_id=f"evento_{evento}")
            boton.callback = self.seleccionar_evento
            self.add_item(boton)

        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_evento(self, interaction: discord.Interaction):
        try:
            evento_seleccionado = interaction.component.custom_id.replace("evento_", "")
        except AttributeError:
            try:
                evento_seleccionado = interaction.data['custom_id'].replace("evento_", "")
            except KeyError:
                await interaction.response.send_message(
                    "No se pudo determinar el evento seleccionado.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id del componente en 'seleccionar_evento'.")
                return

        self.evento_seleccionado = evento_seleccionado
        self.clear_items()
        embed = discord.Embed(
            title="CUANTO DKP?",
            description="Selecciona la cantidad de DKP para asignar al evento.",
            color=discord.Color.orange()
        )

        dkp_valores = [3, 9, 21, 45]
        for dkp in dkp_valores:
            boton = Button(label=str(dkp), style=ButtonStyle.primary, custom_id=f"dkp_{dkp}")
            boton.callback = self.seleccionar_dkp
            self.add_item(boton)

        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_dkp(self, interaction: discord.Interaction):
        try:
            self.dkp_seleccionado = int(interaction.component.custom_id.replace("dkp_", ""))
        except AttributeError:
            try:
                self.dkp_seleccionado = int(interaction.data['custom_id'].replace("dkp_", ""))
            except (KeyError, ValueError):
                await interaction.response.send_message(
                    "No se pudo determinar la cantidad de DKP seleccionada.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id del componente en 'seleccionar_dkp'.")
                return

        self.clear_items()
        embed = discord.Embed(
            title="EL EVENTO RESTA DKP?",
            description="¿El evento resta DKP?",
            color=discord.Color.purple()
        )
        boton_si = Button(label="SI", style=ButtonStyle.danger, custom_id="resta_si")
        boton_no = Button(label="NO", style=ButtonStyle.success, custom_id="resta_no")
        boton_si.callback = self.seleccionar_resta
        boton_no.callback = self.seleccionar_resta
        self.add_item(boton_si)
        self.add_item(boton_no)
        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        cancelar.callback = self.cancel_operation
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def seleccionar_resta(self, interaction: discord.Interaction):
        try:
            decision = interaction.component.custom_id.replace("resta_", "").upper()
        except AttributeError:
            try:
                decision = interaction.data['custom_id'].replace("resta_", "").upper()
            except KeyError:
                await interaction.response.send_message(
                    "No se pudo determinar la opción seleccionada.",
                    ephemeral=True
                )
                logger.error("No se pudo acceder al custom_id en 'seleccionar_resta'.")
                return

        self.resta_dkp = True if decision == "SI" else False
        self.clear_items()
        embed = discord.Embed(
            title="CONFIRMAR",
            description=(
                f"**Evento:** {self.evento_seleccionado}\n"
                f"**DKP:** {self.dkp_seleccionado}\n"
                f"**Resta DKP:** {'SI' if self.resta_dkp else 'NO'}\n\n"
                f"**Nombres:**\n```\n" + "\n".join(self.nombres_filtrados) + "\n```"
            ),
            color=discord.Color.gold()
        )
        confirmar = Button(label="CONFIRMAR", style=ButtonStyle.success, custom_id="confirmar")
        cancelar = Button(label="CANCELAR", style=ButtonStyle.red, custom_id="cancelar")
        confirmar.callback = self.confirmar_operacion
        cancelar.callback = self.cancel_operation
        self.add_item(confirmar)
        self.add_item(cancelar)
        self.embed = embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def confirmar_operacion(self, interaction: discord.Interaction):
        noresta = not self.resta_dkp
        noresta_str = "NORESTA" if self.resta_dkp else ""
        listadenombres = self.nombres_filtrados
        comando_evento = f"!evento {self.evento_seleccionado} {self.dkp_seleccionado} {noresta_str} " + " ".join(listadenombres)
        comando_evento = comando_evento.strip()

        canal_admin = bot.get_channel(CANAL_ADMIN)
        if canal_admin is None:
            await interaction.response.send_message(
                "No se pudo encontrar el canal de administración.",
                ephemeral=True
            )
            logger.error(f"No se pudo encontrar el canal con ID {CANAL_ADMIN}.")
            return

        await handle_evento(
            nombre_evento=self.evento_seleccionado,
            puntaje=self.dkp_seleccionado,
            noresta=noresta,
            listadenombres=listadenombres,
            channel=canal_admin,
            executor=interaction.user
        )

        self.clear_items()
        embed_final = discord.Embed(
            title="Asistencia Registrada",
            description="La asistencia ha sido registrada exitosamente en el canal de administración.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed_final, view=self)
        self.stop()
