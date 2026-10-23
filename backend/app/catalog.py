"""Shared form catalogue. The API validates this schema; the client renders it."""
def field(key, label, type='text', required=False, options=None):
    return dict(key=key, label=label, type=type, required=required, options=options)

def module(title, singular, fields, read, write, student=False, classroom=False):
    return dict(title=title, singular=singular, fields=fields, read=read.split(), write=write.split(), student=student, classroom=classroom)

C = 'coordenador'
P = 'coordenador professor'
ALL = 'coordenador professor responsavel aluno'
date = lambda k, l, required=True: field(k,l,'date',required)
text = lambda k,l,required=True: field(k,l,'text',required)
area = lambda k,l,required=False: field(k,l,'textarea',required)
number = lambda k,l,required=True: field(k,l,'number',required)
select = lambda k,l,opts,required=True: field(k,l,'select',required,opts)
CRITERIA = ['Coordenação','Equilíbrio','Força','Lateralidade','Flexibilidade','Participação','Velocidade']
CATALOG = {
 'anos': module('Anos letivos','Ano letivo',[number('year','Ano'), date('start','Início'),date('end','Fim')],P,C),
 'series': module('Séries','Série',[text('name','Nome'),number('order','Ordem')],P,C),
 'turmas': module('Turmas','Turma',[text('name','Nome'),field('year_id','Ano letivo','ref:anos',True),field('grade_id','Série','ref:series',True),select('shift','Turno',['Manhã','Tarde','Integral','Noite']),field('teacher_ids','Professores','users:professor',True)],P,C),
 'alunos': module('Alunos','Aluno',[text('name','Nome completo'),text('registration','Matrícula'),date('birth','Nascimento'),select('sex','Sexo',['Não informado','Feminino','Masculino']),select('status','Situação',['Ativo','Transferido','Inativo'])],ALL,P,classroom=True),
 'responsaveis': module('Responsáveis','Responsável',[text('name','Nome'),field('email','E-mail','email',True),text('phone','Telefone',False),text('relationship','Parentesco')],P,C,student=True),
 'modelos': module('Modelos de avaliação','Modelo',[text('name','Nome'),field('criteria','Critérios e pesos','criteria',True)],P,C),
 'ciclos': module('Ciclos de avaliação','Ciclo',[text('name','Nome'),field('model_id','Modelo','ref:modelos',True),field('year_id','Ano letivo','ref:anos',True),select('type','Tipo',['Diagnóstica','Formativa','Final']),date('start','Início'),date('end','Prazo final')],P,C),
 'testes': module('Testes físicos','Teste',[text('name','Nome'),text('unit','Unidade'),select('best','Melhor resultado',['Maior','Menor']),area('reference','Fonte / protocolo adotado')],P,C),
 'resultados': module('Resultados físicos','Resultado',[field('test_id','Teste','ref:testes',True),date('date','Data'),number('value','Resultado'),area('notes','Observações')],ALL,P,student=True),
 'atividades': module('Banco de atividades','Atividade',[text('name','Título'),text('criterion','Critério trabalhado'),area('description','Como realizar',True),number('minutes','Duração (minutos)'),text('materials','Materiais',False),text('bncc','Código BNCC',False)],P,P),
 'planos': module('Planos de intervenção','Plano',[text('name','Título'),text('criterion','Critério'),area('objective','Objetivo',True),field('activity_id','Atividade sugerida','ref:atividades'),date('start','Início'),date('end','Prazo'),select('status','Situação',['Em andamento','Concluído','Cancelado']),area('notes','Acompanhamento')],'coordenador professor responsavel',P,student=True),
 'metas': module('Metas','Meta',[text('name','Objetivo'),text('criterion','Critério'),number('initial','Valor inicial'),number('target','Valor esperado'),date('end','Prazo'),select('status','Situação',['Em andamento','Alcançada','Replanejar'])],ALL,P,student=True),
 'aulas': module('Aulas','Aula',[text('name','Tema'),date('date','Data'),area('content','Conteúdo e atividades',True),text('bncc','Habilidade BNCC',False)],P,P,classroom=True),
 'frequencias': module('Frequência','Registro de frequência',[field('lesson_id','Aula','ref:aulas',True),select('status','Presença',['Presente','Ausente','Justificada']),area('notes','Justificativa')],ALL,P,student=True),
 'saude': module('Saúde e inclusão','Ficha de saúde',[area('restrictions','Restrições'),area('allergies','Alergias'),area('medication','Medicação'),area('adaptations','Adaptações pedagógicas'),area('notes','Observações')],'coordenador professor responsavel',C,student=True),
 'afastamentos': module('Afastamentos','Afastamento',[date('start','Início'),date('end','Fim'),area('reason','Motivo',True)],'coordenador professor responsavel',C,student=True),
 'consentimentos': module('Autorizações','Autorização',[select('purpose','Finalidade',['Uso de imagem','Dados de saúde','Participação em evento']),select('status','Decisão',['Concedido','Revogado']),area('notes','Registro da autorização')],'coordenador responsavel','coordenador responsavel',student=True),
 'observacoes': module('Observações de aula','Observação',[field('teacher_id','Professor','user:professor',True),date('date','Data'),area('notes','Observação e devolutiva',True)],C,C,classroom=True),
 'avaliacoes-professores': module('Avaliação de professores','Avaliação do professor',[field('teacher_id','Professor','user:professor',True),date('date','Data'),number('score','Nota (1 a 5)'),area('feedback','Devolutiva',True),area('goals','Metas')],C,C),
 'comunicados': module('Comunicados','Comunicado',[text('name','Título'),area('body','Mensagem',True),date('date','Data de publicação')],'diretor coordenador professor responsavel aluno','diretor coordenador professor'),
 'mensagens': module('Mensagens','Mensagem',[field('recipient_id','Destinatário','user:all',True),text('name','Assunto'),area('body','Mensagem',True)],'diretor coordenador professor responsavel','diretor coordenador professor responsavel'),
 'reunioes': module('Reuniões','Reunião',[text('name','Assunto'),field('recipient_id','Participante','user:all',True),field('date','Data e horário','datetime-local',True),text('location','Local ou link'),select('status','Situação',['Agendada','Realizada','Cancelada']),area('notes','Pauta')],'diretor coordenador professor responsavel','diretor coordenador professor'),
 'autoavaliacoes': module('Autoavaliações','Autoavaliação',[date('date','Data'),select('feeling','Como foi sua participação?',['Preciso de ajuda','Estou aprendendo','Consegui participar bem']),area('strengths','O que você aprendeu?',True),area('goal','O que quer melhorar?')],'coordenador professor aluno','aluno',student=True),
 'eventos': module('Eventos esportivos','Evento',[text('name','Nome'),date('date','Data'),text('location','Local'),area('description','Descrição'),number('capacity','Vagas')],'diretor coordenador professor responsavel aluno',P),
 'inscricoes': module('Inscrições','Inscrição',[field('event_id','Evento','ref:eventos',True),text('team','Equipe',False),text('result','Resultado',False)],ALL,P,student=True),
 'agendamentos': module('Relatórios agendados','Agendamento',[text('name','Nome'),field('recipient_id','Destinatário interno','user:all',True),select('frequency','Frequência',['Semanal','Mensal']),date('next_date','Próximo envio')],'diretor coordenador','diretor coordenador'),
}
