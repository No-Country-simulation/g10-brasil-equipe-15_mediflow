# Contrato de dados da triagem — MediFlow v1.0

> **Nota de Integração no Repositório Oficial (24/10/2026):**  
> Este documento representa a especificação canônica original criada pelo colega William para governar os 79 fixtures de teste.  
> No repositório oficial (`g10-brasil-equipe-15_mediflow`), sua implementação ativa reside em [`src/schemas/clinical.py`](../../src/schemas/clinical.py) e sua versão harmonizada e resiliente está documentada em [`CONTRATO_DE_DADOS_v2.md`](CONTRATO_DE_DADOS_v2.md).  
> Os testes automatizados são executados diretamente via Pytest: `python -m pytest tests/test_contrato_fixtures.py`.

**Projeto:** MediFlow — Equipe 15 (Hackathon ONE G10 - Oracle & Alura)  
**Código Original:** `app/models.py` | **Código Oficial:** [`src/schemas/clinical.py`](../../src/schemas/clinical.py)  
**Data Original:** 20/10/2026 | **Integração:** 24/10/2026  
**Escopo:** o contrato que os 79 `expected.json` documentam e validam.

---

## 1. O que é este documento

O contrato responde a três perguntas, e só a estas:

1. **Qual é o formato da resposta** que o agente devolve para um documento aceito (`TriagemMediFlow`) e para uma requisição recusada (`ErroResposta`).
2. **Quais valores são válidos** em cada campo controlado — sem texto livre, sem acento, sem espaço.
3. **Como a decisão é tomada** a partir dos fatos extraídos (score, campos ausentes, incertos, conflitos, prioridade).

Ele é executável: `src/schemas/clinical.py` roda as regras e recusa payload incoerente. Os 79 fixtures são instâncias válidas desse modelo, e o teste `tests/test_contrato_fixtures.py` prova isso a cada execução.

```bash
python -m pytest tests/test_contrato_fixtures.py        # 79/79 fixtures validados via Pytest
python -m pytest                                       # Suíte completa (143 testes)
```

---

## 2. Enums (fonte única)

| Enum | Valores | Onde aparece |
| --- | --- | --- |
| `TipoDocumento` | `RECEITUARIO_MEDICO`, `LAUDO_EXAME_LABORATORIAL`, `LAUDO_EXAME_IMAGEM`, `GUIA_PROCEDIMENTO`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO`, `OUTRO`, `NAO_IDENTIFICADO` | `classificacao.tipo_documento` |
| `NivelPrioridade` | `URGENTE`, `ROTINA`, `NAO_IDENTIFICADA` | `classificacao.nivel_prioridade` |
| `StatusTriagem` | `RECEBIDO`, `PROCESSANDO`, `PROCESSADO`, `EM_REVISAO`, `ERRO_PROCESSAMENTO`, `ERRO_PERSISTENCIA` | `status` |
| `Destino` | `FILA_URGENCIA_MEDICA`, `FARMACIA_HOSPITALAR`, `AUDITORIA_AUTORIZACOES`, `PRONTUARIO_ELETRONICO`, `FILA_REVISAO_HUMANA` | `decisao_roteamento.destinos` |
| `Urgencia` | `SIM`, `NAO`, `INDETERMINADO` | `dados_extraidos.urgencia` |
| `Gravidade` | `ALTA`, `MEDIA`, `BAIXA` | `qualidade.conflitos[].gravidade` |
| `CodigoErro` | `FORMATO_NAO_SUPORTADO`, `CAMPOS_INVALIDOS`, `REQUISICAO_INVALIDA`, `ARQUIVO_MAIOR_QUE_LIMITE`, `MIME_INVALIDO`, `PDF_PROTEGIDO`, `PDF_CORROMPIDO` | erros |

Decisões que fecham divergências antigas:

- **Tokens, não rótulos.** `LAUDO_EXAME_IMAGEM` (não `"Laudo de Exame de Imagem"`), `FILA_URGENCIA_MEDICA` (não `"Fila_Emergencia_Medica"`). Nada de acento, espaço ou barra em valor de enum.
- **`POUCO_URGENTE` não existe.** A especificação define três níveis; o valor foi removido em vez de ficar sem fixture.
- **`OUTRO` e `NAO_IDENTIFICADO` são resultados**, não erros: continuam sendo `TipoDocumento`, com revisão obrigatória.
- **`NAO_IDENTIFICADA` é prioridade**; `N/A` deixou de existir em qualquer campo.
- **Urgência isolada não gera revisão humana** (`PROCESSADO` + `requer_auditoria_humana=False`). Decisão tomada a partir do `Projeto_oracle.pdf`, cujo exemplo devolve `"status": "processado"` e `"requer_auditoria_humana": false` para um caso urgente, e guarda o objeto em `processados/urgentes/`. Revisão é consequência de **ambiguidade**, nunca de urgência sozinha.

---

## 3. Payload de triagem

```jsonc
{
  "status": "EM_REVISAO",
  "documento_id": "DOC-A757DAD2",
  "classificacao": {
    "tipo_documento": "RECEITUARIO_MEDICO",
    "especialidade": ["Cardiologia"],
    "nivel_prioridade": "ROTINA",
    "score_classificacao": 0.93
  },
  "dados_extraidos": {
    "paciente": {"nome": "Neusa Ferreira Lima", "idade": 73},
    "medico": {"nome": "Dr. Paulo Mendes Rocha", "crm": {"numero": "203114", "uf": "SP"}},
    "diagnostico": "Hipertensão arterial sistêmica",
    "cid": "I10",
    "exames": [],
    "medicamentos": [{"nome": "Losartana potássica", "dosagem": "500 mg", "frequencia": null}],
    "urgencia": "NAO"
  },
  "qualidade": {
    "score_extracao": 0.91,
    "score_combinado": 0.91,
    "limiar_aplicado": 0.85,
    "campos_ausentes": [],
    "campos_incertos": [],
    "conflitos": [{"tipo": "DOSE_SUSPEITA", "campos": ["medicamentos[0].dosagem"],
                   "gravidade": "ALTA", "descricao": "Losartana 500 mg excede a dose usual"}]
  },
  "decisao_roteamento": {
    "destino_principal": "FILA_REVISAO_HUMANA",
    "destinos": ["FILA_REVISAO_HUMANA"],
    "requer_auditoria_humana": true,
    "justificativa_roteamento": "Revisão humana obrigatória: conflitos: DOSE_SUSPEITA.",
    "notificacao": null
  },
  "armazenamento_oci": null,
  "erro": null
}
```

Notas de modelagem:

| Campo | Regra |
| --- | --- |
| `especialidade`, `exames` | listas — um documento pode ter mais de uma especialidade e vários exames |
| `medicamentos` | objeto `{nome, dosagem?, frequencia?}`; `dosagem` é opcional porque há prescrição sem dose |
| `medico.crm` | **um** objeto `{numero, uf}`; não existe mais `crm` texto + `crm_detalhado` duplicado |
| `medico.crm.uf` | sempre `SP`: todas as fixtures acontecem no Hospital Aurora, em São Paulo, e o CRM acompanha a UF de atuação |
| `dados_extraidos.urgencia` | declara o que o documento diz (`SIM`/`NAO`/`INDETERMINADO`), em vez de inferir do texto |
| `qualidade.campos_ausentes` / `campos_incertos` | vêm do extrator; o validador **não recalcula** (ver §5) |
| `qualidade.score_extracao` | produzido pelo extrator com a fórmula do §5 (`calcular_score_extracao`); o validador não o recalcula, porque os 79 casos aprovados trazem scores ilustrativos |
| `qualidade.score_combinado` | sempre `min(score_classificacao, score_extracao)` — recalculado pelo validador |
| `decisao_roteamento.destino_principal` | derivado: é sempre `destinos[0]` |
| `armazenamento_oci` | opcional: persistência é etapa posterior e pode falhar (`ERRO_PERSISTENCIA`) |

---

## 4. Erro: dois formatos, cada um no seu nível

| Situação | Formato | Exemplo nos fixtures |
| --- | --- | --- |
| Requisição inválida (formato, tamanho, MIME, envelope, sintaxe) — **não chega a virar triagem** | `ErroResposta {http, codigo_funcional, mensagem}` | os 8 `Validacao_*` |
| Documento aceito, mas ilegível na leitura (PDF protegido/corrompido) | `TriagemMediFlow` com `status=ERRO_PROCESSAMENTO`, `erro={codigo, mensagem}` e sem classificação/dados | `Qualidade_Pdf_ComSenha` (`PDF_PROTEGIDO`), `Qualidade_Pdf_Corrompido` (`PDF_CORROMPIDO`) |

Os dois casos de leitura antes usavam o schema de triagem preenchido com `"N/A"` — um valor que não é enum nenhum. Agora são payloads válidos, com erro tipado.

---

## 5. Regras de decisão

| # | Regra | Efeito |
| --- | --- | --- |
| R1 | `nivel_prioridade == URGENTE` | `FILA_URGENCIA_MEDICA` + `notificacao` + `PROCESSADO`. **Urgência isolada não gera revisão humana** (`requer_auditoria_humana=False`) — é o comportamento do exemplo do `Projeto_oracle.pdf` |
| R2 | Ambiguidade: campo obrigatório ausente **ou** campo incerto **ou** conflito **impeditivo** (`ALTA`/`MEDIA`) **ou** `score_combinado < limiar` **ou** `OUTRO`/`NAO_IDENTIFICADO` **ou** prioridade `NAO_IDENTIFICADA` **ou** `urgencia == INDETERMINADO` | revisão humana |
| R3 | Ambiguidade **sem** urgência | destino **substituído** por `FILA_REVISAO_HUMANA` |
| R4 | Ambiguidade **com** urgência | `FILA_URGENCIA_MEDICA` **+** `FILA_REVISAO_HUMANA` + `requer_auditoria_humana=True` + `EM_REVISAO` |
| R5 | `score_combinado = min(...)`, limiar **estrito** | 0,85 passa; 0,84 revisa |
| R8 | Conflito de gravidade `BAIXA` | é registrado em `qualidade.conflitos` e na justificativa, mas **não** vira conflito impeditivo e **não** gera revisão |
| R6 | `campos_ausentes` é do extrator | só os 5 obrigatórios disparam revisão; CID/medicamentos/exames ausentes são registrados e não bloqueiam |
| R7 | Erro de leitura | `ERRO_PROCESSAMENTO` + `erro.codigo`, sem dados |

**Campos obrigatórios (RF-21):** `paciente.nome`, `paciente.idade`, `medico.nome`, `medico.crm`, `diagnostico`.

### A urgência, explicada

**Urgência isolada não é ambiguidade, e por isso não gera revisão humana.** Um documento urgente sem nenhuma ambiguidade termina em `PROCESSADO`, com `requer_auditoria_humana = false`, um único destino (`FILA_URGENCIA_MEDICA`) e o alerta registrado. É o comportamento do exemplo do `Projeto_oracle.pdf`, que devolve `"status": "processado"`, `"requer_auditoria_humana": false` e guarda o objeto em `processados/urgentes/`.

A `FILA_REVISAO_HUMANA` só entra quando existe, além da urgência, uma ambiguidade (R4) — campo obrigatório ausente, campo incerto, conflito impeditivo, score abaixo do limiar, tipo fora da taxonomia, prioridade `NAO_IDENTIFICADA` ou urgência `INDETERMINADO`. Nesse caso a urgência **acrescenta** o destino em vez de substituí-lo, e o status passa a `EM_REVISAO`.

É o que acontece em `Matriz_Guia_Imagem`, `Matriz_LaudoDeImagem_Pdf`, `Matriz_LaudoDeImagem_Imagem`, `Matriz_Receituario_Imagem` e `Conflito_AltoRisco` — cinco casos, um destino, status `PROCESSADO`, com alerta. Os três casos de duas filas (`Conflito_Prioridade`, `Simultaneo_Urgencia_Ilegivel`, `Simultaneo_Urgencia_Score`) mantêm `EM_REVISAO` porque há ambiguidade junto.

### Por que o validador não deduz "campo ausente"

`Matriz_LaudoLaboratorial_Texto` tem `diagnostico: null` e termina em `PROCESSADO` — um laudo laboratorial legitimamente não tem diagnóstico. `Ausencia_Diagnostico` também tem `diagnostico: null` e termina em `EM_REVISAO`. O dado é o mesmo; a diferença está na intenção registrada em `qualidade.campos_ausentes`, que é saída do extrator. Recalcular essa lista olhando para `null` erraria um dos dois lados.

### Decisões de 21/10/2026 incorporadas ao contrato

| Decisão | Regra | Onde |
| --- | --- | --- |
| A1 | Só conflito de gravidade `ALTA` ou `MEDIA` é **impeditivo** e leva à revisão. `BAIXA` é registrado e não bloqueia. | `GRAVIDADES_IMPEDITIVAS`, R2, R8 |
| A3 | `score_extracao` é determinístico: `1 − 0,2×campo obrigatório ausente − 0,1×campo incerto − 0,3/0,2/0,1 por conflito ALTA/MEDIA/BAIXA`, com piso 0. | `calcular_score_extracao`, `PESO_CONFLITO` |
| A4 | `nivel_prioridade == NAO_IDENTIFICADA` é ambiguidade e gera revisão. | R2 |
| A5 | `urgencia == INDETERMINADO` entra como campo incerto e gera revisão. | R2 |

A `GRAVIDADES_IMPEDITIVAS` e o `calcular_score_extracao` ficam em `app/models.py`; a regra também está registrada no Anexo A da Especificação Funcional v1.0 (A.1 a A.7).

**As duas primeiras eram invisíveis nos 67 casos originais** — e é por isso que o catálogo ganhou 3 fixtures:

| Regra | Situação nos 67 casos | Caso criado para prová-la |
| --- | --- | --- |
| A1 (gravidade) | todos os conflitos existentes eram `ALTA`; nada distinguia `MEDIA` de `BAIXA` | `Conflito_Gravidade_Media` (revisa) e `Conflito_Gravidade_Baixa` (não revisa) |
| A4 (`NAO_IDENTIFICADA`) | os 8 casos `NAO_IDENTIFICADA` já revisavam por outros gatilhos | `Borda_Prioridade_NaoIdentificada` — prioridade indefinida como único gatilho |
| A5 (`INDETERMINADO`) | os 8 casos `INDETERMINADO` já revisavam por outros gatilhos | `Borda_Urgencia_Indeterminada` — urgência indeterminada como único gatilho |

Medição: com `GRAVIDADES_IMPEDITIVAS = {ALTA, MEDIA, BAIXA}` o caso `Conflito_Gravidade_Baixa` passaria a `EM_REVISAO`; com `{ALTA}` o caso `Conflito_Gravidade_Media` passaria a `PROCESSADO`; sem A4 e A5 os dois casos de borda passariam a `PROCESSADO`. Os três novos casos pegam a mudança — antes deles, a suíte não detectaria nenhuma regressão em A1, A4 ou A5.

---

## 5.1 Coerência clínica dos fixtures

Toda fixture conta **uma** história nos três formatos. O texto (`{ID}.txt`) é a
referência do que se espera extrair:

- campo preenchido no `expected.json` aparece no texto (`paciente.nome`, `medico.nome`, `medico.crm`, `diagnostico`, `cid`, idade);
- campo ausente aparece como ausente (`—`, `não informado`, `CRM não visível`);
- campo ilegível aparece ilegível (`4?_ anos — mancha sobre o campo`), e a mancha na imagem cobre exatamente esse campo;
- **todo CRM é `SP`**, porque o hospital é paulista.

O verificador checa os quatro pontos caso a caso (`== 5. Coerência clínica` em
`tools/verificar_consistencia.py`), então uma edição futura que quebre a
coerência falha o build em vez de virar um teste enganoso.

## 6. Formato de um `expected.json`

```jsonc
{
  "schema": "mediflow.fixture/2",
  "fixture_id": "Conflito_Dose",
  "documento_ficticio": true,
  "tipo_de_teste": "funcional",              // funcional | erro_processamento | negativo_tecnico
  "entrada": {
    "formatos_disponiveis": ["TXT", "PDF", "JPG"],
    "renditions": {"txt": "...", "pdf": "...", "jpg": "..."}
  },
  "resposta_esperada": { /* TriagemMediFlow ou ErroResposta */ },
  "modo_fixture": {"score_forcado": {"score_classificacao": 0.92, "score_extracao": 0.84}},
  "assercoes": ["..."],
  "observacoes": ""
}
```

- `resposta_esperada` é o payload **completo**: quem consome o fixture compara o JSON da API com este bloco, sem tradução de nomes.
- `modo_fixture` só existe nos três casos que exigem score forçado (`Borda_Score_084`, `Borda_Score_085`, `Simultaneo_Urgencia_Score`).
- `tipo_de_teste` elimina a ambiguidade que existia entre "triagem normal", "triagem com erro" e "requisição recusada".

### Como os arquivos são gerados

Os geradores descrevem os **fatos clínicos** do caso; quem decide status, destinos, revisão e notificação é o contrato. Se o contrato e a intenção escrita no caso divergirem, a geração **aborta** — é assim que uma mudança de regra aparece imediatamente.

```bash
python3 tools/gerar_fixtures_demo.py                  # 12 casos (TXT+PDF+JPG+expected.json)
python3 tools/gerar_fixtures_catalogo.py              # 55 casos
python3 tools/gerar_fixtures_demo.py --somente-expected    # reescreve só os JSON
python3 tools/gerar_fixtures_catalogo.py --somente-expected
```

---

## 7. Verificação

| Comando | O que garante |
| --- | --- |
| `python3 tests/testar_contrato.py` | cada `expected.json` valida no modelo certo e é **ponto fixo**: rodar as regras de novo devolve o mesmo JSON |
| `python3 tools/verificar_consistencia.py` | estrutura (arquivos esperados lidos de `entrada.renditions`), `manifest.csv` × expected, legibilidade de PDF/JPG/PNG/WEBP/TXT, duplicidade |
| `python3 tools/gerar_mapa_documentos.py` | regera o mapa em PDF a partir do manifesto |

Resultado atual:

```text
tests/testar_contrato.py        → 79 fixtures: 65 funcionais + 2 erros de leitura + 12 negativos, 0 falhas
tools/verificar_consistencia.py → 79 pastas (65 com 4 arquivos + 12 com 2), 0 erros, 0 avisos
```

---

## 8. O que mudou em relação ao modelo v2.0

O modelo anterior (v2.0) foi descartado. Resumo do que ele não cobria e que agora está no contrato:

| Antes (v2.0) | Agora (v1.0) |
| --- | --- |
| enums com texto livre (`"Urgente"`, `"Fila_Emergencia_Medica"`) | tokens do domínio + `OUTRO`, `NAO_IDENTIFICADO`, `NAO_IDENTIFICADA` |
| `status: str` com default `PROCESSADO` | `StatusTriagem` com os 6 estados, sem default |
| sem contrato de erro; `dados_extraidos` obrigatório | `ErroResposta` (HTTP) e `TriagemMediFlow.erro` (leitura) |
| validador apagava `campos_incertos`/`conflitos` recebidos | evidência preservada e cobrada nas regras |
| urgência não gerava `EM_REVISAO`; diagnóstico "ou exame" | urgência isolada volta a terminar em `PROCESSADO`, agora **por decisão** (R1: exemplo do `Projeto_oracle.pdf`), e não por omissão de regra; diagnóstico obrigatório segue R6 |
| `especialidade: str`, `exame_ou_procedimento: str`, `crm` duplicado | listas e objeto CRM único |
| limiar 0,85 fixo no corpo do validador | `qualidade.limiar_aplicado` (default 0,85, por payload) |

O histórico completo dessa comparação está no commit `cacdfba` (relatório removido depois de resolvido).
