# Escopo e estado da implementação

## O que está implementado

| Área | Implementação |
| --- | --- |
| Acesso | Cadastro de escola/gestor, confirmação de e-mail, login, logout, recuperação de senha, reenvio de confirmação, convite de uso único e renovação de sessão. |
| Perfis | Admin técnico, diretor, coordenador, professor, responsável e aluno; autorização no servidor e isolamento entre escolas. |
| Cadastros | Anos letivos, séries, turmas, professores vinculados, alunos, responsáveis e importação atômica de CSV UTF-8. |
| Avaliação | Individual e por turma, modelos e pesos, ciclos, notas de 1 a 5 em passos de 0,5, média ponderada, idempotência e correções com versões anteriores preservadas. |
| Evolução | Linha do tempo, radar, histórico por critério, comparação agregada com a turma, percentil de turma/ciclo para equipe pedagógica e resumo textual por regras. |
| Alertas | Queda, estagnação e pendências no painel; resolução manual dos alertas; afastados não entram nas pendências do período. |
| Relatórios | Ficha individual em PDF pelo servidor e exportação CSV protegida contra fórmulas de planilha. |
| Coordenação | Painel por turma/professor, observações de aula e avaliação do professor com devolutiva e metas textuais. |
| Intervenção | Metas individuais, planos, banco de atividades e vínculo de uma atividade ao plano. |
| Aulas | Registro de conteúdo, código BNCC e frequência individual por aula, com bloqueio de duplicidade. |
| Saúde | Fichas, adaptações textuais, afastamentos, autorizações e anexos privados PDF/PNG/JPEG de até 5 MB. Dados sensíveis e arquivos são cifrados. |
| Comunidade | Comunicados da escola, mensagens privadas entre remetente/destinatário, reuniões, acesso dos responsáveis e autoavaliação do aluno. |
| Eventos | Eventos, capacidade de vagas, inscrições, equipe textual e resultado por inscrição. |
| Agendamentos | Resumos institucionais semanais ou a cada 30 dias, por e-mail, para direção/coordenação; envio depende de SMTP e API ativa. |
| Offline | Cache mínimo em IndexedDB por usuário e fila de avaliações com chaves idempotentes. Revisão/descarte da fila e tentativa de sincronização ao reconectar. A interface instalável e recarregamento offline usam o build de produção. |
| Administração | Convites, ativação/desativação de usuários, nome da escola e últimas 500 ações de auditoria. |

Os módulos de cadastro usam um catálogo compartilhado de campos. O servidor valida tipos, opções, referências, permissões e conflitos; a interface gera formulários a partir desse catálogo. As telas ficam vazias quando não há dados, sem números demonstrativos misturados à escola real.

## Permissões principais

- Coordenação: gestão pedagógica e convites da própria escola.
- Professor: alunos e avaliações das turmas em que está vinculado; saúde em leitura; não altera a estrutura de turmas.
- Responsável: apenas alunos vinculados; consulta registros permitidos, registra autorizações e envia mensagens à equipe.
- Aluno: apenas sua ficha, evolução e autoavaliação; sem saúde e sem percentil.
- Diretor: indicadores consolidados, comunicação e auditoria; sem avaliações individuais ou saúde.
- Admin técnico: usuários, configurações e auditoria; sem dados pedagógicos ou saúde.

## Limites desta entrega e evolução para produção

Esta é uma versão funcional local abrangente, **não a conclusão de todas as exigências avançadas da documentação original**. Os seguintes pontos ainda precisam de implementação ou validação antes de declarar o produto completo para produção:

- Publicação em domínio com HTTPS, credenciais SMTP, política de retenção, backups cifrados e teste de restauração.
- MFA, limitação de tentativas distribuída e por e-mail, infraestrutura Redis/ARQ, armazenamento S3 e observabilidade.
- Normalização do banco por domínio, migrações evolutivas independentes dos modelos Python, Row Level Security e paginação no servidor. O catálogo atual carrega as listas completas e atende melhor escolas pequenas em homologação.
- Histórico formal de matrículas/transferências por ano, gestão de redes de escolas, integrações externas e revisão de perfis/vínculos de contas já criadas.
- Tabelas normativas de testes físicos por idade/sexo aprovadas pela escola; resultados atuais registram valores sem classificação normativa automática.
- Critérios com descritores por nível, limites de classificação configuráveis, percentil por série/escola, mapa de calor coletivo e análises de distribuição mais completas.
- Sugestão automática de atividades por critério, metas para turmas/professores, calendário visual, notificações push e comunicação segmentada por série/turma.
- Importação de XLSX (o importador atual é CSV), frequência em lote e relatórios PDF agendados como anexos (o agendamento atual envia resumo textual).
- Offline completo de todos os módulos e sincronização em segundo plano com aplicativo fechado. Atualmente, a fila é de avaliações, depende de sessão válida e sincroniza com a aplicação aberta.
- Exportação completa dos dados do titular, fluxo de exclusão/anonimização e revisão institucional dos textos de privacidade. O texto exibido no cadastro está identificado como inicial.
- Homologação com escola real, testes de carga, revisão completa de acessibilidade e testes automatizados de navegador.

O worker de e-mails/agendamentos roda no processo da API; use uma única instância enquanto não houver fila distribuída. Os envios podem ser repetidos em caso de falha entre envio SMTP e confirmação no banco. A fila offline envia até 200 avaliações por solicitação.

## Verificações executadas

- Compilação TypeScript e build Vite.
- Nove testes de integração cobrindo cadastro/confirmação, revogação de sessão, origem de requisição, isolamento entre escolas, professor/responsável/aluno/diretor/admin, criptografia, idempotência, atomicidade, PDF/CSV, importação, alertas, afastamentos, frequência, eventos, mensagens, anexos e correção de avaliações.
- Migração inicial Alembic sobre SQLite.
- Inspeção visual do cadastro e painel, login da escola de demonstração, gravação de avaliação pelo formulário e confirmação da média/observações no histórico pelo navegador.

Os testes usam banco temporário e não alteram a escola local. A integração contínua está em `.github/workflows/ci.yml`.

