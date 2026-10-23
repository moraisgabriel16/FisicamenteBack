import os
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.mkdtemp())/'test.db')
os.environ['APP_URL']='http://testserver'
from fastapi.testclient import TestClient
import pytest
from backend.app.main import app, attempts
from backend.app.db import Session, Record

@pytest.fixture
def client():
    attempts.clear()
    with TestClient(app) as c:
        yield c

def register(c):
    email=f'{uuid4()}@example.com'
    response=c.post('/api/v1/auth/register',json={'name':'Gestora Escola','email':email,'password':'SenhaSegura123!','school':'Escola Teste','accepted_terms':True})
    assert response.status_code==201,response.text
    token=parse_qs(urlparse(response.json()['development_link']).query)['token'][0]
    assert c.post('/api/v1/auth/verify',json={'token':token}).status_code==200
    assert c.post('/api/v1/auth/verify',json={'token':token}).status_code==400
    assert c.post('/api/v1/auth/login',json={'email':email,'password':'SenhaSegura123!'}).status_code==200
    return c.get('/api/v1/me').json()

def create(c,kind,data,**links):
    response=c.post('/api/v1/records/'+kind,json={'data':data,**links})
    assert response.status_code==201,response.text
    return response.json()

def setup_school(c):
    user=register(c)
    year=c.get('/api/v1/records/anos').json()[0]
    model=c.get('/api/v1/records/modelos').json()[0]
    grade=create(c,'series',{'name':'6º ano','order':6})
    teacher=invite(c,'professor')
    classroom=create(c,'turmas',{'name':'6º A','grade_id':grade['id'],'year_id':year['id'],'shift':'Manhã','teacher_ids':[teacher['id']]})
    student=create(c,'alunos',{'name':'Ana Silva','registration':uuid4().hex,'birth':'2014-05-20','sex':'Feminino','status':'Ativo'},class_id=classroom['id'])
    cycle=create(c,'ciclos',{'name':'Diagnóstico','model_id':model['id'],'year_id':year['id'],'type':'Diagnóstica','start':f'{date.today().year}-01-01','end':f'{date.today().year}-12-31'})
    return user,teacher,classroom,student,cycle,model

def invite(c,role,students=[]):
    email=f'{uuid4()}@example.com'
    r=c.post('/api/v1/invites',json={'email':email,'role':role,'student_ids':students})
    assert r.status_code==201,r.text
    token=parse_qs(urlparse(r.json()['development_link']).query)['token'][0]
    r=c.post('/api/v1/auth/accept',json={'token':token,'name':'Pessoa '+role,'password':'SenhaSegura123!'})
    assert r.status_code==200,r.text
    u=next(u for u in c.get('/api/v1/users').json() if u['email']==email)
    return u

def login(c,user):
    r=c.post('/api/v1/auth/login',json={'email':user['email'],'password':'SenhaSegura123!'})
    assert r.status_code==200,r.text

def evaluation(student,cycle,model,score=3):
    return dict(student_id=student['id'],cycle_id=cycle['id'],date=date.today().isoformat(),scores={c['name']:score for c in model['criteria']},strengths='Participou bem',develop='Equilíbrio',request_key=uuid4().hex)

def test_registration_auth_csrf_and_revoke(client):
    u=register(client)
    assert u['role']=='coordenador'
    assert client.post('/api/v1/settings',json={'name':'Outra escola'},headers={'origin':'https://evil.example'}).status_code==403
    cookie=client.cookies.get('fm_session')
    assert 'SenhaSegura' not in cookie
    assert client.post('/api/v1/auth/logout').status_code==200
    client.cookies.set('fm_session',cookie,path='/api')
    assert client.get('/api/v1/me').status_code==401

def test_evaluations_atomic_idempotent_and_report(client):
    _,_,_,s,c,m=setup_school(client)
    ev=evaluation(s,c,m,3.5)
    r=client.post('/api/v1/evaluations',json={'evaluations':[ev]})
    assert r.status_code==201,r.text
    assert r.json()[0]['score']==3.5
    again=client.post('/api/v1/evaluations',json={'evaluations':[ev]})
    assert again.json()[0]['id']==r.json()[0]['id']
    bad=evaluation(s,c,m,5.5)
    good=evaluation(s,c,m,4)
    assert client.post('/api/v1/evaluations',json={'evaluations':[good,bad]}).status_code==422
    assert len(client.get('/api/v1/evaluations').json())==1
    pdf=client.get('/api/v1/reports/'+s['id']+'/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    assert 'Ana Silva' in client.get('/api/v1/export/csv').text
    assert client.get('/api/v1/dashboard').json()['evaluated']==1

def test_cross_school_access_is_blocked(client):
    _,_,_,s,c,m=setup_school(client)
    ev=evaluation(s,c,m)
    register(client)
    assert client.get('/api/v1/evolution/'+s['id']).status_code==404
    assert client.post('/api/v1/evaluations',json={'evaluations':[ev]}).status_code==404
    assert client.get('/api/v1/records/alunos').json()==[]

def test_teacher_scope_and_guardian_links(client):
    owner,teacher,cl,s,c,m=setup_school(client)
    guardian=invite(client,'responsavel',[s['id']])
    other_teacher=invite(client,'professor')
    login(client,other_teacher)
    assert client.get('/api/v1/records/alunos').json()==[]
    assert client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m)]}).status_code==403
    login(client,teacher)
    assert len(client.get('/api/v1/records/alunos').json())==1
    assert client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m)]}).status_code==201
    login(client,guardian)
    assert len(client.get('/api/v1/records/alunos').json())==1
    assert client.get('/api/v1/evolution/'+s['id']).status_code==200
    assert client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m)]}).status_code==403
    assert client.get('/api/v1/users').json()
    assert all('email' not in u for u in client.get('/api/v1/users').json())

def test_sensitive_encryption_and_director_aggregates(client):
    owner,teacher,cl,s,c,m=setup_school(client)
    health=create(client,'saude',{'restrictions':'Informação privada','allergies':'','medication':'','adaptations':'','notes':''},student_id=s['id'])
    with Session() as db:
        stored=db.get(Record,health['id'])
        assert 'encrypted' in stored.data and 'Informação privada' not in str(stored.data)
    director=invite(client,'diretor')
    admin=invite(client,'admin')
    login(client,director)
    assert client.get('/api/v1/records/saude').status_code==403
    assert client.get('/api/v1/evaluations').status_code==403
    assert isinstance(client.get('/api/v1/dashboard').json()['pending'],int)
    login(client,admin)
    assert client.get('/api/v1/records/saude').status_code==403
    assert client.get('/api/v1/records/alunos').status_code==403

def test_validation_conflicts_and_import_rollback(client):
    owner,teacher,cl,s,c,m=setup_school(client)
    old={k:s[k] for k in ['name','registration','birth','sex','status']}
    body={'data':{**old,'name':'Ana Atualizada'},'class_id':cl['id'],'updated_at':s['updated_at']}
    assert client.put('/api/v1/records/alunos/'+s['id'],json=body).status_code==200
    assert client.put('/api/v1/records/alunos/'+s['id'],json=body).status_code==409
    assert client.delete('/api/v1/records/turmas/'+cl['id']).status_code==409
    csv='nome;matricula;nascimento\nBom;nova;2014-01-01\nRuim;outra;2030-01-01'
    r=client.post('/api/v1/import/students?class_id='+cl['id'],files={'file':('alunos.csv',csv.encode(),'text/csv')})
    assert r.status_code==422,r.text
    assert len(client.get('/api/v1/records/alunos').json())==1

def test_alerts_and_absence(client):
    _,_,_,s,c,m=setup_school(client)
    for score in [4,2.5]:
        assert client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m,score)]}).status_code==201
    alerts=client.get('/api/v1/dashboard').json()['alerts']
    assert len(alerts)==7
    assert client.post('/api/v1/alerts/resolve',json={'key':alerts[0]['key']}).status_code==200
    assert len(client.get('/api/v1/dashboard').json()['alerts'])==6
    create(client,'afastamentos',{'start':date.today().isoformat(),'end':date.today().isoformat(),'reason':'Afastamento temporário'},student_id=s['id'])
    assert client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m)]}).status_code==422
    assert client.get('/api/v1/dashboard').json()['eligible']==0

def test_all_operational_modules_and_private_messages(client):
    owner,teacher,cl,s,c,m=setup_school(client)
    guardian=invite(client,'responsavel',[s['id']])
    student_user=invite(client,'aluno',[s['id']])
    day=date.today().isoformat()
    test=create(client,'testes',dict(name='Corrida',unit='segundos',best='Menor',reference='Protocolo da escola'))
    create(client,'resultados',dict(test_id=test['id'],date=day,value=12.5,notes='Registro de teste'),student_id=s['id'])
    activity=create(client,'atividades',dict(name='Jogo',criterion='Participação',description='Jogo cooperativo',minutes=15,materials='',bncc=''))
    plan=create(client,'planos',dict(name='Acompanhar equilíbrio',criterion='Equilíbrio',objective='Ampliar experiências',activity_id=activity['id'],start=day,end=day,status='Em andamento',notes=''),student_id=s['id'])
    create(client,'metas',dict(name='Melhorar equilíbrio',criterion='Equilíbrio',initial=2,target=3,end=day,status='Em andamento'),student_id=s['id'])
    lesson=create(client,'aulas',dict(name='Jogos',date=day,content='Atividades cooperativas',bncc=''),class_id=cl['id'])
    frequency=dict(lesson_id=lesson['id'],status='Presente',notes='')
    create(client,'frequencias',frequency,student_id=s['id'])
    assert client.post('/api/v1/records/frequencias',json={'data':frequency,'student_id':s['id']}).status_code==409
    create(client,'observacoes',dict(teacher_id=teacher['id'],date=day,notes='Boa participação'),class_id=cl['id'])
    create(client,'avaliacoes-professores',dict(teacher_id=teacher['id'],date=day,score=4,feedback='Bom acompanhamento',goals='Expandir atividades'))
    create(client,'comunicados',dict(name='Bem-vindos',body='Mensagem da escola',date=day))
    message=create(client,'mensagens',dict(recipient_id=guardian['id'],name='Reunião',body='Vamos acompanhar o percurso'))
    create(client,'reunioes',dict(recipient_id=guardian['id'],name='Acompanhamento',date=day+'T10:00',location='Escola',status='Agendada',notes=''))
    event=create(client,'eventos',dict(name='Festival',date=day,location='Quadra',description='',capacity=1))
    create(client,'inscricoes',dict(event_id=event['id'],team='Azul',result=''),student_id=s['id'])
    create(client,'agendamentos',dict(name='Resumo',recipient_id=owner['id'],frequency='Semanal',next_date=day))
    upload=client.post('/api/v1/attachments/'+s['id'],files={'file':('atestado.pdf',b'%PDF-1.4\ntest','application/pdf')})
    assert upload.status_code==201,upload.text
    login(client,teacher)
    assert client.get('/api/v1/records/mensagens').json()==[]
    assert client.get('/api/v1/attachments/'+s['id']).status_code==403
    login(client,guardian)
    assert client.get('/api/v1/records/mensagens').json()[0]['id']==message['id']
    assert client.get('/api/v1/attachment/'+upload.json()['id']+'/download').status_code==200
    assert client.get('/api/v1/records/planos').json()[0]['id']==plan['id']
    create(client,'consentimentos',dict(purpose='Participação em evento',status='Concedido',notes='Autorização'),student_id=s['id'])
    login(client,student_user)
    create(client,'autoavaliacoes',dict(date=day,feeling='Estou aprendendo',strengths='Jogos em grupo',goal='Participar mais'),student_id=s['id'])
    assert client.get('/api/v1/records/saude').status_code==403

def test_correction_preserves_previous_and_rejects_stale(client):
    _,_,_,s,c,m=setup_school(client)
    row=client.post('/api/v1/evaluations',json={'evaluations':[evaluation(s,c,m,3)]}).json()[0]
    body=dict(scores={k:4 for k in row['scores']},strengths='Correção',develop='',reason='Correção de lançamento',updated_at=row['updated_at'])
    result=client.patch('/api/v1/evaluations/'+row['id'],json=body)
    assert result.status_code==200,result.text
    assert result.json()['score']==4
    assert result.json()['revisions'][0]['previous']['score']==3
    assert client.patch('/api/v1/evaluations/'+row['id'],json=body).status_code==409
