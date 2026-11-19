# 🏥 MediFlow: Arquitetura do Sistema e Especificação Técnica

> **Hackathon ONE G10 — Oracle Next Education & Alura**  
> **Projeto 2:** Agente Autônomo para Triagem, Extração e Roteamento de Documentos Clínicos  
> **Equipe 15:** MediFlow  
> **Manual Oficial de Referência:** `34aa946f-2883-4917-aec1-aae0df0f43d1.pdf`  
> **Implementação Central:** [`src/schemas/clinical.py`](src/schemas/clinical.py) | **Suíte de Testes:** testes automatizados com Pytest; execuções de referência na seção 7

---

## 📌 1. Visão Geral e Contexto da Solução

O **MediFlow** é um agente autônomo inteligente projetado para os setores de **HealthTech, Gestão Hospitalar e Operadoras de Saúde**. Ele automatiza a triagem, a extração estruturada de dados clínicos e o roteamento de documentos heterogêneos (receitas médicas, laudos laboratoriais e de imagem, guias de autorização TISS/TUSS, relatórios de alta e atestados médicos). A solução resolve o problema de atrasos no atendimento emergencial, elimina tarefas manuais repetitivas e reduz custos com glosas hospitalares com estrito rigor regulatório e de segurança.

### 🎯 Matriz de Aderência ao Manual Oficial da Oracle (Projeto 2):

| Requisito do Edital Oracle | Implementação Técnica no MediFlow | Módulo / Código Responsável |
| :--- | :--- | :--- |
| **Ingestão Multimodal (Upload e API REST)** | Suporte a upload de arquivos PDF (digital e escaneado), imagens (JPG, PNG, WEBP) e TXT; integração via API REST com envelopes JSON. Bloqueio estrito de DOCX e outros formatos não suportados (HTTP 415). Limites de segurança: **máximo de 10.00 MB** e **máximo de 20 páginas por documento** (Regra A6). | [`src/ingestion/loader.py`](src/ingestion/loader.py) |
| **Classificação de Tipo Documental** | Classificação automática nas 8 categorias controladas (`RECEITUARIO_MEDICO`, `LAUDO_EXAME_LABORATORIAL`, `LAUDO_EXAME_IMAGEM`, `GUIA_PROCEDIMENTO`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO`, `OUTRO`, `NAO_IDENTIFICADO`). | [`src/agents/`](src/agents/) |
| **Extração Estruturada com LLM Multimodal** | Extração de entidades clínicas via Google Gemini (modelos `gemini-3.8-flash` e `gemini-3.5-flash-lite`) com *Structured Outputs* nativos via Pydantic v2: Paciente, Médico/CRM com UF paulista/nacional, Diagnóstico/CID-10, Medicamentos (nome, dose, frequência), Exames/Analitos laboratoriais (RF-12) e declaração de urgência. Inclui resiliência REST, timeout de 30s e duplo fallback seguro. | [`src/services/gemini_service.py`](src/services/gemini_service.py), [`src/agents/`](src/agents/) & [`src/schemas/clinical.py`](src/schemas/clinical.py) |
| **Grafo de Decisão Condicional (LangGraph)** | Grafo de estados (`StateGraph`) com nós de extração, validação de regras clínicas e arestas condicionais de roteamento para 5 departamentos. | [`src/workflow/`](src/workflow/) |
| **Tratamento de Urgências e Human-in-the-Loop** | Notificação imediata para a equipe de plantão em casos urgentes e retenção obrigatória em fila de auditoria humana (*Human-in-the-Loop*) em caso de ambiguidade, rasura, campo vital ausente ou score $< 0.85$. | [`src/workflow/graph.py`](src/workflow/graph.py) |
| **Persistência OCI Object Storage (Always Free)** | Organização e segregação de arquivos e metadados em buckets gratuitos da nuvem Oracle (`/recebidos`, `/processados/urgentes`, `/processados`, `/auditoria_humana`). | [`src/storage/`](src/storage/) |
| **Demonstração dos 3 Cenários Obrigatórios** | Cobertura comprovada por testes e dados sintéticos: (1) Fluxo Padrão de Rotina, (2) Urgência Médica (TEP Agudo), (3) Caso Ambíguo para Revisão Humana. | [`tests/fixtures/demo/`](tests/fixtures/demo/) |
| **Diferenciais Implementados** | Interface web em Streamlit para Human-in-the-Loop, validação determinística de conflitos clínicos e governança com 79 fixtures oficiais. | [`src/app/`](src/app/), [`src/workflow/graph.py`](src/workflow/graph.py) & [`src/schemas/clinical.py`](src/schemas/clinical.py) |

---

## 🏗️ 2. Diagrama de Arquitetura em Camadas

O MediFlow é estruturado em 5 camadas funcionais desacopladas e auditáveis:

```mermaid
flowchart TD
    subgraph CLIENTS["🖥️ Camada de Interface & Exposição"]
        REACT["⚛️ Portal Web Hospitalar (React SPA)<br/><i>Interface Corporativa de Produção</i>"]
        STREAMLIT["🔬 Bancada de Auditoria Médica (Streamlit)<br/><i>Painel de Testes & Human-in-the-Loop</i>"]
        API_CLI["🌐 Sistemas Hospitalares Externos (HIS / PEP)<br/><i>Integração REST B2B</i>"]
    end

    subgraph API_GATEWAY["⚡ Gateway FastAPI Server (src/api/)"]
        EP_POST["POST /api/v1/triagens<br/>(HTTP 202 Accepted)"]
        EP_GET["GET /api/v1/triagens/{id}<br/>(Polling de Resultados)"]
    end

    subgraph INGESTION["📥 Camada 1: Ingestão & Gateway de Proteção"]
        LOADER["src/ingestion/loader.py<br/>(DocumentLoader & Sanitização)"]
        VAL_RULES{"Validação de Limites:<br/>Tamanho <= 10.00MB?<br/>Páginas <= 20?<br/>MIME suportado?"}
        ERR_GATEWAY["Nível 1: ErroResposta<br/>(HTTP 400 / 413 / 415)"]
    end

    subgraph AI_CORE["🤖 Camada 2: Inteligência Multimodal (Gemini Flash-Lite principal / Flash alternativo)"]
        OCR["Extração de Texto & Mídia<br/>(PyMuPDF + Bytes Multimodais)"]
        LLM["Google Gemini (Flash-Lite principal / Flash alternativo)<br/>(Extração Estruturada Pydantic v2)"]
        SCHEMA["Contrato Canônico Pydantic v2<br/>(src/schemas/clinical.py)"]
    end

    subgraph WORKFLOW["⚖️ Camada 3: Motor de Decisão LangGraph"]
        STATE["GraphState"]
        N_EXTRACT["Nó: Processar Documento"]
        N_EVAL["Nó: Avaliar Qualidade & Regras"]
        COND_DECIDE{"Aresta Condicional:<br/>Score Combinado >= 0.85 &<br/>5 Campos Vitais OK?"}
        
        Q_URG["🚨 Fila de Urgência Médica<br/>(Alerta Plantão + PROCESSADO)"]
        Q_REV["🧑‍⚕️ Fila de Revisão Humana<br/>(Status: EM_REVISAO)"]
        Q_ROT["📁 Prontuário / Farmácia<br/>(Status: PROCESSADO)"]
        Q_MISTO["⚠️ Fila Dupla (Urgência + Revisão)<br/>(Status: EM_REVISAO)"]
    end

    subgraph STORAGE["☁️ Camada 4: Oracle Cloud (OCI Always Free)"]
        OCI_IN[("Bucket OCI: /recebidos<br/>(Mídia original do upload)")]
        OCI_PROC[("Bucket OCI: /processados<br/>(/urgentes e /rotina)")]
        OCI_AUDIT[("Bucket OCI: /auditoria_humana<br/>(Documentos retidos)")]
    end

    REACT -->|Upload & Polling| API_GATEWAY
    STREAMLIT -->|Processamento direto pelo pipeline| LOADER
    API_CLI -->|Integração B2B| API_GATEWAY

    API_GATEWAY -->|Encaminha Documento| LOADER
    LOADER --> VAL_RULES
    VAL_RULES -- "Rejeitado" --> ERR_GATEWAY
    VAL_RULES -- "Aprovado" --> OCI_IN
    VAL_RULES -- "Aprovado" --> OCR
    
    OCR --> LLM
    LLM --> SCHEMA
    SCHEMA --> STATE
    STATE --> N_EXTRACT --> N_EVAL --> COND_DECIDE
    
    COND_DECIDE -- "Score < 0.85 ou Incompleto" --> Q_REV
    COND_DECIDE -- "Score >= 0.85 & Urgente" --> Q_URG
    COND_DECIDE -- "Score >= 0.85 & Rotina" --> Q_ROT
    COND_DECIDE -- "Urgente com Ambiguidade" --> Q_MISTO
    
    Q_URG --> OCI_PROC
    Q_ROT --> OCI_PROC
    Q_REV --> OCI_AUDIT
    Q_MISTO --> OCI_AUDIT
    
    Q_REV -.->|Inspeção da fila lógica de revisão| STREAMLIT
    Q_REV -.->|Consulta do resultado em revisão| REACT
```

O React envia documentos e consulta resultados pela API FastAPI. A bancada Streamlit executa o pipeline diretamente no processo Python. No MVP, a revisão humana é uma fila lógica para inspeção dos resultados. Aprovação, rejeição e correção interativa ficam fora do escopo.

---

## 🧩 3. Detalhamento das 5 Camadas de Engenharia

### 3.1 Camada 1: Ingestão, Validação e Gateway (`src/ingestion/`)
- **Objetivo:** Blindar a esteira de processamento contra ataques, custos desnecessários com tokens de IA e falhas de leitura.
- **Regras Executadas:**
  - **Tamanho Máximo:** Rejeição imediata de arquivos $> 10.00\text{ MB}$ com HTTP 413 `ARQUIVO_MAIOR_QUE_LIMITE`.
  - **Limite de Páginas:** Rejeição de PDFs com mais de 20 páginas (HTTP 413).
  - **Formatos Aceitos para Upload (Allowlist A6):** `.pdf` (digital e digitalizado), `.txt` e imagens (`.jpg`, `.jpeg`, `.png`, `.webp`).
  - **Integração via API REST:** Envelopes estruturados em `JSON` contendo o payload e texto clínico.
  - **Formatos Bloqueados no Gateway (Negativos Técnicos):** Rejeição imediata com `HTTP 415 FORMATO_NAO_SUPORTADO` para arquivos `.docx`, `.zip`, executáveis ou qualquer extensão fora do allowlist (comprovado pelo teste e fixture `Validacao_ArquivoDocx.docx`).
  - **Tratamento Precoce de Falhas:** Detecção imediata de PDFs com senha (`PDF_PROTEGIDO`) e PDFs ilegíveis/corrompidos (`PDF_CORROMPIDO`), emitindo contratos de erro sem executar inferência.

### 3.2 Camada 2: Inteligência Multimodal e Schemas (`src/services/`, `src/agents/` e `src/schemas/`)
- **Objetivo:** Compreender visualmente o documento e estruturar os dados clínicos com determinismo absoluto e tolerância a falhas.
- **Componentes:**
  - **Serviço Central GeminiService ([`src/services/gemini_service.py`](src/services/gemini_service.py)):**
    - **Protocolo de Rede Resiliente:** Configurado com `genai.configure(transport="rest")` para evitar problemas de socket/gRPC no ambiente Windows.
    - **Timeout Restrito (30s):** Limita as requisições com `request_options={"timeout": 30.0}` para garantir previsibilidade sem travar o pipeline.
    - **Saídas Estruturadas Nativas (Pydantic v2):** Utiliza `response_mime_type: "application/json"` validado com `ClassificacaoDocumento` e `DadosClinicosExtraidos`, garantindo validação rigorosa sem alucinação de formato.
    - **Defesa Contra Prompt Injection:** Todo conteúdo documental é envolvido nas tags `<documento_clinico>` e interpretado estritamente como dado passivo.
    - **Duplo Fallback de Alta Disponibilidade:**
      1. *Fallback de Modelos:* Tenta primeiro `gemini-3.5-flash-lite` e, em caso de falha, tenta `gemini-3.8-flash`.
      2. *Fallback Clínico (Fail-Safe Seção 12 da E.F. v1.0):* Se houver falha total ou ausência de chave de API, gera `ClassificacaoDocumento(tipo_documento=NAO_IDENTIFICADO, score=0.0)`, desviando o documento para `FILA_REVISAO_HUMANA` sem quebrar a API.
  - **Contrato Canônico Pydantic v2 ([`src/schemas/clinical.py`](src/schemas/clinical.py)):** Modelo de dados unificado com validação estrita de tokens, enums resilientes via `_missing_` e suporte a submodelos dedicados (`Paciente`, `Medico`, `Crm`, `ItemExameLaboratorial`, `ConflitoQualidade`).

### 3.3 Camada 3: Motor de Decisão LangGraph (`src/workflow/`)
- **Objetivo:** Garantir a governança do fluxo de decisão de forma auditável e não probabilística.
- **Componentes:**
  - `GraphState`: Estado compartilhado contendo dados brutos, entidades extraídas, qualidade e decisões.
  - **Avaliação de Qualidade e Regras Clínicas** ([`src/workflow/graph.py`](src/workflow/graph.py) e [`src/schemas/clinical.py`](src/schemas/clinical.py)): Motor determinístico que avalia conflitos clínicos reportados na extração, campos obrigatórios e inconsistências cadastrais.
  - `Arestas Condicionais`: Decisão matemática entre os 5 destinos do edital.

### 3.4 Camada 4: Armazenamento OCI Always Free (`src/storage/`)
- **Objetivo:** Persistência em nuvem segura em conformidade com as diretrizes do edital da Oracle.
- **Configuração OCI:** O bucket é definido por `OCI_BUCKET_NAME`. Nas validações reais registradas pela equipe, foi utilizado `mediflow-documentos`. A configuração e os custos dos recursos da publicação devem ser conferidos no ambiente da entrega.

### 3.5 Camada 5: Apresentação e Integração — React via API e Streamlit direto
A camada de apresentação do MediFlow adota a **Estratégia Dual**, garantindo aderência total ao edital da Oracle e maturidade de engenharia corporativa:

- **Portal Web Corporativo (React SPA — Giovane):**
  - Frontend moderno em React (Single Page Application) desenvolvido para ambiente de produção hospitalar.
  - Interface rica com upload *drag-and-drop*, dashboards de produtividade médica, renderização em alta resolução de laudos e receitas, e tela avançada de triagem clínica.
  - Opera de forma 100% desacoplada, consumindo a API REST assíncrona via HTTP/JSON.

- **Bancada de Triagem & Auditoria Médica (Streamlit — `src/app/streamlit_app.py`):**
  - Painel visual interativo em Python que atende ao diferencial oficial do checklist da Oracle (*"Painel de Auditoria Human-in-the-Loop em Streamlit"*).
  - Funciona como bancada operacional de testes rápidos para a equipe de engenharia e auditores médicos, permitindo inspecionar o JSON estruturado lado a lado com a mídia original.

- **FastAPI REST Gateway Assíncrono (`src/api/`):**
  - Servidor backend padronizado com documentação OpenAPI/Swagger interativa automática (`/docs`).
  - Responde com `HTTP 202 Accepted` nas submissões assíncronas e executa o processamento em background. O React consome a API por HTTP/JSON. A bancada Streamlit chama o pipeline diretamente.
  - **Especificação dos Endpoints Oficiais (`/api/v1`):**
    - `POST /api/v1/triagens`: Recebe payloads em JSON (`CriarTriagemTextoRequest`) ou `multipart/form-data` (arquivos até 10MB/20 páginas). Valida integridade e retorna imediatamente `HTTP 202 Accepted` contendo `documento_id`, `status: "RECEBIDO"`, `status_url` e `historico_url`.
    - `GET /api/v1/triagens/{id}`: Retorna o modelo canônico completo [`TriagemMediFlow`](src/schemas/clinical.py) enriquecido com o roteamento do LangGraph e metadados OCI.
    - `GET /api/v1/triagens/{id}/status`: Retorna o status (`RECEBIDO`, `PROCESSANDO`, `PROCESSADO`, `EM_REVISAO`, `ERRO_PROCESSAMENTO` ou `ERRO_PERSISTENCIA`), os destinos, a indicação de revisão humana e o campo `concluido` para controlar o polling.
    - `GET /api/v1/triagens/{id}/historico`: Linha do tempo auditável de eventos emitidos durante o ciclo de vida do documento (ingestão, extração, roteamento LangGraph e OCI).
    - `GET /api/v1/health`: Endpoint de sanidade e liveness probe para orquestradores de contêiner e monitoramento hospitalar.
  - **Blindagem Contra Falhas e Segurança:**
    - Erros de validação HTTP 400, 413, 415 e 422 mapeados para envelopes controlados [`ErroResposta`](src/schemas/clinical.py).
    - Exception handlers globais protegem contra vazamento de stack traces e dados sensíveis (CT-080 da EPT).
    - Decodificação resiliente com suporte automático a UTF-8, Windows-1252 e Latin-1 para terminais hospitalares heterogêneos.
  - **Delimitação de Escopo do MVP (Critério 15):**
    - A fila de trabalho e o histórico em execução no backend (`TriagemService`) operam em memória RAM durante a vida do processo (sem continuidade automática entre reinícios do servidor), enquanto os artefatos originais e os resultados JSON confirmados são persistidos no OCI Object Storage.
    - O projeto não inclui motor de OCR local offline (como Tesseract): PDFs com camada textual utilizam PyMuPDF, enquanto imagens e PDFs digitalizados dependem da análise multimodal via `GeminiService`.

---

## ⚖️ 4. O Grafo de Decisão Clínica (LangGraph) e Ciclo de Vida

### 4.1 Máquina de Estados e Ciclo de Vida da Triagem

O ciclo de vida de qualquer documento processado pelo **MediFlow** transita de forma estrita e rastreável pelos estados controlados pelo enum `StatusTriagem`:

```mermaid
stateDiagram-v2
    [*] --> RECEBIDO: Upload via API / Streamlit
    RECEBIDO --> PROCESSANDO: Ingestão validada & início do pipeline
    
    state PROCESSANDO {
        [*] --> IngestaoSanitizacao: Validação 10MB / 20 págs / MIME
        IngestaoSanitizacao --> ExtracaoMultimodal: Gemini (Flash-Lite principal / Flash alternativo) + Schemas
        ExtracaoMultimodal --> AvaliacaoRegras: Pydantic v2 & LangGraph
        AvaliacaoRegras --> [*]
    }

    PROCESSANDO --> PROCESSADO: Score >= 0.85 & Vitais Presentes
    PROCESSANDO --> EM_REVISAO: Score < 0.85 ou Incerteza / Ausência de Vital
    PROCESSANDO --> ERRO_PROCESSAMENTO: Falha de Leitura / PDF Corrompido / Senha
    
    PROCESSADO --> PersistenciaOCI: Salva em /processados (/rotina ou /urgentes)
    EM_REVISAO --> PersistenciaOCI: Salva em /auditoria_humana
    ERRO_PROCESSAMENTO --> [*]: Retorna ErroResposta / ErroProcessamento

    PersistenciaOCI --> [*]: Fim do Pipeline
    PersistenciaOCI --> ERRO_PERSISTENCIA: Falha no Upload OCI SDK
    ERRO_PERSISTENCIA --> [*]
```

### 4.2 O Grafo de Decisão Clínica (LangGraph)

O LangGraph avalia a qualidade antes de decidir o destino. O score combinado é comparado ao limiar configurado para a execução, cujo valor padrão é `0.85`.

```mermaid
graph TD
    Start(["Início da Triagem"]) --> NodeExtract["Extração e validação Pydantic"]
    NodeExtract --> NodeRules["Avaliar qualidade e registrar motivos de revisão<br/>Campos obrigatórios ausentes, campos ou sinais incertos,<br/>conflitos impeditivos, sinais contraditórios,<br/>score abaixo do limiar ou tipo que exige revisão"]
    NodeRules --> CondUrgencia{"Há sinal estruturado de urgência?"}
    CondUrgencia -- "Sim" --> RevisaoUrgente{"Há motivos de revisão?"}
    RevisaoUrgente -- "Sim" --> NodeMisto["FILA_URGENCIA_MEDICA + FILA_REVISAO_HUMANA<br/>Alerta simulado"]
    RevisaoUrgente -- "Não" --> NodeUrgencia["FILA_URGENCIA_MEDICA<br/>Alerta simulado"]
    CondUrgencia -- "Não" --> RevisaoRotina{"Há motivos de revisão?"}
    RevisaoRotina -- "Sim" --> NodeRevisao["FILA_REVISAO_HUMANA"]
    RevisaoRotina -- "Não" --> CondTipo{"Qual é o tipo documental?"}
    CondTipo -- "RECEITUARIO_MEDICO" --> NodeFarmacia["FARMACIA_HOSPITALAR"]
    CondTipo -- "GUIA_PROCEDIMENTO" --> NodeAuditoria["AUDITORIA_AUTORIZACOES"]
    CondTipo -- "Demais tipos de rotina mapeados" --> NodeProntuario["PRONTUARIO_ELETRONICO"]
    NodeMisto --> EndNode(["Decisão calculada"])
    NodeUrgencia --> EndNode
    NodeRevisao --> EndNode
    NodeFarmacia --> EndNode
    NodeAuditoria --> EndNode
    NodeProntuario --> EndNode
```

### 4.3 As 8 Regras Clínicas Determinísticas de Roteamento (R1 a R8):

1. **Regra R1 (Urgência com Alta Confiança):**  
   Urgência bem documentada (`prioridade == URGENTE` ou `urgencia == SIM`), score combinado $\ge 0.85$ e campos vitais completos.  
   ➔ **Destino:** `[FILA_URGENCIA_MEDICA]`, **Status:** `PROCESSADO`, **Auditoria Humana:** `False`, com emissão de alerta imediato.
2. **Regra R2 (Rotina de Alta Confiança - Roteamento por Tipo Documental):**  
   Score combinado $\ge 0.85$, sem pendências vitais e sem urgência.  
   ➔ `RECEITUARIO_MEDICO` $\rightarrow$ `[FARMACIA_HOSPITALAR]`  
   ➔ `GUIA_PROCEDIMENTO` $\rightarrow$ `[AUDITORIA_AUTORIZACOES]`  
   ➔ `LAUDO_EXAME_IMAGEM`, `LAUDO_EXAME_LABORATORIAL`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO` $\rightarrow$ `[PRONTUARIO_ELETRONICO]`  
   ➔ **Status:** `PROCESSADO`, **Auditoria Humana:** `False`.
3. **Regra R3 (Score Baixo ou Conflitos Impeditivos):**  
   Score combinado $< 0.85$, campos incertos presentes ou conflitos de gravidade `ALTA` ou `MEDIA` (ex.: sobredosagem medicamentosa, CRM inválido).  
   ➔ **Destino:** `[FILA_REVISAO_HUMANA]`, **Status:** `EM_REVISAO`, **Auditoria Humana:** `True`.
4. **Regra R4 (Casos Mistos - Urgência com Ambiguidade ou Ilegibilidade):**  
   Urgência clínica combinada com score baixo, dados truncados ou rasura.  
   ➔ **Destinos Duplos:** `[FILA_URGENCIA_MEDICA, FILA_REVISAO_HUMANA]`, **Status:** `EM_REVISAO`, **Auditoria Humana:** `True`, com disparo de alerta de emergência simultâneo.
5. **Regra R5 (Fórmula Canônica do Score Combinado):**  
   `score_combinado = min(score_classificacao, score_extracao)`  
   As penalidades determinísticas de qualidade (conflitos ALTA: `-0.30`, MEDIA: `-0.20`, BAIXA: `-0.10`, vitais ausentes: `-0.20` e incertezas: `-0.10`) são abatidas no cálculo prévio do `score_extracao` (com piso em `0.0`). Se `score_combinado < 0.85`, a revisão humana é acionada.
6. **Regra R6 (Trava de Segurança dos 5 Campos Vitais - RF-21):**  
   Campos vitais obrigatórios: `paciente.nome`, `paciente.idade`, `medico.nome`, `medico.crm`, `diagnostico` (ou analitos laboratoriais). A ausência de qualquer um deles retém o documento compulsoriamente em `EM_REVISAO`.
7. **Regra R7 (Documentos Não Classificados ou Fora de Escopo):**  
   Tipos `OUTRO`, `NAO_IDENTIFICADO` ou sem mapeamento departamental direto.  
   ➔ **Destino:** `[FILA_REVISAO_HUMANA]`, **Status:** `EM_REVISAO`, **Auditoria Humana:** `True`.
8. **Regra R8 (Garantia de Idempotência e Ponto Fixo):**  
   A revalidação sucessiva de qualquer payload (`TriagemMediFlow.model_validate(obj.model_dump())`) preserva exatamente o mesmo estado, sem oscilações de scores, destinos ou flags.

---

## 📋 5. O Contrato Canônico de Dados (`TriagemMediFlow`)

Exemplo ilustrativo de uma triagem urgente sem pendências, com alerta simulado e persistência confirmada. Os valores representam um cenário fictício; o contrato é definido em `src/schemas/clinical.py`.

```json
{
  "status": "PROCESSADO",
  "documento_id": "DOC-CLIN-2026-8F31A92B",
  "classificacao": {
    "tipo_documento": "LAUDO_EXAME_IMAGEM",
    "especialidade": ["Radiologia", "Pneumologia"],
    "nivel_prioridade": "URGENTE",
    "score_classificacao": 0.99
  },
  "dados_extraidos": {
    "paciente": {
      "nome": "Carlos Eduardo Mendes",
      "idade": 52,
      "cpf": null
    },
    "medico": {
      "nome": "Dra. Renata Silveira",
      "crm": {
        "numero": "145892",
        "uf": "SP"
      }
    },
    "diagnostico": "Tromboembolismo Pulmonar Agudo (TEP)",
    "cid": "I26.9",
    "exames": ["Tomografia de Tórax com contraste"],
    "medicamentos": [],
    "urgencia": "SIM"
  },
  "qualidade": {
    "score_extracao": 0.98,
    "score_combinado": 0.98,
    "limiar_aplicado": 0.85,
    "campos_ausentes": [],
    "campos_incertos": [],
    "conflitos": []
  },
  "decisao_roteamento": {
    "destino_principal": "FILA_URGENCIA_MEDICA",
    "destinos": ["FILA_URGENCIA_MEDICA"],
    "requer_auditoria_humana": false,
    "justificativa_roteamento": "Achado crítico de alta gravidade (TEP agudo) detectado em paciente sintomático.",
    "notificacao": {
      "gerada": true,
      "canal": "SIMULADO_SLACK_PLANTAO",
      "mensagem": "ALERTA URGENTE [DOC-CLIN-2026-8F31A92B]: Tromboembolismo Pulmonar Agudo (TEP)",
      "status": "REGISTRADA"
    }
  },
  "armazenamento_oci": {
    "bucket": "mediflow-documentos",
    "caminho_objeto": "processados/urgentes/DOC-CLIN-2026-8F31A92B/resultado.json",
    "status_backup": "sucesso",
    "modo_simulacao": false
  },
  "erro": null
}
```

---

## ☁️ 6. Topologia de Armazenamento OCI (Always Free)

A persistência em nuvem é operada pelo conector [`src/storage/oci_storage.py`](src/storage/oci_storage.py), construído sobre o SDK oficial da Oracle Cloud (`oci.object_storage.ObjectStorageClient`). O conector aplica:
- **Proteção contra sobrescrita:** Header `if-none-match: *` em `enviar_bytes()` para garantir idempotência e impedir perda de dados.
- **Validação de tipos e tamanho:** Tratamento de buffers binários com `content_type` apropriado.
- **Paginação de listagem:** Itera todas as páginas usando cursor (`next_start_with`).
- **Resiliência a falhas (`ERRO_PERSISTENCIA`):** Se a chamada OCI falhar por indisponibilidade temporária de rede ou quota, o sistema registra `CodigoErro.ERRO_PERSISTENCIA` preservando integralmente em memória a decisão clínica e as métricas calculadas pelo LangGraph (RF-28 / RF-30).
- **Simulação do Catálogo EPT v1.0 (§12):** Gatilhos controlados via nome de arquivo ou metadado (`Simulacao_OciFalhaNoOriginal` -> ServiceError 503; `Simulacao_OciFalhaNoResultado` -> ServiceError 507) permitem homologar a resiliência em pipelines fechados de CI/CD sem depender de conectividade real com a nuvem da Oracle.
- **Tratamento de 412 na Retentativa (Preservação do Original):** Quando a falha ocorre apenas na Etapa 2 (resultado JSON) e a Etapa 1 (original) já havia sido salva, a retentativa via `/reprocessar-persistencia` recebe HTTP 412 (*PreconditionFailed* do `if_none_match="*"`). O sistema identifica que o arquivo original está seguro e avança diretamente para gravar o JSON pendente, sem sobrescrever o original.
- **Bloqueio Estrito de Falso Sucesso:** Em documentos reais (fora do modo de simulação), o sistema só confirma `PROCESSADO` e `status_backup="sucesso"` se o conector OCI estiver de fato configurado e a gravação for confirmada pelo bucket. Sem conector, a retentativa falha com erro seguro 502/ERRO_PERSISTENCIA, evitando falsos positivos no prontuário.
- **Preservação Soberana da Justificativa do LangGraph:** A justificativa clínica gerada pelo agente analítico é mantida integralmente no contrato Pydantic `TriagemMediFlow`, prevenindo que validações pós-construção substituam o raciocínio clínico por mensagens genéricas.

A segregação dos documentos no bucket `mediflow-documentos` obedece à hierarquia abaixo:

```text
mediflow-documentos/
├── recebidos/
│   └── {documento_id}/
│       └── original.{ext}
├── processados/
│   ├── {documento_id}/
│   │   └── resultado.json
│   └── urgentes/
│       └── {documento_id}/
│           └── resultado.json
├── auditoria_humana/
│   └── {documento_id}/
│       └── resultado.json
└── historico/
    └── {documento_id}/
        └── {evento_id}.json
```

---

## 🧪 7. Engenharia de Qualidade e Testes Automatizados

Os testes automatizados cobrem contratos, ingestão, extração, roteamento, API e persistência. A quantidade de casos varia conforme o commit e as suítes selecionadas. Cada evidência deve identificar a versão testada, o comando executado e o resultado.

| Área | Cobertura |
| :--- | :--- |
| Workflow | Qualidade, campos obrigatórios, urgência, revisão humana, justificativas e destinos. |
| Contratos e fixtures | Validação Pydantic, serialização e coerência das respostas esperadas. |
| API | Submissão assíncrona, validações de entrada, status, resultado, histórico e tratamento de erros. |
| Ingestão | Formatos aceitos, limites de tamanho e páginas, arquivos protegidos, vazios e corrompidos. |
| Gemini e adaptadores | Respostas simuladas, normalização, preservação dos dados e tratamento de falhas. |
| OCI | Escrita e leitura com cliente de teste, integridade, idempotência, prefixos e retentativa. |
| Streamlit | Pipeline, indicadores de qualidade e persistência com mensagens públicas seguras. |

### Execuções de referência

- Revisão integrada do PR #26: **220 testes aprovados e 1 pulado**, na combinação local do commit `5ad3865` com a `develop` no `54eac2b`. Foram executadas as suítes de persistência Streamlit, indicadores de qualidade, pipeline Streamlit, API, histórico OCI, workflow e ingestão.
- Frontend React: **298 testes aprovados em 25 arquivos**, no commit `18b234b8`, com 2 workers.

Essas execuções correspondem às versões e aos conjuntos de testes indicados. Os resultados da versão publicada devem ser registrados com o SHA da entrega.

Os testes com respostas simuladas verificam contratos e regras. As chamadas com Gemini real e as operações no bucket real possuem evidências próprias de execução.

---

## 🚀 8. Guia de Execução Local e Demonstração

```bash
# 1. Acessar o diretório do projeto
cd g10-brasil-equipe-15_mediflow

# 2. Criar e ativar o ambiente virtual Python (3.11 ou superior)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Instalar as dependências oficiais
pip install -r requirements.txt

# 4. Configurar as chaves de ambiente
cp .env.example .env
# Configurar GEMINI_API_KEY e credenciais OCI Always Free

# 5. Executar os testes automatizados
python -m pytest

# 6. Testes Manuais Opcionais (Cloud OCI e IA Gemini)
python -m scripts.testar_oci
python scripts/testar_simulacao_oci.py
python testar_gemini.py

# 7. Opção A: Iniciar o Servidor FastAPI (Backend REST para React e API)
uvicorn src.api.main:app --reload --port 8000

# 8. Opção B: Iniciar a Bancada Streamlit (Auditoria Rápida & HiTL)
streamlit run src/app/streamlit_app.py
```

---

## 📁 9. Estrutura de Diretórios & Organização do Repositório

### 9.1 Árvore Oficial Atual (Backend, IA, Nuvem & Testes)

```text
g10-brasil-equipe-15_mediflow/
├── data/
│   └── samples/                                <- Amostras clínicas dos 3 cenários do edital
│       ├── 01_cenario_rotina.json              <- RX Tórax normal (Rotina ambulatorial)
│       ├── 01_laudo_rotina.pdf                 <- PDF digital de rotina
│       ├── 02_cenario_urgencia.json            <- TEP Agudo I26.9 (Urgência com alerta)
│       ├── 02_laudo_urgencia_tep.pdf           <- PDF digital de urgência
│       └── 03_cenario_ambiguidade.json         <- Receita com dose anômala (Revisão humana)
│
├── docs/                                       <- Documentação técnica e governança de QA
│   ├── testes/                                 <- Central de Engenharia de Qualidade
│   │   ├── CONTRATO_DE_DADOS.md                <- Contrato canônico unificado (fonte da verdade)
│   │   ├── CATALOGO_DE_DOCUMENTOS_DE_TESTE.md  <- Catálogo completo dos 79 fixtures
│   │   ├── AUDITORIA_2026-10-20.md             <- Histórico de resolução de pendências
│   │   ├── VISUAL_SCHEMAS.md                   <- Guia visual com diagramas Mermaid autoritativos
│   │   ├── Mapa_de_Documentos_de_Teste_MediFlow.pdf <- Matriz visual de rastreabilidade (PDF)
│   │   └── README.md                           <- Guia de navegação de testes e QA
│   └── GUIA_INTEGRACAO_LLM.md                  <- Guia de consumo do Ingestion Loader para IA
│
├── src/                                        <- Código-fonte da aplicação (Python Backend & IA)
│   ├── agents/                                 <- Estrutura de agentes do sistema
│   ├── api/                                    <- API REST FastAPI Assíncrona (/api/v1/triagens)
│   ├── app/                                    <- Interfaces Python (Streamlit HiTL)
│   │   ├── streamlit_app.py                    <- Painel web de auditoria médica e testes rápidos
│   │   └── triage_pipeline.py                  <- Pipeline que conecta GeminiService ao grafo
│   ├── ingestion/                              <- Camada de Ingestão e Gateway de Segurança
│   │   └── loader.py                           <- Carregador blindado (10MB, 20 págs, MIME, magic bytes)
│   ├── schemas/                                <- Modelos de Dados Pydantic v2
│   │   └── clinical.py                         <- Schemas canônicos (TriagemMediFlow, ErroResposta, etc.)
│   ├── services/                               <- Serviços de Integração Multimodal
│   │   └── gemini_service.py                   <- GeminiService estruturado (REST, 30s, Pydantic v2, duplo fallback)
│   ├── storage/                                <- Conector OCI Object Storage Always Free (oci_storage.py)
│   ├── workflow/                               <- Motor de Orquestração Determinística (LangGraph)
│   │   ├── extraction_adapter.py               <- Adaptador de envelopes para entrada do grafo
│   │   ├── graph.py                            <- Grafo de estados, nós e cálculo de regras
│   │   └── state.py                            <- Estrutura do GraphState compartilhado
│   └── config.py                               <- Configurações globais e variáveis de ambiente
│
├── scripts/                                    <- Utilitários de homologação e scripts de diagnóstico
│   ├── testar_simulacao_oci.py                 <- Validação da simulação de falhas OCI do catálogo EPT v1.0 (§12)
│   └── testar_oci.py                           <- Validação real ponta a ponta no bucket OCI Always Free
│
├── tests/                                      <- Testes automatizados com Pytest
│   ├── test_workflow.py                        <- Transições e arestas do LangGraph
│   ├── test_contrato_fixtures.py               <- Contratos das fixtures e regras R1 a R8
│   ├── test_api.py                            <- Endpoints REST FastAPI e EPT
│   ├── test_extraction_adapter.py             <- Adaptação de envelopes clínicos
│   ├── test_ingestion.py                      <- Formatos, limites e rejeições de arquivos
│   ├── test_gemini_service.py                 <- GeminiService, transporte REST, timeout e fallback
│   ├── test_gemini_workflow_adapter.py        <- Integração entre GeminiService e workflow
│   ├── test_audit_items.py                    <- Auditoria técnica e sanidade
│   ├── test_oci_storage.py                    <- Persistência OCI com SDK simulado
│   ├── test_schemas.py                        <- Pydantic v2 e envelopes de erro
│   ├── test_streamlit_pipeline.py             <- Pipeline Streamlit e preservação de sinais
│   ├── test_gemini_prioridades_dosagem.py      <- Prioridades e dosagens na extração
│   ├── test_exemplos_extracao_workflow.py      <- Exemplos de extração no workflow
│   ├── test_pr13_persistencia_pendente.py     <- Persistência pendente e retentativa OCI
│   └── fixtures/                               <- Base de 79 fixtures canônicos
│       ├── demo/                               <- 12 casos essenciais para o pitch (TXT, PDF, JPG, JSON)
│       ├── catalogo/                           <- 67 casos avançados (qualidade, borda, limites)
│       └── manifest.csv                        <- Rastreabilidade formal em formato de máquina
│
├── testar_gemini.py                            <- Script de validação manual da IA com Google Gemini
├── ARQUITETURA.md                              <- Especificação Técnica Oficial da Arquitetura
├── README.md                                   <- Documentação Principal do Repositório
├── pytest.ini                                  <- Configuração corporativa do Pytest
├── requirements.txt                            <- Dependências oficiais do ecossistema Python
└── .env.example                                <- Modelo de chaves (Gemini API e OCI Always Free)
```

---

### 9.2 Frontend React implementado (`frontend/`)

O portal utiliza React, TypeScript, Vite e Tailwind CSS. A comunicação com a API usa Fetch, com acompanhamento do processamento pela rota de status.

A estrutura implementada, os comandos de execução, as variáveis de ambiente e as limitações do modo de demonstração estão documentados no [README do frontend](frontend/README.md).

O login é de demonstração. A fila de revisão humana permite consultar os resultados, conforme o escopo do MVP.

