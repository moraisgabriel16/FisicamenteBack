# Revisão funcional — FísicaMente

Data: 24/10/2026. Ambiente: https://fisicamente-sigma.vercel.app/.
Escola de demonstração: Objetivo Integrado Uberaba, somente dados fictícios.

## Resultado e alcance

As 35 opções visíveis para a coordenação foram percorridas no navegador. Os 24 formulários de criação disponíveis abriram corretamente. Foram consultados os 25 módulos de registros na API publicada, além de sessão, usuários, painel, avaliações, auditoria, evolução, documentos, CSV e PDF. Todos responderam com sucesso. O PDF foi validado pelo conteúdo, e não apenas pelo status HTTP.

As contas dos três professores foram verificadas pela API: 48, 44 e 40 alunos, respectivamente; tentativas de consultar evolução de alunos de outras turmas foram bloqueadas com 403. A suíte de integração usa banco temporário, sem alterar a escola de apresentação.

Esta revisão cobre navegação, abertura de formulários, leitura online, relatórios, permissões e os fluxos de gravação cobertos pelos testes. Não representa homologação de carga, de todos os dispositivos ou de todas as combinações de campos.

## Opções percorridas

| Opção | Resultado / observação |
| --- | --- |
| Visão geral | Indicadores, gráficos e pendências carregados: 132 alunos, 112 avaliados e 12 alertas. |
| Avaliar alunos | Seleção individual e por turma disponível; gravação, limites, atomicidade e idempotência cobertos pela integração. |
| Evolução | Histórico, critérios, radar e resumo consultados para aluno demonstrativo. |
| Atenção pedagógica | 12 alertas carregados; resolução coberta pela integração. |
| Relatórios | Histórico individual e PDF online disponíveis. |
| Alunos | 132 registros; formulário e importador CSV disponíveis. Importação e rollback cobertos pela integração. |
| Turmas | 6 turmas; vínculos com ano, série e professores. |
| Responsáveis | 22 contatos demonstrativos. Contato cadastrado não cria uma conta de acesso; para isso é necessário convite com vínculo ao aluno. |
| Professores | 3 professores; turmas, alunos e médias carregados. |
| Anos letivos | Ano de 2026 e formulário disponíveis. |
| Séries | 6º, 7º e 8º anos cadastrados. |
| Modelos de avaliação | Modelo com critérios/pesos disponível; modelo em uso agora abre somente para consulta, com explicação. |
| Ciclos | 4 ciclos demonstrativos cadastrados. |
| Aulas | 36 aulas; formulário e vínculos disponíveis. |
| Frequência | 396 registros; seleção de aula agora limitada à turma do aluno, com data visível. |
| Testes físicos | 3 protocolos cadastrados. |
| Resultados físicos | 57 registros; ainda sem classificação normativa automática. |
| Metas | 10 metas individuais. |
| Intervenções | 10 planos com acompanhamento e vínculo de atividade. |
| Atividades | 12 atividades; formulário e consulta disponíveis. |
| Observações de aula | 6 registros de observação. |
| Avaliar professores | 3 avaliações demonstrativas com devolutivas. |
| Autoavaliação | Módulo em leitura para coordenação; gravação pelo perfil aluno coberta pela integração. Ainda sem dados de apresentação. |
| Saúde e inclusão | Formulário disponível; criptografia e escopo cobertos pela integração. Sem dados médicos demonstrativos. |
| Afastamentos | Formulário disponível; bloqueio de avaliações em afastamento coberto pela integração. Sem dados demonstrativos. |
| Autorizações | Formulário disponível; registro pelo responsável coberto pela integração. Sem autorizações demonstrativas. |
| Documentos e atestados | Seleção de aluno disponível; upload, criptografia, persistência e download cobertos pela integração. Sem documentos demonstrativos. |
| Comunicados | 4 comunicados carregados. |
| Mensagens | 3 conversas internas; privacidade remetente/destinatário coberta pela integração. |
| Reuniões | 3 reuniões; listagem agora mostra data e horário. |
| Eventos esportivos | 2 eventos; capacidade de vagas validada no servidor. |
| Inscrições | 27 inscrições; duplicidade coberta pela integração. |
| Usuários e convites | Contas e formulário de convite disponíveis; convite por link enquanto o envio de e-mail não está configurado. |
| Histórico de ações | Últimas ações carregadas. |
| Configurações | Identidade da escola e CSV disponíveis para a coordenação; exportação pedagógica removida da tela do administrador técnico. |

## Correções desta revisão

- Sincronização offline em lotes de até 200 avaliações. Lotes confirmados são removidos separadamente; falhas preservam o restante e as chaves idempotentes. Alterações locais da fila são serializadas.
- A fila em memória é reiniciada ao trocar a sessão, evitando reaproveitar a referência de outro usuário.
- Ações de exclusão respeitam a autoria exigida pela API.
- Destinatários e usuários selecionáveis respeitam perfil, atividade da conta e restrições do módulo.
- Frequência oferece somente aulas da turma do aluno e limpa a aula quando o aluno é trocado.
- Modelos já utilizados são apresentados para consulta; alterações exigem novo modelo.
- Reuniões exibem horário na listagem.
- Telas vazias em leitura não convidam a criar registros sem permissão.
- Administrador técnico não recebe botão de exportação de avaliações.

## O que ainda falta

### Para operação com pessoas reais

1. Configurar entrega de e-mail e um executor compatível com a hospedagem para confirmação, recuperação de senha e envio automático de convites. O cadastro imediato continua conforme a escolha do proprietário; convites por link funcionam.
2. Ativar um executor de tarefas para os relatórios agendados. O módulo está oculto na Vercel, evitando oferecer um envio que não será executado.
3. Homologar backup/restauração, retenção, textos institucionais de privacidade e procedimentos de atendimento com a escola. A interface ainda apresenta os termos como versão inicial.
4. Homologar uso em celulares/tablets, acessibilidade e carga com o volume esperado. Hoje as listas são carregadas integralmente, sem paginação no servidor.

### Evoluções ainda não implementadas

- Importação XLSX e frequência em lote; atualmente CSV e frequência individual.
- Calendário visual, notificações push e comunicação segmentada por turma/série.
- Classificação normativa automática dos testes físicos e descritores por nível dos critérios.
- Metas de turma, sugestões automáticas de atividades e análises coletivas mais completas.
- Edição de perfil/vínculos de contas existentes, histórico formal de transferências, gestão de redes e integrações externas.
- Offline de todos os módulos e sincronização com o aplicativo fechado. O offline atual é de avaliações, com a aplicação aberta.

## Validação

- 11 testes de integração do backend passaram na raiz do repositório correto.
- 4 testes da fila offline passaram: 450 avaliações, falha parcial e retomada, inclusão durante envio e falha ao persistir confirmação.
- TypeScript e build de produção passaram.
- Verificação online de 25 módulos e 9 endpoints auxiliares passou.
- Versão publicada conferida no navegador: horários das reuniões, modelo em consulta, 6 aulas filtradas por aluno, edição de atividade salva sem mudança de conteúdo, 7 critérios individuais e 168 campos para a turma de 24 alunos. Nenhum erro no console durante essa conferência.
- Dados de apresentação preservados: 6 turmas, 132 alunos e 508 avaliações.
