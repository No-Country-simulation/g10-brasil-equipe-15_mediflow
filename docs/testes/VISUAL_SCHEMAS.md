# 📊 Guia Visual dos Schemas e Contratos de Dados — MediFlow

> **Projeto:** MediFlow — Equipe 15 (Hackathon ONE G10 - Oracle & Alura)  
> **Referência Técnica:** [`src/schemas/clinical.py`](../../src/schemas/clinical.py)  
> **Contrato Canônico:** [`docs/testes/CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md)  
> **Validação:** Pydantic v2 com validação estrita, tolerância resiliente via `_missing_` e motor determinístico de regras (R1 a R8).

---

## 1. 🏗️ Diagrama de Classes e Composição (Pydantic v2)

O diagrama abaixo ilustra o modelo raiz [`TriagemMediFlow`](../../src/schemas/clinical.py) e sua hierarquia de agregação e composição de submodelos clínicos:

```mermaid
classDiagram
    direction TB

    class TriagemMediFlow {
        +StatusTriagem status
        +string documento_id
        +string canal_origem
        +Classificacao classificacao
        +DadosExtraidos dados_extraidos
        +Qualidade qualidade
        +DecisaoRoteamento decisao_roteamento
        +ArmazenamentoOCI armazenamento_oci
        +ErroProcessamento erro
        +aplicar_regras() TriagemMediFlow
    }

    class Classificacao {
        +TipoDocumento tipo_documento
        +List~string~ especialidade
        +NivelPrioridade nivel_prioridade
        +float score_classificacao
    }

    class DadosExtraidos {
        +Paciente paciente
        +Medico medico
        +string diagnostico
        +string cid
        +List~string~ exames
        +List~ItemExameLaboratorial~ exames_laboratoriais
        +List~Medicamento~ medicamentos
        +Urgencia urgencia
        +float score_confianca_extracao
        +string achados_criticos
        +List~string~ inconsistencias_detectadas
    }

    class Paciente {
        +string nome
        +int idade
        +string cpf
    }

    class Medico {
        +string nome
        +Crm crm
    }

    class Crm {
        +string numero
        +string uf
    }

    class Medicamento {
        +string nome
        +string dosagem
        +string frequencia
    }

    class ItemExameLaboratorial {
        +string analito
        +string valor_medido
        +string unidade
        +string referencia_impressa
        +bool alterado
    }

    class Qualidade {
        +float score_extracao
        +float score_combinado
        +float limiar_aplicado
        +List~string~ campos_ausentes
        +List~string~ campos_incertos
        +List~Conflito~ conflitos
    }

    class Conflito {
        +string tipo
        +List~string~ campos
        +Gravidade gravidade
        +string descricao
    }

    class DecisaoRoteamento {
        +Destino destino_principal
        +List~Destino~ destinos
        +bool requer_auditoria_humana
        +string justificativa_roteamento
        +Notificacao notificacao
    }

    class Notificacao {
        +bool gerada
        +string canal
        +string mensagem
        +string status
    }

    class ArmazenamentoOCI {
        +string bucket
        +string caminho_objeto
        +string status_backup
    }

    class ErroProcessamento {
        +CodigoErro codigo
        +string mensagem
    }

    class ErroResposta {
        +int http
        +CodigoErro codigo_funcional
        +string mensagem
    }

    %% Relações de Composição do Modelo Principal
    TriagemMediFlow *-- Classificacao : 1..1
    TriagemMediFlow *-- DadosExtraidos : 1..1
    TriagemMediFlow *-- Qualidade : 1..1
    TriagemMediFlow *-- DecisaoRoteamento : 1..1
    TriagemMediFlow *-- ArmazenamentoOCI : 0..1
    TriagemMediFlow *-- ErroProcessamento : 0..1

    %% Relações de Submodelos de Dados Clínicos
    DadosExtraidos *-- Paciente : 1..1
    DadosExtraidos *-- Medico : 1..1
    DadosExtraidos *-- "0..*" Medicamento : medicamentos
    DadosExtraidos *-- "0..*" ItemExameLaboratorial : exames_laboratoriais
    Medico *-- Crm : 1..1

    %% Relações de Qualidade e Decisão
    Qualidade *-- "0..*" Conflito : conflitos
    DecisaoRoteamento *-- "0..1" Notificacao : notificacao
```

---

## 2. 🏷️ Mapa de Enums Controlados e Tokens Canônicos

Todos os enums utilizam **tokens em caixa alta sem acentos nem espaços**, com normalização resiliente automática (`_missing_`):

```mermaid
graph LR
    subgraph ENUMS["Tokens Canônicos Controlados (Enums)"]
        TD["<b>TipoDocumento</b><br/>• RECEITUARIO_MEDICO<br/>• LAUDO_EXAME_LABORATORIAL<br/>• LAUDO_EXAME_IMAGEM<br/>• GUIA_PROCEDIMENTO<br/>• RELATORIO_ALTA_INTERNACAO<br/>• ATESTADO_MEDICO<br/>• OUTRO<br/>• NAO_IDENTIFICADO"]
        
        NP["<b>NivelPrioridade</b><br/>• URGENTE<br/>• ROTINA<br/>• NAO_IDENTIFICADA"]
        
        ST["<b>StatusTriagem</b><br/>• RECEBIDO<br/>• PROCESSANDO<br/>• PROCESSADO<br/>• EM_REVISAO<br/>• ERRO_PROCESSAMENTO<br/>• ERRO_PERSISTENCIA"]
        
        DS["<b>Destino</b><br/>• FILA_URGENCIA_MEDICA<br/>• FARMACIA_HOSPITALAR<br/>• AUDITORIA_AUTORIZACOES<br/>• PRONTUARIO_ELETRONICO<br/>• FILA_REVISAO_HUMANA"]
        
        UG["<b>Urgencia</b><br/>• SIM<br/>• NAO<br/>• INDETERMINADO"]
        
        GV["<b>Gravidade</b><br/>• ALTA<br/>• MEDIA<br/>• BAIXA"]
        
        CE["<b>CodigoErro</b><br/>• FORMATO_NAO_SUPORTADO<br/>• CAMPOS_INVALIDOS<br/>• REQUISICAO_INVALIDA<br/>• ARQUIVO_MAIOR_QUE_LIMITE<br/>• MIME_INVALIDO<br/>• PDF_PROTEGIDO<br/>• PDF_CORROMPIDO<br/>• ERRO_PERSISTENCIA"]
    end

    subgraph SCHEMAS["Modelos Pydantic v2"]
        C["Classificacao"]
        DE["DadosExtraidos"]
        Q["Qualidade / Conflito"]
        DR["DecisaoRoteamento"]
        TMF["TriagemMediFlow"]
        ER["ErroResposta / ErroProcessamento"]
    end

    TD -->|tipo_documento| C
    NP -->|nivel_prioridade| C
    UG -->|urgencia| DE
    GV -->|gravidade| Q
    DS -->|destinos / destino_principal| DR
    ST -->|status| TMF
    CE -->|codigo / codigo_funcional| ER
```

---

## 3. 🔄 Ciclo de Vida e Máquina de Estados da Triagem

O processamento de qualquer documento pelo ecossistema **MediFlow** é governado por uma máquina de estados finita e auditável:

```mermaid
stateDiagram-v2
    [*] --> RECEBIDO: Ingestão via API / Streamlit
    RECEBIDO --> PROCESSANDO: Validação preliminar (Allowlist & Limites A6)
    
    state PROCESSANDO {
        [*] --> SanitizacaoMime: Limite 10.00MB e 20 páginas
        SanitizacaoMime --> ExtracaoMultimodal: Gemini 1.5 + Schemas Canônicos
        ExtracaoMultimodal --> AvaliacaoRegras: Validador Pydantic v2 + LangGraph
        AvaliacaoRegras --> [*]
    }

    PROCESSANDO --> PROCESSADO: Score >= 0.85 & Vitais Presentes
    PROCESSANDO --> EM_REVISAO: Score < 0.85 ou Incerteza / Ausência de Vital
    PROCESSANDO --> ERRO_PROCESSAMENTO: Falha na Leitura (PDF Corrompido / Protegido)
    
    PROCESSADO --> PersistenciaOCI: Salva em /processados (/rotina ou /urgentes)
    EM_REVISAO --> PersistenciaOCI: Salva em /auditoria_humana
    ERRO_PROCESSAMENTO --> [*]: Retorna ErroResposta / ErroProcessamento

    PersistenciaOCI --> [*]: Finalizado com Sucesso
    PersistenciaOCI --> ERRO_PERSISTENCIA: Falha no Upload OCI SDK
    ERRO_PERSISTENCIA --> [*]
```

### Matriz de Transição de Estados

| Estado Origem | Evento / Condição | Estado Destino | Ação / Efeito Colateral |
| :--- | :--- | :--- | :--- |
| `[*]` | Envio via API (`POST /api/v1/triagens`) ou Streamlit | `RECEBIDO` | Emissão de `documento_id`, persistência em `/recebidos` e retorno `HTTP 202 Accepted`. |
| `RECEBIDO` | Início da esteira assíncrona | `PROCESSANDO` | Execução do carregador seguro e sanitização PyMuPDF. |
| `PROCESSANDO` | `score_combinado >= 0.85` e vitais presentes | `PROCESSADO` | Encaminhamento direto para a fila departamental correspondente. |
| `PROCESSANDO` | `score_combinado < 0.85` ou rasura ou vital ausente | `EM_REVISAO` | Retenção obrigatória para auditoria médica (*Human-in-the-Loop*). |
| `PROCESSANDO` | PDF protegido por senha ou corrompido | `ERRO_PROCESSAMENTO` | Geração do envelope `ErroProcessamento` sem invocar IA desnecessariamente. |
| `PROCESSADO` / `EM_REVISAO` | Falha de rede ou timeout com a nuvem Oracle | `ERRO_PERSISTENCIA` | Registro do incidente para retry sem perda de metadados. |

---

## 4. 🧠 Motor de Decisão Clínica Integrado no Schema (`@model_validator`)

O modelo [`TriagemMediFlow`](../../src/schemas/clinical.py) implementa um validador pós-construção (`@model_validator(mode="after")`) que aplica de maneira determinística as regras **R1 a R8**:

```mermaid
flowchart TD
    START(["📄 Entrada Bruta:<br/>Classificacao + DadosExtraidos"]) --> CALC["1. Calcula Score Combinado:<br/><b>score_combinado = min(score_class, score_ext)</b><br/>Limiar canônico: <b>0.85</b>"]

    CALC --> VITAL{"2. Campos Vitais Presentes?<br/>• paciente.nome<br/>• paciente.idade<br/>• medico.nome<br/>• medico.crm<br/>• diagnostico ou exames"}

    VITAL -- ❌ Ausente --> SET_AMB["Registra em campos_ausentes<br/>Define ambiguidade = True"]
    VITAL -- 🟢 Presentes --> QUAL_CHECK{"3. Critérios de Qualidade:<br/>• score_combinado >= 0.85?<br/>• campos_incertos vazio?<br/>• Sem conflitos ALTA/MEDIA?<br/>• Taxonomia válida?"}

    QUAL_CHECK -- ❌ Reprovado --> SET_AMB
    QUAL_CHECK -- 🟢 Aprovado --> URG_CHECK{"4. Urgência Clínica?<br/>Prioridade == URGENTE ou<br/>urgencia == SIM?"}

    %% Caminho de Ambiguidade
    SET_AMB --> AMB_URG{"Urgência Presente?"}
    
    AMB_URG -- 🟢 SIM --> R2["<b>Regra R2 / R4: Urgência com Ambiguidade</b><br/>• Destinos: [FILA_URGENCIA_MEDICA, FILA_REVISAO_HUMANA]<br/>• Status: <b>EM_REVISAO</b><br/>• Notificação de Emergência Gerada"]
    
    AMB_URG -- ❌ NÃO --> R3["<b>Regra R3: Rotina com Ambiguidade</b><br/>• Destinos: [FILA_REVISAO_HUMANA]<br/>• Status: <b>EM_REVISAO</b><br/>• Requer auditoria humana = True"]

    %% Caminho Seguro
    URG_CHECK -- 🟢 SIM --> R1["<b>Regra R1: Urgência Sem Ambiguidade</b><br/>• Destino: [FILA_URGENCIA_MEDICA]<br/>• Status: <b>PROCESSADO</b><br/>• Notificação de Emergência Imediata<br/>• Requer auditoria = False"]

    URG_CHECK -- ❌ NÃO --> R4["<b>Regra R4: Rotina Normal por Tipo</b><br/>• RECEITUARIO_MEDICO -> FARMACIA_HOSPITALAR<br/>• GUIA_PROCEDIMENTO -> AUDITORIA_AUTORIZACOES<br/>• LAUDOS / ATESTADO -> PRONTUARIO_ELETRONICO<br/>• Status: <b>PROCESSADO</b>"]

    style R1 fill:#F8D7DA,stroke:#721C24,stroke-width:2px
    style R2 fill:#FFF3CD,stroke:#856404,stroke-width:2px
    style R3 fill:#FFF3CD,stroke:#856404,stroke-width:2px
    style R4 fill:#D4EDDA,stroke:#155724,stroke-width:2px
```

---

## 5. 🏥 Roteamento Clínico Hospitalar e Alocação OCI

O diagrama a seguir detalha o mapeamento determinístico entre as entidades classificadas e as 5 filas hospitalares canônicas, bem como a segregação de persistência no OCI Object Storage:

```mermaid
flowchart LR
    subgraph ENTRADA["Documento Validado"]
        DOC["TriagemMediFlow<br/>(Classificação & Qualidade)"]
    end

    subgraph MOTOR["Motor de Decisão (LangGraph)"]
        DECISAO{"Avaliação de Destino"}
    end

    subgraph FILAS["As 5 Filas Hospitalares Canônicas"]
        F1["🚨 FILA_URGENCIA_MEDICA<br/><i>Achados críticos / TEP / Emergência</i>"]
        F2["💊 FARMACIA_HOSPITALAR<br/><i>Receituários médicos de rotina</i>"]
        F3["📋 AUDITORIA_AUTORIZACOES<br/><i>Guias TISS/TUSS de procedimentos</i>"]
        F4["📁 PRONTUARIO_ELETRONICO<br/><i>Laudos (Imagem/Lab), Altas e Atestados</i>"]
        F5["🧑‍⚕️ FILA_REVISAO_HUMANA<br/><i>Ambiguidade, rasura, score < 0.85</i>"]
    end

    subgraph OCI["Nuvem Oracle (Always Free)"]
        BUCKET_URG[("processados/urgentes/")]
        BUCKET_ROT[("processados/rotina/")]
        BUCKET_AUD[("auditoria_humana/")]
    end

    DOC --> DECISAO

    DECISAO -- "Urgência Alta Confiança" --> F1
    DECISAO -- "Receituário Rotina" --> F2
    DECISAO -- "Guia Procedimento" --> F3
    DECISAO -- "Laudos / Atestados" --> F4
    DECISAO -- "Score Baixo / Rasura" --> F5
    DECISAO -- "Urgência Ambígua (Caso Misto)" --> F1
    DECISAO -- "Urgência Ambígua (Caso Misto)" --> F5

    F1 --> BUCKET_URG
    F2 --> BUCKET_ROT
    F3 --> BUCKET_ROT
    F4 --> BUCKET_ROT
    F5 --> BUCKET_AUD

    style F1 fill:#F8D7DA,stroke:#721C24,stroke-width:2px
    style F5 fill:#FFF3CD,stroke:#856404,stroke-width:2px
    style F2 fill:#D4EDDA,stroke:#155724,stroke-width:2px
    style F3 fill:#D4EDDA,stroke:#155724,stroke-width:2px
    style F4 fill:#D4EDDA,stroke:#155724,stroke-width:2px
```

---

## 5.1 🧠 Arquitetura de Duplo Fallback do GeminiService (IA Resiliente)

O diagrama a seguir ilustra a blindagem e o fluxo de extração estruturada do [`GeminiService`](../../src/services/gemini_service.py):

```mermaid
flowchart TD
    DocIn["📄 Documento Clínico (Texto / Imagem / PDF)"] --> Shield["🛡️ Prompt Shielding: Delimitador <documento_clinico><br/><i>Tratamento estrito como dado passivo</i>"]
    
    subgraph LLM_RETRY["Camada 1: Redundância de Modelos Modernos da Google"]
        Shield --> Try1["1ª Tentativa: gemini-3.8-flash<br/><i>(Timeout: 15s | temperature=0.0)</i>"]
        Try1 -- "Sucesso" --> ParsePydantic["✅ Validação Estruturada Pydantic v2<br/>(_ClassificacaoDocumentoSchema / _DadosClinicosExtraidosSchema)"]
        Try1 -- "Timeout / Erro 404 / 429" --> Try2["2ª Tentativa: gemini-3.5-flash-lite<br/><i>(Fallback de Modelo Econômico e Leve)</i>"]
        Try2 -- "Sucesso" --> ParsePydantic
    end

    subgraph CLINICAL_FAILSAFE["Camada 2: Fallback Clínico de Segurança (Seção 12 E.F.)"]
        Try2 -- "Falha Total / Sem Conexão / Chave Inválida" --> FailSafe["⚠️ _fallback_classificacao() / _fallback_extracao()<br/><i>tipo_documento = NAO_IDENTIFICADO<br/>score_confianca = 0.0</i>"]
    end

    ParsePydantic --> StateGraph["⚖️ Grafo LangGraph (Roteamento Determinístico)"]
    FailSafe --> RetencaoCompulsoria["🧑‍⚕️ Destino Compulsório: FILA_REVISAO_HUMANA<br/><i>Status: EM_REVISAO (Nenhum paciente é prejudicado)</i>"]

    style DocIn fill:#E1F5FE,stroke:#0288D1,stroke-width:2px
    style Shield fill:#EDE7F6,stroke:#512DA8,stroke-width:2px
    style ParsePydantic fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style FailSafe fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style RetencaoCompulsoria fill:#FFEBEE,stroke:#C62828,stroke-width:2px
```

---

## 6. 📋 Dicionário de Componentes e Modelos

| Modelo | Arquivo | Responsabilidade | Sub-entidades Contidas |
| :--- | :--- | :--- | :--- |
| **`TriagemMediFlow`** | [`clinical.py`](../../src/schemas/clinical.py) | **Root Model (Payload Oficial):** Consolida status, classificações, entidades, qualidade, roteamento e metadados OCI. Executa o validador pós-modelo. | `Classificacao`, `DadosExtraidos`, `Qualidade`, `DecisaoRoteamento`, `ArmazenamentoOCI`, `ErroProcessamento` |
| **`Classificacao`** | [`clinical.py`](../../src/schemas/clinical.py) | Categoria estável do documento, especialidade médica, prioridade clínica e score de confiança (0.0 a 1.0). | `TipoDocumento`, `NivelPrioridade` |
| **`DadosExtraidos`** | [`clinical.py`](../../src/schemas/clinical.py) | Entidades clínicas extraídas pelo Gemini Multimodal com validação de formato e filtros anti-alucinação. | `Paciente`, `Medico`, `Medicamento`, `ItemExameLaboratorial`, `Urgencia` |
| **`Paciente`** | [`clinical.py`](../../src/schemas/clinical.py) | Dados demográficos canônicos: nome, idade (`0 <= idade <= 120`) e CPF sanitizado. | — |
| **`Medico`** | [`clinical.py`](../../src/schemas/clinical.py) | Identificação do profissional solicitante com CRM estruturado e normalizado. | `Crm` (`numero`, `uf`) |
| **`ItemExameLaboratorial`** | [`clinical.py`](../../src/schemas/clinical.py) | **RF-12:** Parâmetros bioquímicos estruturados com analito, valor medido, unidade e sinalizador de alteração. | — |
| **`Medicamento`** | [`clinical.py`](../../src/schemas/clinical.py) | Prescrição farmacêutica contendo nome do fármaco, dosagem e posologia/frequência. | — |
| **`Qualidade`** | [`clinical.py`](../../src/schemas/clinical.py) | Governança de acurácia: score combinado (mínimo entre classificação e extração), limiar (0.85), campos ausentes/incertos e conflitos. | `Conflito` |
| **`Conflito`** | [`clinical.py`](../../src/schemas/clinical.py) | Inconsistências clínicas detectadas (ex: `DOSE_SUSPEITA`, `CRM_INCOMPATIVEL`, `DOCUMENTO_MUTILADO`). | `Gravidade` (`ALTA`, `MEDIA`, `BAIXA`) |
| **`DecisaoRoteamento`** | [`clinical.py`](../../src/schemas/clinical.py) | Resultado do motor clínico: destino principal, lista de filas, flag de auditoria humana, justificativa em linguagem natural e alerta. | `Destino`, `Notificacao` |
| **`ArmazenamentoOCI`** | [`clinical.py`](../../src/schemas/clinical.py) | Metadados de persistência em nuvem Oracle (Always Free): bucket, caminho do objeto e status do backup. | — |
| **`GeminiService`** | [`gemini_service.py`](../../src/services/gemini_service.py) | **Serviço de IA Multimodal:** Orquestra classificação documental e extração com transporte REST, timeout de 15s e duplo fallback seguro. | `_ClassificacaoDocumentoSchema`, `_DadosClinicosExtraidosSchema` |
| **`ErroProcessamento`** | [`clinical.py`](../../src/schemas/clinical.py) | Erros ocorridos durante a leitura de documentos aceitos no pipeline. | `CodigoErro` |
| **`ErroResposta`** | [`clinical.py`](../../src/schemas/clinical.py) | Rejeição HTTP imediata na camada de ingestão (`400`, `413`, `415`). | `CodigoErro` |

---

## 7. 🛡️ Garantias e Regras de Qualidade dos Schemas

1. **Proteção Extra (`extra="ignore"`):** Todos os modelos aceitam payloads com campos adicionais sem quebrar a desserialização, garantindo interoperabilidade entre agentes e versões da API.
2. **Propriedades de Conveniência:** Suporte transparente a nomes legados (`medico_solicitante`, `diagnostico_principal`, `cid_extraido`, `cid_sugerido`, `score_confianca_classificacao`).
3. **Ponto Fixo e Idempotência:** Uma instância de `TriagemMediFlow` revalidada (`TriagemMediFlow.model_validate(obj.model_dump())`) preserva rigorosamente o mesmo estado, sem oscilação de score ou destinos.
4. **Cobertura Integral de Testes:** 100% dos modelos são validados contra os **79 fixtures canônicos** e auditados pelos **245 testes automatizados (100% verde)** em [`tests/test_contrato_fixtures.py`](../../tests/test_contrato_fixtures.py), [`tests/test_schemas.py`](../../tests/test_schemas.py), [`tests/test_workflow.py`](../../tests/test_workflow.py), [`tests/test_ingestion.py`](../../tests/test_ingestion.py), [`tests/test_api.py`](../../tests/test_api.py), [`tests/test_gemini_service.py`](../../tests/test_gemini_service.py), [`tests/test_audit_items.py`](../../tests/test_audit_items.py) e [`tests/test_oci_storage.py`](../../tests/test_oci_storage.py).

