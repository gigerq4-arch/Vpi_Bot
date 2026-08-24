import enum
import datetime
from sqlalchemy import BigInteger, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

class Base(DeclarativeBase):
    pass

class RoleEnum(enum.Enum):
    root = "root"
    player = "player"

class TradeStatusEnum(enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = 'users'

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.player)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    country: Mapped["Country"] = relationship("Country", back_populates="owner", uselist=False)

class Country(Base):
    __tablename__ = 'countries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), unique=True)
    name: Mapped[str] = mapped_column(String)
    ideology: Mapped[str] = mapped_column(String)
    ruler: Mapped[str] = mapped_column(String)
    party: Mapped[str] = mapped_column(String)
    religion: Mapped[str] = mapped_column(String, server_default='Не указана', default='Не указана')
    stability: Mapped[float] = mapped_column(Float)
    war_support: Mapped[float] = mapped_column(Float)
    area: Mapped[float] = mapped_column(Float)
    flag_photo_id: Mapped[str] = mapped_column(String)
    map_photo_id: Mapped[str] = mapped_column(String)
    treasury: Mapped[float] = mapped_column(Float, default=10.0)
    taxpayers: Mapped[int] = mapped_column(BigInteger, default=1000000)
    military: Mapped[int] = mapped_column(BigInteger, default=10000)
    inflation: Mapped[float] = mapped_column(Float, default=0.0)
    built_this_turn: Mapped[int] = mapped_column(Integer, default=0)
    intel_points: Mapped[float] = mapped_column(Float, default=0.0)
    counter_intel_points: Mapped[float] = mapped_column(Float, default=0.0)
    # Additional state for mechanics
    martial_law: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    

    owner: Mapped["User"] = relationship("User", back_populates="country")
    buildings: Mapped[list["CountryBuilding"]] = relationship("CountryBuilding", back_populates="country")
    productions: Mapped[list["CountryProduction"]] = relationship("CountryProduction", back_populates="country")
    stockpiles: Mapped[list["CountryStockpile"]] = relationship("CountryStockpile", back_populates="country")
    events: Mapped[list["CountryEvent"]] = relationship("CountryEvent", back_populates="country")

    # Ядерная программа
    nuclear_phase_1: Mapped[float] = mapped_column(Float, default=0.0)
    nuclear_phase_2: Mapped[float] = mapped_column(Float, default=0.0)
    nuclear_phase_3: Mapped[float] = mapped_column(Float, default=0.0)
    nuclear_phase_4: Mapped[float] = mapped_column(Float, default=0.0)
    nuclear_phase_5: Mapped[float] = mapped_column(Float, default=0.0)

    lab_assigned_phase_1: Mapped[int] = mapped_column(Integer, default=0)
    lab_assigned_phase_2: Mapped[int] = mapped_column(Integer, default=0)
    lab_assigned_phase_3: Mapped[int] = mapped_column(Integer, default=0)
    lab_assigned_phase_4: Mapped[int] = mapped_column(Integer, default=0)
    lab_assigned_phase_5: Mapped[int] = mapped_column(Integer, default=0)
    last_expand_turn: Mapped[int] = mapped_column(Integer, default=-3)
    growth_modifier: Mapped[float] = mapped_column(Float, default=0.0)

class CountryBuilding(Base):
    __tablename__ = 'country_buildings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    building_id: Mapped[int] = mapped_column(Integer)
    total_count: Mapped[int] = mapped_column(Integer, default=0)

    country: Mapped["Country"] = relationship("Country", back_populates="buildings")

class CountryProduction(Base):
    __tablename__ = 'country_production'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    item_id: Mapped[int] = mapped_column(Integer)
    assigned_factories: Mapped[int] = mapped_column(Integer, default=0)

    country: Mapped["Country"] = relationship("Country", back_populates="productions")

class CountryStockpile(Base):
    __tablename__ = 'country_stockpile'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    item_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    country: Mapped["Country"] = relationship("Country", back_populates="stockpiles")


class CountryEvent(Base):
    __tablename__ = 'country_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    description: Mapped[str] = mapped_column(String)
    
    tax_modifier: Mapped[float] = mapped_column(Float, default=0.0)
    stability_modifier: Mapped[float] = mapped_column(Float, default=0.0)
    war_support_modifier: Mapped[float] = mapped_column(Float, default=0.0)
    
    turns_left: Mapped[int] = mapped_column(Integer)
    
    country: Mapped["Country"] = relationship("Country", back_populates="events")

class TradeSession(Base):
    __tablename__ = 'trade_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    receiver_country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    sender_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    receiver_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    sender_slots: Mapped[dict] = mapped_column(JSON, default=dict)
    receiver_slots: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[TradeStatusEnum] = mapped_column(Enum(TradeStatusEnum), default=TradeStatusEnum.active)


class ExpansionRequest(Base):
    __tablename__ = 'expansion_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey('countries.id'))
    turn_number: Mapped[int] = mapped_column(Integer)
    troops: Mapped[int] = mapped_column(Integer, default=0)
    civilians: Mapped[int] = mapped_column(Integer, default=0)
    equipment: Mapped[dict] = mapped_column(JSON, default=dict)
    photo_file_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    country: Mapped["Country"] = relationship("Country")

class GameState(Base):
    __tablename__ = 'game_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn_number: Mapped[int] = mapped_column(Integer, default=1)

# --- Database initialization ---

import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./vpi_bot.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if "postgresql+asyncpg://" in DATABASE_URL:
    import re
    if "sslmode=require" in DATABASE_URL or "ssl=require" in DATABASE_URL:
        DATABASE_URL = re.sub(r'[\?&]sslmode=require', '', DATABASE_URL)
        DATABASE_URL = re.sub(r'[\?&]ssl=require', '', DATABASE_URL)
        connect_args["ssl"] = "require"


engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args if "connect_args" in locals() else {}, pool_pre_ping=True, pool_recycle=1800)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class ExpandRequest(Base):
    __tablename__ = 'expand_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    army: Mapped[int] = mapped_column(Integer)
    population: Mapped[int] = mapped_column(Integer)
    vehicles: Mapped[str] = mapped_column(String) # JSON string
    photo_id: Mapped[str] = mapped_column(String)


async def init_db():
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
    alter_statements = [
        "ALTER TABLE countries ADD COLUMN nuclear_phase_1 FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN nuclear_phase_2 FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN nuclear_phase_3 FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN nuclear_phase_4 FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN nuclear_phase_5 FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN lab_assigned_phase_1 INTEGER DEFAULT 0;",
        "ALTER TABLE countries ADD COLUMN lab_assigned_phase_2 INTEGER DEFAULT 0;",
        "ALTER TABLE countries ADD COLUMN lab_assigned_phase_3 INTEGER DEFAULT 0;",
        "ALTER TABLE countries ADD COLUMN lab_assigned_phase_4 INTEGER DEFAULT 0;",
        "ALTER TABLE countries ADD COLUMN lab_assigned_phase_5 INTEGER DEFAULT 0;",
        "ALTER TABLE countries ADD COLUMN last_expand_turn INTEGER DEFAULT -3;",
        "ALTER TABLE countries ADD COLUMN growth_modifier FLOAT DEFAULT 0.0;",
        "ALTER TABLE countries ADD COLUMN is_approved BOOLEAN DEFAULT 1;",
        "CREATE TABLE IF NOT EXISTS country_events (id SERIAL PRIMARY KEY, country_id INTEGER REFERENCES countries(id), description VARCHAR, tax_modifier FLOAT DEFAULT 0.0, stability_modifier FLOAT DEFAULT 0.0, war_support_modifier FLOAT DEFAULT 0.0, turns_left INTEGER);"
    ]
    
    from sqlalchemy import text
    for stmt in alter_statements:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:
            pass
            
    async with async_session() as session:
        from sqlalchemy import select
        state = await session.scalar(select(GameState))
        if not state:
            session.add(GameState(turn_number=1))
            await session.commit()

