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
        
        CE["<b>CodigoErro</b><br/>• FORMATO_NAO_SUPORTADO<br/>• CAMPOS_INVALIDOS<br/>• REQUISICAO_INVALIDA<br/>• ARQUIVO_MAIOR_QUE_LIMITE<br/>• MIME_INVALIDO<br/>• PDF_PROTEGIDO<br/>• PDF_CORROMPIDO"]
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

## 3. 🧠 Motor de Decisão Clínica Integrado no Schema (`@model_validator`)

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
    
    AMB_URG -- 🟢 SIM --> R2["<b>Regra R2: Urgência com Ambiguidade</b><br/>• Destinos: [FILA_URGENCIA_MEDICA, FILA_REVISAO_HUMANA]<br/>• Status: <b>EM_REVISAO</b><br/>• Notificação de Emergência Gerada"]
    
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

## 4. 📋 Dicionário de Componentes e Modelos

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
| **`ErroProcessamento`** | [`clinical.py`](../../src/schemas/clinical.py) | Erros ocorridos durante a leitura de documentos aceitos no pipeline. | `CodigoErro` |
| **`ErroResposta`** | [`clinical.py`](../../src/schemas/clinical.py) | Rejeição HTTP imediata na camada de ingestão (`400`, `413`, `415`). | `CodigoErro` |

---

## 5. 🛡️ Garantias e Regras de Qualidade dos Schemas

1. **Proteção Extra (`extra="ignore"`):** Todos os modelos aceitam payloads com campos adicionais sem quebrar a desserialização, garantindo interoperabilidade entre agentes e versões da API.
2. **Propriedades de Conveniência:** Suporte transparente a nomes legados (`medico_solicitante`, `diagnostico_principal`, `cid_extraido`, `cid_sugerido`, `score_confianca_classificacao`).
3. **Ponto Fixo e Idempotência:** Uma instância de `TriagemMediFlow` revalidada (`TriagemMediFlow.model_validate(obj.model_dump())`) preserva rigorosamente o mesmo estado, sem oscilação de score ou destinos.
4. **Cobertura de Testes:** 100% dos modelos são validados contra os **79 fixtures canônicos** em [`tests/test_contrato_fixtures.py`](../../tests/test_contrato_fixtures.py) e [`tests/test_schemas.py`](../../tests/test_schemas.py).
