# Auditoria de Consistência e Homologação — MediFlow

> **Hackathon ONE G10 (Oracle & Alura) — Equipe 15**  
> **Documento Vivo de Rastreabilidade, Qualidade e Governança de Dados**

Este relatório consolida a auditoria inicial realizada em **20/10/2026** (protótipo de QA do William) e a sua respectiva **homologação final em 24/10/2026** no repositório oficial da organização: [`No-Country-simulation/g10-brasil-equipe-15_mediflow`](https://github.com/No-Country-simulation/g10-brasil-equipe-15_mediflow).

---

## 1. Branches e Ciclo de Vida do Repositório

### 📜 Retrato Original (20/10/2026 — Workspace William)
| Branch | Conteúdo | Situação Histórica |
| :--- | :--- | :--- |
| `main` | Só o `README.md` inicial (`# hackatoon_oracle`) | Destino do merge |
| `arena/9bba261b-hackatoon-oracle` | Projeto completo: 67 fixtures, contrato, geradores, verificadores, PDFs de origem, ZIP. 10 commits, 2026-10-19/20 | Trazido para `main` nesta auditoria |
| `arena/7ab29156-hackatoon-oracle` | Sessão temporária de trabalho; base em `main` | Recebeu o merge (fast-forward) e as correções |

### 🚀 Status Atual no Repositório Oficial (24/10/2026)
O projeto foi formalmente incorporado à organização oficial da equipe adotando o padrão **GitFlow**:
* **`main`**: Branch de produção e entrega final para a banca avaliadora (Oracle & Alura).
* **`develop`**: Branch principal de integração contínua entre todas as frentes (Backend, Frontend, IA e QA).
* **`feature/ingestao-documentos`**: Branch de trabalho ativa da frente de Ingestão e QA, onde o contrato v2, a blindagem do loader e os 79 fixtures foram homologados.
* **Branches temporárias `arena/*`**: Foram superadas e descontinuadas, sem poluir a árvore oficial do Git.

---

## 2. Regra CRM-SP: Conferência e Resiliência Clínica

O hospital de referência do projeto é o fictício **Hospital Aurora**, sediado em São Paulo. 

### 📜 Retrato Original (20/10/2026)
Na branch inicial de testes, três médicos assinavam com CRM de outra UF (`203114-RJ`, `176543-MG`, `154321-PR`). Foi aplicada a unificação para `-SP`, mantendo os números dos médicos estáveis.

| Formato Auditado | Itens Analisados | Resultado Original |
| :--- | :---: | :--- |
| `.txt` com CRM | 47 | 47 de 47 em `-SP`; 0 em outra UF |
| `expected.json` com CRM | 47 | 47 de 47 com `uf: "SP"` e o mesmo número do TXT |
| Imagens `.jpg` (OCR local, RapidOCR) | 111 leituras de CRM | 111 de 111 em `-SP`; número igual ao `expected.json` |
| PDFs com camada de texto | 46 abertos com texto | 37 ocorrências `número-SP`; 0 em outra UF |
| PDFs sem camada de texto (OCR da página) | 17 | CRM lido em `-SP` onde o expected declara CRM |
| PDFs de origem (`Projeto_oracle.pdf` e especificações) | 3 | `CRM-SP 145892`; nenhuma UF divergente |
| Mapa de documentos (PDF, 8 páginas) | 1 | Sem CRM de outra UF |

*Casos sem CRM (corretos e validados):* `Ausencia_Medico_Crm`, `Qualidade_Foto_Cortada` (CRM fora do recorte visual), os 4 `*_NaoIdentificado_*`/`*_Outro_*` e documentos ilegíveis.

### 🚀 Status Atual no Repositório Oficial (24/10/2026)
* **Preservação e Rastreabilidade:** Todos os 47 documentos com CRM do catálogo de 79 fixtures foram incorporados em `tests/fixtures/catalogo/` e `tests/fixtures/demo/`, mantendo 100% de conformidade com os registros sintéticos de SP.
* **Resiliência Arquitetural no Schema Pydantic:** Em vez de restringir rigidamente a UF no código e potencialmente travar o sistema em casos reais de médicos transferidos de outros estados, o modelo canônico [`Crm`](../../src/schemas/clinical.py) foi implementado com preenchimento inteligente:
  - Aceita formalmente qualquer UF de 2 letras válida da federação (`RJ`, `MG`, `PR`, etc.).
  - Se a UF for omitida na leitura do documento (ex: apenas `CRM 145892`), o normalizador `@field_validator("crm")` adota automaticamente `"SP"` como padrão do Hospital Aurora.

---

## 3. Problemas Encontrados e Correções de Engenharia

### 📜 Tabela Histórica de Correções do Protótipo (20/10/2026)
| # | Onde | Problema Original | Correção Aplicada |
| :-: | :--- | :--- | :--- |
| 1 | `tools/verificar_consistencia.py` | Seções impressas desordenadas (1, 2, 3, 4, 6, 7) | Seções renumeradas de 1 a 6 de forma consistente |
| 2 | `verificar_consistencia.py` × docs | Erro em clone limpo pelo arquivo de 25 MB ausente | Arquivo ausente virou aviso com instrução de regeneração |
| 3 | `testar_contrato.py` × verificador | Divergência de contagem de casos funcionais (57 vs 59) | Contagem padronizada por `tipo_de_teste` |
| 4 | Geradores sintéticos | Falta de reprodutibilidade por ausência de seed determinística | Ruído com semente fixa (`ruido_deterministico`) e `/ID` derivado |
| 5 | `Qualidade_Pdf_ComSenha.pdf` | Salt criptográfico AES-256 aleatório do PyMuPDF | Documentado como exceção inerente ao algoritmo |
| 6 | Pacote ZIP de entrega | Nomes com acentuação corrompidos | Utilitário `gerar_pacote.py` com flag UTF-8 explícita |
| 7 | `dist/README.md` | Contagem de arquivos incorreta e link para branch antiga | Contagem corrigida e links apontados para `main` |
| 8 | `CONTRATO_DE_DADOS.md` | Referências a seções antigas | Referências alinhadas com as contagens reais |
| 9 | `CATALOGO_DE_DOCUMENTOS_DE_TESTE.md` | Erro na árvore de diretórios | Árvore e contagens corrigidas |
| 10 | `tests/fixtures/README.md` | Falta de explicação sobre UF e arquivos de 25 MB | Notas técnicas adicionadas |
| 11 | `LEIA-ME.txt`, `README.md` | Listas de ferramentas desatualizadas | Documentação atualizada |

### 🚀 Evolução e Modernização no Repositório Oficial (24/10/2026)
* **Migração para Pytest Corporativo:** Os scripts customizados legados (`python3 tests/testar_contrato.py` e `tools/verificar_consistencia.py`) foram substituídos por testes nativos do ecossistema Pytest em [`tests/test_contrato_fixtures.py`](../../tests/test_contrato_fixtures.py), permitindo execução automatizada em qualquer ambiente de CI/CD padrão.
* **Governança de Tamanho de Repositório (`.gitignore`):** Para evitar estouro de limite de cota no GitHub e lentidão no `git clone`, os 4 arquivos sintéticos > 10MB (`Validacao_ArquivoGrande.pdf`, `Limite_Tamanho_10MB.pdf`, `Limite_Tamanho_Acima10MB.pdf` e `Limite_Texto_Acima10MB.txt`) foram adicionados ao `.gitignore`, enquanto os seus metadados de asserção em `expected.json` e o manifesto continuam versionados e plenamente testados.

---

## 4. Verificações Executadas e Suíte de Testes

### 📊 Comparativo: Protótipo (20/10) vs Repositório Oficial (24/10)

| Métrica | Retrato Original (20/10/2026) | Repositório Oficial (24/10/2026) |
| :--- | :---: | :---: |
| **Total de Fixtures de Teste** | 67 fixtures | **79 fixtures** (+ Bloco Limite A6) |
| **Framework de Execução** | Script avulso `testar_contrato.py` | **Pytest Automatizado** (`pytest`) |
| **Total de Testes da Aplicação** | 67 testes | **149 testes automatizados** |
| **Tempo de Execução** | ~3.5s | **1.20s** |
| **Taxa de Aprovação** | 100% | **100% (149 pass / 0 fail)** |

### 🔬 Composição Atual dos 149 Testes Integrados:
1. **79 Testes de Fixtures Clínicos Oficiais** ([`tests/test_contrato_fixtures.py`](../../tests/test_contrato_fixtures.py)):  
   Valida cada um dos 79 cenários do catálogo sintético, a consistência de serialização e a conformidade estrita das regras R1 a R8.
2. **46 Testes de Roteamento LangGraph** ([`tests/test_workflow.py`](../../tests/test_workflow.py)):  
   Valida todo o fluxo condicional de nós, transições e tomadas de decisão da arquitetura de agentes da equipe.
3. **17 Testes de Ingestão e Segurança** ([`tests/test_ingestion.py`](../../tests/test_ingestion.py)):  
   Valida leitura direta de fixtures reais do William (PDFs protegidos, corrompidos, DOCX inválido e fotos multimodais), bloqueio de arquivos > 10 MB, bloqueio de PDFs > 20 páginas e detecção de encoding Latin-1/UTF-8.
4. **7 Testes de Schemas Clínicos e Regras de Negócio** ([`tests/test_schemas.py`](../../tests/test_schemas.py)):  
   Valida a unificação Pydantic v2, limiares de score de confiança (0.85), extração laboratorial estruturada (RF-12) e envelope de erros HTTP.

---

## 5. Resolução Definitiva das Pendências de Produto

Todas as 6 pendências registradas em 20/10/2026 como "decisões de produto não corrigidas" foram oficialmente analisadas, decididas e implementadas no código:

### 1. Validação de UF no Contrato
* **Situação Original:** Modelo aceitava qualquer UF, mas verificador dos fixtures forçava apenas SP.
* **Decisão & Resolução Oficial (24/10/2026):** **CONCLUÍDO**.  
  O schema canônico [`Crm`](../../src/schemas/clinical.py) aceita qualquer UF de 2 letras e aplica fallback automático para `"SP"` quando omitida, garantindo que profissionais de saúde com registro interestadual não tenham o processamento bloqueado indevidamente.

### 2. Limite de Upload (Tamanho em Bytes e Contagem de Páginas)
* **Situação Original:** Especificação Funcional v1.0 não definia o limite formal de upload para o MVP.
* **Decisão & Resolução Oficial (24/10/2026):** **CONCLUÍDO**.  
  Alinhado à premissa do MVP A6 validada nos fixtures (`Limite_Tamanho_Acima10MB` e `Limite_Paginas_21`). O [`DocumentLoader`](../../src/ingestion/loader.py) foi parametrizado com:
  - `LIMITE_MAXIMO_BYTES = 10 * 1024 * 1024` (10 MB).
  - `LIMITE_MAXIMO_PAGINAS = 20` (Máximo de 20 páginas por PDF).  
  Uploads que excedem esses limites disparam `TamanhoExcedidoError` resultando em resposta HTTP 413 com código `ARQUIVO_MAIOR_QUE_LIMITE`.

### 3. Números Sintéticos de CRM e Privacidade
* **Situação Original:** Alerta sobre possível colisão aleatória de CRMs sintéticos de 6 dígitos com registros de terceiros.
* **Decisão & Resolução Oficial (24/10/2026):** **MITIGADO / CONCLUÍDO**.  
  Todos os documentos contêm marcas d'água visíveis de ambiente de teste acadêmico (*Hospital Aurora*). Foi formalizada a cláusula de **Privacidade e LGPD (RNF-08)** no [`README.md` principal da raiz do repositório](../../README.md) (linhas 218 a 220), assegurando que o projeto opera exclusivamente sobre dados fictícios e anônimos.

### 4. Divergência Brief × Especificação (Urgência Clínica)
* **Situação Original:** `Projeto_oracle.pdf` mandava urgência seguir sem auditoria humana obrigatória (`requer_auditoria_humana: false`), enquanto a EF v1.0 mandava `EM_REVISAO`.
* **Decisão & Resolução Oficial (24/10/2026):** **CONCLUÍDO**.  
  Implementado estritamente conforme o edital da Oracle no contrato canônico e no grafo:
  - **Urgência clínica pura:** Encaminha imediatamente para `FILA_URGENCIA_MEDICA` com `requer_auditoria_humana = false`, status `PROCESSADO` e alerta prioritário disparado.
  - **Urgência com ambiguidade clínica ou score abaixo do limiar:** Encaminha com prioridade para `[FILA_URGENCIA_MEDICA, FILA_REVISAO_HUMANA]` com status `EM_REVISAO`.

### 5. Identificação da Equipe e Licença no README
* **Situação Original:** Repositório inicial do William possuía placeholders "A definir".
* **Decisão & Resolução Oficial (24/10/2026):** **CONCLUÍDO**.  
  O [`README.md` principal da raiz do repositório](../../README.md) lista os **9 integrantes da Equipe 15** na seção de Equipe (linhas 176 a 192) com seus respectivos papéis de atuação (Luciana, Giovane, Iza, Marcelo, Cristiano, Victor, William, Gisele e Alexander), e traz formalizada a cláusula de **Licença MIT** (linhas 228 a 230).

### 6. Branch `arena/9bba261b-hackatoon-oracle`
* **Situação Original:** Branch de desenvolvimento isolado do William aguardando decisão.
* **Decisão & Resolução Oficial (24/10/2026):** **SUPERADO / ENCERRADO**.  
  A branch pertencia exclusivamente ao ambiente de desenvolvimento do gerador de fixtures. A base oficial da organização adota o fluxo limpo com `main`, `develop` e `feature/ingestao-documentos`.
