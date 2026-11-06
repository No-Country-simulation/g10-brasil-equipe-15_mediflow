# MediFlow — Análise de Requisitos

**Equipe:** Hackathon ONE G10 Equipe 15 | **Versão:** 1.2 | **Data:** 05/11/2026
**Autor / responsável:** William — QA & Requirements Lead

> **Como usar este documento:** leia as seções 1 a 4 para entender o projeto; use as seções 5 a 8 como referência durante o desenvolvimento; a seção 12 registra as decisões já tomadas; o **Anexo (seção 13.1)** consolida as decisões de 21/10/2026; a **seção 14** registra o alinhamento desta versão ao documento original do projeto. Este documento é a base da Especificação Funcional v1.2.

> **Revisão de 05/11/2026.** Esta versão parte da **Análise v1.1 (8 páginas, com Anexo de decisões de 21/10/2026)** e preserva integralmente o Anexo, a regra de urgência isolada, a fórmula da nota combinada e as demais decisões fechadas. Realinha a análise ao `Projeto_oracle.pdf`, que é a **fonte de precedência 1** (Especificação Funcional, seção 2). Três exigências que haviam sido acrescentadas por interpretação da equipe — continuidade entre processos, E2E por cliente HTTP real com OCI no ambiente final e eventos próprios de destino/alerta no histórico — foram reclassificadas como propostas de endurecimento do QA, não como exigências originais do Brief. Nenhum requisito obrigatório do Brief e nenhuma decisão da v1.1 foi reduzida ou revertida.

---

## Registro de alterações — v1.1 → v1.2

| # | Seção | Redação anterior | Redação v1.2 | Fundamento |
| --- | --- | --- | --- | --- |
| D-01 | 4, 6 (RNF-03), 11, 12, 14 | "Falhas não derrubam o sistema nem perdem documentos" (sem delimitar processo) | Delimitado ao **mesmo processo de execução**; continuidade entre processos registrada como fora do escopo obrigatório do MVP | Brief pede tratamento de exceções/fallback, não retomada entre execuções; EF §2 |
| D-02 | 5.5 (RF-26), 8, 12, 14 | "Disponibilizar o histórico de triagem em JSON" sem composição mínima | Histórico com recebimento, processamento, conclusão/erro e recuperação; decisão, destino, alerta e armazenamento constam do **resultado estruturado** | Brief: "resultados e histórico de triagem em formato JSON estruturado" |
| D-03 | 4, 10, 12, 14 | Integração ativa com OCI lida como exigência de teste E2E por cliente HTTP real | Integração ativa comprovada por escrita/leitura byte a byte no bucket + suíte automatizada; E2E é **reforço de QA dispensado no MVP**, com ressalva sobre as rotas | Brief: "Integração ativa com o OCI Object Storage ... para segregação e armazenamento" |
| — | 6 (coluna Origem), 14 | `RNF-03` marcado como "Brief" sem ressalva | Mantido como Brief, com nota de que a redação "não perdem documentos" é interpretação da equipe delimitada | EF §2 |
| — | 12 | Sem registro das decisões de escopo | Três linhas "Decidido" (D-01, D-02, D-03) | Rastreabilidade das decisões |
| — | 14 (nova) | — | Hierarquia de fontes e tabela de conformidade Brief × análise | EF §2 e §17 |
| — | 5.1 (RF-02), 7 (RN-01/RN-02), 12, 13.1 (Anexo) | Análise v1.1 real (8 páginas, Anexo de 21/10/2026) | **Preservada integralmente**; nenhuma decisão fechada foi reaberta | Base de revisão |

---

## 1. Visão geral

**O que é o MediFlow.** Um agente de IA que recebe documentos clínicos (receitas, laudos, guias, atestados), descobre sozinho que tipo de documento é, extrai os dados importantes e envia o documento para o setor certo do hospital. Quando o agente não tem certeza, ou quando o caso é urgente, ele avisa uma pessoa.

A solução MediFlow deve resolver desafios complexos de visão multimodal, extração estruturada de dados clínicos, lógica de decisão condicional e tratamento de casos ambíguos ou urgentes (como dados ilegíveis, prescrições de alto risco ou solicitações de urgência).

**Objetivo do hackathon.** Entregar um MVP (versão mínima funcional) do agente, com demonstração de três cenários: rotina, urgência e caso ambíguo.

**Formações ONE relacionadas.** Indispensáveis: Engenharia de Agentes e Automação e Oracle Cloud Infrastructure (OCI). Reforço: Desarrollo y Orquestación con IA Generativa.

**Stack adotada pelo time.** LLM: Gemini · Orquestração: LangGraph · Validação: Pydantic · Interface: React + FastAPI · Armazenamento: OCI Object Storage.

**Como o agente funciona, em 6 passos**

1. Receber o documento clínico ou administrativo nos formatos suportados (PDF, imagem, texto ou JSON).
2. Classificar o tipo, a especialidade e a prioridade (ex.: Receituário Médico, Laudo de Exame Laboratorial/Imagem, Guia de Solicitação de Procedimento...).
3. Extrair entidades e os dados clínicos (paciente, médico, diagnóstico, medicamentos, exames) com altíssima precisão.
4. Avaliar a consistência, potenciais conflitos e a nota combinada de confiabilidade (classificação + extração).
5. Rotear para o destino correto em casos padrão, ou para revisão humana se houver dúvida (nota combinada < 0.85, por padrão).
6. Guardar o documento e a decisão no OCI Object Storage e devolver o resultado em JSON.

## 2. Glossário

| Termo | Significado |
| --- | --- |
| MVP | Produto mínimo viável: a menor versão que já funciona e cumpre o essencial. |
| Agente autônomo | Programa que toma decisões e executa etapas sozinho, usando uma IA. |
| LLM | Modelo de linguagem que lê e interpreta textos e imagens. No MediFlow, o modelo adotado é o Gemini. |
| Multimodal | Capaz de entender mais de um tipo de entrada, como texto e imagem. |
| Human-in-the-Loop (HITL) | "Humano no circuito": uma pessoa revisa os casos em que a IA não tem certeza. |
| Score de confiança | Nota de 0 a 1 que indica o quanto o sistema confia no próprio resultado. |
| Nota combinada | Nota final de 0 a 1 que junta a confiança da classificação e a da extração. É ela que é comparada com o limiar. |
| Limiar de confiança | Valor mínimo da nota combinada para o documento seguir sem revisão humana. Padrão: 0.85. Abaixo disso, o documento vai obrigatoriamente para a Fila de Revisão Humana. |
| Grafo de decisão | Fluxo com etapas (nós) e caminhos condicionais: se urgente, vai para A; se ambíguo, vai para B. |
| LangGraph / n8n | LangGraph (Python) monta o grafo de decisão do MediFlow. O n8n é uma ferramenta de fluxos visuais, citada apenas nos alertas opcionais (RF-D5). |
| Pydantic / JSON | Biblioteca Python que valida tipos / Formato de texto estruturado para dados. |
| React / FastAPI / Streamlit | React: biblioteca para montar a tela. FastAPI: framework Python para a API. Streamlit: ferramenta Python para painéis rápidos (painel do gestor). |
| **[v1.2] Continuidade entre processos** | Capacidade de retomar uma triagem após o processo da API ser reiniciado, reconstruindo o índice de consultas a partir do OCI. **Não é exigência do Brief** nesta versão (D-01). |

## 3. Partes interessadas

| Papel | O que precisa do sistema |
| --- | --- |
| Gestor hospitalar / operadora (cliente) | Reduzir horas de digitação, erros e glosas; acelerar autorizações; calibrar o limite de confiança para revisão. |
| Equipe administrativa | Documentos já classificados e com os dados extraídos, sem redigitar. |
| Auditor clínico | Fila clara dos casos duvidosos, com o motivo da dúvida, para aprovar ou rejeitar. |
| Equipe de plantão médico | Alerta imediato quando há achado crítico. |
| Farmácia e Auditoria de autorizações | Receber só os documentos do seu tipo, já estruturados. |
| Avaliadores do hackathon | Checklist cumprido, demonstração de 3 cenários e documentação completa. |
| Time de desenvolvimento | Requisitos claros e divisão de trabalho. |

## 4. Escopo

### Dentro do escopo (MVP obrigatório)

- Receber documentos em PDF, imagem, texto ou JSON.
- Classificar, extrair, avaliar a confiança e rotear usando LLM multimodal (Gemini).
- Grafo de decisão condicional (LangGraph) com tratamento de urgência e ambiguidade.
- Limiar de confiança padrão de 0.85, guardado em variável de configuração: nota combinada abaixo dele vai obrigatoriamente para revisão humana.
- Persistência no OCI Object Storage (Always Free).
- Interface de triagem em React e API REST em FastAPI, com dados validados por Pydantic.
- Repositório Git, README com diagrama e demonstração de 3 cenários.
- Resultados e histórico de triagem em JSON estruturado.

### Diferenciais (opcionais, só depois do MVP)

- Configuração externa pelo gestor (limites, regras e destinos sem mexer no código), começando por um slider interativo no Streamlit para calibrar o limiar de confiança.
- Deploy na OCI Compute (VM Always Free).
- Leitura de receitas manuscritas e laudos escaneados (OCR e visão computacional).
- Painel de auditoria HITL em Streamlit (aprovar/rejeitar com um clique) e Alertas em tempo real.

### [v1.2] Fora do escopo obrigatório — fronteiras de verificação do MVP

As três fronteiras abaixo **não constam do `Projeto_oracle.pdf`**. Foram tratadas em versões anteriores como se fossem exigências do Brief, mas são interpretações acrescentadas por esta análise. Conforme a seção 2 da Especificação Funcional ("quando a análise acrescenta uma restrição ou decisão que não está no brief, ela é identificada como proposta da equipe, não como exigência original do Projeto Oracle"), ficam reclassificadas:

| Fronteira | Situação admitida no MVP | O que o Brief exige | Decisão |
| --- | --- | --- | --- |
| Continuidade entre processos | Índice de triagens, resultado e histórico mantidos em memória no processo da API; sem reconstrução a partir do OCI após reinício. Objetos já gravados no bucket permanecem íntegros. | Tratamento de exceções e fallback para revisão humana; persistência de documentos e decisões no OCI. | **D-01** — fora do escopo obrigatório; limitação documentada. |
| E2E por cliente HTTP real contra bucket no ambiente final | Integração ativa comprovada por escrita/leitura byte a byte no bucket real e pela suíte automatizada com cliente de teste (319 aprovados, 1 ignorado em 05/11/2026). | "Integração ativa com o OCI Object Storage (camada Always Free) para segregação e armazenamento". | **D-03** — reforço de QA, dispensado no MVP. |
| Eventos próprios de destino, alerta e persistência no histórico | Esses dados constam do resultado estruturado (seção 8); o histórico cobre recebimento, processamento, conclusão/erro e recuperação. | "Resultados e histórico de triagem em formato JSON estruturado". | **D-02** — interpretação registrada. |

**Ressalva sobre D-03:** a dispensa do E2E não autoriza afirmar que as rotas HTTP são mera delegação. `src/api/routes.py` faz parsing de JSON/multipart, agenda `background_tasks`, mapeia códigos em `_tratar_erro_ingestao` e o `GET /triagens/{id}` dispara a triagem sincronamente (L195-213). Essa lógica é coberta pela suíte; dispensa-se apenas a execução contra o bucket real no ambiente final.

**Natureza das fronteiras:** são propostas de endurecimento do QA para versões futuras, não redução de requisito obrigatório do Brief. Se forem adotadas, devem ser registradas como **nova exigência da equipe** na seção 12.

## 5. Requisitos funcionais

Prioridade: **O** = obrigatório (MVP), **D** = diferencial. O símbolo **+** marca requisitos derivados pela análise.

### 5.1 Ingestão

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-01 | Receber documentos por endpoint (FastAPI) ou tela de envio (React). | O |
| RF-02 | Aceitar PDF (digital e digitalizado), imagem e texto; **JSON é o envelope da requisição**, não formato de documento. | O |
| RF-03 + | Validar formato e campos obrigatórios da entrada, rejeitando com mensagem clara. | O |
| RF-04 | Ler o conteúdo do documento com LLM multimodal (Gemini). | O |

### 5.2 Classificação

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-05 | Identificar a categoria: Receituário Médico, Laudo de Exame Laboratorial/Imagem, Guia, Relatório de Alta/Internação e Atestado Médico. | O |
| RF-06 | Identificar a especialidade médica relacionada ao documento (campo `especialidade` da saída). | O |
| RF-07 | Classificar o nível de prioridade do documento: no mínimo "Urgente" e "Rotina" (campo `nivel_prioridade` da saída). | O |

### 5.3 Extração

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-08 | Extrair a identificação do paciente (nome, idade). | O |
| RF-09 | Extrair o profissional solicitante: nome e CRM (formato número-UF). | O |
| RF-10 | Extrair a hipótese diagnóstica ou diagnóstico principal e o CID-10. | O |
| RF-11 | Extrair medicamentos e dosagens, quando houver. | O |
| RF-12 | Extrair os exames solicitados ou realizados. | O |
| RF-13 | Extrair o indicador de urgência. | O |
| RF-14 | Entregar os dados em JSON validado com Pydantic. | O |
| RF-15 + | Nunca inventar dado ausente: o campo faltante fica vazio e é sinalizado. | O |

### 5.4 Decisão e roteamento

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-16 | Avaliar consistência e conflitos (ex.: CID incompatível com diagnóstico, dose incomum). | O |
| RF-17 / 18 | Calcular a nota combinada de confiabilidade (classificação + extração), de 0 a 1 / Detectar urgências e alto risco. | O |
| RF-19 / 20 | Grafo de decisão (LangGraph) com nós condicionais / Roteamento para as filas específicas. | O |
| RF-21 | Enviar para revisão humana quando houver ambiguidade, dado faltante ou nota combinada < 0.85. O 0.85 é o limiar padrão, lido de uma variável de configuração; abaixo dele o envio para a Fila de Revisão Humana é obrigatório. Nota igual ou maior que 0.85 segue o fluxo normal, se não houver outro motivo de revisão ou urgência. | O |
| RF-22 a 24 + | Gerar notificação para urgentes, registrar justificativa e tratar exceções com fallback humano. | O |

### 5.5 Resultado e histórico

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-25 | Retornar resposta estruturada (status, dados extraídos, decisão, armazenamento). | O |
| RF-26 | Disponibilizar o histórico de triagem em JSON. **[v1.2]** No MVP, com eventos de recebimento, processamento, conclusão/erro e recuperação; decisão, destino, alerta e armazenamento constam do resultado estruturado (seção 8), conforme D-02. | O |
| RF-27 | Oferecer interface de triagem (React) e API REST (FastAPI) para visualizar os fluxos. | O |

### 5.6 Armazenamento (OCI) e 5.7 Diferenciais

| ID | Requisito | Prior. |
| --- | --- | --- |
| RF-28 a 30 | Salvar no OCI (Always Free), separar buckets por status, e informar caminho na resposta. | O |
| RF-D1 | Configuração externa pelo gestor, sem mexer no código. O limiar de confiança (padrão 0.85) fica em variável de configuração (isso já faz parte do MVP) e o diferencial é o slider interativo no Streamlit para o gestor calibrar esse limite. Regras e destinos customizáveis também entram neste diferencial. | D |
| RF-D2 a D5 | Deploy na OCI Compute, OCR, painel HITL em Streamlit e alertas n8n. | D |

## 6. Requisitos não funcionais

| ID | Categoria | Requisito | Origem |
| --- | --- | --- | --- |
| RNF-01 | Precisão | Extração com altíssima precisão; erro clínico é falha grave. | Brief |
| RNF-02 | Segurança | Nenhuma urgência tratada como rotina; na dúvida, revisão. | Derivado |
| **[v1.2] RNF-03** | **Confiabilidade** | **Falhas não derrubam o sistema nem perdem documentos dentro do mesmo processo de execução. A continuidade entre processos (retomada após reiniciar a API) não é exigência do Brief e está fora do escopo obrigatório do MVP (seção 4).** | **Brief + interpretação da equipe** |
| RNF-04 | Rastreabilidade | Toda decisão tem justificativa e fica registrada no histórico. | Brief |
| RNF-05 | Custo | Usar exclusivamente recursos Always Free da OCI. | Brief |
| RNF-06 | Padronização | Saídas sempre em JSON válido e tipado (Pydantic). | Derivado |
| RNF-07 | Agilidade | Resposta rápida para não atrasar casos urgentes. | Brief |
| RNF-08 | Privacidade | Apenas dados fictícios; nenhuma chave/segredo no Git. | Brief |
| RNF-09 | Manutenção | Código modular, commits documentados e README atual. | Brief |
| RNF-10 | Flexibilidade | Camada de LLM isolada em módulo próprio, para poder trocar o modelo sem refazer o pipeline (o modelo adotado é o Gemini). | Brief |
| RNF-11 | Usabilidade | Interface simples (tipo, prioridade, destino e justificativa). | Derivado |

**[v1.2] Nota sobre a coluna Origem:** o Brief pede "tratamento de exceções e fallback para revisão humana". A redação "não perdem documentos" é interpretação desta análise e, conforme a seção 2 da Especificação Funcional, não pode ser estendida a uma exigência de continuidade entre processos que o Brief não formula. A conversão em verificação está delimitada na EF v1.2, seção 14 (RNF-03).

## 7. Regras de negócio

| ID | Regra |
| --- | --- |
| RN-01 | Casos padrão (sem ambiguidade e com nota combinada de 0.85 ou mais) seguem direto ao destino, sem intervenção humana. |
| RN-02 | Documento ambíguo, ilegível, inconsistente, **com prioridade ou urgência indeterminada**, ou com nota combinada < 0.85 (limiar padrão) vai obrigatoriamente para a Fila de Revisão Humana. |
| RN-03 | Achado crítico ou prescrição de alto risco vai para a Fila de Urgência Médica com alerta. |
| RN-04 | Todo documento é salvo no OCI conforme seu status (recebido, processado, auditoria). |
| RN-05 | Toda decisão de roteamento traz uma justificativa estruturada. |
| RN-06 | Somente recursos Always Free da OCI podem ser usados. |
| RN-07 + | Cada documento tem um `documento_id` único gerado pelo sistema. |

**Roteamento proposto**

| Situação | Destino sugerido |
| --- | --- |
| Achado crítico ou urgência | Fila de Urgência Médica, com alerta |
| Receituário de rotina | Farmácia Hospitalar |
| Guia de solicitação de procedimento | Auditoria de Autorizações |
| Laudos, relatórios de alta e atestados de rotina | Prontuário Eletrônico do Paciente |
| Ambiguidade, dado faltante ou nota combinada < 0.85 | Fila de Revisão Humana |

**Urgência com ambiguidade:** o caso vai para as duas filas (Urgência Médica e Revisão Humana) e gera alerta (EF v1.2, seções 8.2 e 15). **Urgência isolada** vai apenas para a Fila de Urgência Médica com alerta, sem revisão humana (RN-08/ADR-001, EF seção 8.3).

## 8. Dados de entrada e saída (visão geral)

**Entrada**

| Campo | Descrição | Exemplo |
| --- | --- | --- |
| `documento_id` | Identificador único do documento | `DOC-CLIN-2026-8942` |
| `tipo_arquivo` | Formato do arquivo | `PDF` |
| `documento_texto` | Texto do documento | Texto do laudo... |
| `canal_origem` | Setor de onde o documento veio | `Pronto_Socorro` |

**Saída**

| Bloco | Campos |
| --- | --- |
| `status` | Situação do processamento (ex.: processado, em_auditoria) |
| `documento_id` | Mesmo identificador da entrada |
| `classificacao` | `tipo_documento`, `especialidade`, `nivel_prioridade`, `score_confianca` (nota combinada, comparada com o limiar 0.85) |
| `dados_extraidos` | paciente (nome, idade); medico (nome, crm); `diagnostico_principal`; `cid` |
| `decisao_roteamento` | `destino_principal`, `requer_auditoria_humana`, `justificativa`, `notificacao` |
| `armazenamento_oci` | `bucket`, `caminho_objeto`, `status_backup` |

**Atenção:** o exemplo do brief original não mostra campos para medicamentos, dosagens, exames solicitados, urgência detalhada, score de extração nem conflitos, mas o texto exige essas informações. Esses campos devem constar na Especificação Funcional final.

**[v1.2]** No MVP, os blocos `decisao_roteamento` e `armazenamento_oci` são **o registro de decisão, destino, alerta e persistência**. O Brief pede apenas que resultados e histórico estejam em JSON estruturado; não exige eventos de histórico duplicando esses campos (D-02). Ver EF v1.2, seções 9.2 e 13.

## 9. Tecnologias

| Camada | Opções permitidas pelo brief | Situação |
| --- | --- | --- |
| LLM | Google Gemini (curso), OpenAI, Claude | Decidido: Gemini |
| Orquestração | LangGraph, n8n, Python puro, CrewAI | Decidido: LangGraph |
| Validação de dados | Pydantic ou JSON Schema | Decidido: Pydantic |
| Interface ou API | Streamlit, FastAPI, Flask, n8n, Node.js | Decidido: React (interface) + FastAPI (API) |
| Painel do gestor (diferencial) | Streamlit | Slider do limiar (RF-D1) e painel HITL (RF-D4) |
| Armazenamento | OCI Object Storage (Always Free) | Obrigatório |
| Hospedagem | OCI Compute (VM Always Free) | Opcional |
| Versionamento | Git e GitHub | Obrigatório |

## 10. Entregáveis e critérios de aceite

**Entregáveis:** Repositório Git com commits bem documentados; README com arquitetura e diagrama de decisão; Notebook/Módulos do pipeline; e Aplicação com endpoint/tela.

**Demonstração obrigatória (3 cenários)**

1. Fluxo padrão aprovado, sem intervenção humana.
2. Caso com prioridade de urgência médica.
3. Caso ambíguo direcionado para auditoria humana.

**[v1.2] Evidência de integração ativa com o OCI (checklist do Brief):** gravação e leitura byte a byte de documento original, resultado e histórico no bucket real (`scripts/testar_historico_oci.py`, L142 e L184-186), além da suíte automatizada com cliente de teste e OCI simulado (319 aprovados, 1 ignorado em 05/11/2026). A execução ponta a ponta por cliente HTTP real contra o bucket no ambiente final é **reforço de QA, não exigência do Brief**, e fica dispensada no MVP (D-03). A ressalva sobre a lógica própria de `src/api/routes.py` está registrada na seção 4.

**[v1.2] Registro de volumetria:** contagens de testes divergentes em documentos e corpos de PR (245, 208, 304, 306, 317, 319) são registros históricos de momentos diferentes da suíte, não um único total. A evidência vigente para o PR #22 em 05/11/2026 é **319 aprovados, 1 ignorado**; o corpo do PR deve ser atualizado a partir de 304.

## 11. Restrições, premissas e riscos

**Restrições:** usar só OCI Always Free; prazo de 5 semanas. **Premissas:** documentos fictícios em testes; filas simuladas.

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Erros do LLM (dado inventado) | Dado clínico incorreto | Validação Pydantic, score e revisão humana. |
| Urgência não detectada | Risco grave ao paciente | Regras explícitas além do LLM. |
| Respostas do LLM instáveis | Inconsistências | Testes de consistência (QA William). |
| Conflitos de código da equipe | Retrabalho | Frentes claras e Pull Requests pequenos. |
| Escopo grande para 5 semanas | MVP incompleto | Priorizar núcleo; diferenciais por último. |
| Chaves de API expostas | Falha de segurança | Usar `.gitignore` e `.env`; não commitar segredos. |
| **[v1.2] Estado de triagem em memória** | **Após reiniciar a API, consultas por `documento_id` não são recuperadas; os objetos no OCI permanecem íntegros.** | **Fora do escopo obrigatório do Brief (D-01). Registrar a limitação no README e no cartão de aceite; não declarar "RNF-03 100%". Evolução futura: reconstruir o índice a partir dos objetos do bucket.** |
| **[v1.2] Interpretação de requisito como exigência do Brief** | **Cobrança indevida de implementação e bloqueio de aceite.** | **Aplicar a seção 2 da EF: marcar origem (Brief / Derivado / Decisão da equipe) e registrar toda restrição acrescentada.** |

## 12. Decisões do time e pontos em aberto

| Decisão | Situação | Detalhe |
| --- | --- | --- |
| LLM principal | Decidido | Gemini. |
| Orquestração | Decidido | LangGraph. |
| Interface e API | Decidido | React para a tela de triagem e FastAPI para a API. Streamlit fica só no painel do gestor (diferencial). |
| Validação de dados | Decidido | Pydantic. |
| Limiar de confiança para revisão | Decidido | Padrão de 0.85, em variável de configuração. Nota combinada < 0.85 vai obrigatoriamente para a Fila de Revisão Humana. Slider no Streamlit para o gestor calibrar (RF-D1). |
| **[v1.2] D-01 — Continuidade entre processos** | **Decidido** | **Retomada de triagens após reiniciar a API não é exigência do Brief; fora do escopo obrigatório do MVP. RNF-03 delimitado a falhas dentro do mesmo processo. Limitação documentada no README e no cartão de aceite.** |
| **[v1.2] D-02 — Composição do histórico** | **Decidido** | **No MVP, decisão, destino, alerta e persistência constam do resultado estruturado; o histórico cobre recebimento, processamento, conclusão/erro e recuperação. Sem evento próprio de destino/alerta em `EventoHistorico`.** |
| **[v1.2] D-03 — Verificação da integração OCI** | **Decidido** | **Integração ativa comprovada por escrita/leitura byte a byte no bucket real + suíte automatizada. E2E por cliente HTTP real no ambiente final é reforço de QA, dispensado no MVP, com ressalva sobre `src/api/routes.py`.** |
| Fórmula da nota combinada | Decidido (21/10/2026) | Mínimo entre a nota de classificação e a de extração (postura conservadora, alinhada ao RNF-02). |
| Urgência e ambiguidade simultâneas | Decidido (21/10/2026) | Urgência vai para a Fila de Urgência Médica com alerta **e não gera revisão humana por si só**; com ambiguidade, o caso vai para as duas filas e gera alerta. |
| Níveis de prioridade exatos | Decidido (21/10/2026) | `URGENTE`, `ROTINA` e `NAO_IDENTIFICADA`. Prioridade ou urgência indeterminadas levam à revisão humana. |
| Tempo-alvo de resposta | Decidido (21/10/2026) | Sem meta numérica no MVP; a latência é medida por etapa e o aceite é o conjunto de casos aprovados. |
| Conflito impeditivo | Decidido (21/10/2026) | Gravidade ALTA ou MÉDIA; gravidade BAIXA é registrada e não bloqueia. Dicionário clínico fechado no Anexo A.2 da EF. |
| Vocabulário | Decidido (21/10/2026) | Status em maiúsculas (`PROCESSADO`, `EM_REVISAO`) e JSON como envelope da requisição, não como formato de documento. |

## 13. Próximos passos

1. Revisar e validar este documento em equipe (principalmente as seções 12 e 14).
2. Elaborar a Especificação Funcional, detalhando cada campo, payload e tratamento de erro.
3. Dividir as frentes de trabalho e abrir Issues estruturadas no GitHub.
4. Usar o Plano de Testes (`tests/PLANO_DE_TESTES.md`) para balizar o desenvolvimento.
5. **[v1.2]** Publicar EF v1.2 e Análise v1.2 na pasta de referência e atualizar o corpo do PR #22 de 304 para 319 aprovados, 1 ignorado.

### 13.1 Anexo — Decisões registradas em 21/10/2026 (preservado da v1.1)

As linhas que estavam como "A definir" na seção 12 foram fechadas nesta versão, junto com a regra de urgência. O detalhamento de cada decisão está no Anexo A da Especificação Funcional v1.0 e na seção 8.3 da EF v1.2.

- **Urgência:** vai para a Fila de Urgência Médica com alerta e **não gera revisão humana por si só**. Revisão é consequência de ambiguidade.
- **Urgência com ambiguidade:** o caso vai para as duas filas (Urgência Médica e Revisão Humana) e gera alerta.
- **Fórmula da nota combinada:** mínimo entre a nota de classificação e a de extração.
- **Níveis de prioridade:** `URGENTE`, `ROTINA` e `NAO_IDENTIFICADA`. Prioridade ou urgência indeterminadas levam à revisão humana.
- **Tempo-alvo:** sem meta numérica no MVP; a latência é medida por etapa e o aceite é o conjunto de casos aprovados.
- **Conflito impeditivo:** gravidade ALTA ou MÉDIA; gravidade BAIXA é registrada e não bloqueia. Dicionário clínico fechado no Anexo A.2 da EF.
- **Vocabulário:** status em maiúsculas (`PROCESSADO`, `EM_REVISAO`) e JSON como envelope da requisição, não como formato de documento.

**[v1.2]** Nenhuma dessas decisões foi reaberta ou alterada pela revisão de alinhamento ao Brief.

## 14. [v1.2] Alinhamento ao documento original do projeto

### 14.1 Hierarquia de fontes

A Especificação Funcional, seção 2, já define a precedência e a regra de interpretação:

1. `Projeto_oracle.pdf` — define objetivo, escopo do hackathon, capacidades e entregáveis mínimos. **Fonte 1, referência que o projeto precisa manter de acordo.**
2. Esta Análise de Requisitos — organiza o entendimento da equipe, propõe requisitos e registra decisões tomadas e pendentes. **Documento derivado, de autoria e responsabilidade do QA & Requirements Lead.**
3. Especificação Funcional — detalha comportamento para implementação.

> "Quando a análise acrescenta uma restrição ou decisão que não está no brief, ela é identificada como proposta da equipe, não como exigência original do Projeto Oracle."

Reforços: a matriz de rastreabilidade da EF (seção 17) tem todas as linhas ancoradas em `Brief: ...`; a única linha de origem diversa é `Análise: requisitos derivados/decisões`. Esta análise mantém a coluna `Origem` com `Brief` e `Derivado`, e o símbolo `+` para requisitos derivados.

### 14.2 O que o Brief exige

| Exigência | Onde no Brief |
| --- | --- |
| Resultados e histórico de triagem em formato JSON estruturado; persistência de documentos e decisões integrada ao OCI Object Storage | p.2 |
| Tratamento de exceções e fallback para revisão humana quando o score de confiança for baixo | p.3 |
| OCI Object Storage como requisito obrigatório do MVP, com buckets segregados por status | p.3 |
| Integração ativa com o OCI (Always Free) para segregação e armazenamento | p.5, Checklist de Avaliação |
| README com arquitetura, diagrama do fluxo e instruções; demonstração de 3 casos (padrão aprovado, urgência médica, ambíguo para auditoria humana) | p.3 e p.5 |
| Recursos opcionais/diferenciais (deploy OCI Compute, OCR, painel HITL, alertas em tempo real, configuração customizável) | p.3 e p.5 |

**O Brief não exige:** `202 Accepted` com consulta posterior por ID (decisão 6 da seção 15 da EF; o exemplo de saída do Brief é síncrono), retomada de processamento após reinício da API, validação E2E por cliente HTTP real contra o bucket no ambiente final, nem eventos de destino/alerta/persistência dentro do histórico.

### 14.3 Tabela de conformidade

| Decisão | Análise v1.1 / EF v1.1 | Brief | v1.2 |
| --- | --- | --- | --- |
| D-01 | "Falhas não derrubam o sistema nem perdem documentos" | Tratamento de exceções + fallback | Delimitado ao mesmo processo; continuidade entre processos fora do escopo obrigatório |
| D-02 | Histórico sem composição mínima explícita; leitura do §13 da EF como eventos de decisão/destino/alerta/persistência | "Resultados e histórico em JSON estruturado" | Resultado estruturado registra decisão/destino/alerta/persistência; histórico registra eventos de processo |
| D-03 | "Integração ativa com OCI" lida como E2E das rotas HTTP com bucket real | "Integração ativa ... para segregação e armazenamento" | Comprovada por escrita/leitura no bucket + suíte; E2E = reforço de QA dispensado |

### 14.4 Efeito no aceite

Com D-01 a D-03 registrados, o aceite do cartão 09 se apoia na **fonte 1**: o critério de aceite 6 é decisão da equipe e está atendido; o RNF-03 está atendido no escopo do MVP com a fronteira documentada; a integração ativa com o OCI está comprovada com bucket real. Não resta pendência normativa de implementação; resta apenas a atualização do corpo do PR #22 de **304** para **319 aprovados, 1 ignorado**, que é registro de evidência da autora do PR.

**[v1.2] Preservação da v1.1:** a regra de urgência isolada (RN-08/ADR-001), o Anexo de decisões de 21/10/2026 (seção 13.1), a coerência com o Contrato de Dados da Triagem v1.0 e todas as decisões fechadas na seção 12 foram mantidos. A revisão D-01/D-02/D-03 não reverte nenhuma delas.

**Registro de revisão:** 05/11/2026 — alinhamento ao `Projeto_oracle.pdf` conforme a seção 2 da Especificação Funcional; sem alteração de escopo obrigatório do Brief.
