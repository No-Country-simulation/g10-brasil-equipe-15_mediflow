# Catálogo de documentos de teste — MediFlow

**Projeto:** MediFlow — Equipe 15 (Hackathon ONE G10 - Oracle & Alura)  
**Repositório Oficial:** `g10-brasil-equipe-15_mediflow`  
**Versão:** 2.1 — 26/10/2026 (Homologado e Integrado ao Pytest — 208 testes)  
**Atualização desta versão:** 79 fixtures oficiais cobrindo integralmente as 8 categorias, limites de tamanho e páginas (10MB / 20 páginas), múltiplos encodings (Latin-1/UTF-8), regras de conflito (A1) e casos de borda (A4/A5).  
**Execução Automatizada:** `python -m pytest tests/test_contrato_fixtures.py` (79 testes) ou `python -m pytest` (208 testes)  
**Contrato Canônico:** [`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md) e [`src/schemas/clinical.py`](../../src/schemas/clinical.py)  
**Base documental:** `Projeto_oracle.pdf`, `MediFlow_-_Análise_de_Requisitos_v1.1.pdf` e `MediFlow_Especificacao_Funcional_v1.0.pdf`  
**Manifesto executável:** [`tests/fixtures/manifest.csv`](../../tests/fixtures/manifest.csv)

---

## 1. Resposta curta

Você não precisa de um documento por especialidade médica. Precisa de **um documento por tipo controlado × formato**, mais um conjunto pequeno de **variações deliberadas** para provar as regras de revisão, o limiar de confiança, os conflitos e os erros.

| Nível | Quantidade | Para que serve |
| --- | ---: | --- |
| **Kit de demonstração** | **12 arquivos** ✅ | Cobre os 3 cenários obrigatórios, os 5 destinos, os 3 formatos e as 8 classes de tipo. É o mínimo defensável para o pitch. |
| **Kit recomendado** | **57 arquivos** ✅ | Cobre tipos × formatos, ausência de campos, limiar, conflitos, urgência simultânea, qualidade de imagem e negativos técnicos. É o conjunto que eu levaria para a banca. |
| **Kit completo** | **79 arquivos** ✅ | Acrescenta PDF digitalizado para todos os tipos, os 4 casos de diferenciais (OCR, carimbo, tabela de exames, guia TISS) e o bloco Limite (tamanho, páginas, formato e texto). |
| **Simulações operacionais** | **8 cenários, 0 documentos novos** | Falhas de Gemini e de OCI, testadas por stub/flag reutilizando os documentos acima. Timeout de 60 s e 2 retries (A6). |

> **Mínimo literal dos critérios de aceite (seção 16 da especificação): 8 arquivos.** Três rendições do mesmo conteúdo (texto, PDF e imagem) + cinco variações de campo ausente. Esse número passa na leitura literal, mas não prova os 5 destinos nem os 8 tipos — por isso não recomendo usá-lo como meta.

**Distribuição do kit completo (79):** PDF digital, PDF digitalizado, imagem (JPG/PNG/WEBP) e texto, mais os arquivos inválidos. Por cenário: rotina, urgência, ambiguidade e erro — a contagem exata está no manifesto e no mapa em PDF, ambos gerados a partir dele.

> **Status: 79 de 79 fixtures produzidos.** O kit de demonstração está em [`tests/fixtures/demo/`](../../tests/fixtures/demo/) — 12 casos × (TXT + PDF + JPG + `expected.json`). O restante está em [`tests/fixtures/catalogo/`](../../tests/fixtures/catalogo/) — 65 casos × 4 arquivos + 12 negativos técnicos × 2. O mapa visual dos 79 está em [Mapa_de_Documentos_de_Teste_MediFlow.pdf](Mapa_de_Documentos_de_Teste_MediFlow.pdf).
>
> **Quatro arquivos grandes (> 10MB) ficam fora do versionamento do git** (`.gitignore`) para manter o repositório leve e ágil (conforme documentado em [`AUDITORIA_2026-10-20.md`](AUDITORIA_2026-10-20.md) Seção 3), enquanto seus respectivos metadados de asserção (`expected.json`) e o manifesto oficial permanecem 100% versionados e testados pela suíte Pytest.

---

## 2. O que o sistema precisa avaliar

Tudo abaixo vem da especificação funcional v1.0 e define as dimensões do catálogo.

| Dimensão | Valores | Fonte |
| --- | --- | --- |
| **Tipo de documento** | `RECEITUARIO_MEDICO`, `LAUDO_EXAME_LABORATORIAL`, `LAUDO_EXAME_IMAGEM`, `GUIA_PROCEDIMENTO`, `RELATORIO_ALTA_INTERNACAO`, `ATESTADO_MEDICO`, `OUTRO`, `NAO_IDENTIFICADO` | §5.1 |
| **Formato de entrada** | PDF digital, PDF digitalizado, imagem (JPG/PNG/WEBP) e texto | RF-02, §3.1, decisão A6 |
| **Prioridade** | `URGENTE`, `ROTINA`, `NAO_IDENTIFICADA` | §5.2 |
| **Status** | `RECEBIDO`, `PROCESSANDO`, `PROCESSADO`, `EM_REVISAO`, `ERRO_PROCESSAMENTO`, `ERRO_PERSISTENCIA` | §5.3 |
| **Destino lógico** | `FILA_URGENCIA_MEDICA`, `FARMACIA_HOSPITALAR`, `AUDITORIA_AUTORIZACOES`, `PRONTUARIO_ELETRONICO`, `FILA_REVISAO_HUMANA` | §5.4 |
| **Desfecho do cenário** | rotina, urgência, ambiguidade/ilegibilidade, erro | §8.2, §16 |

### Duas leituras importantes

1. **`OUTRO` e `NAO_IDENTIFICADO` são resultados de classificação, não tipos que se "escrevem".** Você não cria um atestado "não identificado": você cria um documento fora da taxonomia (declaração de acompanhante, relatório de enfermagem) ou um documento ilegível, e o sistema deve devolver `OUTRO` ou `NAO_IDENTIFICADO`. Por isso o bloco Matriz tem 3 arquivos para cada um: são **testes negativos de classificação**, não documentos clínicos válidos.
2. **JSON não é um tipo de documento.** O JSON é o envelope da API (`documento_texto`, `metadados`, `canal_origem`). Um texto enviado como JSON continua sendo um documento de texto. Não é preciso criar "um JSON por tipo".

---

## 3. Por que 24 não bastam

A matriz 8 tipos × 3 formatos = **24** é o piso, não o teto. A especificação exige comportamentos que só aparecem quando você **quebra uma coisa de cada vez**:

- **RF-21** lista 5 campos cuja ausência obriga revisão (nome do paciente, idade, nome do médico, CRM, diagnóstico) e 3 cuja ausência **não** obriga (CID, medicamentos, exames). São 8 asserções diferentes.
- **RF-18** exige o comportamento nas duas bordas do limiar: `0,84` revisa e `0,85` não revisa. Um único documento não prova as duas.
- **RF-16** pede conflito de CID × diagnóstico, dose suspeita, campos contraditórios e discrepância de prioridade. Cada conflito tem uma regra distinta.
- **§8.2** exige o caso simultâneo de urgência + ambiguidade, com **dois destinos** no mesmo payload.
- **RF-02/RF-04** separam PDF digital de PDF digitalizado; **RF-03** exige rejeições de formato, tamanho, MIME e envelope.

Um mesmo arquivo pode servir a vários **casos de teste** (submissão 202, polling, histórico, persistência), mas não a várias **asserções de conteúdo** — se ele falhar, você não sabe qual regra quebrou.

---

## 4. Contagem por bloco

| Bloco | Para que serve | Arquivos | Acumulado |
| --- | --- | ---: | ---: |
| **Matriz** | Tipos × formatos | 24 | 24 |
| **Ausencia** | Campos ausentes (5 que revisam + 3 que não revisam) | 8 | 32 |
| **Borda** | Fronteira do limiar (0,84 e 0,85) e de prioridade/urgência indefinidas (A4, A5) | 4 | 36 |
| **Conflito** | Conflitos, contradições, alto risco e gravidade do conflito (A1) | 7 | 43 |
| **Simultaneo** | Urgência + ambiguidade simultâneas | 2 | 45 |
| **Qualidade** | Ilegibilidade e PDFs especiais | 8 | 53 |
| **Validacao** | Negativos técnicos de entrada | 8 | 61 |
| **Limite** | Limites operacionais: tamanho, páginas, formato e texto (A6) | 8 | 69 |
| **Escaneado** | PDF digitalizado para os 6 tipos restantes | 6 | 75 |
| **Diferencial** | Itens opcionais | 4 | **79** |

---

## 5. Bloco Matriz — tipo × formato (24)

Composição: 6 tipos clínicos × 3 formatos = 18; `OUTRO` × 3 = 3; `NAO_IDENTIFICADO` × 3 = 3.

Regra de Ouro: **PDF = PDF digital com camada de texto** (não escaneado). O PDF digitalizado tem bloco próprio (Q e E), porque o caminho de leitura é diferente.

#### Bloco Matriz — tipo × formato (24)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Matriz_Receituario_Pdf` | RECEITUARIO_MEDICO | PDF | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Receita médica de rotina, 2 medicamentos, paciente e CRM completos, legível. |
| `Matriz_Receituario_Imagem` | RECEITUARIO_MEDICO | IMAGEM | URGENCIA | FILA_URGENCIA_MEDICA | PROCESSADO | NAO | Foto de receita com prescrição de alto risco (opioide) e sinal textual de urgência. |
| `Matriz_Receituario_Texto` | RECEITUARIO_MEDICO | TEXTO | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Texto de receita de rotina com medicamento, dose, via e frequência explícitos. |
| `Matriz_LaudoLaboratorial_Pdf` | LAUDO_EXAME_LABORATORIAL | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Hemograma de rotina com resultados nominais, sem medicamentos. |
| `Matriz_LaudoLaboratorial_Imagem` | LAUDO_EXAME_LABORATORIAL | IMAGEM | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Foto de laudo laboratorial impresso, boa qualidade, rotina. |
| `Matriz_LaudoLaboratorial_Texto` | LAUDO_EXAME_LABORATORIAL | TEXTO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Texto de laudo laboratorial com exames realizados e ausência de CID (não exige revisão). |
| `Matriz_LaudoDeImagem_Pdf` | LAUDO_EXAME_IMAGEM | PDF | URGENCIA | FILA_URGENCIA_MEDICA | PROCESSADO | NAO | Laudo de tomografia com TEP agudo e recomendação de correlação clínica urgente (caso do brief). |
| `Matriz_LaudoDeImagem_Imagem` | LAUDO_EXAME_IMAGEM | IMAGEM | URGENCIA | FILA_URGENCIA_MEDICA | PROCESSADO | NAO | Foto de laudo de raio-X com achado crítico e recomendação de urgência. |
| `Matriz_LaudoDeImagem_Texto` | LAUDO_EXAME_IMAGEM | TEXTO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Texto de laudo de ultrassom de rotina, sem sinais de urgência. |
| `Matriz_Guia_Pdf` | GUIA_PROCEDIMENTO | PDF | ROTINA | AUDITORIA_AUTORIZACOES | PROCESSADO | NAO | Guia de solicitação de ressonância eletiva, diagnóstico e CID explícitos. |
| `Matriz_Guia_Imagem` | GUIA_PROCEDIMENTO | IMAGEM | URGENCIA | FILA_URGENCIA_MEDICA | PROCESSADO | NAO | Foto de guia com pedido de urgência e justificativa clínica crítica. |
| `Matriz_Guia_Texto` | GUIA_PROCEDIMENTO | TEXTO | ROTINA | AUDITORIA_AUTORIZACOES | PROCESSADO | NAO | Texto de guia de procedimento eletivo, sem sinais de risco. |
| `Matriz_RelatorioDeAlta_Pdf` | RELATORIO_ALTA_INTERNACAO | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Relatório de alta completo: diagnóstico, CID, medicações de alta e orientações. |
| `Matriz_RelatorioDeAlta_Imagem` | RELATORIO_ALTA_INTERNACAO | IMAGEM | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Foto de relatório de internação impresso, rotina e legível. |
| `Matriz_RelatorioDeAlta_Texto` | RELATORIO_ALTA_INTERNACAO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Texto de relatório de alta truncado, sem diagnóstico/hipótese: ausência obrigatória. |
| `Matriz_Atestado_Pdf` | ATESTADO_MEDICO | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Atestado de afastamento de 3 dias, com CID e CRM completos. |
| `Matriz_Atestado_Imagem` | ATESTADO_MEDICO | IMAGEM | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Foto de atestado com carimbo e assinatura, dados legíveis. |
| `Matriz_Atestado_Texto` | ATESTADO_MEDICO | TEXTO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Texto de atestado de comparecimento, sem exames e sem medicamentos (não exige revisão). |
| `Matriz_Outro_Pdf` | OUTRO | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Declaração de comparecimento de acompanhante: fora da taxonomia, destino não mapeado. |
| `Matriz_Outro_Imagem` | OUTRO | IMAGEM | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Foto de relatório de enfermagem: fora da taxonomia de documentos clínicos do MVP. |
| `Matriz_Outro_Texto` | OUTRO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Texto administrativo de agendamento, sem dados clínicos: deve resultar em OUTRO + revisão. |
| `Matriz_NaoIdentificado_Pdf` | NAO_IDENTIFICADO | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | PDF escaneado ilegível (manchas/baixa qualidade): NAO_IDENTIFICADO, sem inventar dados. |
| `Matriz_NaoIdentificado_Imagem` | NAO_IDENTIFICADO | IMAGEM | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Foto totalmente desfocada de um documento: NAO_IDENTIFICADO e revisão obrigatória. |
| `Matriz_NaoIdentificado_Texto` | NAO_IDENTIFICADO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Texto genérico sem conteúdo clínico (lista de compras): NAO_IDENTIFICADO e revisão. |

#### Bloco Ausencia — campos ausentes (8)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Ausencia_Paciente_Nome` | RECEITUARIO_MEDICO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Receita sem nome do paciente, com todos os demais campos presentes. |
| `Ausencia_Paciente_Idade` | RECEITUARIO_MEDICO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Receita sem idade do paciente, com nome presente. |
| `Ausencia_Medico_Nome` | LAUDO_EXAME_LABORATORIAL | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Laudo sem nome do médico solicitante, mantendo CRM preenchido. |
| `Ausencia_Medico_Crm` | LAUDO_EXAME_LABORATORIAL | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Laudo sem CRM do solicitante, mantendo nome preenchido. |
| `Ausencia_Diagnostico` | GUIA_PROCEDIMENTO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Guia sem diagnóstico/hipótese diagnóstica. |
| `Ausencia_SomenteCid` | LAUDO_EXAME_IMAGEM | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Laudo com diagnóstico explícito mas sem CID: ausência de CID isolada NÃO exige revisão. |
| `Ausencia_SomenteMedicamentos` | LAUDO_EXAME_LABORATORIAL | TEXTO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Laudo sem medicamentos (lista vazia): NÃO exige revisão por si só. |
| `Ausencia_SomenteExames` | ATESTADO_MEDICO | TEXTO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Atestado sem exames: NÃO exige revisão por si só. |

#### Bloco Borda — limiar, prioridade e urgência indefinidas (4)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Borda_Score_084` | RECEITUARIO_MEDICO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Score combinado forçado em 0,84 (< 0,85): revisão obrigatória. Exige stub de score. |
| `Borda_Score_085` | RECEITUARIO_MEDICO | TEXTO | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Score combinado exatamente 0,85: NÃO revisa por esse critério isolado. Exige stub de score. |
| `Borda_Prioridade_NaoIdentificada` | RECEITUARIO_MEDICO | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Receita completa e legível em que nada permite definir a prioridade: `NAO_IDENTIFICADA` **é** ambiguidade e gera revisão (decisão A4). É o único gatilho do caso. |
| `Borda_Urgencia_Indeterminada` | LAUDO_EXAME_LABORATORIAL | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Laudo completo que não permite afirmar nem afastar urgência: `INDETERMINADO` conta como campo incerto e gera revisão (decisão A5). Não é urgência: sem alerta. |

#### Bloco Conflito — contradições, risco e gravidade (7)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Conflito_Cid_Diagnostico` | LAUDO_EXAME_IMAGEM | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Diagnóstico de lombalgia com CID de infarto agudo (I21): conflito explícito CID × diagnóstico. |
| `Conflito_Dose` | RECEITUARIO_MEDICO | TEXTO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Dose 10× acima do usual (ex.: losartana 500 mg): sinaliza conflito sem alterar o valor. |
| `Conflito_Prioridade` | GUIA_PROCEDIMENTO | TEXTO | AMBIGUIDADE | FILA_URGENCIA_MEDICA + FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Guia marcada como ROTINA no cabeçalho, mas com texto de urgência e sinais críticos. |
| `Conflito_Dados` | RELATORIO_ALTA_INTERNACAO | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Relatório com dois nomes/idades divergentes no cabeçalho e no corpo: contradição interna. |
| `Conflito_AltoRisco` | RECEITUARIO_MEDICO | IMAGEM | URGENCIA | FILA_URGENCIA_MEDICA | PROCESSADO | NAO | Receita de varfarina 10 mg sem texto de urgência: alto risco deve acionar a fila urgente. |
| `Conflito_Gravidade_Media` | GUIA_PROCEDIMENTO | PDF | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Conflito de gravidade **MÉDIA**: é impeditivo, revisa (A1). Scores forçados em 0,95 — o gatilho é a gravidade, não o score. Sem o caso, nada prova que MÉDIA continua bloqueando. |
| `Conflito_Gravidade_Baixa` | ATESTADO_MEDICO | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Conflito de gravidade **BAIXA** (grafia do nome): registrado em `qualidade.conflitos`, **não** bloqueia (A1). `score_extracao` 0,90 vem da fórmula aprovada: 1 − 0,1 por um conflito BAIXA (A3). |

#### Bloco Simultaneo — urgência + ambiguidade (2)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Simultaneo_Urgencia_Ilegivel` | RECEITUARIO_MEDICO | IMAGEM | URGENCIA | FILA_URGENCIA_MEDICA + FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Foto de receita urgente parcialmente ilegível: dois destinos, alerta e revisão simultâneos. |
| `Simultaneo_Urgencia_Score` | LAUDO_EXAME_IMAGEM | PDF | URGENCIA | FILA_URGENCIA_MEDICA + FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Laudo legível com urgência e score forçado em 0,70: dois destinos e alerta. Exige stub de score. |

#### Bloco Qualidade — ilegibilidade e PDFs especiais (8)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Qualidade_Foto_Desfocada` | NAO_IDENTIFICADO | IMAGEM | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Receita manuscrita muito desfocada: não preencher lacunas, encaminhar para revisão. |
| `Qualidade_Foto_Rotacionada` | LAUDO_EXAME_IMAGEM | IMAGEM | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Laudo fotografado com rotação de 90 graus: testa robustez do pipeline multimodal. |
| `Qualidade_Foto_Cortada` | GUIA_PROCEDIMENTO | IMAGEM | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Guia com metade da página fora do enquadramento, sem CRM: ausência obrigatória. |
| `Qualidade_Foto_BaixoContraste` | ATESTADO_MEDICO | IMAGEM | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Atestado com sombra e baixo contraste: campos incertos devem ser sinalizados. |
| `Qualidade_Pdf_SemTexto` | LAUDO_EXAME_IMAGEM | PDF_DIGITALIZADO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | PDF escaneado sem camada de texto (apenas imagem): prova o caminho multimodal do PDF digitalizado. |
| `Qualidade_Pdf_Multipagina` | RELATORIO_ALTA_INTERNACAO | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Relatório de 7 páginas: dentro do limite de 20 páginas (A6). Testa custo e extração em documento longo. |
| `Qualidade_Pdf_ComSenha` | — | PDF | ERRO | — | ERRO_PROCESSAMENTO | — | PDF protegido por senha: `ERRO_PROCESSAMENTO` + código `PDF_PROTEGIDO`, sem dados extraídos. |
| `Qualidade_Pdf_Corrompido` | — | PDF | ERRO | — | ERRO_PROCESSAMENTO | — | PDF truncado: `ERRO_PROCESSAMENTO` + código `PDF_CORROMPIDO`, sem dados extraídos. |

#### Bloco Validacao — negativos técnicos de entrada (8)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Validacao_ArquivoDocx` | — | DOCX | ERRO | — | 415 FORMATO_NAO_SUPORTADO | NAO | Arquivo .docx válido: formato fora do allowlist do MVP. |
| `Validacao_ArquivoVazio` | — | ARQUIVO_0KB | ERRO | — | 422 CAMPOS_INVALIDOS | NAO | Arquivo de 0 bytes: rejeitar antes de chamar o modelo. |
| `Validacao_JsonMalformado` | — | JSON | ERRO | — | 400 REQUISICAO_INVALIDA | NAO | JSON com vírgula final/sintaxe inválida. |
| `Validacao_EnvelopeVazio` | — | JSON | ERRO | — | 422 CAMPOS_INVALIDOS | NAO | Envelope JSON vazio ou sem campos obrigatórios. |
| `Validacao_SemConteudo` | — | MULTIPART | ERRO | — | 422 CAMPOS_INVALIDOS | NAO | Requisição sem arquivo e sem documento_texto. |
| `Validacao_ArquivoZip` | — | ZIP | ERRO | — | 415 FORMATO_NAO_SUPORTADO | NAO | Arquivo .zip: formato não suportado. |
| `Validacao_ArquivoGrande` | — | ARQUIVO_25MB | ERRO | — | 413 ARQUIVO_MAIOR_QUE_LIMITE | NAO | PDF válido de 25 MB: acima do limite de 10 MB (A6). Fora do git; o gerador recria. |
| `Validacao_MimeInvalido` | — | PDF_FALSO | ERRO | — | 415 MIME_INVALIDO | NAO | Extensão .pdf com conteúdo real de PNG: inconsistência extensão × MIME. |

#### Bloco Escaneado — PDFs digitalizados dos 6 tipos restantes (6)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Escaneado_Receituario_PdfDigitalizado` | RECEITUARIO_MEDICO | PDF_DIGITALIZADO | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Receita impressa escaneada em PDF (com camada de imagem), rotina. |
| `Escaneado_LaudoLaboratorial_PdfDigitalizado` | LAUDO_EXAME_LABORATORIAL | PDF_DIGITALIZADO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Laudo laboratorial escaneado em PDF, rotina. |
| `Escaneado_Guia_PdfDigitalizado` | GUIA_PROCEDIMENTO | PDF_DIGITALIZADO | ROTINA | AUDITORIA_AUTORIZACOES | PROCESSADO | NAO | Guia de procedimento escaneada em PDF, rotina. |
| `Escaneado_RelatorioDeAlta_PdfDigitalizado` | RELATORIO_ALTA_INTERNACAO | PDF_DIGITALIZADO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Relatório de alta escaneado em PDF, rotina. |
| `Escaneado_Atestado_PdfDigitalizado` | ATESTADO_MEDICO | PDF_DIGITALIZADO | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Atestado médico escaneado em PDF, rotina. |
| `Escaneado_Outro_PdfDigitalizado` | OUTRO | PDF_DIGITALIZADO | AMBIGUIDADE | FILA_REVISAO_HUMANA | EM_REVISAO | SIM | Documento administrativo escaneado fora da taxonomia: OUTRO + revisão. |

#### Bloco Diferencial — itens opcionais (4)

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Diferencial_ReceituarioManuscrito` | RECEITUARIO_MEDICO | IMAGEM | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Receita manuscrita legível (letra de médico): diferencial de OCR/visão. |
| `Diferencial_CarimboSobreposto` | LAUDO_EXAME_IMAGEM | IMAGEM | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Laudo escaneado com carimbo/assinatura sobreposta ao texto. |
| `Diferencial_HemogramaCompleto` | LAUDO_EXAME_LABORATORIAL | PDF | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Tabela de hemograma com 20 analitos, unidades e valores de referência. |
| `Diferencial_GuiaTiss` | GUIA_PROCEDIMENTO | PDF | ROTINA | AUDITORIA_AUTORIZACOES | PROCESSADO | NAO | Guia no formato TISS com códigos de procedimento e autorização. |

#### Bloco Limite — limites operacionais (8) · decisão A6 de 21/10/2026

Até aqui o catálogo não tinha **nenhum** caso de tamanho acima do limite nem de documento com mais páginas do que o permitido — os dois únicos casos que chegavam perto (`Validacao_ArquivoGrande` e `Qualidade_Pdf_Multipagina`) diziam "limite pendente na spec". Com o limite fixado em **10 MB e 20 páginas**, o bloco abaixo prova o corte dos dois lados, inclusive na fronteira.

| ID | Tipo | Formato | Cenário | Destino(s) esperado(s) | Status | Revisão | O que testa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Limite_Tamanho_10MB` | ATESTADO_MEDICO | PDF_10MB | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | PDF válido de **exatamente 10 MB** (10.485.760 bytes): no limite, deve ser **aceito**. O tamanho vem de um comentário de preenchimento; o conteúdo é o de um atestado comum. |
| `Limite_Tamanho_Acima10MB` | — | PDF_10_5MB | ERRO | — | 413 ARQUIVO_MAIOR_QUE_LIMITE | NAO | PDF válido de **10,5 MB**: 0,5 MB acima do limite. Provam, com o caso anterior, que o corte está em 10 MB — não em "muito maior". |
| `Limite_Paginas_20` | RELATORIO_ALTA_INTERNACAO | PDF_20PAGINAS | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Relatório de **exatamente 20 páginas**: no limite, deve ser **aceito**. |
| `Limite_Paginas_21` | — | PDF_21PAGINAS | ERRO | — | 413 ARQUIVO_MAIOR_QUE_LIMITE | NAO | Relatório de **21 páginas**: uma acima do limite. Rejeitar antes de qualquer inferência. |
| `Limite_Formato_Png` | RECEITUARIO_MEDICO | PNG | ROTINA | FARMACIA_HOSPITALAR | PROCESSADO | NAO | Imagem **PNG**: formato da lista aceita. A pasta tem os 3 arquivos padrão + o `.png` sob teste, declarado em `entrada.renditions`. |
| `Limite_Formato_Webp` | LAUDO_EXAME_IMAGEM | WEBP | ROTINA | PRONTUARIO_ELETRONICO | PROCESSADO | NAO | Imagem **WEBP**: formato da lista aceita. Mesma convenção do caso PNG. |
| `Limite_Texto_Acima10MB` | — | TEXTO_10_5MB | ERRO | — | 413 ARQUIVO_MAIOR_QUE_LIMITE | NAO | Texto de **10,5 MB** no envelope JSON: o limite de 10 MB vale para `documento_texto`, não só para o upload de arquivo. Fora do git; o gerador recria. |
| `Limite_Paginas_21_Digitalizado` | — | PDF_21PAGINAS_DIGITALIZADO | ERRO | — | 413 ARQUIVO_MAIOR_QUE_LIMITE | NAO | PDF **digitalizado** (só imagem) de **21 páginas**: a contagem de páginas não pode depender da camada de texto, senão o arquivo passaria por 1 página e seguiria para OCR. |

**Convenção dos casos de formato:** a pasta continua com `{ID}.txt`, `{ID}.pdf`, `{ID}.jpg` e `expected.json`, e ganha o arquivo no formato sob teste. O verificador lê a lista de arquivos esperados de `entrada.renditions`, não do nome da pasta — por isso não há exceção à regra dos 4 arquivos.

---

## 6. Simulações operacionais (8 cenários, **sem arquivos neste pacote**)

Estas falhas não se testam com um documento novo: testam-se com **stub, flag de ambiente ou mock do adaptador**, durante a implementação do pipeline. Nenhum arquivo é entregue aqui — a lista existe para o plano de testes da aplicação. Reutilize `Matriz_LaudoDeImagem_Pdf` (urgente) ou `Matriz_Receituario_Texto` (rotina) como entrada.

| ID | Falha simulada | Resultado esperado | Regra |
| --- | --- | --- | --- |
| `Simulacao_GeminiTimeout` | Gemini não responde em **60 s** (limite fixado em A6) | **2 retentativas com backoff**; se persistir, `ERRO_PROCESSAMENTO` (ou `EM_REVISAO` se já houver sinal de risco) | RF-04, §12, A6 |
| `Simulacao_GeminiIndisponivel` | Provedor indisponível (502/503/504) | Erro seguro, sem stack trace; possibilidade de reenvio | RF-04, §10.1 |
| `Simulacao_GeminiJsonInvalido` | Resposta do modelo não valida no Pydantic | Reparo limitado; se falhar, fallback para revisão/erro | RF-14, §12 |
| `Simulacao_GeminiCampoInvalido` | Campo desconhecido ou tipo errado na resposta | Não quebrar o consumidor; validar campos obrigatórios e enums | RF-14 |
| `Simulacao_OciFalhaNoOriginal` | OCI falha ao gravar o original | `ERRO_PERSISTENCIA`; **não** declarar recebimento durável | RF-28/RF-30, §12 |
| `Simulacao_OciFalhaNoResultado` | OCI falha ao gravar o resultado | `ERRO_PERSISTENCIA`; não marcar sucesso completo | RF-30, §12 |
| `Simulacao_FalhaNoAlerta` | Falha ao registrar o evento de alerta | Preservar a triagem urgente e registrar a falha do evento | §12 |
| `Simulacao_RetriesEsgotados` | As **2 retentativas** esgotaram | Estado de erro observável + correlação; permitir reenvio | RF-24, A6 |
| `Simulacao_GeminiRateLimit` | O provedor devolve **429** (limite de requisições) | Respeitar o retry com backoff; se persistir, `ERRO_PROCESSAMENTO` sem stack trace e com reenvio possível | RF-24, §10.1 |

Os códigos **401, 403 e 404** do §10.1 não entram nesta tabela nem viram fixture: autenticação está fora do MVP (decisão A8, §4 e §10.1 da EF) e 404 é roteamento da API, coberto pelo teste da aplicação — não por um documento de entrada.

---

## 7. Kit de demonstração — os 12 arquivos

Se o tempo apertar, produza **estes 12** primeiro. Eles cobrem os 15 critérios de aceite de forma defensável.

| # | ID | Prova que… |
| ---: | --- | --- |
| 1 | `Matriz_Receituario_Texto` | Texto é aceito e uma receita de rotina vai para `FARMACIA_HOSPITALAR` |
| 2 | `Matriz_Receituario_Pdf` | PDF digital é aceito e classificado |
| 3 | `Matriz_Receituario_Imagem` | Imagem é aceita e um sinal de urgência nunca vira rotina |
| 4 | `Matriz_LaudoDeImagem_Pdf` | Urgência explícita gera `FILA_URGENCIA_MEDICA` + alerta, sem revisão humana |
| 5 | `Matriz_LaudoLaboratorial_Pdf` | Laudo laboratorial de rotina vai para `PRONTUARIO_ELETRONICO` |
| 6 | `Matriz_Guia_Pdf` | Guia de procedimento vai para `AUDITORIA_AUTORIZACOES` |
| 7 | `Matriz_RelatorioDeAlta_Pdf` | Relatório de alta é classificado e extraído |
| 8 | `Matriz_Atestado_Texto` | Atestado é classificado; ausência de exames não gera revisão |
| 9 | `Matriz_NaoIdentificado_Imagem` | Documento ilegível vira `NAO_IDENTIFICADO` + revisão, sem dado inventado |
| 10 | `Matriz_Outro_Texto` | Documento fora da taxonomia vira `OUTRO` + revisão |
| 11 | `Ausencia_Paciente_Nome` | Ausência de campo obrigatório força `EM_REVISAO` |
| 12 | `Borda_Score_084` | Score abaixo de 0,85 força `EM_REVISAO` |

**Cobertura do kit:** 5 destinos, 3 formatos, 3 cenários, 8 classes de tipo, 1 ausência obrigatória e 1 caso de limiar.

---

## 8. Artefatos que acompanham cada documento

O documento sozinho não é um teste. Para cada fixture funcional, produza também:

| Artefato | Quantidade | Formato |
| --- | ---: | --- |
| Documento de entrada | 79 | TXT / PDF / JPG (+ PNG e WEBP nos casos de formato) — mais os 12 arquivos inválidos dos blocos Validacao e Limite |
| **Saída esperada** (`expected.json`) | 79 | `resposta_esperada` no formato do contrato: tipo, prioridade, destinos, revisão, qualidade e status |
| **Manifesto** | 1 | `tests/fixtures/manifest.csv` (este catálogo, em formato de máquina) |

O `expected.json` segue o schema `mediflow.fixture/2`:

| `tipo_de_teste` | Quantos | `resposta_esperada` |
| --- | ---: | --- |
| `funcional` | 65 | `TriagemMediFlow` completa |
| `erro_processamento` | 2 | `TriagemMediFlow` com `status=ERRO_PROCESSAMENTO` e `erro.codigo` |
| `negativo_tecnico` | 12 | `ErroResposta` (HTTP + código funcional) |

O contrato executável canônico é [`src/schemas/clinical.py`](../../src/schemas/clinical.py); a especificação oficial em português é o [`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md) (versão canônica oficial unificada).

**Não compare scores exatos.** O score autorrelatado pelo LLM não é probabilidade calibrada (RF-17). Compare faixas (`< 0,85`, `>= 0,85`, `== 0,85`) e, para os casos de borda Borda_Score_084/Borda_Score_085/Simultaneo_Urgencia_Score, use **stub de score** — sem isso o teste é intermitente e não serve como evidência.

---

## 9. Regras de construção dos documentos

1. **Somente dados fictícios**, conforme decisão confirmada da especificação (§15, item 5). Nada de nome, CPF, telefone, CRM ou e-mail de pessoa real.
2. **Marca d'água** em toda página: `DOCUMENTO FICTÍCIO — USO EXCLUSIVO EM TESTES`.
3. **Identidades consistentes**: um mesmo hospital fictício, um mesmo paciente por fixture e um mesmo médico por fixture. Se o paciente muda no meio do documento, isso deve ser um teste de contradição (Conflito_Dados), não um acidente.
4. **Uma variável por vez**: cada fixture de borda parte de um documento "base" e altera **só** o atributo testado. Se `Ausencia_Paciente_Nome` também estiver sem CRM, você não sabe qual regra disparou.
5. **CRM no formato `número-UF`** (RF-09), com `numero` e `uf` separados na saída.
6. **CID-10 só quando explícito** (RF-10). Ausência vira `null`, nunca sugestão.
7. **Ground truth revisada por uma pessoa** antes de virar `expected.json`. Um expected errado é pior do que não ter teste.
8. **Sem segredo no fixture**: nenhuma chave, token, URL assinada ou credencial da OCI.
9. **Nada de dado clínico real**, nem "anonimizado". O MVP inteiro é fictício.

---

## 10. Resolução das Decisões de Engenharia e Produto (Homologado em 24/10/2026)

Todas as definições de produto e engenharia que balizam as respostas esperadas dos 79 fixtures foram formalmente implementadas e homologadas na suíte de testes:

| Decisão / Item | Estado Histórico | Situação Homologada no Repositório Oficial (24/10/2026) |
| :--- | :--- | :--- |
| **Limite de upload (tamanho e páginas)** | ~~Pendente na EF v1.0~~ | **✅ Implementado e Blindado.** [`src/ingestion/loader.py`](../../src/ingestion/loader.py) valida `LIMITE_MAXIMO_BYTES = 10 * 1024 * 1024` (10 MB) e `LIMITE_MAXIMO_PAGINAS = 20`. Uploads que excedem esses limites retornam HTTP 413 `ARQUIVO_MAIOR_QUE_LIMITE` antes de qualquer chamada a LLM. |
| **Contrato de upload (multipart × JSON)** | A definir no backend | **✅ Implementado.** O `DocumentLoader` oferece `carregar_bytes` e `carregar_arquivo` suportando uploads web multipart e streams com detecção automática de formato e encodings (`UTF-8` e `Latin-1`). |
| **Regras clínicas de alto risco e conflito** | Dicionários abertos | **✅ Implementado.** Mapeado no modelo canônico [`src/schemas/clinical.py`](../../src/schemas/clinical.py) com regras R1 a R8 (detecção de CID divergente, doses fora de faixa, sinais clínicos e gravidade média/baixa). |
| **Urgência clínica isolada** | Divergência brief × EF | **✅ Resolvido conforme edital da Oracle.** Urgência pura vai para `FILA_URGENCIA_MEDICA` com status `PROCESSADO` e `requer_auditoria_humana = false`. `FILA_REVISAO_HUMANA` só é acionada em caso de ambiguidade clínica ou score abaixo do limiar. |
| **Autenticação e autorização** | `403` fora do escopo | **✅ Confirmado fora do escopo do MVP.** A API prioriza os fluxos assíncronos de triagem e persistência. |
| **Política de retenção e LGPD** | Risco de dados reais | **✅ Blindado.** O projeto opera exclusivamente com base sintética e fictícia (RNF-08), com disclaimer explícito formalizado no [`README.md` principal da raiz](../../README.md#privacidade-e-lgpd-rnf-08). |
| **Throughput e velocidade de execução** | Dependia de medição | **✅ Validado.** A suíte com 144 testes automatizados executa em apenas **~1.1s** com 100% de aprovação. |

**Dica de implementação e testes:** Para execução estritamente determinística dos casos de borda (`Borda_Score_084`, `Borda_Score_085` e `Simultaneo_Urgencia_Score`), os fixtures utilizam asserções exatas de limiar e regras de inferência sem depender de flutuações de rede da LLM externa.

---

## 11. Estrutura de pastas e nomes

```text
tests/fixtures/
├── manifest.csv                  # este catálogo em formato de máquina
├── README.md                     # regras, convenção de nomes e casos especiais
├── demo/                         # ✅ 12 casos de pitch
│   ├── Matriz_Receituario_Texto/
│   │   ├── Matriz_Receituario_Texto.txt
│   │   ├── Matriz_Receituario_Texto.pdf
│   │   ├── Matriz_Receituario_Texto.jpg
│   │   └── expected.json
│   └── ... (12 pastas)
└── catalogo/                     # ✅ 55 casos restantes
    ├── README.md
    ├── Ausencia_Paciente_Idade/ ...          # 47 casos com 4 arquivos (45 funcionais + 2 de erro de leitura)
    └── Validacao_ArquivoDocx/ ...            # 8 negativos técnicos, com 1 arquivo inválido cada
```

**Nome da pasta e do arquivo:** o ID é a própria pasta e o prefixo dos arquivos — `Bloco_Assunto_Detalhe`, sem abreviações e sem acentos. O formato entra apenas como sufixo do arquivo: `Matriz_Receituario_Pdf.pdf`, `Matriz_Receituario_Imagem.jpg`, `Matriz_Receituario_Texto.txt`. O ID é único e casa com o `manifest.csv` e o `expected.json`.

| Bloco | Prefixo da pasta | Regra do restante do nome |
| --- | --- | --- |
| Matriz | `Matriz_` | tipo + formato (`Matriz_Guia_Imagem`) |
| Ausencia | `Ausencia_` | sujeito + campo ausente (`Ausencia_Paciente_Nome`) |
| Borda | `Borda_` | score testado (`Borda_Score_084`) |
| Conflito | `Conflito_` | tipo de contradição (`Conflito_Dose`) |
| Simultaneo | `Simultaneo_` | condição + condição (`Simultaneo_Urgencia_Ilegivel`) |
| Qualidade | `Qualidade_` | origem + defeito (`Qualidade_Foto_Rotacionada`) |
| Validacao | `Validacao_` | entrada inválida (`Validacao_ArquivoDocx`) |
| Escaneado | `Escaneado_` | tipo + condição (`Escaneado_Guia_PdfDigitalizado`) |
| Diferencial | `Diferencial_` | item opcional (`Diferencial_GuiaTiss`) |

Como o bloco vem primeiro, ordenar a pasta por nome já agrupa os casos por assunto — e nenhum nome depende de abreviação para ser entendido.

---

## 12. Como executar e reproduzir os testes

> **Todos os 79 fixtures oficiais estão integrados e são executados diretamente pelo Pytest:**
> - Para rodar apenas os 79 fixtures do catálogo: `python -m pytest tests/test_contrato_fixtures.py`
> - Para rodar a suíte completa da aplicação (208 testes automatizados): `python -m pytest`
> 
> *(Nota de Governança: Todos os 79 fixtures sintéticos já se encontram pré-gerados e prontos para consumo imediato em `tests/fixtures/`. A equipe e a banca avaliadora não precisam compilar nem gerar arquivos adicionais para executar os testes via Pytest. Os scripts originais de síntese estão preservados no pacote de insumos históricos de QA).*

1. **Escolha a fonte**: escreva o conteúdo clínico em `source/{ID}.md`, com dados fictícios e marca d'água.
2. **Gere as três rendições**: texto puro, PDF digital (com camada de texto) e imagem (foto/scan). Para o PDF digitalizado, gere o PDF a partir de uma imagem, sem camada de texto.
3. **Crie as bordas**: para cada fixture dos blocos Ausencia, Borda, Conflito e Simultaneo, remova ou altere **um único** campo em relação ao documento base.
4. **Escreva o `expected.json`** com tipo, prioridade, destinos, `requer_auditoria_humana`, campos ausentes/incertos, status e regra acionada.
5. **Rode o pipeline** e compare com `resposta_esperada`. No bloco Validacao, compare o envelope de erro (`http` + `codigo_funcional`); nos dois PDFs ilegíveis, compare o `status` e o `erro.codigo`.
6. **Atualize o manifesto** se algum comportamento mudar — o `manifest.csv` é a fonte de verdade dos testes.

---

## 13. Rastreabilidade com os critérios de aceite (§16)

> **Status de Cobertura Oficial (26/10/2026):** ✅ **100% dos 15 critérios de aceite comprovados e aprovados** via testes automatizados no Pytest (208 testes aprovados em ~3.3s).

| Critério | Fixtures que comprovam |
| --- | --- |
| 1. Texto + 1 PDF + 1 imagem aceitos | `Matriz_Receituario_Texto`, `Matriz_Receituario_Pdf`, `Matriz_Receituario_Imagem` |
| 2. Documento padrão classificado e roteado | `Matriz_Receituario_*`, `Matriz_LaudoLaboratorial_*`, `Matriz_Guia_*`, `Matriz_RelatorioDeAlta_*`, `Matriz_Atestado_*` |
| 3. Documento urgente com alerta | `Matriz_LaudoDeImagem_Pdf`, `Matriz_LaudoDeImagem_Imagem`, `Matriz_Guia_Imagem`, `Conflito_AltoRisco` |
| 4. Documento ambíguo/ilegível em revisão | `Matriz_NaoIdentificado_*`, `Qualidade_Foto_Desfocada`, `Matriz_RelatorioDeAlta_Texto` |
| 5. Ausência dos 5 campos obrigatórios | `Ausencia_Paciente_Nome`, `Ausencia_Paciente_Idade`, `Ausencia_Medico_Nome`, `Ausencia_Medico_Crm`, `Ausencia_Diagnostico` |
| 6. Submissão 202 + consulta posterior | Qualquer fixture funcional (mesmo `documento_id`) |
| 7. Evento urgente simulado, sem envio externo | `Matriz_LaudoDeImagem_Pdf`, `Simultaneo_Urgencia_*` |
| 8. Score < 0,85 revisa; == 0,85 não revisa | `Borda_Score_084`, `Borda_Score_085` |
| 8a. Prioridade/urgência indefinidas revisam | `Borda_Prioridade_NaoIdentificada`, `Borda_Urgencia_Indeterminada` (A4, A5) |
| 8b. Conflito: MÉDIA revisa, BAIXA só registra | `Conflito_Gravidade_Media`, `Conflito_Gravidade_Baixa` (A1) |
| 8c. Limites de tamanho, páginas, formato e texto | `Limite_Tamanho_10MB`, `Limite_Tamanho_Acima10MB`, `Limite_Paginas_20`, `Limite_Paginas_21`, `Limite_Paginas_21_Digitalizado`, `Limite_Formato_Png`, `Limite_Formato_Webp`, `Limite_Texto_Acima10MB` (A6) |
| 9. Campos ausentes não inferidos | `Ausencia_*`, `Matriz_NaoIdentificado_*` |
| 10. Persistência no OCI informada | qualquer fixture + simulação de falha do OCI |
| 11. Histórico ordenado e JSON validado | Qualquer fixture funcional + `GET /historico` |
| 12. Regras, versão, justificativa e destino rastreáveis | `Conflito_*`, `Simultaneo_*` |
| 13. Interface mostra estados sem segredos | `Matriz_*` |
| 14. README + demonstração dos 3 cenários | Kit de demonstração (12) |
| 15. Nenhum opcional declarado sem prova | Bloco Diferencial (se implementado) |

---

## 14. O que você **não** precisa criar

- **Um documento por especialidade médica.** A especialidade é texto livre (RF-06); não há lista fechada. Use 3 ou 4 especialidades variadas (radiologia, cardiologia, clínica médica, pediatria) e siga.
- **Um JSON por tipo de documento.** O JSON é envelope de transporte, não tipo documental.
- **Um caso urgente para cada um dos 8 tipos.** Dois ou três já provam a regra; o resto é custo sem cobertura nova.
- **Integrações reais** com prontuário, farmácia, operadora, TISS/TUSS, Slack ou e-mail. Os destinos são lógicos/simulados no MVP (§3.2).
- **Documentos com dados reais ou "anonimizados".** O MVP inteiro usa dados fictícios.
- **79 arquivos antes de codificar.** Comece pelos 12 do kit de demonstração; o restante entra em paralelo ao desenvolvimento.

---

## 15. Referências

- `Projeto_oracle.pdf` — brief do hackathon, formatos, entregáveis e checklist de avaliação.
- `MediFlow_-_Análise_de_Requisitos_v1.1.pdf` — visão geral, requisitos RF/RNF/RN e decisões do time.
- `MediFlow_Especificacao_Funcional_v1.0.pdf` — §5 (vocabulário), §6 (fluxo), §7 (RF-01 a RF-30), §8 (regras e tabela de decisão), §9 (modelo de dados), §10 (API), §12 (erros), §16 (critérios de aceite) e §15 (pendências).
- [`tests/fixtures/manifest.csv`](../../tests/fixtures/manifest.csv) — os 79 fixtures em formato de máquina.
