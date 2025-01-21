import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_FILE = "scores.json"
EVENTS_FILE = "events.json"
REGISTERED_EVENTS_FILE = "registered_events.json"
HISTORY_FILE = "score_history.json"
PARTYS_FILE = "partys.json"

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")

user_data = {}
events_info = {}
registered_events = set()
score_history = {}
PARTYS = {}

def cargar_todos_los_datos():
    cargar_datos()
    cargar_eventos()
    cargar_eventos_registrados()
    cargar_historial_dkp()
    cargar_partys()

def cargar_datos():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for nombre, datos in data.items():
                    if "absence_until" in datos and datos["absence_until"]:
                        try:
                            datos["absence_until"] = datetime.fromisoformat(datos["absence_until"])
                        except ValueError:
                            datos["absence_until"] = None
                    
                    # Ajustes de sets
                    if "justified_events" in datos:
                        datos["justified_events"] = set(datos["justified_events"])
                    else:
                        datos["justified_events"] = set()

                    if "justificado" not in datos or not isinstance(datos["justificado"], list):
                        datos["justificado"] = []

                    # Default status
                    if "status" not in datos:
                        datos["status"] = "normal"

                user_data = data
        except json.JSONDecodeError:
            user_data = {}
    else:
        user_data = {}

def guardar_datos():
    serializable_data = {}
    for nombre, datos in user_data.items():
        temp = datos.copy()
        if temp.get("absence_until"):
            temp["absence_until"] = temp["absence_until"].isoformat()
        else:
            temp["absence_until"] = None
        
        if "justified_events" in temp:
            temp["justified_events"] = list(temp["justified_events"])
        
        serializable_data[nombre] = temp

    with open(DATA_FILE, "w") as f:
        json.dump(serializable_data, f, indent=4)

def cargar_eventos():
    global events_info
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r") as f:
                data = json.load(f)
                for evento, info in data.items():
                    try:
                        info["timestamp"] = datetime.fromisoformat(info["timestamp"])
                    except ValueError:
                        info["timestamp"] = datetime.utcnow()
                    
                    # Convertir linked_users y late_users a set
                    if isinstance(info.get("linked_users"), list):
                        info["linked_users"] = set(info["linked_users"])
                    else:
                        info["linked_users"] = set()

                    if isinstance(info.get("late_users"), list):
                        info["late_users"] = set(info["late_users"])
                    else:
                        info["late_users"] = set()

                    if not isinstance(info.get("penalties"), dict):
                        info["penalties"] = {}
                events_info = data
        except json.JSONDecodeError:
            events_info = {}
    else:
        events_info = {}

def guardar_eventos():
    serializable_events = {}
    for evento, info in events_info.items():
        serializable_events[evento] = {
            "timestamp": info["timestamp"].isoformat(),
            "linked_users": list(info["linked_users"]),
            "late_users": list(info["late_users"]),
            "puntaje": info["puntaje"],
            "penalties": info.get("penalties", {})
        }
    with open(EVENTS_FILE, "w") as f:
        json.dump(serializable_events, f, indent=4)

def cargar_eventos_registrados():
    global registered_events
    if os.path.exists(REGISTERED_EVENTS_FILE):
        try:
            with open(REGISTERED_EVENTS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    registered_events = set(data)
                else:
                    registered_events = set()
        except json.JSONDecodeError:
            registered_events = set()
    else:
        registered_events = set()

def guardar_eventos_registrados():
    with open(REGISTERED_EVENTS_FILE, "w") as f:
        json.dump(list(registered_events), f, indent=4)

def cargar_historial_dkp():
    global score_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    score_history = data
                else:
                    score_history = {}
        except json.JSONDecodeError:
            score_history = {}
    else:
        score_history = {}

def guardar_historial_dkp():
    with open(HISTORY_FILE, "w") as f:
        json.dump(score_history, f, indent=4)

def cargar_partys():
    global PARTYS
    if os.path.exists(PARTYS_FILE):
        try:
            with open(PARTYS_FILE, "r", encoding="utf-8") as f:
                PARTYS = json.load(f)
        except json.JSONDecodeError:
            PARTYS = {}
    else:
        PARTYS = {}

def save_partys():
    with open(PARTYS_FILE, "w", encoding="utf-8") as f:
        json.dump(PARTYS, f, indent=4, ensure_ascii=False)

def registrar_cambio_dkp(nombre_usuario, delta, razon=""):
    global score_history
    if nombre_usuario not in score_history:
        score_history[nombre_usuario] = []
    registro = {
        "timestamp": datetime.utcnow().isoformat(),
        "delta": delta,
        "razon": razon
    }
    score_history[nombre_usuario].append(registro)
    guardar_historial_dkp()