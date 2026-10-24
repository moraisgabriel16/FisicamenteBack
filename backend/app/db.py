import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import JSON, Boolean, ForeignKey, LargeBinary, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

SERVERLESS = bool(os.getenv('VERCEL'))
DATA = Path(os.getenv('DATA_DIR', '/tmp/fisicamente' if SERVERLESS else str(Path(__file__).resolve().parents[1] / 'data')))
DATA.mkdir(exist_ok=True)
URL = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
if not URL:
    if SERVERLESS or os.getenv('APP_ENV') == 'production':
        raise RuntimeError('Configure DATABASE_URL com um banco PostgreSQL persistente antes de publicar a API.')
    URL=f'sqlite:///{(DATA / "fisicamente.db").as_posix()}'
if URL.startswith(('postgres://','postgresql://')):
    URL='postgresql+psycopg://'+URL.split('://',1)[1]
if (SERVERLESS or os.getenv('APP_ENV') == 'production') and URL.startswith('sqlite'):
    raise RuntimeError('SQLite local não pode ser utilizado para os dados de produção.')
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {}, pool_pre_ping=True, **({'poolclass':NullPool} if SERVERLESS else {}))
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_setup(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')

Session = sessionmaker(engine, expire_on_commit=False)

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

class Base(DeclarativeBase):
    pass

class School(Base):
    __tablename__ = 'escolas'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

class User(Base):
    __tablename__ = 'usuarios'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('escolas.id'), index=True)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    links: Mapped[dict] = mapped_column(JSON, default=dict)

class AuthSession(Base):
    __tablename__ = 'sessoes'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('usuarios.id'), index=True)
    expires: Mapped[str] = mapped_column(String(40))

class Token(Base):
    __tablename__ = 'tokens'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON)
    expires: Mapped[str] = mapped_column(String(40))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class Record(Base):
    __tablename__ = 'registros'
    __table_args__ = (UniqueConstraint('school_id', 'kind', 'request_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('escolas.id'), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    student_id: Mapped[str | None] = mapped_column(String(36), index=True)
    class_id: Mapped[str | None] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('usuarios.id'))
    data: Mapped[dict] = mapped_column(JSON)
    request_key: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

class Audit(Base):
    __tablename__ = 'auditoria'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('escolas.id'), index=True)
    user_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(100))
    at: Mapped[str] = mapped_column(String(40), default=now)

class AttachmentBlob(Base):
    __tablename__ = 'anexos_conteudo'
    id: Mapped[str] = mapped_column(ForeignKey('registros.id'), primary_key=True)
    encrypted: Mapped[bytes] = mapped_column(LargeBinary)

class Mail(Base):
    __tablename__ = 'emails'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(ForeignKey('escolas.id'))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

def get_db():
    with Session() as db:
        yield db
