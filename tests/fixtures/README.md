# Fixtures do MediFlow

Este diretório guarda os documentos fictícios usados nos testes do agente de triagem.

- **Contrato (o que é uma resposta válida):** [`docs/testes/CONTRATO_DE_DADOS.md`](../../docs/testes/CONTRATO_DE_DADOS.md) e [`app/models.py`](../../app/models.py)
- **Catálogo analítico:** [`docs/testes/CATALOGO_DE_DOCUMENTOS_DE_TESTE.md`](../../docs/testes/CATALOGO_DE_DOCUMENTOS_DE_TESTE.md)
- **Mapa em PDF:** [`docs/testes/Mapa_de_Documentos_de_Teste_MediFlow.pdf`](../../docs/testes/Mapa_de_Documentos_de_Teste_MediFlow.pdf)
- **Manifesto (fonte de verdade):** [`manifest.csv`](manifest.csv)
- **Status:** **79 de 79 fixtures produzidos**

## Estrutura

```text
tests/fixtures/
├── manifest.csv        # 79 linhas: ID, tipo, formato, cenário, destino e status esperados
├── demo/               # 12 casos de pitch (1 pasta por fixture)
├── catalogo/           # 67 casos restantes, incluindo os 12 negativos técnicos
└── README.md           # este arquivo
```

Cada pasta de fixture contém:

| Arquivo | O que é |
| --- | --- |
| `{ID}.txt` | Documento em texto puro (UTF-8) |
| `{ID}.pdf` | Mesma peça em PDF (digital, escaneado, protegido ou corrompido, conforme o caso) |
| `{ID}.jpg` | Mesma peça fotografada, em JPEG 150 dpi |
| `{ID}.png` / `{ID}.webp` | Só nos dois casos de formato do bloco Limite |
| `expected.json` | Resposta esperada completa (`resposta_esperada`), no formato do contrato, + asserções em texto |

Os 12 negativos técnicos (8 do bloco **Validação** e 4 do bloco **Limite**) são a exceção: têm **um único arquivo inválido** (`Validacao_ArquivoDocx.docx`, `Validacao_ArquivoVazio.pdf`, `Limite_Paginas_21.pdf`, etc.) e um `expected.json` com o **envelope de erro** (HTTP + código funcional), não um JSON de triagem.

Quatro arquivos grandes ficam fora do git (`.gitignore`) e são recriados pelo gerador: `Validacao_ArquivoGrande.pdf` (25 MB), `Limite_Tamanho_10MB.pdf` (10 MB), `Limite_Tamanho_Acima10MB.pdf` (10,5 MB) e `Limite_Texto_Acima10MB.txt` (10,5 MB).

### O que há dentro de um `expected.json`

```jsonc
{
  "schema": "mediflow.fixture/2",
  "fixture_id": "Conflito_Dose",
  "documento_ficticio": true,
  "tipo_de_teste": "funcional",        // funcional | erro_processamento | negativo_tecnico
  "entrada": {
    "formatos_disponiveis": ["TXT", "PDF", "JPG"],
    "renditions": {"txt": "...", "pdf": "...", "jpg": "..."}
  },
  "resposta_esperada": { /* payload completo do contrato */ },
  "modo_fixture": {"score_forcado": {"score_classificacao": 0.93, "score_extracao": 0.84}},
  "assercoes": ["..."],
  "observacoes": ""
}
```

`resposta_esperada` **é** o JSON da API — não há tradução de nomes entre o fixture e a resposta. Os 79 arquivos validam no contrato (`python3 tests/testar_contrato.py`).

## Como ler os nomes

Nenhum nome usa abreviação. O padrão é **`Bloco_Assunto_Detalhe`**: três partes separadas por `_`, cada uma escrita por inteiro, com a primeira letra maiúscula e sem acentos (para o nome funcionar igual em qualquer sistema de arquivos).

| Bloco | Quantos | Pergunta que responde | Exemplos |
| --- | ---: | --- | --- |
| **Matriz** | 24 | "O sistema acerta cada tipo de documento em cada formato?" | `Matriz_Receituario_Pdf`, `Matriz_LaudoLaboratorial_Imagem`, `Matriz_Guia_Texto` |
| **Ausencia** | 8 | "O que acontece quando falta um campo?" | `Ausencia_Paciente_Nome`, `Ausencia_Medico_Crm`, `Ausencia_SomenteCid` |
| **Borda** | 4 | "O comportamento muda exatamente no limiar 0,85? E com prioridade ou urgência indefinidas?" | `Borda_Score_084`, `Borda_Score_085`, `Borda_Prioridade_NaoIdentificada`, `Borda_Urgencia_Indeterminada` |
| **Conflito** | 7 | "O sistema detecta contradição clínica? E distingue a gravidade do conflito?" | `Conflito_Dose`, `Conflito_Cid_Diagnostico`, `Conflito_Gravidade_Media`, `Conflito_Gravidade_Baixa` |
| **Simultaneo** | 2 | "E quando urgência e ambiguidade acontecem juntas?" | `Simultaneo_Urgencia_Ilegivel` |
| **Qualidade** | 8 | "E quando o arquivo está ruim ou protegido?" | `Qualidade_Foto_Rotacionada`, `Qualidade_Pdf_ComSenha` |
| **Validacao** | 8 | "E quando a entrada é inválida?" | `Validacao_ArquivoDocx`, `Validacao_ArquivoGrande`, `Validacao_MimeInvalido` |
| **Limite** | 8 | "O corte está mesmo em 10 MB, 20 páginas, nesses formatos e no texto?" | `Limite_Tamanho_10MB`, `Limite_Paginas_21`, `Limite_Paginas_21_Digitalizado`, `Limite_Formato_Webp`, `Limite_Texto_Acima10MB` |
| **Escaneado** | 6 | "E quando o PDF é só imagem, sem texto?" | `Escaneado_Receituario_PdfDigitalizado` |
| **Diferencial** | 4 | "Os opcionais funcionam?" | `Diferencial_ReceituarioManuscrito`, `Diferencial_HemogramaCompleto` |

Como todas as pastas começam pelo nome do bloco, a ordenação alfabética já agrupa os casos por assunto — não é preciso abrir cada uma para saber a que grupo pertence.

### Lendo um nome do bloco Matriz

O bloco Matriz responde com **tipo de documento + formato**:

```text
Matriz_Guia_Imagem
│      │    └── formato do arquivo: Pdf, Imagem ou Texto
│      └─────── tipo de documento: Receituario, LaudoLaboratorial,
│               LaudoDeImagem, Guia, RelatorioDeAlta, Atestado,
│               Outro ou NaoIdentificado
└────────────── bloco Matriz (tipo × formato)
```

Atenção a um detalhe que confunde: **no meio está o tipo, no fim está o formato**. Em `Matriz_LaudoDeImagem_Imagem`, o primeiro `Imagem` é *laudo de exame de imagem* (o tipo) e o segundo é *formato imagem* (o arquivo). Já `Matriz_LaudoDeImagem_Pdf` é o mesmo tipo de documento entregue em PDF.

### Lendo um nome dos outros blocos

A lógica é **bloco + sujeito + o que está sendo testado**:

| ID | Leitura |
| --- | --- |
| `Ausencia_Paciente_Nome` | ausência · paciente · nome |
| `Ausencia_Medico_Crm` | ausência · médico · CRM |
| `Ausencia_SomenteCid` | ausência · **somente** o CID (que **não** gera revisão) |
| `Conflito_Dose` | conflito · dose suspeita |
| `Qualidade_Pdf_ComSenha` | qualidade · PDF · protegido por senha |
| `Escaneado_Receituario_PdfDigitalizado` | escaneado · receituário · PDF digitalizado |
| `Borda_Score_084` / `Borda_Score_085` | borda · score 0,84 / 0,85 |
| `Validacao_ArquivoGrande` | validação · arquivo · grande demais |

### Onde está cada coisa

```text
tests/fixtures/
├── manifest.csv     ← comece por aqui: 79 linhas, uma por documento, com o resultado esperado
├── demo/            ← 12 casos que cobrem o pitch (todos os blocos, exceto Qualidade e Validacao)
└── catalogo/        ← 55 casos restantes (Qualidade e Validacao ficam só aqui)
```

O mesmo ID existe em um único lugar — `demo/` e `catalogo/` não se repetem. Para saber o que se espera de um documento, abra o `expected.json` dentro da pasta dele; para ver o catálogo inteiro de uma vez, use o `manifest.csv` ou o PDF em `docs/testes/`.

## Os 12 casos de pitch (`demo/`)

| # | ID | Caso | Destino | Status |
| ---: | --- | --- | --- | --- |
| 1 | `Matriz_Receituario_Texto` | Receituário — rotina | `FARMACIA_HOSPITALAR` | `PROCESSADO` |
| 2 | `Matriz_Receituario_Pdf` | Receituário — 2 medicamentos | `FARMACIA_HOSPITALAR` | `PROCESSADO` |
| 3 | `Matriz_Receituario_Imagem` | Receituário — urgência com opioide | `FILA_URGENCIA_MEDICA` | `PROCESSADO` |
| 4 | `Matriz_LaudoDeImagem_Pdf` | TC de tórax — TEP agudo | `FILA_URGENCIA_MEDICA` | `EM_REVISAO` |
| 5 | `Matriz_LaudoLaboratorial_Pdf` | Hemograma — rotina | `PRONTUARIO_ELETRONICO` | `PROCESSADO` |
| 6 | `Matriz_Guia_Pdf` | Guia de ressonância — eletiva | `AUDITORIA_AUTORIZACOES` | `PROCESSADO` |
| 7 | `Matriz_RelatorioDeAlta_Pdf` | Relatório de alta — pneumonia | `PRONTUARIO_ELETRONICO` | `PROCESSADO` |
| 8 | `Matriz_Atestado_Texto` | Atestado de comparecimento | `PRONTUARIO_ELETRONICO` | `PROCESSADO` |
| 9 | `Matriz_NaoIdentificado_Imagem` | Documento ilegível | `FILA_REVISAO_HUMANA` | `EM_REVISAO` |
| 10 | `Matriz_Outro_Texto` | Comunicação administrativa | `FILA_REVISAO_HUMANA` | `EM_REVISAO` |
| 11 | `Ausencia_Paciente_Nome` | Receita sem nome do paciente | `FILA_REVISAO_HUMANA` | `EM_REVISAO` |
| 12 | `Borda_Score_084` | Score forçado em 0,84 | `FILA_REVISAO_HUMANA` | `EM_REVISAO` |

## Os 55 casos do catálogo (`catalogo/`)

| Bloco | Casos | O que cobre |
| --- | ---: | --- |
| Matriz | 14 | Tipos × formatos (os 2 formatos que faltavam em cada tipo) |
| Ausencia | 7 | Campos ausentes que revisam e que não revisam |
| Borda | 1 | Limiar exato de 0,85 |
| Conflito | 5 | Conflitos, dose suspeita, contradições e alto risco |
| Simultaneo | 2 | Urgência + ambiguidade simultâneas |
| Qualidade | 8 | Desfoque, rotação, corte, sombra, PDF sem texto, 7 páginas, senha e corrompido |
| Validacao | 8 | Negativos técnicos (DOCX, 0 KB, JSON inválido, envelope vazio, ZIP, 25 MB, MIME falso) |
| Escaneado | 6 | PDF digitalizado dos tipos restantes |
| Diferencial | 4 | Manuscrito, carimbo, hemograma de 20 analitos e guia TISS |

## Consistência (verificação automática)

```bash
python3 tools/verificar_consistencia.py
```

O script confere, nos 79 casos: conjunto de arquivos por pasta (lido de `entrada.renditions`), nome da pasta = nome dos arquivos = `fixture_id`, schema do `expected.json`, aderência ao `manifest.csv`, legibilidade de PDF/JPG/PNG/WEBP/TXT, e **duplicidade** (arquivos byte-idênticos, textos clínicos iguais e saídas esperadas iguais). Sai com código 1 se encontrar erro.

Três grupos compartilham a mesma saída esperada sem serem redundantes:

| Grupo | O que muda entre eles |
| --- | --- |
| `Matriz_NaoIdentificado_Pdf`, `Matriz_NaoIdentificado_Imagem`, `Matriz_NaoIdentificado_Texto`, `Qualidade_Foto_Desfocada` | Os três primeiros são a matriz do tipo `NAO_IDENTIFICADO` nos 3 formatos. O último é **manuscrito fotografado** com desfoque severo — falha de captura, não de formato. |
| `Matriz_Outro_Pdf`, `Matriz_Outro_Imagem`, `Matriz_Outro_Texto`, `Escaneado_Outro_PdfDigitalizado` | Documento fora da taxonomia nos 3 formatos + a versão digitalizada (prova que o caminho multimodal chega ao mesmo `OUTRO`). |
| `Qualidade_Pdf_ComSenha`, `Qualidade_Pdf_Corrompido` | Ambos em `ERRO_PROCESSAMENTO`, por causas distintas: AES-256 versus arquivo truncado em 40%. |

## Casos especiais

| Fixture | Particularidade |
| --- | --- |
| `Matriz_NaoIdentificado_Imagem`, `Matriz_NaoIdentificado_Pdf`, `Qualidade_Foto_Desfocada` | PDF somente imagem e JPG com desfoque forte; cabeçalho de identificação preservado |
| `Qualidade_Foto_Rotacionada` | Imagem e PDF rotacionados em 90° |
| `Qualidade_Foto_Cortada` | Recorte remove o CRM da assinatura — deve gerar revisão |
| `Qualidade_Foto_BaixoContraste` | Mancha elíptica sobre a idade — campo incerto, não inventado |
| `Qualidade_Pdf_SemTexto`, `Escaneado_*` | PDFs sem camada de texto (0 caracteres extraíveis) |
| `Qualidade_Pdf_Multipagina` | 7 páginas, rodapé "página N de 7" |
| `Qualidade_Pdf_ComSenha` | Protegido por AES-256; senha de teste `mediflow123` |
| `Qualidade_Pdf_Corrompido` | Truncado em 40% do tamanho original |
| `Validacao_ArquivoGrande` | 25 MB, PDF **válido** (1 página + preenchimento); **não versionado** — regenere com o script |
| `Borda_Score_084`, `Borda_Score_085`, `Simultaneo_Urgencia_Score` | Exigem `FIXTURE_MODE` para forçar os scores — os valores estão em `modo_fixture.score_forcado` |

## Regras

1. Somente dados fictícios, com a marca d'água `DOCUMENTO FICTÍCIO — USO EXCLUSIVO EM TESTES`.
2. Um fixture de borda altera **apenas um** atributo em relação ao documento base.
3. Toda fixture tem `expected.json` no schema `mediflow.fixture/2`; o bloco **Validacao** usa `ErroResposta` e os dois PDFs ilegíveis usam `TriagemMediFlow` com `status=ERRO_PROCESSAMENTO`.
4. Não comparar scores exatos do LLM: use faixas e, nas bordas 0,84 / 0,85 / 0,70, o modo `FIXTURE_MODE`.
5. Nenhum segredo, chave OCI ou dado pessoal real neste diretório.
6. **Um só hospital, uma só UF.** Todas as fixtures acontecem no Hospital Aurora (São Paulo); por isso **todo CRM é `SP`** — o CRM acompanha a UF de atuação do médico. Um CRM de outra unidade federativa num hospital paulista seria erro de domínio, não variação de teste.
7. **O TXT é a fonte do que se espera extrair.** Todo campo preenchido no `expected.json` (paciente, médico, CRM, diagnóstico, CID, idade) aparece no texto da própria fixture; o que está ausente ou ilegível também aparece assim no texto (`—`, `não informado`, `4?_ anos`). O verificador confere isso caso a caso.

## Verificar e regerar

```bash
python3 -m pip install -r requirements.txt

python3 tests/testar_contrato.py           # 79/79 expected.json válidos no contrato
python3 tools/verificar_consistencia.py    # estrutura, schema, manifesto, legibilidade, coerência clínica (CRM-SP) e duplicidade

python3 tools/gerar_fixtures_demo.py       # 12 casos → 48 arquivos em tests/fixtures/demo/
python3 tools/gerar_fixtures_catalogo.py   # 55 casos → 204 arquivos em tests/fixtures/catalogo/
python3 tools/gerar_mapa_documentos.py     # PDF do mapa em docs/testes/
```

Se a mudança for **só no contrato** (nome de campo, enum, texto de justificativa), não é preciso redesenhar PDF/JPG: use `--somente-expected` nos dois geradores. Eles reescrevem apenas os `expected.json`, e abortam se a regra nova não reproduzir a intenção escrita em cada caso.

> `Validacao_ArquivoGrande.pdf` (25 MB) é ignorado pelo Git por padrão. O script o recria quando necessário; sem ele, `verificar_consistencia.py` mostra um **aviso**, não um erro.
>
> **Reprodutibilidade:** rodar os geradores duas vezes produz os mesmos bytes em todos os arquivos, exceto `Qualidade_Pdf_ComSenha.pdf`. A criptografia AES-256 do PDF usa um salt aleatório do PyMuPDF; o conteúdo e a senha (`mediflow123`) não mudam.
