# Documentação de Testes, QA e Contratos — MediFlow

> **Hackathon ONE G10 (Oracle & Alura) — Equipe 15**  
> **Frente de QA & Consistência (William)** em conjunto com a **Frente de Ingestão (Cristiano)** e **Agentes LLM (Luciana / Gisele)**.

Este diretório centraliza toda a base documental de engenharia de software, garantia de qualidade (QA), rastreabilidade de requisitos e contratos executáveis do projeto MediFlow.

---

## 📚 Índice dos Documentos

| Arquivo | Descrição | Para que serve |
| :--- | :--- | :--- |
| **[`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md)** | **Contrato Canônico Oficial (Unificado)** | O contrato ativo que rege `src/schemas/clinical.py`, o motor LangGraph, a ingestão e as interfaces. Unifica os 79 fixtures do William e os schemas da Luciana com resiliência total. |
| **[`CATALOGO_DE_DOCUMENTOS_DE_TESTE.md`](CATALOGO_DE_DOCUMENTOS_DE_TESTE.md)** | Catálogo Completo dos 79 Fixtures | Descreve minuciosamente os 79 casos de teste divididos em 9 blocos (taxonomia, formatos, urgências, limiares, rasuras, limites e hemograma). |
| **[`AUDITORIA_2026-10-20.md`](AUDITORIA_2026-10-20.md)** | Relatório de Auditoria de Consistência | Registra a evolução dos fixtures, a padronização CRM-SP e a resolução da regra de urgência alinhada ao edital da Oracle. |
| **[`Mapa_de_Documentos_de_Teste_MediFlow.pdf`](Mapa_de_Documentos_de_Teste_MediFlow.pdf)** | Matriz Visual de Rastreabilidade (PDF) | Documento visual de 8 páginas mapeando cenários, arquivos, regras e destinos para apresentação à banca. |

---

## 🧪 Execução Automatizada dos Testes

Todos os 79 fixtures do catálogo foram integrados como testes nativos do `pytest` em [`tests/test_contrato_fixtures.py`](../../tests/test_contrato_fixtures.py).

### Para executar apenas os 79 fixtures do contrato:
```powershell
python -m pytest tests/test_contrato_fixtures.py
```

### Para executar a suíte completa da aplicação (149 testes):
```powershell
python -m pytest
```

### Distribuição dos 149 Testes Automatizados:
* **79 testes de Fixtures Oficiais** (`tests/test_contrato_fixtures.py`): ✅ 100% Aprovados
* **17 testes de Ingestão e Segurança** (`tests/test_ingestion.py`): ✅ 100% Aprovados (amostras, limites e fixtures físicos reais do William)
* **7 testes de Schemas Harmonizados** (`tests/test_schemas.py`): ✅ 100% Aprovados
* **46 testes de Roteamento LangGraph** (`tests/test_workflow.py`): ✅ 100% Aprovados
