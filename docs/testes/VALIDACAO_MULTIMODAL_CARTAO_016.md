# Validação multimodal — cartão 016

## Versão e escopo

Execuções realizadas na branch `fix/gemini-diagnostico-estruturado`,
com alterações locais sobre o commit `e70c349`.

Modelo utilizado nas chamadas reais: `gemini-3.5-flash-lite`.

As chamadas enviaram somente a mídia original, sem TXT auxiliar.
O fallback foi bloqueado nos testes reais para distinguir uma resposta
do modelo de uma resposta defensiva do serviço.

## Evidências obtidas

- Preparação do PDF digitalizado e da imagem: 2 testes aprovados.
  Foram conferidos os bytes originais, o MIME e a preparação multimodal.
- Regressões relacionadas à extração: 52 testes aprovados e 4 avisos.
- Seleção controlada do adaptador e do grafo: 8 testes aprovados,
  3 não selecionados e 4 avisos.
- PDF `Qualidade_Pdf_SemTexto`: classificação e prioridade coincidiram
  com a referência. Após o ajuste das instruções, médica, CRM e exame
  foram extraídos e aceitos pelo schema.
- Imagem `Matriz_Receituario_Imagem`: classificação, prioridade e os
  campos comparados, exceto a representação dos medicamentos,
  coincidiram com as referências.
- Imagem `Simultaneo_Urgencia_Ilegivel`: a dose permaneceu nula,
  a incerteza foi informada e o grafo manteve as filas de urgência
  e revisão humana. As sete verificações registradas foram verdadeiras.
  O alerta produzido pelo grafo é simulado.

Os totais acima pertencem a seleções diferentes e não devem ser somados.

## Pendências de conferência com o QA

- PDF: definir a comparação de nome com ou sem título profissional,
  diagnóstico conforme a conclusão e nome completo do exame.
- Receita em imagem: conferir a referência de medicamentos,
  concentração, volume, via, condição e momento de administração.
- Não foram alterados os `expected.json` para eliminar divergências.
- Aceitação pelo schema não comprova fidelidade completa da extração.

## Limites de ilegibilidade e manuscritos

A fixture `Simultaneo_Urgencia_Ilegivel` está desfocada e contém
explicitamente a indicação de que a dose inicial está ilegível.
O teste demonstra preservação dessa ausência e do sinal de incerteza
nesse caso. Não comprova reconhecimento geral de ilegibilidade sem
indicação textual, nem desempenho em manuscritos.

Não foi estabelecida uma taxa de acerto para documentos manuscritos.
O comportamento esperado é preservar ausências e incertezas,
sem completar doses, nomes ou registros por suposição.

## Falhas e encaminhamento

Os testes controlados verificaram encaminhamento para revisão após
timeout simulado e rejeição de sinais inválidos pelo adaptador.

A rejeição pelo adaptador não comprova um estado de erro HTTP.
A execução real com incerteza confirmou revisão e urgência simultâneas.

O primeiro script de ilegibilidade falhou ao imprimir a justificativa,
depois de calcular e registrar a decisão. As sete verificações e a
decisão foram recuperadas do relatório. O relatório original foi
preservado como inconclusivo, e o atributo usado na impressão foi corrigido.

## Fora do escopo destas execuções

- Rotas HTTP, interface React e persistência OCI.
- Entrega de alertas a sistemas externos.
- Avaliação da adequação clínica de diagnósticos ou prescrições.
- Comprovação geral de desempenho multimodal ou em manuscritos.

As capturas e os relatórios JSON estão anexados ao cartão 016.
