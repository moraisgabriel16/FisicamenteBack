import csv
import io
import json
import os
import secrets
import smtplib
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal
from xml.sax.saxutils import escape
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import *
from .catalog import CATALOG, CRITERIA
from .security import *

SENSITIVE = {'saude','afastamentos'}
ROLES = {'admin','diretor','coordenador','professor','responsavel','aluno'}

def outbox(db, school_id, recipient, subject, body):
    mail = Mail(school_id=school_id,recipient=recipient,subject=subject,body=body)
    db.add(mail)

def make_token(db, kind, payload, hours=72):
    raw = secrets.token_urlsafe(40)
    db.add(Token(id=digest(raw),kind=kind,payload=payload,expires=expiry(hours)))
    return raw

def use_token(db, raw, kind):
    token = db.get(Token, digest(raw))
    if not token or token.used or token.kind != kind or token.expires < now():
        raise HTTPException(400,'Link inválido, utilizado ou expirado.')
    token.used = True
    return token.payload

def worker(stop):
    while not stop.wait(30):
        try:
            with Session() as db:
                # Reports intentionally contain school-wide aggregates only.
                schedules = db.scalars(select(Record).where(Record.kind=='agendamentos',Record.deleted==False)).all()
                for r in schedules:
                    if r.data['next_date'] > date.today().isoformat():
                        continue
                    recipient = db.get(User,r.data['recipient_id'])
                    if not recipient or not recipient.active or recipient.role not in {'diretor','coordenador'}:
                        continue
                    n = len(db.scalars(select(Record).where(Record.school_id==r.school_id,Record.kind=='avaliacoes',Record.deleted==False)).all())
                    outbox(db,r.school_id,recipient.email,'FísicaMente · '+r.data['name'],f'Sua escola tem {n} avaliações registradas. Consulte os indicadores em {APP_URL}.')
                    r.data = {**r.data,'next_date':(date.today()+timedelta(days=7 if r.data['frequency']=='Semanal' else 30)).isoformat()}
                db.commit()
                if os.getenv('SMTP_HOST'):
                    for mail in db.scalars(select(Mail).where(Mail.sent==False).limit(20)):
                        message=EmailMessage(); message['From']=os.getenv('SMTP_FROM','fisicamente@localhost'); message['To']=mail.recipient; message['Subject']=mail.subject; message.set_content(mail.body)
                        with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
                            smtp.starttls()
                            if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
                            smtp.send_message(message)
                        mail.sent=True
                        db.commit()
        except Exception:
            import logging
            logging.exception('Falha no processamento de e-mails/agendamentos')

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    stop=threading.Event(); thread=None
    if not SERVERLESS:
        thread=threading.Thread(target=worker,args=(stop,),daemon=True); thread.start()
    yield
    stop.set()
    if thread: thread.join(timeout=1)

app=FastAPI(title='FísicaMente API',version='1.0.0',lifespan=lifespan)
attempts=defaultdict(deque)
rate_lock=threading.Lock()

@app.middleware('http')
async def protections(request, call_next):
    if request.method not in {'GET','HEAD','OPTIONS'}:
        origin=request.headers.get('origin')
        if origin and origin != APP_URL:
            return JSONResponse({'detail':'Origem não autorizada.'},status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Requisição entre sites não autorizada.'},status_code=403)
    if request.url.path.startswith('/api/v1/auth/') and request.method=='POST':
        key=request.client.host
        with rate_lock:
            q=attempts[key]; t=time.monotonic()
            while q and q[0]<t-60: q.popleft()
            if len(q)>=30: return JSONResponse({'detail':'Muitas tentativas. Aguarde um minuto.'},status_code=429)
            q.append(t)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    return response

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({'type':'about:blank','title':'Não foi possível concluir','status':exc.status_code,'detail':exc.detail},status_code=exc.status_code,media_type='application/problem+json')

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse({'detail':'Confira os campos informados.','errors':[{'field':'.'.join(map(str,e['loc'])),'message':e['msg']} for e in exc.errors()]},status_code=422)

@app.exception_handler(IntegrityError)
async def conflict(request,exc):
    return JSONResponse({'detail':'Já existe um registro com estes dados. Atualize a página.'},status_code=409)

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class Registration(Strict):
    name: str = Field(min_length=2,max_length=180)
    email: EmailStr
    password: str = Field(min_length=10,max_length=128)
    school: str = Field(min_length=2,max_length=180)
    accepted_terms: Literal[True]

class Login(Strict):
    email: EmailStr
    password: str = Field(max_length=128)

class TokenBody(Strict):
    token: str

class Reset(TokenBody):
    password: str = Field(min_length=10,max_length=128)

class Accept(Reset):
    name: str = Field(min_length=2,max_length=180)

class EmailBody(Strict):
    email: EmailStr

def base_seed(db, school, owner):
    year=date.today().year
    for kind,data in [('anos',dict(year=year,start=f'{year}-02-01',end=f'{year}-12-20')),('modelos',dict(name='Desenvolvimento integral',criteria=[dict(name=n,weight=1) for n in CRITERIA]))]:
        db.add(Record(school_id=school.id,owner_id=owner.id,kind=kind,data=data))
    for name,criterion,description in [('Circuito de equilíbrio','Equilíbrio','Percorrer linhas no chão e alternar apoios, respeitando as adaptações de cada aluno.'),('Jogos cooperativos','Participação','Propor desafios em pequenos grupos, alternando funções e valorizando a participação.'),('Alongamento orientado','Flexibilidade','Explorar movimentos confortáveis, sem forçar amplitudes ou provocar dor.')]:
        db.add(Record(school_id=school.id,owner_id=owner.id,kind='atividades',data=dict(name=name,criterion=criterion,description=description,minutes=15,materials='',bncc='')))

@app.get('/api/v1/health')
def health(db=Depends(get_db)):
    from sqlalchemy import text
    db.execute(text('SELECT 1'))
    return {'status':'ok','database':'connected'}

@app.get('/api/v1/auth/config')
def auth_config():
    return {'email_verification_required':email_verification_required(),'email_delivery_available':bool(os.getenv('SMTP_HOST'))}

@app.post('/api/v1/auth/register',status_code=201)
def register(body:Registration,db=Depends(get_db)):
    if PRODUCTION and email_verification_required() and not os.getenv('SMTP_HOST'):
        raise HTTPException(503,'O envio de confirmação ainda não foi configurado. Contate a administração.')
    if db.scalar(select(User).where(User.email==str(body.email).lower())): raise HTTPException(409,'Este e-mail já está cadastrado.')
    school=School(name=body.school); db.add(school); db.flush()
    user=User(school_id=school.id,name=body.name,email=str(body.email).lower(),password=valid_password(body.password),role='coordenador')
    db.add(user);db.flush();base_seed(db,school,user)
    url=None
    if email_verification_required():
        raw=make_token(db,'verify',{'user_id':user.id})
        url=f'{APP_URL}/?action=verify&token={raw}'
        outbox(db,school.id,user.email,'Confirme sua conta FísicaMente',url)
    audit(db,user,'aceite-termos-v1',user.id);db.commit()
    return {'message':'Conta criada. Confirme seu e-mail para entrar.' if email_verification_required() else 'Conta criada. Você já pode entrar.','can_login':not email_verification_required(),'development_link':url if not PRODUCTION and not os.getenv('SMTP_HOST') else None}

@app.post('/api/v1/auth/verify')
def confirm(body:TokenBody,db=Depends(get_db)):
    p=use_token(db,body.token,'verify'); db.get(User,p['user_id']).verified=True;db.commit();return {'message':'E-mail confirmado. Você já pode entrar.'}

@app.post('/api/v1/auth/login')
def login(body:Login,response:Response,db=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(body.email).lower()))
    matches=verify(body.password,user.password if user else DUMMY_HASH)
    if not user or not matches or not user.active: raise HTTPException(401,'E-mail ou senha inválidos.')
    if email_verification_required() and not user.verified: raise HTTPException(403,'Confirme seu e-mail antes de entrar.')
    login_session(db,user,response); audit(db,user,'login',user.id);db.commit();return public_user(user)

@app.post('/api/v1/auth/logout')
def logout(request:Request,response:Response,db=Depends(get_db)):
    db.execute(delete(AuthSession).where(AuthSession.id==digest(request.cookies.get('fm_session',''))));db.commit();response.delete_cookie('fm_session',path='/api');return {'ok':True}

@app.post('/api/v1/auth/refresh')
def refresh_session(request:Request,response:Response,user=Depends(current_user),db=Depends(get_db)):
    db.execute(delete(AuthSession).where(AuthSession.id==digest(request.cookies.get('fm_session',''))))
    login_session(db,user,response)
    return {'ok':True}

@app.post('/api/v1/auth/forgot')
def forgot(body:EmailBody,db=Depends(get_db)):
    if PRODUCTION and not os.getenv('SMTP_HOST'): raise HTTPException(503,'A recuperação por e-mail ainda não está disponível. Contate a administração.')
    user=db.scalar(select(User).where(User.email==str(body.email).lower()))
    if user:
        raw=make_token(db,'reset',{'user_id':user.id},1);outbox(db,user.school_id,user.email,'Redefinir senha FísicaMente',f'{APP_URL}/?action=reset&token={raw}');db.commit()
    return {'message':'Se houver uma conta, enviaremos as instruções ao e-mail informado.'}

@app.post('/api/v1/auth/resend')
def resend(body:EmailBody,db=Depends(get_db)):
    if PRODUCTION and not os.getenv('SMTP_HOST'): raise HTTPException(503,'O envio de e-mails ainda não está disponível.')
    user=db.scalar(select(User).where(User.email==str(body.email).lower()))
    if user and not user.verified:
        raw=make_token(db,'verify',{'user_id':user.id});outbox(db,user.school_id,user.email,'Confirme sua conta FísicaMente',f'{APP_URL}/?action=verify&token={raw}');db.commit()
    return {'message':'Se a confirmação estiver pendente, um novo e-mail será enviado.'}

@app.post('/api/v1/auth/reset')
def reset(body:Reset,db=Depends(get_db)):
    p=use_token(db,body.token,'reset');u=db.get(User,p['user_id']);u.password=valid_password(body.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id==u.id));db.commit();return {'message':'Senha alterada. Entre novamente.'}

@app.get('/api/v1/me')
def me(user=Depends(current_user),db=Depends(get_db)):
    school=db.get(School,user.school_id)
    return {**public_user(user),'school':{'id':user.school_id,'name':school.name,'is_demo':bool(school.settings.get('is_demo',False))},'development':not PRODUCTION and not os.getenv('SMTP_HOST'),'email_delivery_available':bool(os.getenv('SMTP_HOST'))}

def require(user, roles):
    if user.role not in roles: raise HTTPException(403,'Seu perfil não permite esta operação.')

def records(db,user,kind):
    return db.scalars(select(Record).where(Record.school_id==user.school_id,Record.kind==kind,Record.deleted==False).order_by(Record.created_at.desc())).all()

def lookup(db,user,id,kind=None):
    r=db.get(Record,id)
    if not r or r.deleted or r.school_id!=user.school_id or (kind and r.kind!=kind): raise HTTPException(404,'Registro não encontrado.')
    return r

def allowed_classes(db,user):
    return {r.id for r in records(db,user,'turmas') if user.id in r.data.get('teacher_ids',[])}

def allowed_students(db,user):
    if user.role in {'responsavel','aluno'}: return set(user.links.get('student_ids',[]))
    if user.role=='professor':
        classes=allowed_classes(db,user)
        return {r.id for r in records(db,user,'alunos') if r.class_id in classes}
    return {r.id for r in records(db,user,'alunos')}

def accessible(db,user,r):
    if r.kind in {'mensagens','reunioes'}: return r.owner_id==user.id or r.data.get('recipient_id')==user.id
    if user.role in {'coordenador','admin','diretor'}: return True
    if r.kind=='alunos': return r.id in allowed_students(db,user)
    if r.student_id: return r.student_id in allowed_students(db,user)
    if r.kind=='turmas' and user.role=='professor': return r.id in allowed_classes(db,user)
    if r.class_id and user.role=='professor': return r.class_id in allowed_classes(db,user)
    return True

def payload(r):
    data=r.data
    if r.kind in SENSITIVE: data=json.loads(fernet.decrypt(data['encrypted'].encode()))
    return {'id':r.id,'kind':r.kind,'student_id':r.student_id,'class_id':r.class_id,'owner_id':r.owner_id,'created_at':r.created_at,'updated_at':r.updated_at,**data}

@app.get('/api/v1/catalog')
def catalog(user=Depends(current_user)):
    return {k:{**v,'can_write':user.role in v['write']} for k,v in CATALOG.items() if user.role in v['read'] and not (k=='agendamentos' and SERVERLESS)}

@app.get('/api/v1/users')
def users(user=Depends(current_user),db=Depends(get_db)):
    # Family contacts are limited to school staff, never other families or students.
    rows=db.scalars(select(User).where(User.school_id==user.school_id)).all()
    if user.role not in {'admin','coordenador','diretor'}:
        rows=[u for u in rows if u.role in {'professor','coordenador','diretor'} or u.id==user.id]
    return [public_user(u) if user.role in {'admin','coordenador'} else dict(id=u.id,name=u.name,role=u.role) for u in rows]

class Invite(Strict):
    email: EmailStr
    role: str
    student_ids: list[str] = []

@app.post('/api/v1/invites',status_code=201)
def invite(body:Invite,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'admin','coordenador'})
    if body.role not in ROLES: raise HTTPException(422,'Perfil inválido.')
    for id in body.student_ids: lookup(db,user,id,'alunos')
    if body.role=='aluno' and len(body.student_ids)!=1: raise HTTPException(422,'Vincule exatamente um aluno.')
    if body.role=='responsavel' and not body.student_ids: raise HTTPException(422,'Vincule pelo menos um aluno.')
    if db.scalar(select(User).where(User.email==str(body.email).lower())): raise HTTPException(409,'E-mail já cadastrado.')
    raw=make_token(db,'invite',dict(school_id=user.school_id,email=str(body.email).lower(),role=body.role,student_ids=body.student_ids))
    url=f'{APP_URL}/?action=invite&token={raw}';outbox(db,user.school_id,str(body.email),'Convite para FísicaMente',url);audit(db,user,'convite',str(body.email));db.commit()
    return {'message':'Convite registrado para envio.' if os.getenv('SMTP_HOST') else 'Convite criado. Compartilhe o link com a pessoa convidada.','invite_link':url if not os.getenv('SMTP_HOST') else None,'development_link':url if not PRODUCTION and not os.getenv('SMTP_HOST') else None}

@app.post('/api/v1/auth/accept')
def accept(body:Accept,db=Depends(get_db)):
    p=use_token(db,body.token,'invite')
    if db.scalar(select(User).where(User.email==p['email'])): raise HTTPException(409,'E-mail já cadastrado.')
    u=User(school_id=p['school_id'],email=p['email'],name=body.name,password=valid_password(body.password),role=p['role'],verified=True,links={'student_ids':p['student_ids']});db.add(u);db.commit();return {'message':'Convite aceito. Entre com seu e-mail e senha.'}

class UserChange(Strict):
    active: bool

@app.patch('/api/v1/users/{id}')
def user_change(id:str,body:UserChange,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'admin','coordenador'});u=db.get(User,id)
    if not u or u.school_id!=user.school_id: raise HTTPException(404,'Usuário não encontrado.')
    if u.id==user.id: raise HTTPException(422,'Você não pode desativar sua própria conta.')
    u.active=body.active
    if not u.active: db.execute(delete(AuthSession).where(AuthSession.user_id==id))
    audit(db,user,'alterar-usuario',id);db.commit();return public_user(u)

@app.get('/api/v1/development-mails')
def development_mails(user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','admin'})
    if PRODUCTION: raise HTTPException(404)
    return [dict(id=m.id,recipient=m.recipient,subject=m.subject,body=m.body,sent=m.sent) for m in db.scalars(select(Mail).where(Mail.school_id==user.school_id).order_by(Mail.created_at.desc()).limit(50))]

class RecordBody(Strict):
    data: dict
    student_id: str | None = None
    class_id: str | None = None
    updated_at: str | None = None

def validate_record(db,user,kind,body,existing=None):
    if kind=='agendamentos' and SERVERLESS:
        raise HTTPException(503,'Agendamentos exigem configurar um executor de tarefas nesta hospedagem.')
    spec=CATALOG.get(kind)
    if not spec: raise HTTPException(404,'Módulo não encontrado.')
    require(user,spec['write'])
    data=dict(body.data)
    known={f['key'] for f in spec['fields']}
    if set(data)-known: raise HTTPException(422,'Campo não permitido.')
    for f in spec['fields']:
        v=data.get(f['key']); typ=f['type']; label=f['label']
        if isinstance(v,str):
            v=v.strip();data[f['key']]=v
        if f['required'] and (v is None or v=='' or v==[]): raise HTTPException(422,f'Preencha: {label}.')
        if v is None or v=='': continue
        if typ=='number':
            try: v=float(v)
            except (ValueError,TypeError): raise HTTPException(422,f'{label}: informe um número.')
            if not (-1e7<v<1e7): raise HTTPException(422,f'{label}: valor inválido.')
            data[f['key']]=v
        elif typ=='select' and v not in f['options']: raise HTTPException(422,f'{label}: opção inválida.')
        elif typ in {'date','datetime-local'}:
            try: datetime.fromisoformat(v)
            except (ValueError,TypeError): raise HTTPException(422,f'{label}: data inválida.')
        elif typ.startswith('ref:'):
            ref=lookup(db,user,v,typ.split(':')[1])
            if not accessible(db,user,ref): raise HTTPException(403,'Vínculo não autorizado.')
        elif typ.startswith(('user:','users:')):
            ids=v if typ.startswith('users:') else [v]
            if not isinstance(ids,list): raise HTTPException(422,'Seleção inválida.')
            for id in ids:
                u=db.get(User,id)
                if not u or u.school_id!=user.school_id or not u.active or (typ.split(':')[1]!='all' and u.role!=typ.split(':')[1]): raise HTTPException(422,'Usuário vinculado inválido.')
                if kind=='agendamentos' and u.role not in {'diretor','coordenador'}: raise HTTPException(422,'Relatórios institucionais somente para direção e coordenação.')
                if user.role in {'responsavel','professor'} and u.role not in {'professor','coordenador','diretor'}: raise HTTPException(403,'Destinatário não autorizado.')
        elif typ=='criteria':
            if not isinstance(v,list) or not 1<=len(v)<=20: raise HTTPException(422,'Informe de 1 a 20 critérios.')
            try:
                if len({c['name'].strip() for c in v})!=len(v) or any(not c['name'].strip() or not 0<float(c['weight'])<=100 for c in v): raise ValueError()
                data[f['key']]=[dict(name=c['name'].strip()[:100],weight=float(c['weight'])) for c in v]
            except (KeyError,ValueError,TypeError): raise HTTPException(422,'Critérios precisam de nomes únicos e pesos positivos.')
        elif not isinstance(v,str) or len(v)>10000: raise HTTPException(422,f'{label}: texto inválido ou muito longo.')
    if spec['student']:
        student=lookup(db,user,body.student_id,'alunos')
        if not accessible(db,user,student): raise HTTPException(403,'Aluno fora do seu escopo.')
        body.class_id=student.class_id
    elif body.student_id: raise HTTPException(422,'Este módulo não aceita vínculo com aluno.')
    if spec['classroom']:
        lookup(db,user,body.class_id,'turmas')
        if user.role=='professor' and body.class_id not in allowed_classes(db,user): raise HTTPException(403,'Turma fora do seu escopo.')
    elif not spec['student'] and body.class_id: raise HTTPException(422,'Vínculo de turma não permitido.')
    if data.get('start') and data.get('end') and data['start']>data['end']: raise HTTPException(422,'O fim deve ser posterior ao início.')
    if kind=='alunos':
        if data['birth']>date.today().isoformat(): raise HTTPException(422,'Nascimento não pode estar no futuro.')
        if any(r.id!=(existing.id if existing else None) and r.data['registration']==data['registration'] for r in records(db,user,'alunos')): raise HTTPException(409,'Matrícula já cadastrada.')
    if kind=='avaliacoes-professores' and not 1<=data['score']<=5: raise HTTPException(422,'Nota deve estar entre 1 e 5.')
    if kind=='frequencias':
        lesson=lookup(db,user,data['lesson_id'],'aulas')
        if lesson.class_id!=body.class_id: raise HTTPException(422,'Aula e aluno pertencem a turmas diferentes.')
        if any(r.id!=(existing.id if existing else None) and r.student_id==body.student_id and r.data['lesson_id']==data['lesson_id'] for r in records(db,user,kind)): raise HTTPException(409,'Presença já registrada para esta aula.')
    if kind=='saude' and not existing and any(r.student_id==body.student_id for r in records(db,user,kind)): raise HTTPException(409,'Este aluno já possui ficha. Edite a ficha existente.')
    if kind=='inscricoes':
        others=[r for r in records(db,user,kind) if r.id!=(existing.id if existing else None) and r.data['event_id']==data['event_id']]
        if any(r.student_id==body.student_id for r in others): raise HTTPException(409,'Aluno já inscrito.')
        if len(others)>=lookup(db,user,data['event_id'],'eventos').data['capacity']: raise HTTPException(409,'Não há vagas neste evento.')
    return {'encrypted':fernet.encrypt(json.dumps(data).encode()).decode()} if kind in SENSITIVE else data

@app.get('/api/v1/records/{kind}')
def list_records(kind:str,user=Depends(current_user),db=Depends(get_db)):
    if kind not in CATALOG: raise HTTPException(404)
    require(user,CATALOG[kind]['read'])
    result=[payload(r) for r in records(db,user,kind) if accessible(db,user,r)]
    if kind in SENSITIVE: audit(db,user,'leitura-sensivel',kind);db.commit()
    return result

@app.post('/api/v1/records/{kind}',status_code=201)
def create_record(kind:str,body:RecordBody,user=Depends(current_user),db=Depends(get_db)):
    data=validate_record(db,user,kind,body)
    r=Record(school_id=user.school_id,kind=kind,student_id=body.student_id,class_id=body.class_id,owner_id=user.id,data=data);db.add(r);db.flush();audit(db,user,'criar',kind+':'+r.id);db.commit();return payload(r)

@app.put('/api/v1/records/{kind}/{id}')
def update_record(kind:str,id:str,body:RecordBody,user=Depends(current_user),db=Depends(get_db)):
    r=lookup(db,user,id,kind)
    if not accessible(db,user,r): raise HTTPException(403)
    if kind in {'mensagens','reunioes','consentimentos'} and r.owner_id!=user.id: raise HTTPException(403,'Somente o autor pode alterar este registro.')
    if body.updated_at!=r.updated_at: raise HTTPException(409,'Este registro foi alterado. Atualize antes de salvar.')
    if kind=='modelos' and any(c.data.get('model_id')==id for c in records(db,user,'ciclos')): raise HTTPException(409,'Modelo utilizado em ciclo. Crie um novo modelo para preservar o histórico.')
    r.data=validate_record(db,user,kind,body,r);r.student_id=body.student_id;r.class_id=body.class_id;r.updated_at=now();audit(db,user,'editar',kind+':'+id);db.commit();return payload(r)

@app.delete('/api/v1/records/{kind}/{id}')
def remove_record(kind:str,id:str,user=Depends(current_user),db=Depends(get_db)):
    if kind not in CATALOG: raise HTTPException(404)
    require(user,CATALOG[kind]['write']);r=lookup(db,user,id,kind)
    if not accessible(db,user,r): raise HTTPException(403)
    if user.role!='coordenador' and r.owner_id!=user.id: raise HTTPException(403,'Somente o autor pode remover este registro.')
    for other in db.scalars(select(Record).where(Record.school_id==user.school_id,Record.deleted==False,Record.id!=id)):
        if other.student_id==id or other.class_id==id or any(v==id for k,v in other.data.items() if k.endswith('_id')): raise HTTPException(409,'Registro possui vínculos. Atualize ou encerre os vínculos antes de excluir.')
    if kind=='alunos' and any(id in u.links.get('student_ids',[]) for u in db.scalars(select(User).where(User.school_id==user.school_id))): raise HTTPException(409,'Aluno vinculado a uma conta. Altere a situação para Inativo.')
    r.deleted=True;r.updated_at=now();audit(db,user,'excluir',kind+':'+id);db.commit();return {'ok':True}

class Evaluation(Strict):
    student_id: str
    cycle_id: str
    date: str
    scores: dict[str,float]
    strengths: str = Field(default='',max_length=5000)
    develop: str = Field(default='',max_length=5000)
    request_key: str = Field(min_length=10,max_length=100)

class Batch(Strict):
    evaluations: list[Evaluation] = Field(min_length=1,max_length=200)

class Correction(Strict):
    scores: dict[str,float]
    strengths: str = Field(default='',max_length=5000)
    develop: str = Field(default='',max_length=5000)
    reason: str = Field(min_length=5,max_length=1000)
    updated_at: str

@app.patch('/api/v1/evaluations/{id}')
def correct_evaluation(id:str,body:Correction,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor'});r=lookup(db,user,id,'avaliacoes')
    if not accessible(db,user,r) or (user.role=='professor' and r.owner_id!=user.id): raise HTTPException(403,'Você só pode corrigir suas próprias avaliações.')
    if r.updated_at!=body.updated_at: raise HTTPException(409,'Avaliação alterada por outra pessoa. Atualize a página.')
    criteria=r.data['criteria']
    if set(body.scores)!={c['name'] for c in criteria} or any(not 1<=v<=5 or v*2!=int(v*2) for v in body.scores.values()): raise HTTPException(422,'Informe os critérios originais com notas de 1 a 5 em passos de 0,5.')
    previous={k:v for k,v in r.data.items() if k!='revisions'}
    score=sum(body.scores[c['name']]*c['weight'] for c in criteria)/sum(c['weight'] for c in criteria)
    revisions=[*r.data.get('revisions',[]),{'at':now(),'by':user.id,'reason':body.reason,'previous':previous}]
    r.data={**r.data,'scores':body.scores,'strengths':body.strengths,'develop':body.develop,'score':round(score,3),'revisions':revisions};r.updated_at=now();audit(db,user,'corrigir-avaliacao',id);db.commit();return payload(r)

def save_evaluation(db,user,b):
    existing=db.scalar(select(Record).where(Record.school_id==user.school_id,Record.kind=='avaliacoes',Record.request_key==b.request_key))
    if existing:
        if existing.owner_id!=user.id: raise HTTPException(409,'Identificador já utilizado.')
        return existing
    student=lookup(db,user,b.student_id,'alunos')
    if not accessible(db,user,student): raise HTTPException(403,'Aluno fora das suas turmas.')
    if student.data['status']!='Ativo': raise HTTPException(422,'O aluno precisa estar ativo.')
    cycle=lookup(db,user,b.cycle_id,'ciclos'); model=lookup(db,user,cycle.data['model_id'],'modelos')
    try: day=date.fromisoformat(b.date)
    except ValueError: raise HTTPException(422,'Data inválida.')
    if day>date.today() or not cycle.data['start']<=b.date<=cycle.data['end']: raise HTTPException(422,'A data precisa estar dentro do ciclo e não pode ser futura.')
    criteria=model.data['criteria']
    if set(b.scores)!={c['name'] for c in criteria}: raise HTTPException(422,'Preencha todos os critérios do modelo.')
    if any(not 1<=v<=5 or v*2!=int(v*2) for v in b.scores.values()): raise HTTPException(422,'Notas de 1 a 5, em passos de 0,5.')
    for off in records(db,user,'afastamentos'):
        d=payload(off)
        if off.student_id==b.student_id and d['start']<=b.date<=d['end']: raise HTTPException(422,'Aluno afastado nesta data.')
    score=sum(b.scores[c['name']]*c['weight'] for c in criteria)/sum(c['weight'] for c in criteria)
    r=Record(school_id=user.school_id,kind='avaliacoes',student_id=student.id,class_id=student.class_id,owner_id=user.id,request_key=b.request_key,data=dict(cycle_id=b.cycle_id,date=b.date,scores=b.scores,score=round(score,3),strengths=b.strengths,develop=b.develop,criteria=criteria))
    db.add(r);db.flush();audit(db,user,'avaliar',r.id);return r

@app.post('/api/v1/evaluations',status_code=201)
def evaluations_save(body:Batch,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor'});rows=[save_evaluation(db,user,b) for b in body.evaluations];db.commit();return [payload(r) for r in rows]

@app.get('/api/v1/evaluations')
def evaluations_list(user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor','responsavel','aluno'})
    return [payload(r) for r in records(db,user,'avaliacoes') if accessible(db,user,r)]

def analytics(db,user):
    require(user,{'diretor','coordenador','professor','responsavel','aluno'})
    students=[r for r in records(db,user,'alunos') if accessible(db,user,r) and r.data.get('status')=='Ativo']
    ev=[payload(r) for r in records(db,user,'avaliacoes') if accessible(db,user,r)]
    cycles=records(db,user,'ciclos'); today=date.today().isoformat()
    current=next((r for r in cycles if r.data['start']<=today<=r.data['end']),None)
    cycle=current or next(iter(sorted(cycles,key=lambda r:r.data['end'],reverse=True)),None)
    histories={s.id:sorted([e for e in ev if e['student_id']==s.id],key=lambda e:(e['date'],e['created_at'])) for s in students}
    latest=[h[-1] for h in histories.values() if h]
    excluded={r.student_id for r in records(db,user,'afastamentos') if payload(r)['start']<=today<=payload(r)['end']}
    eligible=[s for s in students if s.id not in excluded]
    evaluated={e['student_id'] for e in ev if cycle and e['cycle_id']==cycle.id}
    pending=[{'id':s.id,'name':s.data['name'],'class_id':s.class_id} for s in eligible if s.id not in evaluated]
    alerts=[]
    resolved={r.data['key'] for r in records(db,user,'alertas-resolvidos')}
    for s in students:
        h=histories[s.id]
        if len(h)<2: continue
        for criterion,v in h[-1]['scores'].items():
            before=h[-2]['scores'].get(criterion)
            if before is None: continue
            typ='Queda' if v-before<=-1 else None
            if len(h)>=3 and criterion in h[-3]['scores'] and v<3 and abs(v-before)<.5 and abs(before-h[-3]['scores'][criterion])<.5: typ='Estagnação'
            key=f'{s.id}:{h[-1]["id"]}:{criterion}'
            if typ and key not in resolved: alerts.append(dict(key=key,student_id=s.id,name=s.data['name'],criterion=criterion,type=typ,from_value=before,to_value=v))
    classes=[]
    for c in records(db,user,'turmas'):
        members=[s for s in students if s.class_id==c.id]
        values=[e for e in latest if e['student_id'] in {s.id for s in members}]
        if not members and user.role not in {'coordenador','diretor'}: continue
        classes.append(dict(id=c.id,name=c.data['name'],students=len(members),evaluated=len([s for s in members if s.id in evaluated]),average=round(sum(e['score'] for e in values)/len(values),2) if values else None))
    result=dict(students=len(students),evaluated=len(evaluated & {s.id for s in eligible}),eligible=len(eligible),average=round(sum(e['score'] for e in latest)/len(latest),2) if latest else None,alerts=alerts,pending=pending,classes=classes,cycle=cycle.data['name'] if cycle else None)
    if user.role=='diretor': result['alerts']=len(alerts);result['pending']=len(pending)
    return result

@app.get('/api/v1/dashboard')
def dashboard(user=Depends(current_user),db=Depends(get_db)):
    if user.role=='admin': return dict(users=len(db.scalars(select(User).where(User.school_id==user.school_id)).all()))
    return analytics(db,user)

class ResolveBody(Strict):
    key: str = Field(max_length=200)

@app.post('/api/v1/alerts/resolve')
def resolve_alert(body:ResolveBody,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor'})
    if body.key not in {a['key'] for a in analytics(db,user)['alerts']}: raise HTTPException(404)
    db.add(Record(school_id=user.school_id,owner_id=user.id,kind='alertas-resolvidos',data={'key':body.key}));audit(db,user,'resolver-alerta',body.key);db.commit();return {'ok':True}

@app.get('/api/v1/evolution/{id}')
def evolution(id:str,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor','responsavel','aluno'});student=lookup(db,user,id,'alunos')
    if not accessible(db,user,student): raise HTTPException(403)
    history=sorted([payload(r) for r in records(db,user,'avaliacoes') if r.student_id==id],key=lambda e:(e['date'],e['created_at']))
    peers=[r for r in records(db,user,'avaliacoes') if r.class_id==student.class_id]
    last_by_student={}
    if history:
        for r in sorted(peers,key=lambda r:(r.data['date'],r.created_at)):
            if r.data['cycle_id']==history[-1]['cycle_id']: last_by_student[r.student_id]=r.data
    values=list(last_by_student.values()); comparison=[]
    if history:
        for criterion,score in history[-1]['scores'].items():
            vals=[v['scores'][criterion] for v in values if criterion in v['scores']]
            comparison.append(dict(criterion=criterion,student=score,group=round(sum(vals)/len(vals),2) if vals else None))
    percentile=round(100*sum(v['score']<=history[-1]['score'] for v in values)/len(values)) if values and history else None
    delta=round(history[-1]['score']-history[0]['score'],2) if history else None
    summary='Ainda não há avaliações registradas.'
    if history:
        average=f'{history[-1]["score"]:.1f}'.replace('.',',')
        variation=f'{delta:+.1f}'.replace('.',',')
        summary=('Foi registrada 1 avaliação.' if len(history)==1 else f'Foram registradas {len(history)} avaliações.')+f' A média atual é {average}. '+(f'A variação desde o primeiro registro é de {variation} ponto(s).' if len(history)>1 else 'Este é o primeiro registro do percurso.')
    return dict(student=payload(student),history=history,comparison=comparison,percentile=percentile if user.role in {'coordenador','professor'} else None,delta=delta,summary=summary)

@app.get('/api/v1/export/csv')
def export_csv(user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor'})
    buf=io.StringIO();writer=csv.writer(buf,delimiter=';');writer.writerow(['Aluno','Data','Critério','Nota','Média'])
    def safe(s):
        s=str(s);return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
    for r in records(db,user,'avaliacoes'):
        if accessible(db,user,r):
            s=lookup(db,user,r.student_id,'alunos')
            for key,value in r.data['scores'].items():writer.writerow([safe(s.data['name']),r.data['date'],safe(key),value,r.data['score']])
    audit(db,user,'exportar','avaliacoes-csv');db.commit()
    return Response('\ufeff'+buf.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="fisicamente.csv"'})

@app.get('/api/v1/reports/{id}/pdf')
def report_pdf(id:str,user=Depends(current_user),db=Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib.pagesizes import A4
    result=evolution(id,user,db);buf=io.BytesIO();styles=getSampleStyleSheet()
    story=[Paragraph('FísicaMente',styles['Title']),Paragraph(escape(result['student']['name']),styles['Heading1']),Paragraph(escape(db.get(School,user.school_id).name),styles['Normal']),Spacer(1,16),Paragraph(escape(result['summary']),styles['Normal'])]
    for e in result['history']:
        story.extend([Spacer(1,18),Paragraph('Avaliação · '+date.fromisoformat(e['date']).strftime('%d/%m/%Y'),styles['Heading2'])])
        rows=[['Critério','Nota']]+[[Paragraph(escape(k),styles['Normal']),str(v).replace('.',',')] for k,v in e['scores'].items()]+[['Média',f'{e["score"]:.1f}'.replace('.',',')]]
        table=Table(rows,colWidths=[360,90],repeatRows=1);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#dddddd')),('PADDING',(0,0),(-1,-1),8)]));story.append(table)
        for label,key in [('Pontos fortes','strengths'),('A desenvolver','develop')]:
            story.append(Paragraph(escape(label+': '+(e[key] or 'Sem observações.')),styles['Normal']))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',9);canvas.drawString(45,25,'FísicaMente · Emitido em '+date.today().strftime('%d/%m/%Y'));canvas.drawRightString(550,25,str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=40,bottomMargin=45).build(story,onFirstPage=footer,onLaterPages=footer)
    audit(db,user,'exportar-pdf',id);db.commit();return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="ficha-aluno.pdf"'})

@app.post('/api/v1/import/students')
async def import_students(file:UploadFile,class_id:str,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','professor'});lookup(db,user,class_id,'turmas')
    content=await file.read(2_000_001)
    if len(content)>2_000_000: raise HTTPException(422,'Arquivo maior que 2 MB.')
    try:
        text=content.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text),delimiter=';');rows=list(reader)
    except (UnicodeError,csv.Error): raise HTTPException(422,'Use CSV UTF-8 separado por ponto e vírgula.')
    if not rows or len(rows)>1000: raise HTTPException(422,'Envie de 1 a 1000 alunos.')
    if not {'nome','matricula','nascimento'}<=set(reader.fieldnames or []): raise HTTPException(422,'Colunas obrigatórias: nome;matricula;nascimento (AAAA-MM-DD).')
    for i,row in enumerate(rows,2):
        body=RecordBody(class_id=class_id,data=dict(name=row['nome'],registration=row['matricula'],birth=row['nascimento'],sex=row.get('sexo') or 'Não informado',status='Ativo'))
        try: data=validate_record(db,user,'alunos',body)
        except HTTPException as exc: raise HTTPException(exc.status_code,f'Linha {i}: {exc.detail}')
        db.add(Record(school_id=user.school_id,owner_id=user.id,kind='alunos',class_id=class_id,data=data));db.flush()
    audit(db,user,'importar-alunos',str(len(rows)));db.commit();return {'count':len(rows)}

@app.get('/api/v1/audit')
def audit_list(user=Depends(current_user),db=Depends(get_db)):
    require(user,{'admin','diretor','coordenador'})
    return [dict(id=r.id,user_id=r.user_id,action=r.action,target=r.target,at=r.at) for r in db.scalars(select(Audit).where(Audit.school_id==user.school_id).order_by(Audit.at.desc()).limit(500))]

class Settings(Strict):
    name: str = Field(min_length=2,max_length=180)
    is_demo: bool | None = None

@app.put('/api/v1/settings')
def settings(body:Settings,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','admin'});school=db.get(School,user.school_id);school.name=body.name
    if body.is_demo is not None: school.settings={**school.settings,'is_demo':body.is_demo}
    audit(db,user,'configurar','escola');db.commit();return {'ok':True}

# Attachments are private, limited in size and served only after school/profile checks.
@app.post('/api/v1/attachments/{student_id}',status_code=201)
async def upload_attachment(student_id:str,file:UploadFile,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador'});lookup(db,user,student_id,'alunos')
    raw=await file.read(5_000_001)
    if len(raw)>5_000_000: raise HTTPException(422,'Limite de 5 MB por arquivo.')
    mime='application/pdf' if raw.startswith(b'%PDF-') else 'image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else None
    if not mime: raise HTTPException(422,'Envie PDF, PNG ou JPEG válido.')
    r=Record(school_id=user.school_id,owner_id=user.id,kind='anexos',student_id=student_id,data=dict(name=(file.filename or 'arquivo')[:180],mime=mime,size=len(raw)));db.add(r);db.flush()
    db.add(AttachmentBlob(id=r.id,encrypted=fernet.encrypt(raw)));audit(db,user,'anexar',r.id);db.commit();return payload(r)

@app.get('/api/v1/attachments/{student_id}')
def attachments(student_id:str,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','responsavel'});s=lookup(db,user,student_id,'alunos')
    if not accessible(db,user,s): raise HTTPException(403)
    return [payload(r) for r in records(db,user,'anexos') if r.student_id==student_id]

@app.get('/api/v1/attachment/{id}/download')
def attachment_download(id:str,user=Depends(current_user),db=Depends(get_db)):
    require(user,{'coordenador','responsavel'});r=lookup(db,user,id,'anexos')
    if not accessible(db,user,r): raise HTTPException(403)
    audit(db,user,'baixar-anexo',id);db.commit()
    blob=db.get(AttachmentBlob,r.id)
    if blob:
        encrypted=blob.encrypted
    elif not SERVERLESS and (DATA/(r.id+'.enc')).is_file():
        encrypted=(DATA/(r.id+'.enc')).read_bytes()
    else:
        raise HTTPException(404,'Conteúdo do anexo não encontrado.')
    return Response(fernet.decrypt(encrypted),media_type=r.data['mime'],headers={'Content-Disposition':'attachment; filename="documento.'+{'application/pdf':'pdf','image/png':'png','image/jpeg':'jpg'}[r.data['mime']]+'"'})
