# Auditoria de consistência — 2026-10-20

> **Adendo de Homologação no Repositório Oficial (24/10/2026):**  
> Todos os 79 fixtures oficiais, a regra CRM-SP e a resolução da urgência do edital foram completamente migrados e homologados no repositório oficial [`No-Country-simulation/g10-brasil-equipe-15_mediflow`](https://github.com/No-Country-simulation/g10-brasil-equipe-15_mediflow).  
> A verificação de conformidade agora é executada diretamente pelo Pytest (`tests/test_contrato_fixtures.py`), totalizando 143 testes aprovados em conjunto com a ingestão e o workflow LangGraph.

> **Retrato Original de 20/10/2026:** Os números abaixo (67 fixtures, 59 pastas com 4
> arquivos, 8 negativos) eram os daquela data e não devem ser lidos como estado
> atual. Em 21/10/2026 a suíte passou a **79 fixtures** (65 funcionais + 2 erros
> de leitura + 12 negativos técnicos), com o bloco **Limite** e os casos de
> gravidade, prioridade e urgência indefinidas. Vale hoje o que está no
> [`manifest.csv`](../../tests/fixtures/manifest.csv) e no
> [catálogo](CATALOGO_DE_DOCUMENTOS_DE_TESTE.md).

**Escopo:** Validação de regras em todos os formatos: texto, PDF, imagem, `expected.json`, manifesto, documentação e suíte de testes.

---

## 1. Branches analisadas

| Branch | Conteúdo | Situação |
| --- | --- | --- |
| `main` | Só o `README.md` inicial (`# hackatoon_oracle`) | Destino do merge |
| `arena/9bba261b-hackatoon-oracle` | Projeto completo: 67 fixtures, contrato, geradores, verificadores, PDFs de origem, ZIP. 10 commits, 2026-10-19/20 | Trazido para `main` nesta auditoria |
| `arena/7ab29156-hackatoon-oracle` | Sessão atual; base em `main` | Recebeu o merge (fast-forward) e as correções |

Não há Pull Requests abertos.

## 2. Regra CRM-SP: o que foi conferido

O hospital fictício (Hospital Aurora) fica em São Paulo. Todo CRM tem de ser `-SP`. Na branch `9bba261b`, três médicos assinavam com CRM de outra UF (`203114-RJ`, `176543-MG`, `154321-PR`); o commit `07bf2fe` os unificou em SP, mantendo o número de cada médico. Esta auditoria confirmou a correção em cada formato:

| Formato | Itens | Resultado |
| --- | ---: | --- |
| `.txt` com CRM | 47 | 47 de 47 em `-SP`; 0 em outra UF |
| `expected.json` com CRM | 47 | 47 de 47 com `uf: "SP"` e o mesmo número do TXT |
| Imagens `.jpg` (OCR local, RapidOCR) | 111 leituras de CRM | 111 de 111 em `-SP`; número igual ao `expected.json` |
| PDFs com camada de texto | 46 abertos com texto | 37 ocorrências `número-SP`; 0 em outra UF |
| PDFs sem camada de texto (OCR da página renderizada) | 17 | CRM lido em `-SP` onde o expected declara CRM |
| PDFs de origem (`Projeto_oracle.pdf` e especificações) | 3 | `CRM-SP 145892`; nenhuma UF divergente |
| Mapa de documentos (PDF, 8 páginas) | 1 | Sem CRM de outra UF |
| Geradores (`tools/`) e verificador | — | Nenhum CRM de outra UF no código |

Cada médico tem **um único número de CRM** em todos os documentos.

**Casos sem CRM (corretos):** `Ausencia_Medico_Crm`, `Qualidade_Foto_Cortada` (o CRM está fora do recorte), os 4 `*_NaoIdentificado_*`/`*_Outro_*` e os ilegíveis. Nesses casos o TXT diz `CRM não informado` ou `CRM não visível`, e o `expected.json` declara ausência.

## 3. Problemas encontrados e corrigidos

| # | Onde | Problema | Correção |
| --- | --- | --- | --- |
| 1 | `tools/verificar_consistencia.py` | Seções impressas como 1, 2, 3, 4, 6, 7: não existia a 5, e a docstring numerava diferente | Seções renumeradas 1 a 6 (docstring e saída iguais) |
| 2 | `verificar_consistencia.py` × docs | Em clone limpo o verificador dava **1 erro** (`Validacao_ArquivoGrande.pdf`, ignorado pelo Git), enquanto a documentação dizia "0 erros" | Arquivo ausente virou **aviso** com instrução de regeneração |
| 3 | `testar_contrato.py` × verificador | Um dizia "57 funcionais + 2 erros de leitura", o outro "59 funcionais" | Verificador agora conta por `tipo_de_teste` (57 funcionais, 2 erro_processamento, 8 negativo_tecnico) |
| 4 | Geradores | Não eram reprodutíveis: `Image.effect_noise` usa o `rand()` da libc sem semente, e o MuPDF grava `/ID` aleatório. O commit `07bf2fe` dizia "rodar duas vezes não muda um byte", o que era falso para 2 arquivos | Ruído com semente por chamada (`ruido_deterministico`); `/ID` derivado do nome do caso. Agora duas execuções geram os mesmos bytes, exceto o PDF com senha (item 5) |
| 5 | `Qualidade_Pdf_ComSenha.pdf` | Criptografia AES-256 do PyMuPDF usa salt aleatório: o arquivo muda a cada geração | Documentado como exceção. Conteúdo e senha (`mediflow123`) são estáveis |
| 6 | `dist/hackatoon_oracle-mediflow-completo.zip` | Nomes com acento corrompidos (`MediFlow_-_An├ílise…`), porque o ZIP foi gravado sem flag UTF-8 | Novo `tools/gerar_pacote.py`: UTF-8, datas fixas, contagem atualizada sozinha |
| 7 | `dist/README.md` | Declarava 344 arquivos (o pacote tinha 274) e apontava o download para a branch `9bba261b` | Contagem real; link agora aponta para `main` |
| 8 | `docs/testes/CONTRATO_DE_DADOS.md` | Citava "== 6. Coerência clínica" e "0 erros, 0 avisos" sem a ressalva do item 2 | Referência corrigida para a seção 5; resultado descrito com as contagens reais |
| 9 | `docs/testes/CATALOGO_DE_DOCUMENTOS_DE_TESTE.md` | Árvore dizia "47 casos funcionais" (são 45 funcionais + 2 de erro de leitura, todos com 4 arquivos) e colocava os negativos dentro de `Validacao_ArquivoGrande/` | Árvore e contagens corrigidas |
| 10 | `tests/fixtures/README.md` | Não explicava a regra da UF do verificador, o aviso do arquivo de 25 MB nem a exceção de reprodutibilidade | Nota adicionada |
| 11 | `LEIA-ME.txt`, `README.md` | Descreviam o verificador com a lista antiga e não citavam o empacotador | Atualizados |

A reprodutibilidade (item 4) foi confirmada rodando os geradores duas vezes e comparando o SHA-256 de todos os arquivos de `tests/` e `docs/`. O item 2 foi confirmado rodando o verificador num clone sem o arquivo de 25 MB.

## 4. Verificações executadas

| Verificação | Resultado |
| --- | --- |
| `python3 tests/testar_contrato.py` | 67 fixtures válidos (57 funcionais + 2 erros de leitura + 8 negativos), 0 falhas |
| `python3 tools/verificar_consistencia.py` | 67 pastas (59 com 4 arquivos, 8 com 2), 0 erros, 0 avisos |
| Manifesto × `expected.json` | 67 linhas, 0 divergências (tipo, status, revisão, notificação, destinos) |
| Distribuição do catálogo | 19 PDF digital, 7 digitalizado, 16 imagem, 17 texto, 8 inválidos. Cenários: 29 rotina, 7 urgência, 21 ambiguidade, 10 erro. Bate com o texto do catálogo |
| Casos especiais | `Qualidade_Pdf_ComSenha`: AES-256, senha `mediflow123` abre. `Qualidade_Pdf_Multipagina`: 7 páginas. `Validacao_ArquivoGrande.pdf`: 26 214 449 bytes (25 MiB). `Validacao_ArquivoZip.zip` e `Validacao_ArquivoDocx.docx` abrem como ZIP |
| Reprodutibilidade | Duas execuções dos três geradores: idênticas, exceto `Qualidade_Pdf_ComSenha.pdf` (item 5) |
| Pacote ZIP | Gerado por `tools/gerar_pacote.py`; testado com `testzip()` e sem erros de nome |

## 5. Pendências (decisões de produto, não corrigidas)

> **Status de Homologação no Repositório Oficial (24/10/2026):**
> Todas as pendências foram tratadas na integração oficial:
> 1. **UF no contrato:** Resolvido no schema `src/schemas/clinical.py` aceitando qualquer UF e adotando `"SP"` como padrão quando omitida.
> 2. **Limite de tamanho e páginas:** Resolvido em `src/ingestion/loader.py` fixando limite de **10 MB** e máximo de **20 páginas** (`ARQUIVO_MAIOR_QUE_LIMITE`), alinhado a `Limite_Paginas_21`.
> 3. **Números de CRM:** Mitigado via disclaimer e nota explícita de conformidade LGPD (RNF-08) em ambiente sintético.
> 4. **Urgência clínica:** Resolvido conforme edital da Oracle: urgência pura sem ambiguidade vai direta para `FILA_URGENCIA_MEDICA` com `PROCESSADO`.
> 5. **README:** Tabela com os 9 membros da Equipe 15 e seção de licença MIT adicionadas.
> 6. **Branch arena:** Superado; não se aplica ao repositório oficial da equipe.

1. **Validação de UF no contrato.** O modelo `Crm` (`app/models.py`) aceita qualquer UF de 2 letras. A regra "todo CRM é SP" vale para os fixtures (o verificador reprova outra UF), não para o sistema. Forçar SP no contrato bloquearia um médico de outro estado que legitimamente assine um documento. Decisão a confirmar com o time.
2. **Limite de tamanho.** A especificação não define o limite de upload. O catálogo propõe 10 MB e 10 páginas, mas isso ainda não foi decidido (já registrado no catálogo).
3. **Números de CRM.** Os CRMs são fictícios, mas são números de 6 dígitos que podem coincidir com registros reais. Antes de publicar os fixtures fora do repositório, vale conferir ou trocar os números.
4. **Divergência brief × especificação.** O `Projeto_oracle.pdf` diz que urgência tem `requer_auditoria_humana: false`, mas a especificação v1.0 manda `EM_REVISAO` (já registrado no catálogo, seção 10). Os fixtures seguem a especificação.
   > **Resolvido em 21/10/2026 — decisão: seguir o `Projeto_oracle.pdf`.** Urgência isolada passa a terminar em `PROCESSADO`, com `requer_auditoria_humana = false`, um único destino (`FILA_URGENCIA_MEDICA`) e alerta registrado; `EM_REVISAO` só com ambiguidade. Regra R1 de `app/models.py` alterada, 5 fixtures regenerados, contrato e catálogo atualizados. A EF v1.0 (§5.3 e §8.2) e a Análise de Requisitos serão atualizadas pela equipe.
5. **Placeholders do README.** Equipe e licença seguem como "A definir".
6. **Branch `arena/9bba261b-hackatoon-oracle`.** Já está incorporada a `main`. Pode ser apagada quando convier; esta auditoria não a remove.
