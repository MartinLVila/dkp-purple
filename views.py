import os
import logging
import discord

from discord.ext.commands import Bot
from discord.ui import View, Button, Select, Modal, TextInput
from discord import ButtonStyle, SelectOption, TextStyle
from typing import List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from event_logic import handle_evento

import data_manager
from data_manager import (
    user_data,
    registered_events,
    PARTYS,
    guardar_datos,
    save_partys
)

ARMAS_DISPONIBLES = [
    "Greatsword", "Sword", "Crossbow", "Longbow",
    "Staff", "Wand", "Dagger", "Spear"
]

ROLES_DISPONIBLES = [
    "Ranged DPS", "Mid Range DPS", "Melee DPS",
    "Tank", "Healer"
]

logger = logging.getLogger(__name__)

class CrearPartyModal(Modal):
    def __init__(self):
        super().__init__(title="Crear Nueva Party")

        self.nombre = TextInput(
            label="Nombre de la Party",
            placeholder="Ej: Party 1 Frontline",
            required=True,
            max_length=50
        )
        self.add_item(self.nombre)

    async def on_submit(self, interaction: discord.Interaction):
        nombre_party = self.nombre.value.strip()
        if not nombre_party:
            await interaction.response.send_message("El nombre de la party no puede estar vacío.", ephemeral=True)
            return

        if nombre_party in PARTYS:
            await interaction.response.send_message(f"La party **{nombre_party}** ya existe.", ephemeral=True)
            return

        PARTYS[nombre_party] = []
        save_partys()
        await interaction.response.send_message(f"Se ha creado la party **{nombre_party}** exitosamente.", ephemeral=True)

class ArmarPartysView(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.crear_party_button = Button(label="Crear Party", style=discord.ButtonStyle.green, custom_id="crear_party")
        self.crear_party_button.callback = self.crear_party_callback
        self.add_item(self.crear_party_button)

        self.eliminar_party_button = Button(label="Eliminar Party", style=discord.ButtonStyle.red, custom_id="eliminar_party")
        self.eliminar_party_button.callback = self.eliminar_party_callback
        self.add_item(self.eliminar_party_button)

        self.agregar_miembro_button = Button(label="Agregar Miembro", style=discord.ButtonStyle.blurple, custom_id="agregar_miembro")
        self.agregar_miembro_button.callback = self.agregar_miembro_callback
        self.add_item(self.agregar_miembro_button)

        self.quitar_miembro_button = Button(label="Quitar Miembro", style=discord.ButtonStyle.blurple, custom_id="quitar_miembro")
        self.quitar_miembro_button.callback = self.quitar_miembro_callback
        self.add_item(self.quitar_miembro_button)

        self.listar_partys_button = Button(label="Listar Partys", style=discord.ButtonStyle.grey, custom_id="listar_partys")
        self.listar_partys_button.callback = self.listar_partys_callback
        self.add_item(self.listar_partys_button)
        
        self.cancelar_button = Button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="cancelar")
        self.cancelar_button.callback = self.cancelar_callback
        self.add_item(self.cancelar_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in ADMINS_IDS:
            await interaction.response.send_message("No tienes permisos para usar este comando.", ephemeral=True)
            return False
        return True

    async def crear_party_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CrearPartyModal())

    async def eliminar_party_callback(self, interaction: discord.Interaction):
        if not PARTYS:
            await interaction.response.send_message("No hay partys para eliminar.", ephemeral=True)
            return
        select = Select(
            placeholder="Selecciona la party a eliminar...",
            options=[discord.SelectOption(label=party, description=f"Eliminar {party}") for party in PARTYS.keys()],
            custom_id="select_eliminar_party"
        )
        select.callback = self.select_eliminar_party
        view = View(timeout=60)
        view.add_item(select)
        cancelar = Button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="cancelar_eliminar_party")
        cancelar.callback = self.cancelar_eliminar_party
        view.add_item(cancelar)
        await interaction.response.send_message("Selecciona la party que deseas eliminar:", view=view, ephemeral=True)

    async def select_eliminar_party(self, interaction: discord.Interaction):
        party_to_delete = interaction.data['values'][0]
        del PARTYS[party_to_delete]
        save_partys()
        await interaction.response.send_message(f"Se ha eliminado la party **{party_to_delete}**.", ephemeral=True)
        logger.info(f"Party '{party_to_delete}' eliminada por {interaction.user}.")

    async def cancelar_eliminar_party(self, interaction: discord.Interaction):
        await interaction.response.send_message("Operación de eliminación de party cancelada.", ephemeral=True)

    async def agregar_miembro_callback(self, interaction: discord.Interaction):
        if not PARTYS:
            await interaction.response.send_message("No hay partys definidas. Crea una party primero.", ephemeral=True)
            return
        select = Select(
            placeholder="Selecciona la party a modificar...",
            options=[discord.SelectOption(label=party, description=f"Agregar miembro a {party}") for party in PARTYS.keys()],
            custom_id="select_agregar_party"
        )
        select.callback = self.select_agregar_party
        view = View(timeout=60)
        view.add_item(select)
        cancelar = Button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="cancelar_agregar_miembro")
        cancelar.callback = self.cancelar_agregar_miembro
        view.add_item(cancelar)
        await interaction.response.send_message("Selecciona la party a la que deseas agregar un miembro:", view=view, ephemeral=True)

    async def select_agregar_party(self, interaction: discord.Interaction):
        selected_party = interaction.data['values'][0]
        miembros_actuales = set(PARTYS[selected_party])
        candidatos = {nombre for nombre in user_data.keys() if nombre not in miembros_actuales}

        if not candidatos:
            await interaction.response.send_message("No hay usuarios disponibles para agregar.", ephemeral=True)
            return

        view = AgregarMiembroView(selected_party)
        embed = discord.Embed(
            title=f"Agregar Miembro a {selected_party}",
            description="Filtra los miembros por arma, rol o nombre antes de agregarlos.",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def quitar_miembro_callback(self, interaction: discord.Interaction):
        if not PARTYS:
            await interaction.response.send_message("No hay partys definidas.", ephemeral=True)
            return

        select = Select(
            placeholder="Selecciona la party a modificar...",
            options=[discord.SelectOption(label=party, description=f"Quitar miembro de {party}") for party in PARTYS.keys()],
            custom_id="select_quitar_party"
        )
        select.callback = self.select_quitar_party
        view = View(timeout=60)
        view.add_item(select)
        cancelar = Button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="cancelar_quitar_miembro")
        cancelar.callback = self.cancelar_quitar_miembro
        view.add_item(cancelar)
        await interaction.response.send_message("Selecciona la party de la que deseas quitar un miembro:", view=view, ephemeral=True)

    async def select_quitar_party(self, interaction: discord.Interaction):
        selected_party = interaction.data['values'][0]
        miembros_actuales = PARTYS[selected_party]
        if not miembros_actuales:
            await interaction.response.send_message("Esta party está vacía.", ephemeral=True)
            return
        select = Select(
            placeholder="Selecciona el miembro a quitar...",
            options=[discord.SelectOption(label=nombre, value=nombre) for nombre in miembros_actuales],
            custom_id="select_quitar_miembro_final"
        )
        select.callback = lambda i: self.confirmar_quitar_miembro(i, selected_party)
        view = View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message(f"Selecciona el miembro que deseas quitar de **{selected_party}**:", view=view, ephemeral=True)

    async def confirmar_quitar_miembro(self, interaction: discord.Interaction, party: str):
        miembro = interaction.data['values'][0]
        PARTYS[party].remove(miembro)
        save_partys()
        await interaction.response.send_message(f"**{miembro}** ha sido quitado de **{party}**.", ephemeral=True)
        logger.info(f"Miembro '{miembro}' quitado de la party '{party}' por {interaction.user}.")

    async def listar_partys_callback(self, interaction: discord.Interaction):
        if not PARTYS:
            await interaction.response.send_message("No hay partys definidas.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛡️ Partys Actuales",
            description="\n".join(PARTYS.keys()),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cancelar_callback(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Operación cancelada.", embed=None, view=self)
        logger.info(f"Operación de administrar partys cancelada por {interaction.user}.")

    async def cancelar_agregar_miembro(self, interaction: discord.Interaction):
        view = interaction.message.components[-1].children[0].view
        self.miembros_filtrados = set(user_data.keys())
        self.filtro_nombre = ""
        self.select_arma.values = []
        self.select_rol.values = []
        self.select_nombre.values = []

        await interaction.response.send_message("La operación de agregar miembro ha sido cancelada.", ephemeral=True)
        logger.info(f"Operación de agregar miembro cancelada por {interaction.user}.")

    async def cancelar_quitar_miembro(self, interaction: discord.Interaction):
        await interaction.response.send_message("La operación de quitar miembro ha sido cancelada.", ephemeral=True)
        logger.info(f"Operación de quitar miembro cancelada por {interaction.user}.")

class AgregarMiembroView(View):
    def __init__(self, party_name: str):
        super().__init__(timeout=300)
        self.party_name = party_name

        self.select_arma = Select(
            placeholder="Filtrar por Arma",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label="Todos", value="all")] + 
                   [discord.SelectOption(label=arma, value=arma) for arma in sorted(ARMAS_DISPONIBLES)],
            custom_id="select_filtrar_arma"
        )
        self.select_arma.callback = self.filtrar_por_arma
        self.add_item(self.select_arma)

        self.select_rol = Select(
            placeholder="Filtrar por Rol",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label="Todos", value="all")] + 
                   [discord.SelectOption(label=rol, value=rol) for rol in sorted(ROLES_DISPONIBLES)],
            custom_id="select_filtrar_rol"
        )
        self.select_rol.callback = self.filtrar_por_rol
        self.add_item(self.select_rol)

        self.select_nombre = Select(
            placeholder="Filtrar por Nombre",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(label="Todos", value="all")] + 
                   [discord.SelectOption(label="Ingresar Nombre", value="ingresar_nombre")],
            custom_id="select_filtrar_nombre"
        )
        self.select_nombre.callback = self.filtrar_por_nombre
        self.add_item(self.select_nombre)

        self.btn_mostrar = Button(label="Mostrar Usuarios", style=discord.ButtonStyle.green, custom_id="btn_mostrar_usuarios")
        self.btn_mostrar.callback = self.mostrar_usuarios
        self.add_item(self.btn_mostrar)

        self.btn_cancelar = Button(label="Cancelar", style=discord.ButtonStyle.danger, custom_id="btn_cancelar_filtro")
        self.btn_cancelar.callback = self.cancelar_filtro
        self.add_item(self.btn_cancelar)

        self.miembros_filtrados = set(user_data.keys())
        self.filtro_nombre = ""

    async def filtrar_por_arma(self, interaction: discord.Interaction):
        arma_seleccionada = interaction.data['values'][0]
        if arma_seleccionada == "all":
            armas_filtradas = set(user_data.keys())
        else:
            armas_filtradas = {
                nombre for nombre, datos in user_data.items() 
                if datos.get("equipo", {}).get("arma_principal") == arma_seleccionada or 
                   datos.get("equipo", {}).get("arma_secundaria") == arma_seleccionada
            }
        self.miembros_filtrados &= armas_filtradas
        await interaction.response.send_message(f"Filtrado por arma: **{arma_seleccionada}**.", ephemeral=True)
        logger.info(f"Filtrado por arma '{arma_seleccionada}' aplicado en la party '{self.party_name}' por {interaction.user}.")

    async def filtrar_por_rol(self, interaction: discord.Interaction):
        rol_seleccionado = interaction.data['values'][0]
        if rol_seleccionado == "all":
            roles_filtrados = set(user_data.keys())
        else:
            roles_filtrados = {
                nombre for nombre, datos in user_data.items() 
                if datos.get("equipo", {}).get("rol") == rol_seleccionado
            }
        self.miembros_filtrados &= roles_filtrados
        await interaction.response.send_message(f"Filtrado por rol: **{rol_seleccionado}**.", ephemeral=True)
        logger.info(f"Filtrado por rol '{rol_seleccionado}' aplicado en la party '{self.party_name}' por {interaction.user}.")

    async def filtrar_por_nombre(self, interaction: discord.Interaction):
        if "ingresar_nombre" in interaction.data['values']:
            await interaction.response.send_modal(FiltrarPorNombreModal(self))
        else:
            self.miembros_filtrados = set(user_data.keys())
            await interaction.response.send_message("Filtrado por nombre: **Todos**.", ephemeral=True)
            logger.info(f"Filtrado por nombre reseteado en la party '{self.party_name}' por {interaction.user}.")

    async def mostrar_usuarios(self, interaction: discord.Interaction):
        miembros_actuales = set(PARTYS[self.party_name])
        miembros_disponibles = [nombre for nombre in self.miembros_filtrados if nombre not in miembros_actuales]

        if not miembros_disponibles:
            await interaction.response.send_message("No hay usuarios disponibles para agregar con los filtros seleccionados.", ephemeral=True)
            return

        if len(miembros_disponibles) > 25:
            await interaction.response.send_message(
                "La lista de usuarios disponibles excede el límite de 25 opciones. Por favor, ajusta los filtros para reducir la lista.",
                ephemeral=True
            )
            logger.warning(f"Lista de miembros disponibles excede 25 en la party '{self.party_name}' por {interaction.user}.")
            return

        select = Select(
            placeholder="Selecciona los miembros a agregar...",
            min_values=1,
            max_values=min(len(miembros_disponibles), 25),
            options=[discord.SelectOption(label=nombre, value=nombre) for nombre in sorted(miembros_disponibles)],
            custom_id="select_agregar_miembros_final"
        )
        select.callback = lambda i: self.confirmar_agregar_final(i, self.party_name)
        view = View(timeout=300)
        view.add_item(select)
        await interaction.response.send_message(f"Selecciona los miembros a agregar a **{self.party_name}**:", view=view, ephemeral=True)
        logger.info(f"Mostrando usuarios para agregar a la party '{self.party_name}' por {interaction.user}.")

    async def confirmar_agregar_final(self, interaction: discord.Interaction, party: str):
        miembros_a_agregar = interaction.data['values']
        if not miembros_a_agregar:
            await interaction.response.send_message("No se seleccionaron miembros para agregar.", ephemeral=True)
            return

        for miembro in miembros_a_agregar:
            PARTYS[party].append(miembro)

        save_partys()
        await interaction.response.send_message(f"Se han agregado {', '.join(miembros_a_agregar)} a **{party}**.", ephemeral=True)
        logger.info(f"Miembros {miembros_a_agregar} agregados a la party '{party}' por {interaction.user}.")

    async def cancelar_filtro(self, interaction: discord.Interaction):
        self.miembros_filtrados = set(user_data.keys())
        self.filtro_nombre = ""
        
        self.select_arma.values = ["all"] if "all" in [option.value for option in self.select_arma.options] else []
        self.select_rol.values = ["all"] if "all" in [option.value for option in self.select_rol.options] else []
        self.select_nombre.values = ["all"] if "all" in [option.value for option in self.select_nombre.options] else []
        
        for select in [self.select_arma, self.select_rol, self.select_nombre]:
            select.disabled = False

        await interaction.response.send_message("Los filtros han sido reseteados y la operación ha sido cancelada.", ephemeral=True)
        logger.info(f"Filtrado de miembros en party '{self.party_name}' cancelado por {interaction.user}.")
        
class FiltrarPorNombreModal(Modal):
    def __init__(self, view: AgregarMiembroView):
        super().__init__(title="Filtrar por Nombre")
        self.view = view

        self.nombre = TextInput(
            label="Nombre o Parte del Nombre",
            placeholder="Ingresa el nombre completo o parte del nombre",
            required=True,
            max_length=50
        )
        self.add_item(self.nombre)

    async def on_submit(self, interaction: discord.Interaction):
        nombre_filtro = self.nombre.value.strip().lower()
        if not nombre_filtro:
            await interaction.response.send_message("El campo de nombre no puede estar vacío.", ephemeral=True)
            return

        nombres_filtrados = {
            nombre for nombre in user_data.keys() 
            if nombre_filtro in nombre.lower()
        }
        self.view.miembros_filtrados &= nombres_filtrados
        await interaction.response.send_message(f"Filtrado por nombre: **'{self.nombre.value}'**.", ephemeral=True)
        logger.info(f"Filtrado por nombre '{self.nombre.value}' aplicado en la party '{self.view.party_name}' por {interaction.user}.")
        
class EquipoView(View):
    def __init__(self, nombre_usuario: str):
        super().__init__(timeout=500)
        self.nombre_usuario = nombre_usuario
        self.main_weapon = None
        self.secondary_weapon = None
        self.role = None

        self.select_main_weapon = Select(
            placeholder="Selecciona tu Arma Principal",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=arma, value=arma) for arma in ARMAS_DISPONIBLES],
            custom_id="select_main_weapon"
        )
        self.select_main_weapon.callback = self.main_weapon_selected
        self.add_item(self.select_main_weapon)

        self.select_secondary_weapon = Select(
            placeholder="Selecciona tu Arma Secundaria",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=arma, value=arma) for arma in ARMAS_DISPONIBLES],
            custom_id="select_secondary_weapon"
        )
        self.select_secondary_weapon.callback = self.secondary_weapon_selected
        self.add_item(self.select_secondary_weapon)

        self.select_role = Select(
            placeholder="Selecciona tu Rol",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=rol, value=rol) for rol in ROLES_DISPONIBLES],
            custom_id="select_role"
        )
        self.select_role.callback = self.role_selected
        self.add_item(self.select_role)

        self.submit_button = Button(label="Enviar", style=ButtonStyle.green)
        self.submit_button.callback = self.submit
        self.add_item(self.submit_button)

    async def main_weapon_selected(self, interaction: discord.Interaction):
        self.main_weapon = self.select_main_weapon.values[0]
        await interaction.response.send_message(
            f"Arma Principal seleccionada: **{self.main_weapon}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Arma Principal: {self.main_weapon}")

    async def secondary_weapon_selected(self, interaction: discord.Interaction):
        self.secondary_weapon = self.select_secondary_weapon.values[0]
        await interaction.response.send_message(
            f"Arma Secundaria seleccionada: **{self.secondary_weapon}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Arma Secundaria: {self.secondary_weapon}")

    async def role_selected(self, interaction: discord.Interaction):
        self.role = self.select_role.values[0]
        await interaction.response.send_message(
            f"Rol seleccionado: **{self.role}**", ephemeral=True
        )
        logger.info(f"Usuario '{self.nombre_usuario}' seleccionó Rol: {self.role}")

    async def submit(self, interaction: discord.Interaction):
        if not (self.main_weapon and self.secondary_weapon and self.role):
            await interaction.response.send_message(
                "Por favor, selecciona todas las opciones antes de enviar.", ephemeral=True
            )
            logger.warning(f"Usuario '{self.nombre_usuario}' intentó enviar sin completar todas las selecciones.")
            return

        await interaction.response.send_modal(GearScoreModal(
            self.nombre_usuario,
            self.main_weapon,
            self.secondary_weapon,
            self.role,
            self
        ))

class GearScoreModal(Modal):
    def __init__(self, nombre_usuario: str, main_weapon: str, secondary_weapon: str, role: str, view: View):
        super().__init__(title="Completa tu Equipo")
        self.nombre_usuario = nombre_usuario
        self.main_weapon = main_weapon
        self.secondary_weapon = secondary_weapon
        self.role = role
        self.view = view

        self.gear_score = TextInput(
            label="Gear Score",
            placeholder="Ingresa tu Gear Score (número)",
            style=TextStyle.short,
            required=True
        )
        self.add_item(self.gear_score)

    async def on_submit(self, interaction: discord.Interaction):
        gear_score_str = self.gear_score.value.strip()

        if not gear_score_str.isdigit():
            await interaction.response.send_message(
                "El Gear Score debe ser un número válido.", ephemeral=True
            )
            return

        gear_score = int(gear_score_str)
        if gear_score < 0 or gear_score > 10000:
            await interaction.response.send_message(
                "El Gear Score debe estar entre 0 y 10,000.", ephemeral=True
            )
            return

        if self.nombre_usuario not in user_data:
            await interaction.response.send_message(
                "Ocurrió un error: tu usuario no está vinculado al sistema DKP.", ephemeral=True
            )
            return

        user_data[self.nombre_usuario]["equipo"] = {
            "arma_principal": self.main_weapon,
            "arma_secundaria": self.secondary_weapon,
            "rol": self.role,
            "gear_score": gear_score
        }
        guardar_datos()

        embed = discord.Embed(
            title="Equipo Configurado",
            description=(
                f"**Armas:** {self.main_weapon}/{self.secondary_weapon}\n"
                f"**Rol:** {self.role}\n"
                f"**Gear Score:** {gear_score}"
            ),
            color=discord.Color.green()
        )
        await interaction.message.edit(content="✅ Equipo configurado con éxito:", embed=embed, view=None)

        await interaction.response.defer()

        logger.info(f"Equipo configurado para '{self.nombre_usuario}': {self.main_weapon}/{self.secondary_weapon}, Rol: {self.role}, Gear Score: {gear_score}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message(
                "Ocurrió un error al procesar tu Gear Score. Por favor, inténtalo de nuevo más tarde.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error adicional al manejar on_error: {e}")
        logger.error(f"Error en GearScoreModal para '{self.nombre_usuario}': {error}")

class AusenciaInteractiveView(View):
    def __init__(self, author: discord.User):
        super().__init__(timeout=500)
        self.author = author

        self.select_tipo = Select(
            placeholder="¿Cómo deseas justificar tu ausencia?",
            min_values=1,
            max_values=1,
            options=[
                SelectOption(label="Por Evento", description="Justificar ausencia en uno o varios eventos."),
                SelectOption(label="Por Duración", description="Justificar ausencia por días o vacaciones.")
            ]
        )
        self.select_tipo.callback = self.tipo_seleccionado
        self.add_item(self.select_tipo)

        self.btn_cancelar = Button(label="Cancelar", style=ButtonStyle.danger)
        self.btn_cancelar.callback = self.cancelar
        self.add_item(self.btn_cancelar)

        self.tipo_justificacion = None
        self.eventos = []
        self.duracion = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Este comando es privado y no puedes interactuar con él.",
                ephemeral=True
            )
            return False
        return True

    async def tipo_seleccionado(self, interaction: discord.Interaction):
        self.tipo_justificacion = self.select_tipo.values[0]
        self.remove_item(self.select_tipo)

        if self.tipo_justificacion == "Por Evento":
            self.select_eventos = Select(
                placeholder="Selecciona los eventos a los que te ausentas...",
                min_values=1,
                max_values=len(registered_events),
                options=[
                    SelectOption(label=evento, description=f"Justificar ausencia en {evento}") for evento in sorted(registered_events)
                ]
            )
            self.select_eventos.callback = self.eventos_seleccionados
            self.add_item(self.select_eventos)

            self.btn_siguiente = Button(label="Siguiente", style=ButtonStyle.primary)
            self.btn_siguiente.callback = self.siguiente_evento
            self.add_item(self.btn_siguiente)

        elif self.tipo_justificacion == "Por Duración":
            self.select_duracion = Select(
                placeholder="Selecciona la duración de tu ausencia...",
                min_values=1,
                max_values=1,
                options=[
                    SelectOption(label="1 Día", description="Ausentarse por 1 día"),
                    SelectOption(label="2 Días", description="Ausentarse por 2 días"),
                    SelectOption(label="Vacaciones", description="Solicitar vacaciones")
                ]
            )
            self.select_duracion.callback = self.duracion_seleccionada
            self.add_item(self.select_duracion)

            self.btn_siguiente = Button(label="Siguiente", style=ButtonStyle.primary)
            self.btn_siguiente.callback = self.siguiente_duracion
            self.add_item(self.btn_siguiente)

        await interaction.response.edit_message(view=self)

    async def eventos_seleccionados(self, interaction: discord.Interaction):
        self.eventos = self.select_eventos.values
        await interaction.response.defer()

    async def siguiente_evento(self, interaction: discord.Interaction):
        if not self.eventos:
            await interaction.response.send_message(
                "Por favor, selecciona al menos un evento.",
                ephemeral=True
            )
            return

        self.select_eventos.disabled = True
        self.btn_siguiente.disabled = True

        resumen = "**Resumen de tu ausencia:**\n"
        resumen += f"**Eventos:** {', '.join(self.eventos)}\n"

        embed = discord.Embed(
            title="Confirmar Ausencia por Evento",
            description=resumen,
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        usuario = interaction.user
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None and usuario.id not in ADMINS_IDS:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Vinculado",
                    description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{usuario}' no está vinculado y trató de justificar ausencia interactiva.")
            self.stop()
            return

        for nombre_evento in self.eventos:
            if nombre_evento not in registered_events:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Evento No Registrado",
                        description=f"El evento **{nombre_evento}** no está registrado.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                logger.warning(f"Evento '{nombre_evento}' no está registrado.")
                continue

            user_data[nombre_usuario]["justified_events"].add(nombre_evento)
            logger.info(f"Usuario '{nombre_usuario}' justificó ausencia para el evento '{nombre_evento}'.")

        guardar_datos()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has justificado tu ausencia para los eventos: {', '.join(self.eventos)}, **{nombre_usuario}**.",
                color=discord.Color.green()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{nombre_usuario}' justificó ausencia por eventos: {self.eventos}.")
        self.stop()

    async def duracion_seleccionada(self, interaction: discord.Interaction):
        self.duracion = self.select_duracion.values[0]
        await interaction.response.defer()

    async def siguiente_duracion(self, interaction: discord.Interaction):
        if not self.duracion:
            await interaction.response.send_message(
                "Por favor, selecciona una duración.",
                ephemeral=True
            )
            return

        self.select_duracion.disabled = True
        self.btn_siguiente.disabled = True

        resumen = "**Resumen de tu ausencia:**\n"
        resumen += f"**Duración:** {self.duracion}\n"

        embed = discord.Embed(
            title="Confirmar Ausencia por Duración",
            description=resumen,
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        usuario = interaction.user
        nombre_usuario = None
        for nombre, datos in user_data.items():
            if datos.get("discord_id") == usuario.id:
                nombre_usuario = nombre
                break

        if nombre_usuario is None and usuario.id not in ADMINS_IDS:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="No Vinculado",
                    description="No estás vinculado al sistema DKP. Pide a un oficial que te vincule primero.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{usuario}' no está vinculado y trató de justificar ausencia interactiva.")
            self.stop()
            return

        if self.duracion.lower() == "vacaciones":
            admins_mencionados = ' '.join([f"<@{admin_id}>" for admin_id in ADMINS_IDS])
            mensaje = f"{admins_mencionados} El usuario **{nombre_usuario or usuario.name}** solicitó irse de vacaciones."

            canal_admin = bot.get_channel(CANAL_ADMIN)
            if not canal_admin:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error",
                        description="No se pudo encontrar el canal de administración para notificar.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                logger.error(f"Canal de administración con ID {CANAL_ADMIN} no encontrado.")
                self.stop()
                return

            await canal_admin.send(mensaje)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Solicitud Enviada",
                    description="Tu solicitud de vacaciones ha sido enviada a los administradores.",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
            logger.info(f"Usuario '{nombre_usuario or usuario.name}' solicitó vacaciones.")
            self.stop()
            return

        try:
            dias = int(self.duracion.split()[0])
            if dias < 1 or dias > 2:
                raise ValueError
        except (ValueError, IndexError):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Duración Inválida",
                    description="La duración seleccionada no es válida. Por favor, intenta nuevamente.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            logger.warning(f"Usuario '{nombre_usuario or usuario.name}' seleccionó una duración inválida: {self.duracion}")
            self.stop()
            return

        ausencia_until = datetime.utcnow() + timedelta(days=dias)
        user_data[nombre_usuario]["absence_until"] = ausencia_until
        guardar_datos()

        await interaction.followup.send(
            embed=discord.Embed(
                title="Ausencia Justificada",
                description=f"Has quedado justificado por los próximos **{dias} día(s)**, **{nombre_usuario}**.",
                color=discord.Color.green()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{nombre_usuario}' justificó ausencia por {dias} días.")
        self.stop()

    async def cancelar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()
        await interaction.followup.send(
            embed=discord.Embed(
                title="Proceso Cancelado",
                description="Has cancelado la justificación de ausencia.",
                color=discord.Color.orange()
            ),
            ephemeral=True
        )
        logger.info(f"Usuario '{interaction.user}' canceló el proceso de justificación de ausencia.")
        self.stop()

class AsistenciaView(discord.ui.View):
    def __init__(
        self,
        bot,
        canal_admin_id: int,
        nombres_extraidos: List[str],
        nombres_coincidentes: List[str]
    ):
        super().__init__(timeout=1700)
        self.bot = bot
        self.canal_admin_id = canal_admin_id
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

    def get_current_options(self) -> List[SelectOption]:
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return [SelectOption(label=nombre, value=nombre) for nombre in current_page_names]

    def get_max_values(self) -> int:
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])
        return len(current_page_names) if current_page_names else 1

    def update_embed(self) -> None:
        """Actualiza self.embed con los nombres paginados."""
        start = self.current_page * self.names_per_page
        end = start + self.names_per_page
        current_page_names = sorted(self.nombres_filtrados[start:end])

        nombres_str = "\n".join(current_page_names)
        embed = self.embed_initial.copy()
        if nombres_str:
            embed.add_field(
                name=f"Nombres ({self.current_page + 1}/{self.total_pages})",
                value="```\n" + nombres_str + "\n```",
                inline=False
            )
        else:
            embed.add_field(
                name=f"Nombres ({self.current_page + 1}/{self.total_pages})",
                value="```\nNo hay nombres.\n```",
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
                self.current_page = max(self.total_pages - 1, 0)

            self.select.options = self.get_current_options()
            self.select.max_values = self.get_max_values()
            self.update_embed()

            await interaction.response.edit_message(embed=self.embed, view=self)
            await interaction.followup.send(
                "Se han eliminado los siguientes nombres: " + ", ".join(nombres_eliminados),
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
        nombres_str = "\n".join(self.nombres_filtrados)
        embed = discord.Embed(
            title="Asistencia del Evento",
            description="Lista de nombres extraídos de las imágenes para copiar manualmente:\n"
                        "```\n" + nombres_str + "\n```",
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

        dkp_valores = [2, 3, 9, 21, 45]
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

        nombres_str = "\n".join(self.nombres_filtrados)
        embed = discord.Embed(
            title="CONFIRMAR",
            description="**Evento:** " + str(self.evento_seleccionado) + "\n"
                        "**DKP:** " + str(self.dkp_seleccionado) + "\n"
                        "**Resta DKP:** " + ("SI" if self.resta_dkp else "NO") + "\n\n"
                        "**Nombres:**\n```\n" + nombres_str + "\n```",
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
        listadenombres = self.nombres_filtrados

        canal_admin = self.bot.get_channel(self.canal_admin_id)
        if canal_admin is None:
            await interaction.response.send_message(
                "No se pudo encontrar el canal de administración.",
                ephemeral=True
            )
            logger.error(f"No se pudo encontrar el canal con ID {CANAL_ADMIN}.")
            return

        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True

        await interaction.response.edit_message(view=self)

        await handle_evento(
            nombre_evento=self.evento_seleccionado,
            puntaje=self.dkp_seleccionado,
            noresta=noresta,
            listadenombres=listadenombres,
            channel=canal_admin,
            executor=interaction.user
        )

        embed_final = discord.Embed(
            title="Asistencia Registrada",
            description="La asistencia ha sido registrada exitosamente en el canal de administración.",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed_final)
        self.stop()