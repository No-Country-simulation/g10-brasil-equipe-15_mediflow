# Contrato de Dados da Triagem — MediFlow (Versão Oficial Canônica)

> **Projeto:** MediFlow — Equipe 15 (Hackathon ONE G10 - Oracle & Alura)  
> **Status:** Contrato Canônico Oficial Unificado (Governança Central de Dados)  
> **Implementação Ativa:** [`src/schemas/clinical.py`](../../src/schemas/clinical.py)  
> **Escopo:** Rege o Agente Gemini, o Workflow LangGraph, o Ingestor de Documentos, a API FastAPI, as Interfaces (Streamlit/React) e os 79 fixtures de teste automatizados.  
> **Validação Automatizada:** 100% coberto pela suíte Pytest (`python -m pytest`).

---

## 1. O que é este documento

Este documento é a **especificação canônica oficial** do contrato de dados do MediFlow. Ele unifica e harmoniza as regras clínicas e fixtures desenvolvidos por William com a expansão de schemas e interoperabilidade estruturada por Luciana, consolidando uma fonte única da verdade para todo o repositório.

O contrato responde a quatro perguntas fundamentais:

1. **Qual é o formato da resposta** que o agente devolve para um documento aceito ([`TriagemMediFlow`](../../src/schemas/clinical.py)) e para requisições recusadas ou ilegíveis ([`ErroResposta`](../../src/schemas/clinical.py) e `ErroProcessamento`).
2. **Quais valores e tokens são válidos** em cada campo controlado — garantindo formato uniforme (caixa alta, sem acentos, sem espaços) com resiliência automática para variações legadas.
3. **Como a decisão de triagem é calculada** a partir dos fatos clínicos extraídos (scores de confiança, campos obrigatórios, incerteza, conflitos e prioridade).
4. **Como o sistema assegura retrocompatibilidade e interoperabilidade**, permitindo que o Ingestion Loader, a LLM Gemini, a esteira LangGraph, a API e as interfaces interajam sem falhas de desserialização.

O contrato é **executável e determinístico**: implementado via Pydantic v2 em [`src/schemas/clinical.py`](../../src/schemas/clinical.py), ele aplica as regras no `@model_validator` e valida os 79 fixtures oficiais como instâncias estritas.

> 📊 **Guia Visual Completo dos Schemas:** Para visualizar os diagramas de classes, relacionamentos de enums e o fluxograma determinístico das regras R1 a R8, consulte o [**Guia Visual dos Schemas (VISUAL_SCHEMAS.md)**](VISUAL_SCHEMAS.md).

---

## 2. Enums Controlados (Fonte Única com Resiliência Automática)

Todos os enums utilizam **tokens puros em caixa alta (sem acentos e sem espaços)** como padrão estrito de serialização. Para evitar falhas em integrações externas ou legadas, os enums implementam resiliência via método `_missing_`, normalizando automaticamente formatos alternativos para o token canônico correspondente.

| Enum | Tokens Canônicos Oficiais | Aliases e Compatibilidade Aceitos via `_missing_` | Onde aparece |
| :--- | :--- | :--- | :--- |
| `TipoDocumento` | `RECEITUARIO_MEDICO`, `LAUDO_EXAME_LABORATORIAL`, `LAUDO_EXAME_IMAGEM`, `GUIA_PROCEDIMENTO`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO`, `OUTRO`, `NAO_IDENTIFICADO` | `"Laudo de Exame de Imagem"`, `"Receituario Medico"`, `"Guia de Solicitação de Procedimento"`, `"LAUDO_IMAGEM"` | `classificacao.tipo_documento` |
| `NivelPrioridade` | `URGENTE`, `ROTINA`, `NAO_IDENTIFICADA` | `"Urgente"`, `"Rotina"`, `"Pouco_Urgente"` (normalizado para `ROTINA`) | `classificacao.nivel_prioridade` |
| `StatusTriagem` | `RECEBIDO`, `PROCESSANDO`, `PROCESSADO`, `EM_REVISAO`, `ERRO_PROCESSAMENTO`, `ERRO_PERSISTENCIA` | `"processado"`, `"pendente_auditoria"` (normalizado para `EM_REVISAO`) | `status` |
| `Destino` | `FILA_URGENCIA_MEDICA`, `FARMACIA_HOSPITALAR`, `AUDITORIA_AUTORIZACOES`, `PRONTUARIO_ELETRONICO`, `FILA_REVISAO_HUMANA` | `"Fila_Emergencia_Medica"`, `"Farmacia_Hospitalar"`, `"Auditoria_Autorizacoes"`, `"Prontuario_Eletronico"`, `"Fila_Revisao_Humana"` | `decisao_roteamento.destinos` |
| `Urgencia` | `SIM`, `NAO`, `INDETERMINADO` | Case-insensitive (`"sim"`, `"nao"`, `"indeterminado"`) | `dados_extraidos.urgencia` |
| `Gravidade` | `ALTA`, `MEDIA`, `BAIXA` | Case-insensitive | `qualidade.conflitos[].gravidade` |
| `CodigoErro` | `FORMATO_NAO_SUPORTADO`, `CAMPOS_INVALIDOS`, `REQUISICAO_INVALIDA`, `ARQUIVO_MAIOR_QUE_LIMITE`, `MIME_INVALIDO`, `PDF_PROTEGIDO`, `PDF_CORROMPIDO`, `ERRO_PERSISTENCIA` | Alinhado com as exceções de `src/ingestion/loader.py` e persistência OCI | `erro.codigo` / `codigo_funcional` |

### Decisões de Design Clínico e Arquitetural:

- **Tokens, não rótulos:** `LAUDO_EXAME_IMAGEM` (não `"Laudo de Exame de Imagem"`), `FILA_URGENCIA_MEDICA` (não `"Fila_Emergencia_Medica"`). A camada de apresentação (Streamlit/React) formata para o usuário final; o contrato trafega tokens puros.
- **`POUCO_URGENTE` não existe como nível separado:** O edital e a especificação médica definem três níveis (`URGENTE`, `ROTINA`, `NAO_IDENTIFICADA`). Variantes legadas são convertidas com segurança para `ROTINA`.
- **`OUTRO` e `NAO_IDENTIFICADO` são resultados válidos de classificação**, e não erros de sistema: pertencem a `TipoDocumento` e acionam obrigatoriamente a revisão humana.
- **`NAO_IDENTIFICADA` é valor de prioridade**; `N/A` foi abolido de todos os campos.
- **Urgência isolada não gera revisão humana (`PROCESSADO` + `requer_auditoria_humana = False`):** Decisão fundamentada no edital oficial (`Projeto_oracle.pdf`), onde o documento urgente bem estruturado é processado com notificação imediata para `processados/urgentes/`. Revisão humana é consequência de **ambiguidade ou incerteza**, nunca de urgência isolada.

---

## 3. Payload Canônico de Triagem (`TriagemMediFlow`)

Abaixo está a estrutura canônica completa retornada pelo motor de triagem:

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
    "paciente": {
      "nome": "Neusa Ferreira Lima",
      "idade": 73,
      "cpf": null
    },
    "medico": {
      "nome": "Dr. Paulo Mendes Rocha",
      "crm": {
        "numero": "203114",
        "uf": "SP"
      }
    },
    "diagnostico": "Hipertensão arterial sistêmica",
    "cid": "I10",
    "exames": [],
    "exames_laboratoriais": [],
    "medicamentos": [
      {
        "nome": "Losartana potássica",
        "dosagem": "50 mg",
        "frequencia": "1 vez ao dia"
      }
    ],
    "urgencia": "NAO"
  },
  "qualidade": {
    "score_extracao": 0.91,
    "score_combinado": 0.91,
    "limiar_aplicado": 0.85,
    "campos_ausentes": [],
    "campos_incertos": [],
    "conflitos": [
      {
        "tipo": "DOSE_SUSPEITA",
        "campos": ["medicamentos[0].dosagem"],
        "gravidade": "ALTA",
        "descricao": "Dosagem informada excede os padrões terapêuticos habituais"
      }
    ]
  },
  "decisao_roteamento": {
    "destino_principal": "FILA_REVISAO_HUMANA",
    "destinos": ["FILA_REVISAO_HUMANA"],
    "requer_auditoria_humana": true,
    "justificativa_roteamento": "Revisão humana obrigatória: conflitos impeditivos: DOSE_SUSPEITA.",
    "notificacao": null
  },
  "armazenamento_oci": {
    "bucket": "mediflow-documentos-clinicos",
    "caminho_objeto": "processados/revisao/DOC-A757DAD2.json",
    "status_backup": "sucesso"
  },
  "erro": null
}
```

### 3.1 Notas de Modelagem Clínica

| Campo | Regra Canônica |
| :--- | :--- |
| `especialidade`, `exames` | Listas (`list[str]`) — um documento clínico pode envolver múltiplas especialidades e solicitar múltiplos exames. |
| `medicamentos` | Lista de objetos `{nome, dosagem?, frequencia?}` — `dosagem` e `frequencia` são opcionais para suportar prescrições simplificadas. |
| `medico.crm` | Objeto tipado `{numero, uf}` — elimina a duplicidade histórica de ter CRM texto e CRM detalhado separados. |
| `medico.crm.uf` | Padrão `SP` nas fixtures de teste (Hospital Aurora de São Paulo), mas o schema aceita qualquer UF brasileira válida. |
| `dados_extraidos.urgencia` | Declara o que o documento explicita clinicamente (`SIM`, `NAO`, `INDETERMINADO`), em vez de inferência probabilística. |
| `qualidade.campos_ausentes` / `campos_incertos` | Gerados pelo extrator e auditados pelas regras; o validador não os deduz arbitrariamente (ver §5). |
| `qualidade.score_combinado` | Sempre `min(score_classificacao, score_extracao)` — calculado deterministicamente. |
| `decisao_roteamento.destino_principal` | Derivado: corresponde sempre ao primeiro item da lista de `destinos` (`destinos[0]`). |
| `armazenamento_oci` | Opcional (`None` ou objeto tipado): a persistência na nuvem OCI ocorre após o pipeline e pode registrar auditoria sem invalidar a triagem. |

### 3.2 Adaptações e Aliases de Retrocompatibilidade (Pydantic v2)

Para garantir interoperabilidade entre módulos e testes legados sem acoplamento rígido:

| Campo Canônico | Alias / Propriedade de Compatibilidade | Comportamento do Validador |
| :--- | :--- | :--- |
| `dados_extraidos.medico` | `dados_extraidos.medico_solicitante` | Validador aceita ambos os nomes na entrada e expõe acesso unificado. |
| `medico.crm` | `medico.crm: str` (ex: `"203114-SP"`) | Validador converte automaticamente string para o objeto tipado `Crm(numero="203114", uf="SP")`. |
| `dados_extraidos.diagnostico` | `dados_extraidos.diagnostico_principal` | Acesso transparente via properties e aliases. |
| `dados_extraidos.cid` | `dados_extraidos.cid_extraido` / `cid_sugerido` | Sincronizados bidirecionalmente no modelo. |
| `dados_extraidos.exames` | `dados_extraidos.exame_ou_procedimento: str` | Se uma string única for fornecida, é automaticamente convertida em lista `[str]`. |
| `dados_extraidos.exames_laboratoriais` | Sub-modelo [`ItemExameLaboratorial`](../../src/schemas/clinical.py) | Suporte a exames laboratoriais detalhados (`analito`, `valor_medido`, `unidade`, `referencia_impressa`, `alterado`) conforme RF-12. |
| `classificacao.score_classificacao` | `score_confianca_classificacao` | Aceita ambos na carga JSON e sincroniza propriedades. |
| `decisao_roteamento.notificacao` | `notificacao_gerada` | Aceita ambos os campos. |

---

## 4. Contrato de Erro em Dois Níveis

O MediFlow separa formalmente os erros em dois níveis de ciclo de vida:

```text
Entrada de Documento
       │
       ├─► [Nível 1] Falha Pré-Processamento (MIME, Tamanho, Envelope)
       │             └─► Retorna ErroResposta (HTTP 4xx / Erro Técnico)
       │
       └─► [Nível 2] Falha de Leitura / Parsing (PDF Protegido / Corrompido)
                     └─► Retorna TriagemMediFlow (status=ERRO_PROCESSAMENTO)
```

| Nível de Erro | Formato Retornado | Quando Ocorre | Exemplos nos Fixtures |
| :--- | :--- | :--- | :--- |
| **Nível 1: Requisição Inválida (HTTP)** | `ErroResposta {http, codigo_funcional, mensagem}` | O documento é rejeitado no portão de entrada antes de entrar na esteira clínica. | Os 8 fixtures `Validacao_*` (arquivo corrompido, tamanho > 10MB, mime não suportado). |
| **Nível 2: Erro de Leitura/Processamento** | `TriagemMediFlow {status=ERRO_PROCESSAMENTO, erro={codigo, mensagem}}` | O arquivo foi aceito pelo gateway, mas sua leitura técnica falhou internamente. | `Qualidade_Pdf_ComSenha` (`PDF_PROTEGIDO`), `Qualidade_Pdf_Corrompido` (`PDF_CORROMPIDO`). |

### Exemplo JSON de Nível 1 (`ErroResposta`):
```jsonc
{
  "http": 413,
  "codigo_funcional": "ARQUIVO_MAIOR_QUE_LIMITE",
  "mensagem": "O arquivo possui 10.50MB, excedendo o limite de 10.00MB."
}
```

### Exemplo JSON de Nível 2 (`TriagemMediFlow` com `status=ERRO_PROCESSAMENTO`):
```jsonc
{
  "status": "ERRO_PROCESSAMENTO",
  "documento_id": "DOC-9B8A7C6D",
  "classificacao": null,
  "dados_extraidos": null,
  "qualidade": null,
  "decisao_roteamento": null,
  "armazenamento_oci": null,
  "erro": {
    "codigo": "PDF_PROTEGIDO",
    "mensagem": "O documento PDF está protegido por senha e não pôde ser aberto."
  }
}
```

---

## 5. Regras Oficiais de Decisão Clínica (R1 a R8)

As regras são aplicadas deterministicamente no modelo de validação:

| Regra | Condição Clínica | Ação e Efeito no Payload |
| :--- | :--- | :--- |
| **R1** | `nivel_prioridade == URGENTE` | Adiciona `FILA_URGENCIA_MEDICA` + gera `notificacao` + status `PROCESSADO`. **Urgência isolada NÃO gera revisão humana** (`requer_auditoria_humana = False`). |
| **R2** | **Ambiguidade ou Incerteza Detectada**: campo obrigatório ausente **ou** campo incerto **ou** conflito impeditivo (`ALTA`/`MEDIA`) **ou** `score_combinado < limiar` (0.85) **ou** tipo `OUTRO`/`NAO_IDENTIFICADO` **ou** prioridade `NAO_IDENTIFICADA` **ou** urgência `INDETERMINADO` | Aciona **Revisão Humana Obrigatória** (`requer_auditoria_humana = True`). |
| **R3** | Ambiguidade **SEM** urgência | Destino é **substituído** por `FILA_REVISAO_HUMANA` e status passa a `EM_REVISAO`. |
| **R4** | Ambiguidade **COM** urgência (Caso Misto) | Mantém `FILA_URGENCIA_MEDICA` e **acrescenta** `FILA_REVISAO_HUMANA`. Status é `EM_REVISAO` e `requer_auditoria_humana = True`. |
| **R5** | Cálculo do Score Combinado | `score_combinado = min(score_classificacao, score_extracao)`. Se `< 0.85`, aciona R2. |
| **R6** | Escopo dos Campos Obrigatórios (RF-21) | Apenas os 5 obrigatórios (`paciente.nome`, `paciente.idade`, `medico.nome`, `medico.crm`, `diagnostico`) forçam revisão. CID, medicamentos ou exames ausentes são registrados em qualidade, mas não bloqueiam. |
| **R7** | Falha de Leitura Técnica | Status `ERRO_PROCESSAMENTO`, preenche bloco `erro` e anula blocos clínicos. |
| **R8** | Conflitos de Gravidade Baixa | Conflitos com `gravidade == BAIXA` são registrados para auditoria, mas **não** são impeditivos e não geram revisão humana isoladamente. |

**Campos Obrigatórios Auditados (RF-21):**
`paciente.nome`, `paciente.idade`, `medico.nome`, `medico.crm`, `diagnostico`.

---

### 5.1 A Urgência Clínica Explicada

**Urgência isolada não é ambiguidade, e por isso não gera revisão humana.**  
Um documento urgente perfeitamente legível e estruturado termina em `PROCESSADO`, com `requer_auditoria_humana = False`, um único destino (`FILA_URGENCIA_MEDICA`) e o alerta registrado no canal de urgência médica.

Essa decisão segue estritamente o exemplo do edital oficial (`Projeto_oracle.pdf`), no qual uma prescrição de emergência é gravada diretamente na pasta `processados/urgentes/` com `"status": "processado"` e `"requer_auditoria_humana": false`.

A `FILA_REVISAO_HUMANA` só é acionada em documentos urgentes quando há **ambiguidade concomitante** (Regra R4):
- Exemplo: Guia de emergência ilegível, com CRM ausente ou dose suspeita. Nesse cenário misto, o destino é duplo (`["FILA_URGENCIA_MEDICA", "FILA_REVISAO_HUMANA"]`) para permitir atendimento médico rápido com auditoria paralela.

---

### 5.2 Por que o Validador não deduz arbitrariamente "campo ausente"

No ecossistema clínico, a ausência de um campo pode ser legítima ou não, dependendo da tipologia:
- Um `LAUDO_EXAME_LABORATORIAL` frequentemente possui `diagnostico: null` de forma válida, terminando em `PROCESSADO`.
- Uma receita ou guia sem diagnóstico (`Ausencia_Diagnostico`) configura incompletude e termina em `EM_REVISAO`.

O validador respeita a lista `qualidade.campos_ausentes` produzida pelo pipeline de extração. O sistema audita se os campos ausentes informados pertencem aos obrigatórios do RF-21, evitando falsos positivos.

---

### 5.3 Decisões Clínicas Incorporadas ao Contrato (A1 a A5)

| Identificador | Regra Clínica | Implementação no Código |
| :--- | :--- | :--- |
| **A1** | Gravidades impeditivas: apenas conflitos de gravidade `ALTA` ou `MEDIA` bloqueiam a triagem para revisão humana. Conflitos `BAIXA` são não-impeditivos. | Constante `GRAVIDADES_IMPEDITIVAS = {Gravidade.ALTA, Gravidade.MEDIA}` em `src/schemas/clinical.py`. |
| **A3** | Cálculo determinístico do `score_extracao`: `score = 1.0 − (0.2 × campos_obrigatórios_ausentes) − (0.1 × campos_incertos) − (0.3 × conflitos_ALTA) − (0.2 × conflitos_MEDIA) − (0.1 × conflitos_BAIXA)`, com piso em `0.0`. | Função `calcular_score_extracao` e pesos `PESO_CONFLITO`. |
| **A4** | `nivel_prioridade == NAO_IDENTIFICADA` constitui ambiguidade clínica e força revisão humana (R2). | Testado no fixture de borda `Borda_Prioridade_NaoIdentificada`. |
| **A5** | `urgencia == INDETERMINADO` é tratado como incerteza crítica e força revisão humana (R2). | Testado no fixture de borda `Borda_Urgencia_Indeterminada`. |

---

### 5.4 Coerência Clínica dos Fixtures

Toda fixture oficial mantém **estrita coerência** entre seus formatos:
- O texto (`.txt`) é a fonte clínica da verdade: o que consta no texto deve refletir no `.json` esperado.
- Dados ausentes no texto são registrados como ausentes (`—`, `não informado`, `não visível`).
- Dados ilegíveis na imagem (`.jpg`) correspondem rigorosamente aos `campos_incertos` daquele caso.
- Todo CRM gerado possui UF válida (`SP`), compatível com o hospital cenário da demonstração.

---

## 6. Formato Canônico de um `expected.json`

Os 79 fixtures de validação do repositório (`tests/fixtures/catalogo_completo/` e `tests/fixtures/demo/`) seguem a estrutura abaixo:

```jsonc
{
  "schema": "mediflow.fixture/2",
  "fixture_id": "Conflito_Dose",
  "documento_ficticio": true,
  "tipo_de_teste": "funcional",              // funcional | erro_processamento | negativo_tecnico
  "entrada": {
    "formatos_disponiveis": ["TXT", "PDF", "JPG"],
    "renditions": {
      "txt": "tests/fixtures/catalogo_completo/Conflito_Dose/Conflito_Dose.txt",
      "pdf": "tests/fixtures/catalogo_completo/Conflito_Dose/Conflito_Dose.pdf",
      "jpg": "tests/fixtures/catalogo_completo/Conflito_Dose/Conflito_Dose.jpg"
    }
  },
  "resposta_esperada": {
    /* Instância de TriagemMediFlow ou ErroResposta */
  },
  "modo_fixture": {
    "score_forcado": {
      "score_classificacao": 0.92,
      "score_extracao": 0.84
    }
  },
  "assercoes": [
    "status == EM_REVISAO",
    "decisao_roteamento.destino_principal == FILA_REVISAO_HUMANA"
  ],
  "observacoes": "Caso de teste com dosagem acima do limite terapêutico padrão."
}
```

- `resposta_esperada`: Payload completo validado diretamente contra o modelo Pydantic v2.
- `modo_fixture`: Presente exclusivamente nos casos de teste de fronteira com score forçado (`Borda_Score_084`, `Borda_Score_085`, `Simultaneo_Urgencia_Score`).
- `tipo_de_teste`: Distingue formalmente testes funcionais, erros de processamento e negativos técnicos.

---

## 7. Verificação e Testes Automatizados (Suíte Pytest)

A conformidade do sistema com este contrato é garantida pela suíte oficial de testes:

```powershell
# Execução completa de todos os testes
python -m pytest

# Execução exclusiva da validação dos 79 fixtures de contrato
python -m pytest tests/test_contrato_fixtures.py

# Execução dos testes de ingestão física e sanitização
python -m pytest tests/test_ingestion.py tests/test_sanitization.py
```

### Status Atual da Suíte (208 testes passando):
- **79 testes de contrato (`test_contrato_fixtures.py`):** 65 funcionais + 2 erros de leitura + 12 negativos técnicos, todos validados e com consistência de ponto fixo.
- **73 testes de motor LangGraph (`test_workflow.py`):** Cobertura determinística de transições de estado, cálculo de regras R1 a R8 e as 5 filas hospitalares.
- **18 testes de ingestão física e segurança (`test_ingestion.py`):** Validação de envelopes, MIME, arquivos corrompidos, PDFs protegidos e fixtures físicos reais (`.pdf`, `.jpg`, `.webp`, rejeição de `.docx` com HTTP 415).
- **16 testes de API REST FastAPI (`test_api.py`):** Endpoints assíncronos (`/api/v1/triagens`), polling de status, histórico de auditoria e conformidade com a EPT (CT-001 a CT-080).
- **8 testes de persistência OCI Object Storage (`test_oci_storage.py`):** Upload Always Free, simulação de SDK, integridade de hash SHA-256 e sem sobrescrita (`if-none-match`).
- **8 testes de auditoria clínica e sanidade (`test_audit_items.py`):** Verificações adicionais de consistência médica e conformidade com o edital.
- **7 testes de schemas harmonizados (`test_schemas.py`):** Validação Pydantic v2, enums resilientes e envelopes de erro Nível 1 e Nível 2.

---

## 8. Histórico de Harmonização do Contrato

| Fase | Origem | Contribuição Principal para o Contrato |
| :--- | :--- | :--- |
| **Fase 1: Rigor Clínico e Fixtures** | William (`CONTRATO_DE_DADOS.md` original) | Criação dos 79 fixtures canônicos, taxonomia estrita dos enums, definição das regras R1 a R8 e alinhamento da urgência com o edital da Oracle. |
| **Fase 2: Expansão de Negócio** | Luciana (`schema_mediflow_v3.py`) | Expansão para suporte a `ItemExameLaboratorial` (RF-12), propriedades de conveniência para API e integração com armazenamento OCI. |
| **Fase 3: Contrato Canônico Unificado** | Repositório Oficial (`src/schemas/clinical.py`) | Fusão completa em Pydantic v2, normalização resiliente via `_missing_`, tratamento de erros em dois níveis, 208 testes Pytest automatizados e consolidação em um único contrato oficial. |
