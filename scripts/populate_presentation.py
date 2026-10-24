"""Populate an isolated client presentation with fictional records using the public API.

Requires explicit --create-demo. Account credentials and progress stay in a local,
private state file outside the repository. Re-running resumes the same presentation.
No emails are sent and no existing school is modified.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import json
from pathlib import Path
import random
import secrets
from threading import Lock
import time
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
import httpx

SCHOOL='Objetivo Integrado Uberaba'
YEAR=2026
CRITERIA=['Coordenação','Equilíbrio','Força','Lateralidade','Flexibilidade','Participação','Velocidade']
FIRST_F=['Ana Clara','Beatriz','Camila','Clara','Eduarda','Elisa','Fernanda','Gabriela','Helena','Isabela','Júlia','Laura','Letícia','Luísa','Manuela','Maria Eduarda','Mariana','Melissa','Rafaela','Sofia','Valentina','Vitória']
FIRST_M=['Arthur','Bernardo','Caio','Davi','Enzo','Felipe','Gabriel','Gustavo','Heitor','Henrique','João Pedro','Joaquim','Leonardo','Lucas','Matheus','Miguel','Nicolas','Pedro','Rafael','Samuel','Theo','Vicente']
LAST=['Almeida','Andrade','Barbosa','Batista','Cardoso','Carvalho','Castro','Costa','Dias','Duarte','Fernandes','Ferreira','Gomes','Lima','Lopes','Martins','Mendes','Moreira','Nascimento','Oliveira','Pereira','Ribeiro','Rocha','Rodrigues','Santos','Silva','Souza','Teixeira']

class Presentation:
    def __init__(self,origin,state_path):
        self.origin=origin.rstrip('/');self.path=Path(state_path);self.lock=Lock();self.cache={}
        if self.path.exists():
            self.state=json.loads(self.path.read_text(encoding='utf-8'))
            if self.state['origin']!=self.origin: raise RuntimeError('O estado pertence a outro endereço.')
        else:
            suffix=uuid4().hex[:8]
            self.state={'origin':self.origin,'school':SCHOOL,'coordinator':{'name':'Coordenação · Demonstração','email':f'objetivo.uberaba.demo.{suffix}@example.com','password':secrets.token_urlsafe(18)},'accounts':{},'records':{},'evaluations':[]}
        self.path.parent.mkdir(parents=True,exist_ok=True);self.save()
        self.client=httpx.Client(base_url=self.origin+'/api/v1/',headers={'Origin':self.origin},timeout=180)

    def save(self):
        with self.lock:
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(self.path)

    def call(self,method,path,**kwargs):
        response=self.client.request(method,path.lstrip('/'),**kwargs)
        if not response.is_success:
            try: detail=response.json().get('detail','Falha na API')
            except ValueError: detail='Falha temporária de hospedagem'
            raise RuntimeError(f'{method} {path}: HTTP {response.status_code}; {detail}')
        return response.json()

    def login(self):
        owner=self.state['coordinator']
        if not self.state.get('registered'):
            result=self.call('POST','auth/register',json={'name':owner['name'],'email':owner['email'],'password':owner['password'],'school':SCHOOL,'accepted_terms':True})
            if not result.get('can_login'): raise RuntimeError('Esta demonstração exige cadastro imediato habilitado.')
            self.state['registered']=True;self.save()
        self.call('POST','auth/login',json={k:owner[k] for k in ['email','password']})
        self.state['user']=self.call('GET','me');self.save()

    def account(self,key,name,role,student_ids=None):
        if key in self.state['accounts']: return self.state['accounts'][key]
        email=f'{key}.{uuid4().hex[:10]}@example.com';password=secrets.token_urlsafe(18)
        invitation=self.call('POST','invites',json={'email':email,'role':role,'student_ids':student_ids or []})
        token=parse_qs(urlparse(invitation.get('invite_link') or invitation['development_link']).query)['token'][0]
        self.call('POST','auth/accept',json={'token':token,'name':name,'password':password})
        user=next(u for u in self.call('GET','users') if u['email']==email)
        user['password']=password;self.state['accounts'][key]=user;self.save();return user

    def record(self,key,kind,data,**links):
        if key in self.state['records']: return self.state['records'][key]
        with self.lock:
            if kind not in self.cache:
                self.cache[kind]=self.call('GET','records/'+kind)
            existing=next((r for r in self.cache[kind] if all(r.get(k)==v for k,v in data.items()) and all(r.get(k)==v for k,v in links.items())),None)
        row=existing or self.call('POST','records/'+kind,json={'data':data,**links})
        with self.lock:
            self.state['records'][key]=row
            if not existing:self.cache[kind].append(row)
        self.save();return row

    def many(self,jobs,label):
        jobs=[job for job in jobs if job[0] not in self.state['records']]
        if not jobs:return
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(self.record,key,kind,data,**links) for key,kind,data,links in jobs]
            for i,future in enumerate(as_completed(futures),1):
                future.result()
                if i%40==0 or i==len(jobs):print(f'  {label}: {i}/{len(jobs)}',flush=True)

    def run(self):
        self.login();print('1/7 Conta de apresentação e escola preparadas.',flush=True)
        self.call('PUT','settings',json={'name':SCHOOL,'is_demo':True})
        assert self.call('GET','me')['school']['is_demo'] is True
        years=self.call('GET','records/anos');year=next(r for r in years if int(r['year'])==YEAR)
        model=self.call('GET','records/modelos')[0]
        teachers=[self.account('helena','Helena Duarte · Demo','professor'),self.account('rafael','Rafael Martins · Demo','professor'),self.account('camila','Camila Ribeiro · Demo','professor')]
        grades={g:self.record(f'grade-{g}','series',{'name':f'{g}º ano','order':g}) for g in [6,7,8]}
        classes=[]
        for i,(g,letter,n,pending) in enumerate([(6,'A',24,4),(6,'B',24,3),(7,'A',22,4),(7,'B',22,3),(8,'A',20,3),(8,'B',20,3)]):
            row=self.record(f'class-{i}','turmas',{'name':f'{g}º ano {letter}','year_id':year['id'],'grade_id':grades[g]['id'],'shift':'Manhã' if letter=='A' else 'Tarde','teacher_ids':[teachers[i//2]['id']]})
            classes.append({'row':row,'grade':g,'count':n,'pending':pending,'teacher':teachers[i//2],'index':i})
        cycle_specs=[('Diagnóstica · início do ano','Diagnóstica','02-02','03-13','02-26'),('Formativa · 1º semestre','Formativa','04-06','05-15','04-23'),('Formativa · retomada','Formativa','08-03','09-04','08-20'),('Formativa · outubro','Formativa','10-01','11-06','10-21')]
        cycles=[]
        for i,(name,typ,start,end,day) in enumerate(cycle_specs):
            row=self.record(f'cycle-{i}','ciclos',{'name':name,'model_id':model['id'],'year_id':year['id'],'type':typ,'start':f'{YEAR}-{start}','end':f'{YEAR}-{end}'})
            cycles.append((row,f'{YEAR}-{day}'))
        activities=[]
        for i,(name,criterion,description) in enumerate([
            ('Circuito de bases e apoios','Equilíbrio','Alternar apoios em linhas e bases amplas; ajustar a dificuldade ao ritmo de cada aluno.'),
            ('Bola ao alvo em duplas','Coordenação','Lançar e receber bolas leves com distâncias progressivas, registrando estratégias que ajudam.'),
            ('Trilhas de direita e esquerda','Lateralidade','Explorar percursos com comandos laterais, trocando o lado inicial a cada rodada.'),
            ('Desafios com o peso do corpo','Força','Realizar ações curtas de sustentação e deslocamento, com pausas e opções adaptadas.'),
            ('Mobilidade em estações','Flexibilidade','Explorar movimentos confortáveis, sem forçar amplitudes ou provocar dor.'),
            ('Revezamento cooperativo','Velocidade','Percorrer trechos curtos priorizando técnica, segurança e cooperação.'),
            ('Missão de equipe','Participação','Resolver desafios coletivos com rodízio de funções e valorização das contribuições.'),
            ('Jogos de precisão','Coordenação','Experimentar alvos com tamanhos diferentes e compartilhar formas de ajustar o movimento.'),
            ('Equilíbrio com objetos','Equilíbrio','Transportar objetos leves em trajetos simples, com possibilidade de apoio e ajuda entre colegas.')]):
            activities.append(self.record(f'activity-{i}','atividades',{'name':name,'criterion':criterion,'description':description,'minutes':15+i%3*5,'materials':'Cones, bolas leves, arcos e marcações no chão','bncc':''}))
        tests=[]
        for i,(name,unit,best) in enumerate([('Corrida de 20 metros','s','Menor'),('Salto horizontal parado','cm','Maior'),('Alcance sentado','cm','Maior')]):
            tests.append(self.record(f'test-{i}','testes',{'name':name,'unit':unit,'best':best,'reference':'Protocolo ilustrativo da demonstração; valores fictícios, sem classificação normativa.'}))
        print('2/7 Seis turmas, três professores e quatro ciclos organizados.',flush=True)
        pupils=[];jobs=[];counter=0
        for classroom in classes:
            for position in range(classroom['count']):
                female=counter%2==0;names=FIRST_F if female else FIRST_M
                last_one=(counter*11+5)%len(LAST);last_two=(counter*9+17)%len(LAST)
                if last_two==last_one:last_two=(last_two+1)%len(LAST)
                name=f'{names[(counter//2)%len(names)]} {LAST[last_one]} {LAST[last_two]}'
                key=f'student-{counter:03}';data={'name':name,'registration':f'DEMO-{YEAR}-{counter+1:04}','birth':f'{YEAR-classroom["grade"]-5}-{counter%12+1:02}-{counter%24+1:02}','sex':'Feminino' if female else 'Masculino','status':'Ativo'}
                jobs.append((key,'alunos',data,{'class_id':classroom['row']['id']}))
                pupils.append({'key':key,'number':counter,'position':position,'classroom':classroom,'current':position<classroom['count']-classroom['pending']})
                counter+=1
        self.many(jobs,'Alunos')
        for pupil in pupils:pupil['row']=self.state['records'][pupil['key']]
        print(f'3/7 {len(pupils)} alunos fictícios cadastrados.',flush=True)
        rng=random.Random(20261024);evaluations=[]
        for p in pupils:
            base=2.2+(p['number']%7)*.13+rng.uniform(-.18,.18)
            offsets=[rng.uniform(-.35,.35) for _ in CRITERIA]
            p['scores']=[]
            for stage,(cycle,day) in enumerate(cycles):
                scores={name:max(1,min(5,round((base+offsets[k]+[0,.4,.75,1.05][stage])*2)/2)) for k,name in enumerate(CRITERIA)}
                if p['number']%23==4:scores['Equilíbrio']=2.5
                if stage==3 and p['number']%17==0:scores['Equilíbrio']=max(1,p['scores'][2]['Equilíbrio']-1.5)
                p['scores'].append(scores)
                if stage==3 and not p['current']:continue
                strong=max(scores,key=scores.get);weak=min(scores,key=scores.get)
                strengths=[f'Boa disposição para experimentar movimentos. Destacou-se em {strong.lower()} nas atividades propostas.',f'Participa com mais autonomia e colabora com os colegas. Demonstra avanços em {strong.lower()}.',f'Consolidou estratégias nas atividades em grupo e ampliou a confiança. Destaque para {strong.lower()}.',f'Mantém participação consistente e reconhece suas conquistas. Apresentou bons resultados em {strong.lower()}.'][stage]
                develop=f'Ampliar experiências de {weak.lower()} com circuitos curtos e dificuldade progressiva, respeitando o ritmo individual.'
                evaluations.append({'student_id':p['row']['id'],'cycle_id':cycle['id'],'date':day,'scores':scores,'strengths':strengths,'develop':develop,'request_key':f'objetivo-demo-v1-{p["number"]:03}-{stage}'})
        known={(r['student_id'],r['cycle_id'],r['date']) for r in self.call('GET','evaluations')}
        pending=[e for e in evaluations if (e['student_id'],e['cycle_id'],e['date']) not in known]
        for i in range(0,len(pending),48):
            batch=pending[i:i+48]
            self.call('POST','evaluations',json={'evaluations':batch})
            print(f'  Avaliações: {min(i+48,len(pending))}/{len(pending)}',flush=True)
        print(f'4/7 {len(evaluations)} avaliações históricas preparadas.',flush=True)
        jobs=[];lessons=[]
        themes=['Jogos cooperativos e tomada de decisão','Circuito de coordenação e lateralidade','Equilíbrio em diferentes bases de apoio','Jogos de precisão e trabalho em equipe','Revezamentos e deslocamentos','Circuito de desenvolvimento integral']
        days=['09-08','09-15','09-22','09-29','10-13','10-20']
        for cl in classes:
            for i,(theme,day) in enumerate(zip(themes,days)):
                key=f'lesson-{cl["index"]}-{i}'
                jobs.append((key,'aulas',{'name':theme,'date':f'{YEAR}-{day}','content':'Acolhida e aquecimento; estações com opções de dificuldade; desafios em pequenos grupos; fechamento com reflexão sobre participação e estratégias. Registro fictício de demonstração.','bncc':''},{'class_id':cl['row']['id']}))
                lessons.append((key,cl,i))
        self.many(jobs,'Aulas');jobs=[]
        for key,cl,i in lessons:
            if i<3:continue
            lesson=self.state['records'][key]
            for p in pupils:
                if p['classroom']['index']!=cl['index']:continue
                status='Ausente' if (p['number']+i)%19==0 else 'Justificada' if (p['number']+i)%37==0 else 'Presente'
                jobs.append((f'presence-{cl["index"]}-{i}-{p["number"]}','frequencias',{'lesson_id':lesson['id'],'status':status,'notes':'Registro ilustrativo; ausência justificada na demonstração.' if status=='Justificada' else ''},{'student_id':p['row']['id']}))
        self.many(jobs,'Frequências')
        print('5/7 Aulas e frequências preenchidas.',flush=True)
        jobs=[]
        focus=[p for p in pupils if p['current'] and (p['number']%17==0 or p['number']%23==4)][:10]
        for i,p in enumerate(focus):
            activity=activities[0 if i%2==0 else 8];completed=i<2
            jobs.append((f'plan-{i}','planos',{'name':'Percurso de equilíbrio e confiança','criterion':'Equilíbrio','objective':'Ampliar o repertório de apoios e realizar percursos com autonomia e segurança.','activity_id':activity['id'],'start':f'{YEAR}-09-22' if completed else f'{YEAR}-10-22','end':f'{YEAR}-10-16' if completed else f'{YEAR}-11-20','status':'Concluído' if completed else 'Em andamento','notes':'Percurso concluído com maior autonomia; manter os desafios nas aulas.' if completed else 'Realizar duas experiências curtas por semana; observar estratégias, participação e necessidade de apoio. Exemplo fictício para apresentação.'},{'student_id':p['row']['id']}))
            jobs.append((f'goal-{i}','metas',{'name':'Ampliar autonomia nos desafios de equilíbrio','criterion':'Equilíbrio','initial':p['scores'][2]['Equilíbrio'],'target':min(5,p['scores'][2]['Equilíbrio']+.5),'end':f'{YEAR}-11-20','status':'Alcançada' if completed else 'Em andamento'},{'student_id':p['row']['id']}))
        for p in pupils[::7]:
            for t,test in enumerate(tests):
                value=round(5.6-(p['number']%8)*.17,2) if t==0 else 115+(p['number']%12)*5 if t==1 else 18+(p['number']%9)*1.5
                jobs.append((f'physical-{p["number"]}-{t}','resultados',{'test_id':test['id'],'date':f'{YEAR}-10-15','value':value,'notes':'Resultado inteiramente fictício para demonstração; não corresponde a aluno real.'},{'student_id':p['row']['id']}))
        for p in pupils[::6]:
            jobs.append((f'guardian-{p["number"]}','responsaveis',{'name':f'Responsável fictício de {p["row"]["name"].split()[0]}','email':f'responsavel.demo.{p["number"]}@example.com','phone':'','relationship':'Responsável legal (demonstração)'},{'student_id':p['row']['id']}))
        for i,teacher in enumerate(teachers):
            for j in range(2):
                cl=classes[i*2+j]
                jobs.append((f'observation-{i}-{j}','observacoes',{'teacher_id':teacher['id'],'date':f'{YEAR}-10-{8+j*7:02}','notes':'Aula com estações bem organizadas e alternativas de participação. Boa mediação entre os grupos. Como próximo passo, ampliar os registros de devolutiva individual. Observação fictícia.'},{'class_id':cl['row']['id']}))
            jobs.append((f'teacher-review-{i}','avaliacoes-professores',{'teacher_id':teacher['id'],'date':f'{YEAR}-10-19','score':4+i*.25,'feedback':'Planejamento consistente e acolhimento de diferentes ritmos de aprendizagem. Dados ilustrativos para discussão do recurso.','goals':'Concluir a cobertura do ciclo de outubro e documentar as adaptações das estações.'},{}))
            jobs.append((f'message-{i}','mensagens',{'recipient_id':teacher['id'],'name':'Acompanhamento do ciclo de outubro','body':'Vamos revisar as avaliações pendentes e os planos de equilíbrio na próxima reunião pedagógica. Mensagem de demonstração registrada apenas dentro do sistema.'},{}))
            jobs.append((f'meeting-{i}','reunioes',{'recipient_id':teacher['id'],'name':f'Devolutivas e próximos passos · {6+i}º ano','date':f'{YEAR}-10-{27+i:02}T14:00','location':'Sala de coordenação (demonstração)','status':'Agendada','notes':'Cobertura das avaliações; evolução dos alunos; ajustes nos planos; organização do festival. Reunião fictícia.'},{}))
        self.many(jobs,'Acompanhamentos')
        event=self.record('event-festival','eventos',{'name':'Festival de jogos cooperativos','date':f'{YEAR}-11-13','location':'Quadra e pátio · Objetivo Integrado Uberaba','description':'Evento fictício de demonstração, com estações coletivas, desafios motores e participação das turmas do 6º ao 8º ano.','capacity':180})
        self.record('event-internal','eventos',{'name':'Circuito interturmas de primavera','date':f'{YEAR}-09-25','location':'Quadra da escola','description':'Evento fictício já realizado, com foco em participação e cooperação.','capacity':150})
        jobs=[]
        for p in pupils[::5]:jobs.append((f'event-registration-{p["number"]}','inscricoes',{'event_id':event['id'],'team':['Laranja','Azul','Verde'][p['number']%3],'result':''},{'student_id':p['row']['id']}))
        for i,(title,day,body) in enumerate([
            ('Apresentação do ambiente de demonstração','10-01','Este ambiente foi preparado para apresentar o FísicaMente à Objetivo Integrado Uberaba. Todos os alunos, profissionais, avaliações, eventos e acompanhamentos foram simulados; não representam registros reais da instituição.'),
            ('Ciclo de outubro em andamento','10-05','Estamos acompanhando o desenvolvimento em sete critérios. A equipe pode consultar a evolução individual e priorizar as avaliações pendentes.'),
            ('Devolutivas e planos de acompanhamento','10-19','As devolutivas valorizam conquistas, contexto e próximos passos. Consulte os exemplos de planos individuais e metas registrados nesta demonstração.'),
            ('Festival de jogos cooperativos','10-23','O festival demonstrativo está previsto para novembro. A lista de inscrições ilustra a organização das equipes e o acompanhamento da participação.')]):
            jobs.append((f'announcement-{i}','comunicados',{'name':title,'date':f'{YEAR}-{day}','body':body},{}))
        self.many(jobs,'Comunicação e eventos')
        print('6/7 Planos, metas, testes, professores, comunicados e eventos preenchidos.',flush=True)
        board=self.call('GET','dashboard')
        all_evaluations=self.call('GET','evaluations')
        assert board['students']==132 and len(all_evaluations)==508,(board['students'],len(all_evaluations))
        assert board['evaluated']==112 and len(board['pending'])==20
        sample=pupils[3]['row']
        history=self.call('GET','evolution/'+sample['id'])
        assert len(history['history'])==4
        pdf=self.client.get('reports/'+sample['id']+'/pdf');pdf.raise_for_status();assert pdf.content.startswith(b'%PDF')
        self.state['summary']={'school':SCHOOL,'classes':len(classes),'students':len(pupils),'teachers':len(teachers),'cycles':len(cycles),'evaluations':len(all_evaluations),'current_evaluated':board['evaluated'],'pending':len(board['pending']),'alerts':len(board['alerts']),'average':board['average'],'sample_student_id':sample['id'],'records':{k:sum(r['kind']==k for r in self.state['records'].values()) for k in sorted({r['kind'] for r in self.state['records'].values()})}}
        self.save()
        access=self.path.with_name('Acesso-demonstracao-Objetivo.md')
        owner=self.state['coordinator']
        access.write_text(f'# Acesso privado à apresentação\n\nEscola: {SCHOOL}\n\nEndereço: {self.origin}\n\nE-mail: `{owner["email"]}`\n\nSenha: `{owner["password"]}`\n\nTodos os dados são fictícios. Esta conta é destinada à apresentação e não contém registros reais da instituição. Não publique este arquivo no GitHub.\n',encoding='utf-8')
        print('7/7 Demonstração validada. '+json.dumps(self.state['summary'],ensure_ascii=False),flush=True)
        print('Acesso privado salvo no mesmo diretório do arquivo de estado.',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--state-file',required=True);parser.add_argument('--create-demo',action='store_true')
    args=parser.parse_args()
    if not args.create_demo:parser.error('Use --create-demo para autorizar o preenchimento fictício.')
    if date.today()<date(YEAR,10,21):parser.error('Este roteiro contém avaliações até 21/10/2026.')
    presentation=Presentation(args.base_url,args.state_file)
    try:presentation.run()
    finally:presentation.client.close()

if __name__=='__main__':main()
