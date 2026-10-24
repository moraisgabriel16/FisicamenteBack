"""Opt-in smoke test against a deployed instance. Creates an isolated fictional school.

Credentials are generated in memory and never printed or saved. Run only with
--write-test-data when explicitly validating your own deployment.
"""
import argparse
import secrets
from datetime import date
from uuid import uuid4
from urllib.parse import parse_qs,urlparse
import httpx

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url',required=True)
    p.add_argument('--write-test-data',action='store_true')
    args=p.parse_args()
    if not args.write_test_data:
        p.error('Confirme a criação de dados fictícios com --write-test-data.')
    origin=args.base_url.rstrip('/')
    email=f'validacao-{uuid4().hex}@example.com'
    password=secrets.token_urlsafe(24)
    headers={'Origin':origin}
    def call(c,method,path,**kwargs):
        r=c.request(method,'/api/v1'+path,**kwargs)
        if not r.is_success:
            raise RuntimeError(f'{method} {path}: HTTP {r.status_code}; {r.text[:250]}')
        return r
    with httpx.Client(base_url=origin,headers=headers,timeout=60) as c:
        assert call(c,'GET','/health').json()['database']=='connected'
        registered=call(c,'POST','/auth/register',json=dict(name='Validação automática',email=email,password=password,school='Escola fictícia · Validação online',accepted_terms=True)).json()
        assert registered['can_login'] is True
        call(c,'POST','/auth/login',json=dict(email=email,password=password))
        assert call(c,'GET','/me').json()['role']=='coordenador'
        model=call(c,'GET','/records/modelos').json()[0]
        year=call(c,'GET','/records/anos').json()[0]
        def record(kind,data,**links):
            return call(c,'POST','/records/'+kind,json={'data':data,**links}).json()
        teacher_email=f'professor-{uuid4().hex}@example.com'
        invitation=call(c,'POST','/invites',json=dict(email=teacher_email,role='professor',student_ids=[])).json()
        token=parse_qs(urlparse(invitation['invite_link']).query)['token'][0]
        call(c,'POST','/auth/accept',json=dict(token=token,name='Professor fictício',password=secrets.token_urlsafe(24)))
        teacher=next(u for u in call(c,'GET','/users').json() if u['email']==teacher_email)
        grade=record('series',dict(name='Série de validação',order=6))
        classroom=record('turmas',dict(name='Turma fictícia',grade_id=grade['id'],year_id=year['id'],shift='Manhã',teacher_ids=[teacher['id']]))
        student=record('alunos',dict(name='Aluno fictício de validação',registration='TEST-'+uuid4().hex[:12],birth='2014-05-20',sex='Não informado',status='Ativo'),class_id=classroom['id'])
        day=date.today().isoformat()
        cycle=record('ciclos',dict(name='Ciclo de validação',model_id=model['id'],year_id=year['id'],type='Diagnóstica',start=day,end=day))
        evaluation=dict(student_id=student['id'],cycle_id=cycle['id'],date=day,scores={v['name']:3.5 for v in model['criteria']},strengths='Dado fictício para validar persistência.',develop='Dado fictício.',request_key=uuid4().hex)
        first=call(c,'POST','/evaluations',json={'evaluations':[evaluation]}).json()[0]
        second=call(c,'POST','/evaluations',json={'evaluations':[evaluation]}).json()[0]
        assert first['id']==second['id']
        call(c,'POST','/auth/logout',json={})
    # Fresh client/session, ensuring persisted records survive independent requests.
    with httpx.Client(base_url=origin,headers=headers,timeout=60) as c:
        call(c,'POST','/auth/login',json=dict(email=email,password=password))
        history=call(c,'GET','/evolution/'+student['id']).json()['history']
        assert len(history)==1 and history[0]['score']==3.5
        assert call(c,'GET','/reports/'+student['id']+'/pdf').content.startswith(b'%PDF')
        assert call(c,'GET','/dashboard').json()['evaluated']==1
        call(c,'POST','/auth/logout',json={})
    print('OK: PostgreSQL, cadastro, login, convite, turma, aluno, avaliação, idempotência, persistência entre sessões e PDF validados no domínio público.')

if __name__=='__main__':
    main()
