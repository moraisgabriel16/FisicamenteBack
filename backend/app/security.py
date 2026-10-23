import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from .db import DATA, AuthSession, User, get_db

PRODUCTION = os.getenv('APP_ENV') == 'production'
APP_URL = os.getenv('APP_URL', 'http://127.0.0.1:5186').rstrip('/')
key = os.getenv('ENCRYPTION_KEY')
if not key:
    if PRODUCTION:
        raise RuntimeError('ENCRYPTION_KEY é obrigatória em produção')
    keyfile = DATA / 'encryption.key'
    if not keyfile.exists():
        keyfile.write_bytes(Fernet.generate_key())
    key = keyfile.read_text().strip()
fernet = Fernet(key)
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def expiry(hours=12):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

def valid_password(password):
    if len(password) < 10 or len(password) > 128:
        raise HTTPException(422, 'A senha deve ter entre 10 e 128 caracteres.')
    return hasher.hash(password)

def verify(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def current_user(request: Request, db=Depends(get_db)):
    raw = request.cookies.get('fm_session', '')
    session = db.get(AuthSession, digest(raw))
    if not session or session.expires < datetime.now(timezone.utc).isoformat():
        raise HTTPException(401, 'Entre na sua conta para continuar.')
    user = db.get(User, session.user_id)
    if not user or not user.active or not user.verified:
        raise HTTPException(401, 'Conta indisponível ou e-mail não confirmado.')
    return user

def login_session(db, user, response):
    raw = secrets.token_urlsafe(48)
    db.add(AuthSession(id=digest(raw), user_id=user.id, expires=expiry()))
    db.commit()
    response.set_cookie('fm_session',raw,httponly=True,secure=PRODUCTION,samesite='strict',max_age=43200,path='/api')

def audit(db, user, action, target):
    from .db import Audit
    db.add(Audit(school_id=user.school_id,user_id=user.id,action=action,target=target))

def public_user(u):
    return dict(id=u.id,name=u.name,email=u.email,role=u.role,active=u.active,verified=u.verified,links=u.links)
