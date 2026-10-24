# Roteiro de apresentação · Objetivo Integrado Uberaba

Ambiente demonstrativo com pessoas, resultados e acompanhamentos fictícios. Não contém registros reais da instituição.

## Conteúdo preparado

- 6 turmas: 6º, 7º e 8º anos, A e B, nos turnos da manhã e da tarde.
- 132 alunos fictícios, 3 professores e 22 contatos fictícios de responsáveis.
- 4 ciclos entre fevereiro e outubro de 2026, com 508 avaliações.
- Ciclo atual: 112 avaliados, 20 pendentes e cobertura aproximada de 85%.
- 12 pontos de atenção, com exemplos de queda e estagnação.
- 36 aulas e 396 registros de frequência.
- 10 planos de intervenção, 10 metas, 3 testes e 57 resultados físicos fictícios.
- 6 observações de aula e 3 avaliações demonstrativas de professores.
- 4 comunicados, 3 mensagens internas, 3 reuniões, 2 eventos e 27 inscrições.

## Sequência sugerida

1. **Visão geral:** apresente cobertura das avaliações, médias e pontos de atenção.
2. **Turmas e alunos:** mostre a organização por série, turno e professor.
3. **Evolução:** selecione um aluno; mostre as quatro avaliações, o gráfico por critério, o radar e as observações.
4. **Relatórios:** baixe a ficha individual em PDF.
5. **Atenção pedagógica:** mostre os exemplos de queda e estagnação como oportunidades de acompanhamento.
6. **Intervenções e metas:** abra um plano em andamento e outro concluído.
7. **Aulas e frequência:** mostre conteúdo, presenças e faltas fictícias.
8. **Professores:** apresente a visão das turmas de cada docente.
9. **Eventos e comunicados:** demonstre a organização das inscrições e a comunicação interna.

## Recriar ou retomar a demonstração

O script utiliza a API pública e um arquivo de estado privado, fora do repositório. As credenciais são geradas em memória e ficam apenas nesse arquivo e no documento de acesso local. Não são incluídas no Git.

```sh
python scripts/populate_presentation.py --base-url https://fisicamente-sigma.vercel.app --state-file /caminho/privado/objetivo-demo.json --create-demo
```

Uma nova execução com o mesmo arquivo retoma o preenchimento e evita duplicar os registros. Datas e resultados são deliberadamente fixos no cenário de outubro de 2026. Não utilize o roteiro para registrar atividades de uma escola real.
