# Fixtures de teste

Cópia enxuta de `tests/fixtures/` da raiz do repositório (fonte: branch `feature/cenarios-teste-json`). Só o que o frontend usa.

| Pasta | Conteúdo | Formato |
|---|---|---|
| `cenarios/` | `cenario_1_rotina`, `cenario_2_urgencia_tep`, `cenario_3_ambiguidade_rasura` | Formato anterior ao contrato atual; precisa de `normalizarTriagem` |
| `expected/` | `resposta_esperada` dos fixtures de entrada de cada cenário (arquivo `expected.json` inteiro) | Contrato atual (`types/clinical.ts`) |

Os documentos de entrada (`.pdf` e `.txt`) estão em `public/samples/{rotina,urgente,ambiguo}/`:

| Cenário | Fixture de origem |
|---|---|
| rotina | `catalogo/Matriz_LaudoDeImagem_Texto` |
| urgente | `demo/Matriz_LaudoDeImagem_Pdf` |
| ambiguo | `demo/Borda_Score_084` |

Para atualizar, copie de novo os arquivos de `tests/fixtures/`. Não edite à mão.
