# Revisão da demonstração — 20/11/2026

Base: `4bd46f0cf7fd656ab2653f3d8b381c551e6b5bd3`. Branch local: `fix/demo-revisao-luciana`.

## 1. Caso ambíguo

O card anterior carregava `Borda_Score_084.pdf`, receita legível cujo score de teste era forçado. A demonstração passa a carregar `Ausencia_Paciente_Idade.jpg`, cópia byte a byte da fixture do catálogo. A imagem contém uma receita fictícia com idade expressamente não informada; não é manuscrita nem rasurada. O carregador envia MIME `image/jpeg` e o simulador usa a mesma referência de idade ausente e somente revisão humana.

O limiar `0,85`, as regras e o cálculo de qualidade não foram modificados. O prompt de extração foi versionado como `1.1.0`, reforçando transcrição literal dos medicamentos, caminhos canônicos de incerteza e estrutura dos resultados laboratoriais. Não foi introduzida correção aproximada de nomes de medicamentos.

Na rodada histórica da base, as cinco execuções foram para revisão; quatro divergências automáticas eram apenas a ausência do título “Dra.” no nome da médica, mas a primeira rodada também trouxe a transcrição incorreta “Nitrofuranetoína”. Essa evidência não deve ser descartada.

### Rodada real da candidata

API HTTP local com Gemini real, OCI obrigatório e simulação de OCI desativada. Código da aplicação no commit `974bbfb42fef213c957838fcb72d104d4edf73f6`, árvore limpa ao iniciar. Depois dessa rodada, a mudança de código adicional foi somente a entrada textual de um teste unitário, tornando explícito o marcador laboratorial que ele verifica.

| Execução | Documento | Status | Score combinado | Campos ausentes | Destino |
|---|---|---|---|---|---|
| 1 | `DOC-CLIN-2026-125CA8EA` | EM_REVISAO | 0,70 | exames; paciente.idade | FILA_REVISAO_HUMANA |
| 2 | `DOC-CLIN-2026-0D7AA2CE` | EM_REVISAO | 0,70 | exames; paciente.idade | FILA_REVISAO_HUMANA |
| 3 | `DOC-CLIN-2026-305CF32D` | EM_REVISAO | 0,70 | exames; paciente.idade | FILA_REVISAO_HUMANA |
| 4 | `DOC-CLIN-2026-48E14BF1` | EM_REVISAO | 0,70 | exames; paciente.idade | FILA_REVISAO_HUMANA |
| 5 | `DOC-CLIN-2026-D33AC925` | EM_REVISAO | 0,70 | exames; paciente.idade | FILA_REVISAO_HUMANA |

Nas cinco respostas, a idade permaneceu nula, o medicamento foi transcrito como Nitrofurantoína, a dose como 100 mg e não houve alerta. O histórico registrou `gemini_service` e a API registrou persistência bem-sucedida. Cinco acertos não garantem a fidelidade de toda inferência futura.

## 2. Vitest

Na base, `src/fluxoProcessamento.test.tsx` já chamava `iniciarSessao(false)` no `beforeEach`. Os dez testes passaram isoladamente sem alteração desse arquivo. Não foi necessário adicionar uma segunda preparação de sessão nem aumentar os prazos. A causa da execução histórica com falhas não foi reproduzida e não é atribuída definitivamente à carga.

Na candidata, a suíte completa passou com **306 testes em 27 arquivos**. As expectativas do cenário antigo foram atualizadas para a nova referência. Foram adicionados testes do MIME JPEG, coerência do simulador, dose incerta na tabela e mensagem para campo de achados críticos não informado.

Comandos: `npm test -- src/fluxoProcessamento.test.tsx --maxWorkers=2`; `npm test -- --maxWorkers=2`; `npm run build`. O build TypeScript/Vite passou.

## 3. README e arquitetura

Os nomes canônicos dos campos e o ID `DOC-CLIN-2026-XXXXXXXX` já estavam corrigidos na base. O exemplo resumido agora explicita `notificacao` e `armazenamento_oci`. A tabela da demonstração identifica os arquivos reais e os critérios, sem prometer scores fixos ou afirmar que a nova imagem é rasurada. Os caminhos são `recebidos/<id>/original.<ext>`, `processados/<id>/resultado.json`, `processados/urgentes/<id>/resultado.json` e `auditoria_humana/<id>/resultado.json`.

## 4. Ajustes menores e regressões clínicas

- `canal_origem` preservado em JSON e multipart, no resultado e na cópia enviada ao OCI. O campo da requisição prevalece sobre metadados arbitrários. Testes cobrem os dois formatos.
- `dados_extraidos.score_confianca_extracao` é a confiança declarada pelo extrator ou o padrão do schema quando omitida. `qualidade.score_extracao` parte de 1,0 e é calculado por regras de ausências, incertezas e conflitos. O combinado usa o mínimo entre classificação e qualidade de extração. A documentação e a tela explicam a diferença; os valores não certificam correção clínica.
- Alerta permanece simulado e inclui paciente, diagnóstico e CRM do solicitante quando disponíveis; campos ausentes são explicitados, sem dados inventados. Nenhuma notificação externa foi adicionada.
- Valores laboratoriais passaram a ser solicitados explicitamente com analito, valor, unidade e referência. Quando existe fonte textual, um valor `alterado` sem marcador explícito na linha do analito fica nulo, em vez de apresentar inferência numérica como dado impresso. Essa conferência textual não substitui a validação humana de documentos em imagem.
- Alias de incerteza de dose é convertido ao caminho canônico somente quando identifica um medicamento único. A tabela sinaliza a dose como incerta/ilegível. Caso ambíguo ou nome desconhecido não é associado por aproximação.
- `achados_criticos: null` passa a ser apresentado como campo não informado, sem afirmar inexistência de achados críticos.

| Caso real adicional | Documento | Resultado conferido |
|---|---|---|
| Laudo laboratorial | `DOC-CLIN-2026-BB5C2398` | PROCESSADO, sete resultados com valores/unidades/referências |
| Revisão laboratorial | `DOC-CLIN-2026-6555A6D4` | EM_REVISAO, três resultados e urgência indeterminada |
| Dose ilegível | `DOC-CLIN-2026-3E38F4C4` | dose nula, `medicamentos[0].dosagem`, duas filas e alerta contextual simulado |
| Urgência | `DOC-CLIN-2026-53D03A2A` | PROCESSADO, fila de urgência e alerta contextual simulado |

## 5. Versão e testes finais

`python -m pytest -q -rs`: **462 aprovados e 1 pulado**. O pulado é a proteção exclusiva do contrato legado, em `tests/test_workflow.py`. Os avisos de dependências foram preservados nos relatórios. Não são 304 nem 324; o total varia com o SHA e as suítes selecionadas.

As alterações foram feitas somente na branch local. O SHA de publicação e a tag estável devem ser definidos após revisão e integração; nenhum deploy ou tag de release foi criado nesta tarefa. Ainda é necessário conferir a candidata no ambiente publicado e repetir os testes afetados por alterações posteriores. Os retestes históricos da receita e das duas imagens continuam separados dos casos identificados nesta rodada.

Evidências locais do pacote: `pytest-final.txt`, `vitest-final.txt` e a pasta `gemini-real-20261120-005510`, com aceite, resultado e histórico de cada documento e o `resumo.json`. A persistência dessa rodada foi confirmada pela resposta da API; ela não é uma nova auditoria independente de recuperação do bucket.
