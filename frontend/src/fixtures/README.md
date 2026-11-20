# Fixtures de teste

Cópia enxuta de `tests/fixtures/` da raiz do repositório (fonte: branch `feature/cenarios-teste-json`). Só o que o frontend usa.

| Pasta | Conteúdo | Formato |
|---|---|---|
| `cenarios/` | `cenario_1_rotina`, `cenario_2_urgencia_tep`, `cenario_3_ambiguidade_rasura` | Formato anterior ao contrato atual; precisa de `normalizarTriagem` |
| `expected/` | `resposta_esperada` dos fixtures de entrada de cada cenário (arquivo `expected.json` inteiro) | Contrato atual (`types/clinical.ts`) |

Os documentos de entrada (`.pdf`, `.txt` e `.jpg`) estão em `public/samples/{rotina,urgente,ambiguo}/`:

| Cenário | Fixture de origem |
|---|---|
| rotina | `catalogo/Matriz_LaudoDeImagem_Texto` |
| urgente | `demo/Matriz_LaudoDeImagem_Pdf` |
| ambiguo | `catalogo/Ausencia_Paciente_Idade` (JPG, idade não informada) |

Extras usados nos testes da tela de Resultado (também em `expected/`):

| Arquivo | Fixture de origem | Para quê |
|---|---|---|
| `urgente_revisao.json` | `catalogo/Simultaneo_Urgencia_Score` | 03c: urgente + revisão, dois destinos e alerta |
| `conflito_dose.json` | `catalogo/Conflito_Dose` | tabela de medicamentos com dose suspeita |

Para atualizar, copie os documentos de `tests/fixtures/`. A referência `expected/ambiguo.json` usa a imagem sem idade e explicita uma resposta ilustrativa do simulador (qualidade 0,70); ela não força o score da API real. Rotina e urgência ainda usam os cenários legados em `CENARIOS_DEMO`; revisão usa a referência atual de idade ausente. Não apresente o modo simulado como evidência de inferência real.
