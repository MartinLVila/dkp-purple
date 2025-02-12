import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, JSON, text

DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    raise ValueError("No se encontró DB_URL en las variables de entorno")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(BigInteger, index=True)
    name = Column(String(255), unique=True, index=True)
    score = Column(Integer, default=0)
    absence_until = Column(DateTime, nullable=True)
    justified_events = Column(JSON, default=list)
    status = Column(String(50), default="normal")
    equipo = Column(JSON, default=dict)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    timestamp = Column(DateTime)
    puntaje = Column(Integer)
    linked_users = Column(JSON, default=list)
    late_users = Column(JSON, default=list)
    penalties = Column(JSON, default=dict)

class RegisteredEvent(Base):
    __tablename__ = "registered_events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)

class ScoreHistoryEntry(Base):
    __tablename__ = "score_history"
    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(255), index=True)
    timestamp = Column(DateTime)
    delta = Column(Integer)
    razon = Column(String(255))

class Party(Base):
    __tablename__ = "partys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    members = Column(JSON, default=list)

user_data = {}
events_info = {}
registered_events = set()
score_history = {}
PARTYS = {}

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def cargar_todos_los_datos():
    await cargar_datos()
    await cargar_eventos()
    await cargar_eventos_registrados()
    await cargar_historial_dkp()
    await cargar_partys()

async def cargar_datos():
    global user_data
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT * FROM users"))
        rows = result.fetchall()
        user_data = {}
        for row in rows:
            user = row._mapping
            if user["absence_until"]:
                user["absence_until"] = datetime.fromisoformat(user["absence_until"]) if isinstance(user["absence_until"], str) else user["absence_until"]
            if user.get("justified_events") is not None:
                user["justified_events"] = set(json.loads(user["justified_events"]))
            else:
                user["justified_events"] = set()
            if user.get("equipo") is not None:
                user["equipo"] = json.loads(user["equipo"])
            else:
                user["equipo"] = {}
            user_data[user["name"]] = dict(user)

async def guardar_datos():
    async with AsyncSessionLocal() as session:
        for name, data in user_data.items():
            result = await session.execute(text("SELECT * FROM users WHERE name = :name"), {"name": name})
            existing = result.fetchone()
            params = {
                "discord_id": data.get("discord_id"),
                "score": data.get("score"),
                "absence_until": data.get("absence_until").isoformat() if data.get("absence_until") else None,
                "justified_events": json.dumps(list(data.get("justified_events"))) if isinstance(data.get("justified_events"), set) else json.dumps(data.get("justified_events") or []),
                "status": data.get("status"),
                "equipo": json.dumps(data.get("equipo") or {}),
                "name": name
            }
            if existing:
                await session.execute(
                    text("UPDATE users SET discord_id=:discord_id, score=:score, absence_until=:absence_until, justified_events=:justified_events, status=:status, equipo=:equipo WHERE name=:name"),
                    params
                )
            else:
                await session.execute(
                    text("INSERT INTO users (discord_id, name, score, absence_until, justified_events, status, equipo) VALUES (:discord_id, :name, :score, :absence_until, :justified_events, :status, :equipo)"),
                    params
                )
        await session.commit()

async def cargar_eventos():
    global events_info
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT * FROM events"))
        rows = result.fetchall()
        events_info = {}
        for row in rows:
            event = row._mapping
            if event["timestamp"]:
                event["timestamp"] = datetime.fromisoformat(event["timestamp"]) if isinstance(event["timestamp"], str) else event["timestamp"]
            if event.get("linked_users") is not None:
                event["linked_users"] = json.loads(event["linked_users"])
            else:
                event["linked_users"] = []
            if event.get("late_users") is not None:
                event["late_users"] = json.loads(event["late_users"])
            else:
                event["late_users"] = []
            if event.get("penalties") is not None:
                event["penalties"] = json.loads(event["penalties"])
            else:
                event["penalties"] = {}
            events_info[event["name"]] = dict(event)

async def guardar_eventos():
    async with AsyncSessionLocal() as session:
        for name, event in events_info.items():
            result = await session.execute(text("SELECT * FROM events WHERE name = :name"), {"name": name})
            existing = result.fetchone()
            params = {
                "name": name,
                "timestamp": event["timestamp"].isoformat() if event.get("timestamp") else None,
                "puntaje": event.get("puntaje"),
                "linked_users": json.dumps(event.get("linked_users") or []),
                "late_users": json.dumps(event.get("late_users") or []),
                "penalties": json.dumps(event.get("penalties") or {})
            }
            if existing:
                await session.execute(
                    text("UPDATE events SET timestamp=:timestamp, puntaje=:puntaje, linked_users=:linked_users, late_users=:late_users, penalties=:penalties WHERE name=:name"),
                    params
                )
            else:
                await session.execute(
                    text("INSERT INTO events (name, timestamp, puntaje, linked_users, late_users, penalties) VALUES (:name, :timestamp, :puntaje, :linked_users, :late_users, :penalties)"),
                    params
                )
        await session.commit()

async def cargar_eventos_registrados():
    global registered_events
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT * FROM registered_events"))
        rows = result.fetchall()
        registered_events = {row._mapping["name"] for row in rows}

async def guardar_eventos_registrados():
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM registered_events"))
        for name in registered_events:
            await session.execute(
                text("INSERT INTO registered_events (name) VALUES (:name)"),
                {"name": name}
            )
        await session.commit()

async def cargar_historial_dkp():
    global score_history
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT * FROM score_history"))
        rows = result.fetchall()
        score_history = {}
        for row in rows:
            entry = row._mapping
            entry["timestamp"] = datetime.fromisoformat(entry["timestamp"]) if isinstance(entry["timestamp"], str) else entry["timestamp"]
            user = entry["user_name"]
            if user not in score_history:
                score_history[user] = []
            score_history[user].append(dict(entry))

async def cargar_partys():
    global PARTYS
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT * FROM partys"))
        rows = result.fetchall()
        PARTYS = {}
        for row in rows:
            party = row._mapping
            if party.get("members") is not None:
                PARTYS[party["name"]] = json.loads(party["members"])
            else:
                PARTYS[party["name"]] = []
            
async def save_partys():
    async with AsyncSessionLocal() as session:
        for name, members in PARTYS.items():
            result = await session.execute(text("SELECT * FROM partys WHERE name = :name"), {"name": name})
            existing = result.fetchone()
            params = {
                "name": name,
                "members": json.dumps(members)
            }
            if existing:
                await session.execute(
                    text("UPDATE partys SET members=:members WHERE name=:name"),
                    params
                )
            else:
                await session.execute(
                    text("INSERT INTO partys (name, members) VALUES (:name, :members)"),
                    params
                )
        await session.commit()

async def registrar_cambio_dkp(nombre_usuario, delta, razon=""):
    global score_history
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "delta": delta,
        "razon": razon,
        "user_name": nombre_usuario
    }
    if nombre_usuario not in score_history:
        score_history[nombre_usuario] = []
    score_history[nombre_usuario].append(entry)
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("INSERT INTO score_history (user_name, timestamp, delta, razon) VALUES (:user_name, :timestamp, :delta, :razon)"),
            entry
        )
        await session.commit()