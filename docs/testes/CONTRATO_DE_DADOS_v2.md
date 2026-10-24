# Contrato de Dados da Triagem — MediFlow v2.0 (Harmonizado)

> **Projeto:** MediFlow — Hackathon ONE G10 (Oracle & Alura)  
> **Status:** Versão Harmonizada para o Repositório Oficial  
> **Referência Original:** `CONTRATO_DE_DADOS.md` (v1.0 dos 79 fixtures - William) + `schema_mediflow_v3.py` (Luciana)  
> **Escopo:** O contrato canônico executável de dados que rege o Agente Gemini, o Workflow LangGraph, o Ingestion Loader, a API FastAPI e as Interfaces (Streamlit/React).

---

## 1. O que é este documento?

Este documento é a **versão harmonizada (v2.0)** do contrato de dados do MediFlow. Ele preserva **100% das regras clínicas, fixtures e rigor técnico** do `CONTRATO_DE_DADOS.md` original, introduzindo apenas as **adaptações de interoperabilidade e resiliência** necessárias para que todas as frentes da equipe trabalhem em conjunto sem conflito.

O contrato responde com precisão:
1. **Qual é o formato da resposta** que o agente devolve para um documento aceito (`TriagemMediFlow`) e para requisições com erro (`ErroResposta` e `ErroProcessamento`).
2. **Quais são os tokens controlados** em cada enum do sistema.
3. **Como a decisão de triagem é calculada** a partir dos fatos clínicos (score, campos obrigatórios, conflitos, prioridade).
4. **Como o sistema se mantém retrocompatível**, permitindo que legados das frentes em desenvolvimento continuem sendo aceitos sem disparar exceções fatais.

---

## 2. Enums Controlados (Fonte Única com Resiliência Automática)

Todos os enums utilizam **tokens puros em caixa alta (sem acentos e sem espaços)** como padrão de saída. Para evitar falhas em chamadas legadas da API ou do frontend, cada Enum implementa o método `_missing_`, que mapeia automaticamente variantes com espaços ou formatos antigos para o token canônico correspondente.

| Enum | Tokens Canônicos Oficiais | Aliases e Compatibilidade Aceitos Automaticamente | Onde aparece |
| :--- | :--- | :--- | :--- |
| `TipoDocumento` | `RECEITUARIO_MEDICO`, `LAUDO_EXAME_LABORATORIAL`, `LAUDO_EXAME_IMAGEM`, `GUIA_PROCEDIMENTO`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO`, `OUTRO`, `NAO_IDENTIFICADO` | `"Laudo de Exame de Imagem"`, `"Receituario Medico"`, `"Guia de Solicitação de Procedimento"`, `"LAUDO_IMAGEM"` | `classificacao.tipo_documento` |
| `NivelPrioridade` | `URGENTE`, `ROTINA`, `NAO_IDENTIFICADA` | `"Urgente"`, `"Rotina"`, `"Pouco_Urgente"` (mapeia para `ROTINA`) | `classificacao.nivel_prioridade` |
| `StatusTriagem` | `RECEBIDO`, `PROCESSANDO`, `PROCESSADO`, `EM_REVISAO`, `ERRO_PROCESSAMENTO`, `ERRO_PERSISTENCIA` | `"processado"`, `"pendente_auditoria"` (mapeia para `EM_REVISAO`) | `status` |
| `Destino` | `FILA_URGENCIA_MEDICA`, `FARMACIA_HOSPITALAR`, `AUDITORIA_AUTORIZACOES`, `PRONTUARIO_ELETRONICO`, `FILA_REVISAO_HUMANA` | `"Fila_Emergencia_Medica"`, `"Farmacia_Hospitalar"`, `"Auditoria_Autorizacoes"`, `"Prontuario_Eletronico"`, `"Fila_Revisao_Humana"` | `decisao_roteamento.destinos` |
| `Urgencia` | `SIM`, `NAO`, `INDETERMINADO` | Aceita strings em maiúsculas/minúsculas | `dados_extraidos.urgencia` |
| `Gravidade` | `ALTA`, `MEDIA`, `BAIXA` | Usado na tipagem de conflitos | `qualidade.conflitos[].gravidade` |
| `CodigoErro` | `FORMATO_NAO_SUPORTADO`, `CAMPOS_INVALIDOS`, `REQUISICAO_INVALIDA`, `ARQUIVO_MAIOR_QUE_LIMITE`, `MIME_INVALIDO`, `PDF_PROTEGIDO`, `PDF_CORROMPIDO` | Alinhado com as exceções de `src/ingestion/loader.py` | `erro.codigo` |

---

## 3. Payload Canônico de Triagem (`TriagemMediFlow`)

Este é o formato canônico gerado pela triagem:

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

### 3.1. Adaptações e Aliases de Retrocompatibilidade

Para garantir que o código existente no backend, frontend e nos testes continue funcionando sem quebra:

| Campo Canônico | Alias / Propriedade de Compatibilidade Aceita | Descrição da Adaptação |
| :--- | :--- | :--- |
| `dados_extraidos.medico` | `dados_extraidos.medico_solicitante` | Permite acessar tanto `.medico` quanto `.medico_solicitante`. |
| `medico.crm` | `medico.crm.numero` ou `medico.crm: str` | Se for passado CRM como string (ex: `"145892-SP"`), um validador converte automaticamente para o objeto `Crm(numero="145892", uf="SP")`. |
| `dados_extraidos.diagnostico` | `dados_extraidos.diagnostico_principal` | Acesso transparente para os dois nomes. |
| `dados_extraidos.cid` | `dados_extraidos.cid_extraido` / `cid_sugerido` | Acesso transparente para os dois nomes. |
| `dados_extraidos.exames` | `dados_extraidos.exame_ou_procedimento` | Se for passada string única, ela é automaticamente encapsulada em uma lista. |
| `dados_extraidos.exames_laboratoriais` | Sub-modelo `ItemExameLaboratorial` | Suporte dedicado a parâmetros laboratoriais (`analito`, `valor_medido`, `unidade`, `referencia_impressa`, `alterado`) conforme RF-12 e schema v3. |
| `classificacao.score_classificacao` | `score_confianca_classificacao` | Aceita ambos na inicialização e expõe propriedades sincronizadas. |
| `decisao_roteamento.notificacao` | `notificacao_gerada` | Aceita ambos os formatos. |

---

## 4. Contrato de Erro Padronizado

O contrato distingue com clareza os dois níveis de erro:

### 4.1. Nível 1: Erro de Requisição HTTP (`ErroResposta`)
Ocorre **antes** de o documento entrar na triagem (envelope inválido, tamanho excedido, formato não suportado):
```jsonc
{
  "http": 413,
  "codigo_funcional": "ARQUIVO_MAIOR_QUE_LIMITE",
  "mensagem": "O arquivo possui 22.40MB, excedendo o limite seguro de 20.00MB."
}
```

### 4.2. Nível 2: Erro de Leitura do Documento (`TriagemMediFlow` com `status=ERRO_PROCESSAMENTO`)
Ocorre quando o arquivo foi aceito, mas não pôde ser lido (ex: PDF protegido com senha ou corrompido):
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

## 5. Regras Oficiais de Decisão (R1 a R8)

As regras abaixo são executadas de forma determinística pelo `@model_validator` do Pydantic:

* **R1 (Urgência)**: `nivel_prioridade == URGENTE` direciona primariamente para `FILA_URGENCIA_MEDICA` e gera a notificação. **Urgência isolada NÃO gera revisão humana** (`status = PROCESSADO`, `requer_auditoria_humana = False`), alinhando-se com o exemplo oficial da Oracle.
* **R2 (Ambiguidade)**: Gera revisão humana obrigatória quando ocorrer qualquer um dos seguintes fatores:
  1. Campo obrigatório ausente (`paciente.nome`, `paciente.idade`, `medico.nome`, `medico.crm`, `diagnostico`).
  2. Qualquer campo listado em `campos_incertos`.
  3. Conflito com gravidade **impeditiva** (`ALTA` ou `MEDIA`).
  4. `score_combinado < limiar_aplicado` (limiar estrito: `0.85`).
  5. `tipo_documento` for `OUTRO` ou `NAO_IDENTIFICADO`.
  6. `nivel_prioridade` for `NAO_IDENTIFICADA`.
  7. `urgencia` declarada como `INDETERMINADO`.
* **R3 (Ambiguidade sem Urgência)**: O destino é substituído integralmente por `FILA_REVISAO_HUMANA`, e o status passa para `EM_REVISAO`.
* **R4 (Ambiguidade com Urgência - Caso Misto)**: O caso mantém `FILA_URGENCIA_MEDICA` e **acrescenta** `FILA_REVISAO_HUMANA`. O status é `EM_REVISAO` e `requer_auditoria_humana = True`.
* **R5 (Score Combinado)**: Calculado como `min(score_classificacao, score_extracao)`. Se `< 0.85`, aciona R2.
* **R6 (Campos Obrigatórios RF-21)**: A ausência de CID, medicamentos ou exames secundários é registrada, mas **não** força revisão humana por si só.
* **R7 (Erro de Leitura)**: Status `ERRO_PROCESSAMENTO`, preenchendo o bloco `erro` e anulando classificação e dados.
* **R8 (Conflitos de Gravidade Baixa)**: Conflitos com `gravidade == BAIXA` são registrados para fins de auditoria, mas **não** são impeditivos e não forçam revisão humana.

---

## 6. Verificação e Testes Automatizados

A conformidade do código com este contrato é garantida pela suíte do `pytest`:

```powershell
python -m pytest
```

Critérios de aceite:
1. Todos os 62 testes atuais devem passar sem regressão.
2. Os fixtures e asserções que validam os contratos e regras de negócio devem produzir o mesmo payload esperado (`expected.json`).
3. Payloads com dados legados devem ser normalizados sem levantar exceção de validação.
