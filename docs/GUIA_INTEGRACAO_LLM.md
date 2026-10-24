# Guia Rápido de Integração: Ingestão de Documentos -> Agente LLM (Gemini)

> **Destinatárias**: Luciana Freitag, Gisele Oliveira (Frente de IA, Prompts e Agentes LLM)  
> **De**: Cristiano Oliveira (Frente de Ingestão & Notificações)  
> **Projeto**: MediFlow (Hackathon ONE G10 - Oracle & Alura)

Olá, Luciana e Gisele! 👋

Para facilitar a integração entre a **etapa de ingestão de arquivos** e o **Agente LLM Gemini**, este guia explica exatamente como carregar qualquer documento clínico (PDF, Imagem ou TXT) e passá-lo diretamente para a API do Gemini com o schema estruturado `TriagemMediFlow`.

---

## 1. Como Chamar o Carregador de Documentos

O módulo de ingestão está pronto e centralizado na classe `DocumentLoader`. Ele já faz toda a parte de segurança (limite de 20MB, tratamento de PDFs protegidos/corrompidos e detecção de codificação):

```python
from src.ingestion import DocumentLoader

# Opção A: A partir de um caminho em disco (arquivo local)
doc = DocumentLoader.carregar_arquivo("data/samples/01_laudo_rotina.pdf")

# Opção B: A partir de bytes recebidos via upload (API FastAPI ou Streamlit)
# doc = DocumentLoader.carregar_bytes(conteudo_bytes, nome_arquivo="upload.pdf")
```

---

## 2. Anatomia do Objeto de Saída (`DocumentoIngerido`)

Quando você chama o `DocumentLoader`, ele retorna um objeto `DocumentoIngerido`. Você só precisa se preocupar com estes 4 atributos principais:

| Atributo | Tipo | O que é e como usar no Prompt |
| :--- | :--- | :--- |
| `doc.documento_id` | `str` | Identificador único (ex: `DOC-A81B2C3D`). Repasse para `TriagemMediFlow.documento_id`. |
| `doc.conteudo_texto` | `str` | Texto cru limpo extraído do documento (se for PDF textual ou TXT). |
| `doc.requer_ocr` | `bool` | Se `False`, o documento tem texto legível. Se `True`, é imagem pura ou PDF escaneado (exige envio multimodal). |
| `doc.conteudo_bytes` | `bytes` | Bytes originais do arquivo. Prontos para envio direto à visão computacional do Gemini. |
| `doc.formato` | `str` | Extensão detectada: `PDF`, `PNG`, `JPG`, `JPEG` ou `TXT`. |

---

## 3. Exemplo Completo: Conectando com a API do Google Gemini

Abaixo está o código completo pronto para uso dentro de `src/agents/clinical_extractor.py`:

```python
import os
from google import genai
from google.genai import types
from src.ingestion import DocumentLoader
from src.schemas import TriagemMediFlow

# 1. Inicializa o cliente do Gemini (lê GEMINI_API_KEY do ambiente)
client = genai.Client()

def processar_documento_com_gemini(caminho_arquivo: str) -> TriagemMediFlow:
    # 2. Ingestão segura do documento
    doc = DocumentLoader.carregar_arquivo(caminho_arquivo)
    
    # 3. Monta o conteúdo para a LLM (Tratamento de Texto vs. Imagem Multimodal)
    if not doc.requer_ocr:
        # Cenário 1: Documento com texto legível extraído
        conteudos = [
            "Você é um agente especialista em triagem e auditoria de documentos clínicos do MediFlow.",
            f"Analise o texto do documento com ID [{doc.documento_id}]:\n\n{doc.conteudo_texto}"
        ]
    else:
        # Cenário 2: Documento escaneado ou imagem (Visão Computacional Multimodal)
        mime_type = "application/pdf" if doc.formato == "PDF" else f"image/{doc.formato.lower()}"
        parte_multimodal = types.Part.from_bytes(data=doc.conteudo_bytes, mime_type=mime_type)
        
        conteudos = [
            "Você é um agente especialista em triagem e auditoria de documentos clínicos do MediFlow.",
            f"Analise o documento digitalizado anexo com ID [{doc.documento_id}]:",
            parte_multimodal
        ]

    # 4. Chamada da LLM forçando Structured Outputs com o Schema Oficial
    resposta = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=conteudos,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TriagemMediFlow,
            temperature=0.1,  # Baixa criatividade para máxima precisão clínica
        )
    )

    # 5. O Gemini retorna o JSON estritamente no formato TriagemMediFlow
    triagem_validada = TriagemMediFlow.model_validate_json(resposta.text)
    return triagem_validada


# Exemplo de teste rápido:
if __name__ == "__main__":
    resultado = processar_documento_com_gemini("data/samples/02_laudo_urgencia_tep.pdf")
    print(f"Documento ID: {resultado.documento_id}")
    print(f"Prioridade: {resultado.classificacao.nivel_prioridade}")
    print(f"Destino: {resultado.decisao_roteamento.destino_principal}")
    print(f"Requer Auditoria Humana: {resultado.decisao_roteamento.requer_auditoria_humana}")
```

---

## 4. Onde Salvar o seu Código

Sugerimos organizar a frente de LLM dentro de:
👉 `src/agents/clinical_extractor.py` (ou `src/agents/triage_agent.py`)

Dessa forma:
* `src/ingestion/`: Ingestão física, sanitização de bytes e limites (Cristiano).
* `src/agents/`: Prompts, chamadas ao Gemini e extração clínica (Luciana e Gisele).
* `src/workflow/`: Roteamento e grafo LangGraph (Iza e Marcelo).
* `src/schemas/`: Contratos Pydantic compartilhados.

Qualquer dúvida ou ajuste que precisarem na ingestão, contem comigo! 🚀
