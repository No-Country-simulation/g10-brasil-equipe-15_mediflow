"""
MediFlow — Camada de Serviço e Orquestração da Triagem (Service Layer)
Gerencia o ciclo assíncrono de vida dos documentos clínicos:
ingestão -> extração -> grafo langgraph -> persistência OCI -> histórico de auditoria.
"""
from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.ingestion import DocumentLoader, DocumentoIngerido, IngestaoError
from src.schemas import (
    TriagemMediFlow,
    StatusTriagem,
    Destino,
    Classificacao,
    DadosExtraidos,
    Paciente,
    Medico,
    Crm,
    Qualidade,
    DecisaoRoteamento,
    ArmazenamentoOCI,
    CodigoErro,
    ErroProcessamento,
    Conflito,
    Gravidade,
)
from src.workflow.graph import criar_grafo
from src.workflow.state import ConflitoWorkflow, EntradaWorkflow
from src.schemas.clinical import ClassificacaoClinica, NivelPrioridade
from src.api.schemas import EventoHistorico

logger = logging.getLogger(__name__)


class TriagemService:
    """Gerenciador de estado em memória e orquestrador do ciclo clínico MediFlow."""

    def __init__(self, storage: Optional[Any] = None):
        # Repositórios em memória para estado rápido da API
        self._triagens: Dict[str, TriagemMediFlow] = {}
        self._historico: Dict[str, List[EventoHistorico]] = {}
        self._documentos_originais: Dict[str, DocumentoIngerido] = {}
        self._status_em_andamento: Dict[str, str] = {}
        self._metadados: Dict[str, Dict[str, Any]] = {}
        self._grafo = criar_grafo()
        self._storage = storage

    def _obter_storage(self) -> Optional[Any]:
        """Obtém cliente OCI Storage configurado ou injetado."""
        if self._storage is not None:
            return self._storage
        # Em ambiente de teste automatizado, evita conexões reais externas a menos que explicitamente injetado
        if os.getenv("TESTING", "").lower() in ("1", "true") or os.getenv("PYTEST_CURRENT_TEST"):
            return None
        try:
            from src.storage.oci_storage import OCIStorage
            return OCIStorage.das_configuracoes()
        except Exception as err:
            logger.debug("OCI Storage não configurado ou indisponível: %s", err)
            return None

    def gerar_documento_id(self) -> str:
        """Gera um identificador canônico no formato DOC-CLIN-YYYY-XXXX (RN-07)."""
        ano = datetime.now(timezone.utc).year
        sufixo = uuid4().hex[:8].upper()
        return f"DOC-CLIN-{ano}-{sufixo}"

    def registrar_evento(
        self,
        documento_id: str,
        tipo_evento: str,
        status_novo: str,
        ator: str,
        status_anterior: Optional[str] = None,
        motivo: Optional[str] = None,
    ) -> EventoHistorico:
        """Registra um evento cronológico na linha do tempo de auditoria (CT-070 a CT-072)."""
        evento = EventoHistorico(
            evento_id=f"EVT-{uuid4().hex[:8].upper()}",
            documento_id=documento_id,
            tipo_evento=tipo_evento,
            ator=ator,
            status_anterior=status_anterior,
            status_novo=status_novo,
            motivo=motivo,
            versao_esquema="2.0.0",
        )
        if documento_id not in self._historico:
            self._historico[documento_id] = []
        self._historico[documento_id].append(evento)
        return evento

    def submeter_texto(
        self,
        texto: str,
        documento_id: Optional[str] = None,
        canal_origem: str = "Prontuário",
        metadados: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Processa e valida a ingestão de texto bruto (CT-001)."""
        if not texto or not texto.strip():
            raise IngestaoError(codigo="CAMPOS_INVALIDOS", mensagem="O conteúdo textual está vazio.")

        doc_id = documento_id.strip() if (documento_id and documento_id.strip()) else self.gerar_documento_id()
        bytes_txt = texto.encode("utf-8")
        nome_arq_informado = (
            metadados.get("nome_arquivo")
            if (metadados and isinstance(metadados, dict) and metadados.get("nome_arquivo"))
            else f"{doc_id}.txt"
        )
        doc = DocumentLoader.carregar_bytes(bytes_txt, nome_arquivo=nome_arq_informado, documento_id=doc_id)

        self._documentos_originais[doc_id] = doc
        self._status_em_andamento[doc_id] = StatusTriagem.RECEBIDO
        self._metadados[doc_id] = dict(metadados) if (metadados and isinstance(metadados, dict)) else {}

        self.registrar_evento(
            documento_id=doc_id,
            tipo_evento="RECEBIDO",
            status_novo=StatusTriagem.RECEBIDO,
            ator="API_INGESTAO",
            motivo=f"Texto recebido via canal {canal_origem}",
        )
        return doc_id

    def submeter_arquivo(
        self,
        conteudo: bytes,
        nome_arquivo: str,
        documento_id: Optional[str] = None,
        canal_origem: str = "Upload",
        metadados: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Processa e valida arquivo binário com checagem de limites e MIME (CT-002, CT-003, CT-004)."""
        if not conteudo or len(conteudo) == 0:
            raise IngestaoError(codigo="CAMPOS_INVALIDOS", mensagem="Arquivo vazio (0 bytes).")

        doc_id = documento_id.strip() if (documento_id and documento_id.strip()) else self.gerar_documento_id()
        doc = DocumentLoader.carregar_bytes(conteudo, nome_arquivo=nome_arquivo, documento_id=doc_id)

        self._documentos_originais[doc_id] = doc
        self._status_em_andamento[doc_id] = StatusTriagem.RECEBIDO
        self._metadados[doc_id] = dict(metadados) if (metadados and isinstance(metadados, dict)) else {}

        self.registrar_evento(
            documento_id=doc_id,
            tipo_evento="RECEBIDO",
            status_novo=StatusTriagem.RECEBIDO,
            ator="API_INGESTAO",
            motivo=f"Arquivo {nome_arquivo} recebido com sucesso",
        )
        return doc_id

    def _detectar_simulacao_oci(self, doc: DocumentoIngerido) -> tuple[bool, Optional[str]]:
        """
        Determina se o documento está em modo de simulação controlada da EPT v1.0 (§12).
        Retorna (eh_simulacao: bool, falha_simulada: Optional[str]).
        falha_simulada pode ser: 'ORIGINAL', 'RESULTADO' ou None.
        
        Regras Estritas de Ativação:
        1. Se OCI_SIMULACAO_HABILITADA for 'false', simulação é sumariamente desativada.
        2. Ativação explícita via metadados ou header:
           - metadados['simular_falha_oci'] in ('ORIGINAL', 'RESULTADO')
           - metadados['modo_simulacao'] is True
        3. Ativação por nome estrito do catálogo EPT v1.0 (§12):
           - Apenas nomes canônicos contendo 'ocifalhanooriginal' ou 'ocifalhanoresultado'.
           Nomes genéricos (ex: 'simulacao_exame.txt') NÃO ativam simulação e são tratados como documentos reais.
        """
        if os.getenv("OCI_SIMULACAO_HABILITADA", "true").lower() in ("false", "0"):
            return False, None

        doc_id = getattr(doc, "documento_id", "")
        meta = self._metadados.get(doc_id, {})

        # 1. Verificação explícita por metadados / header
        sim_val = str(meta.get("simular_falha_oci") or "").upper()
        if "ORIGINAL" in sim_val:
            return True, "ORIGINAL"
        if "RESULTADO" in sim_val:
            return True, "RESULTADO"
        if meta.get("modo_simulacao") is True or sim_val in ("TRUE", "1", "SIMULADO"):
            return True, None

        # 2. Verificação por nome canônico estrito do catálogo EPT §12
        nome_arq = (doc.nome_arquivo or "").lower().replace("_", "").replace("-", "").replace(" ", "")
        if "ocifalhanooriginal" in nome_arq:
            return True, "ORIGINAL"
        if "ocifalhanoresultado" in nome_arq:
            return True, "RESULTADO"

        return False, None

    def executar_triagem(self, documento_id: str) -> TriagemMediFlow:
        """
        Executa o pipeline completo de triagem:
        Persistência inicial OCI -> Extração clínica -> LangGraph -> Persistência final OCI.
        """
        doc = self._documentos_originais.get(documento_id)
        if not doc:
            raise ValueError(f"Documento {documento_id} não encontrado na fila.")

        self._status_em_andamento[documento_id] = StatusTriagem.PROCESSANDO
        self.registrar_evento(
            documento_id=documento_id,
            tipo_evento="PROCESSANDO",
            status_anterior=StatusTriagem.RECEBIDO,
            status_novo=StatusTriagem.PROCESSANDO,
            ator="WORKFLOW_ENGINE",
            motivo="Iniciando extração e roteamento determinístico",
        )

        # 1. Tentativa de backup inicial no bucket OCI (se configurado)
        storage = self._obter_storage()
        bucket_nome = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")
        falha_persistencia: Optional[str] = None
        backup_status = "pendente"
        caminho_oci_original = f"recebidos/{documento_id}/original.{doc.formato.lower()}"
        # Gatilho de Simulação Controlada da EPT v1.0 (RF-28, RF-30, §12)
        eh_simulacao, falha_simulada = self._detectar_simulacao_oci(doc)

        if falha_simulada == "ORIGINAL":
            logger.warning("[Simulação EPT] Forçando falha na gravação do original para documento %s", documento_id)
            falha_persistencia = "FALHA_GRAVACAO_ORIGINAL: ServiceError 503 (Simulação EPT - Nuvem OCI indisponível)"
            backup_status = "falha"
        elif storage is not None:
            try:
                storage.enviar_bytes(
                    caminho_oci_original,
                    doc.conteudo_bytes,
                    tipo_conteudo="application/pdf" if doc.formato == "PDF" else "text/plain",
                )
                backup_status = "sucesso"
            except Exception as err:
                logger.error("Falha ao persistir documento original no OCI: %s", err)
                backup_status = "falha"
                falha_persistencia = f"FALHA_GRAVACAO_ORIGINAL: {str(err)}"
        elif os.getenv("OCI_OBRIGATORIO", "false").lower() in ("true", "1"):
            falha_persistencia = "OCI_OBRIGATORIO: Conector OCI não configurado"
            backup_status = "falha"
        else:
            backup_status = "ignorado_ou_falha"

        # 2. Extração de Entidades Clínicas (Heurística Robusta do MVP)
        texto = doc.conteudo_texto or ""
        tipo_doc = self._inferir_tipo_documento(texto, doc.nome_arquivo)
        urgente = self._inferir_urgencia(texto)

        dados_paciente = self._extrair_paciente(texto)
        dados_medico = self._extrair_medico(texto)
        diagnostico, cid = self._extrair_diagnostico_e_cid(texto)
        medicamentos = self._extrair_medicamentos(texto)
        exames = self._extrair_exames(texto)

        # 3. Execução do Grafo LangGraph
        score_classif = 0.95
        score_extrac = 0.95
        campos_ausentes: List[str] = []

        if not dados_paciente.nome:
            campos_ausentes.append("paciente.nome")
        if dados_paciente.idade is None:
            campos_ausentes.append("paciente.idade")
        if not dados_medico.nome:
            campos_ausentes.append("medico.nome")
        if not (dados_medico.crm and dados_medico.crm.numero):
            campos_ausentes.append("medico.crm")
        if not diagnostico and tipo_doc != "LAUDO_EXAME_LABORATORIAL":
            campos_ausentes.append("diagnostico")

        dados_extraidos_obj = DadosExtraidos(
            paciente=dados_paciente,
            medico=dados_medico,
            diagnostico=diagnostico,
            cid=cid,
            medicamentos=medicamentos,
            exames=exames,
            urgencia="SIM" if urgente else "NAO",
        )

        entrada_workflow = EntradaWorkflow(
            documento_id=documento_id,
            classificacao=ClassificacaoClinica(
                tipo_documento=tipo_doc,
                nivel_prioridade=NivelPrioridade.URGENTE if urgente else NivelPrioridade.ROTINA,
                score_confianca_classificacao=score_classif,
            ),
            dados_extraidos=dados_extraidos_obj,
            urgencia="SIM" if urgente else "NAO",
            campos_ausentes=campos_ausentes,
            campos_incertos=[],
            conflitos=[],
            limiar=float(os.getenv("LIMIAR_CONFIANCA", "0.85")),
        )

        saida_workflow = self._grafo.invoke({"entrada": entrada_workflow})
        decisao_wf = saida_workflow.get("decisao")
        qualidade_wf = saida_workflow.get("qualidade")

        status_final = StatusTriagem.PROCESSADO
        if decisao_wf and decisao_wf.requer_auditoria_humana:
            status_final = StatusTriagem.EM_REVISAO

        destinos_finais = [Destino(d.value) for d in decisao_wf.destinos] if decisao_wf else [Destino.FILA_REVISAO_HUMANA]
        justificativa = decisao_wf.justificativa if decisao_wf else "Processamento concluído."

        # Preserva os motivos de revisão humana levantados pelo agente (CT-057 e §16 item 12)
        if status_final == StatusTriagem.EM_REVISAO and qualidade_wf and getattr(qualidade_wf, "motivos_revisao", None):
            motivos_str = "; ".join(qualidade_wf.motivos_revisao)
            if motivos_str and motivos_str not in justificativa:
                justificativa = f"{justificativa} Motivo da retenção: {motivos_str}."

        notificacao = None
        if decisao_wf and decisao_wf.alerta_simulado:
            notificacao = {
                "canal": "SIMULADO_SLACK_PLANTAO",
                "mensagem": f"ALERTA URGENTE: {justificativa}",
                "status": "REGISTRADA"
            }

        # Extrai os scores e métricas calculadas deterministicamente pelo LangGraph (Fórmula A3)
        score_classif_final = (
            qualidade_wf.score_classificacao
            if qualidade_wf and hasattr(qualidade_wf, "score_classificacao")
            else score_classif
        )
        score_extrac_final = (
            qualidade_wf.score_extracao
            if qualidade_wf and hasattr(qualidade_wf, "score_extracao")
            else score_extrac
        )
        score_combinado_final = (
            qualidade_wf.score_combinado
            if qualidade_wf and hasattr(qualidade_wf, "score_combinado")
            else min(score_classif_final, score_extrac_final)
        )
        campos_ausentes_finais = (
            list(qualidade_wf.campos_ausentes)
            if qualidade_wf and hasattr(qualidade_wf, "campos_ausentes")
            else campos_ausentes
        )
        campos_incertos_finais = (
            list(qualidade_wf.campos_incertos)
            if qualidade_wf and hasattr(qualidade_wf, "campos_incertos")
            else []
        )
        conflitos_finais = []
        if qualidade_wf and hasattr(qualidade_wf, "conflitos"):
            for c in qualidade_wf.conflitos:
                if isinstance(c, Conflito):
                    conflitos_finais.append(c)
                else:
                    conflitos_finais.append(
                        Conflito(
                            tipo=getattr(c, "tipo", str(c)),
                            gravidade=getattr(c, "gravidade", Gravidade.ALTA),
                            descricao=getattr(c, "descricao", ""),
                            campos=getattr(c, "campos", []),
                        )
                    )

        # 4. Construção do Contrato Oficial TriagemMediFlow com métricas reais do agente
        pasta_status = "urgentes/" if urgente else ""
        caminho_oci_resultado = f"processados/{pasta_status}{documento_id}/resultado.json"

        # Se a gravação inicial teve sucesso, tenta persistir o JSON final no OCI
        if falha_simulada == "RESULTADO":
            logger.warning("[Simulação EPT] Forçando falha na gravação do resultado para documento %s", documento_id)
            falha_persistencia = "FALHA_GRAVACAO_RESULTADO: ServiceError 507 (Simulação EPT - Quota do bucket OCI excedida)"
            backup_status = "falha"
            caminho_oci_final = caminho_oci_original
        elif storage is not None and not falha_persistencia:
            try:
                triagem_temp = TriagemMediFlow(
                    status=status_final,
                    documento_id=documento_id,
                    classificacao=Classificacao(
                        tipo_documento=tipo_doc,
                        especialidade=["Clínica Médica"],
                        nivel_prioridade="URGENTE" if urgente else "ROTINA",
                        score_classificacao=score_classif_final,
                    ),
                    dados_extraidos=dados_extraidos_obj,
                    qualidade=Qualidade(
                        score_extracao=score_extrac_final,
                        score_combinado=score_combinado_final,
                        limiar_aplicado=float(os.getenv("LIMIAR_CONFIANCA", "0.85")),
                        campos_ausentes=campos_ausentes_finais,
                        campos_incertos=campos_incertos_finais,
                        conflitos=conflitos_finais,
                    ),
                    decisao_roteamento=DecisaoRoteamento(
                        destinos=destinos_finais,
                        destino_principal=destinos_finais[0] if destinos_finais else Destino.FILA_REVISAO_HUMANA,
                        requer_auditoria_humana=(status_final == StatusTriagem.EM_REVISAO),
                        justificativa_roteamento=justificativa,
                        notificacao=notificacao,
                    ),
                    armazenamento_oci=ArmazenamentoOCI(
                        bucket=bucket_nome,
                        caminho_objeto=caminho_oci_resultado,
                        status_backup="sucesso",
                        modo_simulacao=eh_simulacao,
                    ),
                    erro=None,
                )
                json_bytes = triagem_temp.model_dump_json(indent=2).encode("utf-8")
                storage.enviar_bytes(
                    caminho_oci_resultado,
                    json_bytes,
                    tipo_conteudo="application/json",
                )
                backup_status = "sucesso"
                caminho_oci_final = caminho_oci_resultado
            except Exception as err:
                logger.error("Falha ao persistir JSON do resultado no OCI: %s", err)
                falha_persistencia = f"FALHA_GRAVACAO_RESULTADO: {str(err)}"
                backup_status = "falha"
                caminho_oci_final = caminho_oci_original
        else:
            caminho_oci_final = caminho_oci_original

        # 5. Tratamento de Erro de Persistência vs Conclusão Normal
        if falha_persistencia:
            status_efetivo = StatusTriagem.ERRO_PERSISTENCIA
            erro_obj = ErroProcessamento(
                codigo=CodigoErro.ERRO_PERSISTENCIA,
                mensagem=f"Falha na persistência OCI ({falha_persistencia}). Decisão clínica e qualidade preservadas para nova tentativa."
            )
        else:
            status_efetivo = status_final
            erro_obj = None

        triagem = TriagemMediFlow(
            status=status_efetivo,
            documento_id=documento_id,
            classificacao=Classificacao(
                tipo_documento=tipo_doc,
                especialidade=["Clínica Médica"],
                nivel_prioridade="URGENTE" if urgente else "ROTINA",
                score_classificacao=score_classif_final,
            ),
            dados_extraidos=DadosExtraidos(
                paciente=dados_paciente,
                medico=dados_medico,
                diagnostico=diagnostico,
                cid=cid,
                medicamentos=medicamentos,
                exames=exames,
                urgencia="SIM" if urgente else "NAO",
            ),
            qualidade=Qualidade(
                score_extracao=score_extrac_final,
                score_combinado=score_combinado_final,
                limiar_aplicado=float(os.getenv("LIMIAR_CONFIANCA", "0.85")),
                campos_ausentes=campos_ausentes_finais,
                campos_incertos=campos_incertos_finais,
                conflitos=conflitos_finais,
            ),
            decisao_roteamento=DecisaoRoteamento(
                destinos=destinos_finais,
                destino_principal=destinos_finais[0] if destinos_finais else Destino.FILA_REVISAO_HUMANA,
                requer_auditoria_humana=(status_final == StatusTriagem.EM_REVISAO),
                justificativa_roteamento=justificativa,
                notificacao=notificacao,
            ),
            armazenamento_oci=ArmazenamentoOCI(
                bucket=bucket_nome,
                caminho_objeto=caminho_oci_final,
                status_backup=backup_status,
                modo_simulacao=eh_simulacao,
            ),
            erro=erro_obj,
        )

        self._triagens[documento_id] = triagem
        self._status_em_andamento[documento_id] = status_efetivo

        if falha_persistencia:
            self.registrar_evento(
                documento_id=documento_id,
                tipo_evento="ERRO_PERSISTENCIA",
                status_anterior=StatusTriagem.PROCESSANDO,
                status_novo=StatusTriagem.ERRO_PERSISTENCIA,
                ator="OCI_STORAGE_PERSISTENCE",
                motivo=f"Falha de gravação durável no OCI: {falha_persistencia}. Decisão clínica e qualidade preservadas.",
            )
        else:
            self.registrar_evento(
                documento_id=documento_id,
                tipo_evento="ROTEADO",
                status_anterior=StatusTriagem.PROCESSANDO,
                status_novo=status_final,
                ator="LANGGRAPH_ROUTER",
                motivo=justificativa,
            )
        return triagem

    def reprocessar_persistencia_oci(self, documento_id: str) -> TriagemMediFlow:
        """
        Retenta a persistência durável no OCI para triagens com ERRO_PERSISTENCIA (RF-28, RF-30).
        Preserva rigorosamente a decisão clínica e dados prévios sem reprocessar LLM ou LangGraph.
        """
        triagem = self._triagens.get(documento_id)
        if not triagem:
            raise ValueError(f"Triagem {documento_id} não encontrada.")

        doc = self._documentos_originais.get(documento_id)
        if not doc:
            raise ValueError(f"Documento original {documento_id} não encontrado na fila.")

        if triagem.status not in (StatusTriagem.ERRO_PERSISTENCIA, StatusTriagem.RECEBIDO):
            return triagem

        eh_simulacao, _ = self._detectar_simulacao_oci(doc)

        bucket_nome = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")
        caminho_original = f"recebidos/{documento_id}/original.{doc.formato.lower()}"
        requer_revisao = bool(triagem.decisao_roteamento and triagem.decisao_roteamento.requer_auditoria_humana)
        status_restaurado = StatusTriagem.EM_REVISAO if requer_revisao else StatusTriagem.PROCESSADO
        pasta_status = "urgentes/" if (triagem.classificacao.nivel_prioridade == "URGENTE") else ""
        caminho_resultado = f"processados/{pasta_status}{documento_id}/resultado.json"

        # -------------------------------------------------------------
        # CASO 1: SIMULAÇÃO EXPLÍCITA DO CATÁLOGO EPT v1.0 (§12)
        # -------------------------------------------------------------
        if eh_simulacao:
            logger.info("[Simulação EPT] Conector OCI simulado com sucesso na retentativa para documento %s", documento_id)
            triagem_atualizada = TriagemMediFlow(
                status=status_restaurado,
                documento_id=documento_id,
                classificacao=triagem.classificacao,
                dados_extraidos=triagem.dados_extraidos,
                qualidade=triagem.qualidade,
                decisao_roteamento=triagem.decisao_roteamento,
                armazenamento_oci=ArmazenamentoOCI(
                    bucket=bucket_nome,
                    caminho_objeto=caminho_resultado,
                    status_backup="sucesso",
                    modo_simulacao=True,
                ),
                erro=None,
            )
            self._triagens[documento_id] = triagem_atualizada
            self._status_em_andamento[documento_id] = status_restaurado
            self.registrar_evento(
                documento_id=documento_id,
                tipo_evento="RETRY_PERSISTENCIA_SUCESSO",
                status_anterior=StatusTriagem.ERRO_PERSISTENCIA,
                status_novo=status_restaurado,
                ator="SIMULACAO_EPT_RETRY",
                motivo="Simulação EPT: Persistência no bucket OCI simulada com sucesso",
            )
            return triagem_atualizada

        # -------------------------------------------------------------
        # CASO 2: DOCUMENTO REAL — PERSISTÊNCIA DURÁVEL OBRIGATÓRIA
        # -------------------------------------------------------------
        storage = self._obter_storage()
        if not storage:
            # BLOQUEIO DE FALSO SUCESSO: Conector ausente NUNCA pode fingir sucesso!
            logger.error("Tentativa de retry sem conector OCI configurado para documento %s", documento_id)
            raise RuntimeError("Conector OCI não configurado ou indisponível. A persistência durável não pode ser confirmada.")

        try:
            # 1. Regravação do documento original no OCI (se já existir, preserva e avança)
            try:
                storage.enviar_bytes(
                    caminho_original,
                    doc.conteudo_bytes,
                    tipo_conteudo="application/pdf" if doc.formato == "PDF" else "text/plain",
                )
            except Exception as err_orig:
                status_cod = getattr(err_orig, "status", None)
                msg_err = str(err_orig)
                if status_cod == 412 or "412" in msg_err or "PreconditionFailed" in msg_err:
                    # Conferência estrita de integridade: antes de ignorar o 412, confere se o original gravado no OCI é idêntico
                    try:
                        bytes_existentes = storage.ler_bytes(caminho_original) if hasattr(storage, "ler_bytes") else None
                    except Exception as err_ler:
                        logger.error("Falha ao ler objeto existente no OCI para conferência (%s): %s", caminho_original, err_ler)
                        raise RuntimeError(f"Falha ao validar integridade do objeto existente no OCI: {str(err_ler)}")

                    if bytes_existentes is not None and bytes_existentes != doc.conteudo_bytes:
                        logger.error(
                            "Conflito de integridade OCI: Objeto existente em %s possui conteúdo divergente do documento atual (%s bytes vs %s bytes).",
                            caminho_original, len(bytes_existentes), len(doc.conteudo_bytes)
                        )
                        self.registrar_evento(
                            documento_id=documento_id,
                            tipo_evento="RETRY_PERSISTENCIA_CONFLITO",
                            status_anterior=StatusTriagem.ERRO_PERSISTENCIA,
                            status_novo=StatusTriagem.ERRO_PERSISTENCIA,
                            ator="OCI_STORAGE_INTEGRITY",
                            motivo=f"Conflito de integridade: Objeto existente em {caminho_original} possui conteúdo divergente.",
                        )
                        raise RuntimeError(
                            f"Conflito de integridade OCI: O objeto existente em {caminho_original} possui conteúdo divergente do documento atual."
                        )

                    logger.info("Objeto original já existe no OCI com integridade confirmada (%s); prosseguindo para o JSON do resultado.", caminho_original)
                else:
                    raise

            # 2. Monta o contrato atualizado com persistência confirmada
            triagem_atualizada = TriagemMediFlow(
                status=status_restaurado,
                documento_id=documento_id,
                classificacao=triagem.classificacao,
                dados_extraidos=triagem.dados_extraidos,
                qualidade=triagem.qualidade,
                decisao_roteamento=triagem.decisao_roteamento,
                armazenamento_oci=ArmazenamentoOCI(
                    bucket=bucket_nome,
                    caminho_objeto=caminho_resultado,
                    status_backup="sucesso",
                    modo_simulacao=False,
                ),
                erro=None,
            )

            # 3. Regravação do JSON do resultado no OCI
            json_bytes = triagem_atualizada.model_dump_json(indent=2).encode("utf-8")
            storage.enviar_bytes(
                caminho_resultado,
                json_bytes,
                tipo_conteudo="application/json",
            )
        except Exception as err:
            logger.error("Falha física durante gravação OCI na retentativa para documento %s: %s", documento_id, err)
            self.registrar_evento(
                documento_id=documento_id,
                tipo_evento="RETRY_PERSISTENCIA_FALHA",
                status_anterior=StatusTriagem.ERRO_PERSISTENCIA,
                status_novo=StatusTriagem.ERRO_PERSISTENCIA,
                ator="OCI_STORAGE_RETRY",
                motivo=f"Falha na nova tentativa de gravação OCI: {str(err)}",
            )
            raise RuntimeError(f"Falha na gravação dos objetos no bucket OCI: {str(err)}")

        self._triagens[documento_id] = triagem_atualizada
        self._status_em_andamento[documento_id] = status_restaurado
        self.registrar_evento(
            documento_id=documento_id,
            tipo_evento="RETRY_PERSISTENCIA_SUCESSO",
            status_anterior=StatusTriagem.ERRO_PERSISTENCIA,
            status_novo=status_restaurado,
            ator="OCI_STORAGE_RETRY",
            motivo=f"Objetos gravados com sucesso no bucket {bucket_nome}",
        )
        return triagem_atualizada

    def obter_triagem(self, documento_id: str) -> Optional[TriagemMediFlow]:
        return self._triagens.get(documento_id)

    def obter_status(self, documento_id: str) -> Optional[str]:
        return self._status_em_andamento.get(documento_id)

    def obter_historico(self, documento_id: str) -> List[EventoHistorico]:
        return self._historico.get(documento_id, [])

    # Métodos auxiliares de extração heurística para o MVP
    def _inferir_tipo_documento(self, texto: str, nome: str) -> str:
        t = (texto + " " + nome).upper()
        if "RECEITUARIO" in t or "RECEITA" in t or "PRESCRIÇÃO" in t:
            return "RECEITUARIO_MEDICO"
        if "GUIA" in t or "SOLICITAÇÃO DE PROCEDIMENTO" in t or "TISS" in t:
            return "GUIA_PROCEDIMENTO"
        if "TOMOGRAFIA" in t or "RAIO-X" in t or "RADIOGRAFIA" in t or "IMAGEM" in t or "ULTRASSOM" in t:
            return "LAUDO_EXAME_IMAGEM"
        if "HEMOGRAMA" in t or "GLICEMIA" in t or "LABORATORIAL" in t or "COLESTEROL" in t:
            return "LAUDO_EXAME_LABORATORIAL"
        if "ALTA" in t or "INTERNACAO" in t or "INTERNAÇÃO" in t:
            return "RELATORIO_ALTA"
        if "ATESTADO" in t:
            return "ATESTADO_MEDICO"
        return "OUTRO"

    def _inferir_urgencia(self, texto: str) -> bool:
        t = texto.upper()
        termos_urgencia = [
            "URGENTE", "URGÊNCIA", "EMERGÊNCIA", "EMERGENCIA", "CRÍTICO", "CRITICO",
            "TEP", "TROMBOEMBOLISMO", "INFARTO", "HEMORRAGIA", "SEPSE"
        ]
        return any(termo in t for termo in termos_urgencia)

    def _extrair_paciente(self, texto: str) -> Paciente:
        nome_match = re.search(r"Paciente:\s*([^\n\r,]+)", texto, re.IGNORECASE)
        idade_match = re.search(r"Idade:\s*(\d{1,3})", texto, re.IGNORECASE)
        nome = nome_match.group(1).strip() if nome_match else None
        idade = int(idade_match.group(1)) if idade_match else None
        return Paciente(nome=nome, idade=idade)

    def _extrair_medico(self, texto: str) -> Medico:
        nome_match = re.search(r"M[eé]dico(?:\s+Solicitante)?:\s*([^\n\r,]+)", texto, re.IGNORECASE)
        crm_num_match = re.search(r"CRM(?:\/([A-Z]{2}))?:\s*(\d{4,8})", texto, re.IGNORECASE)
        nome = nome_match.group(1).strip() if nome_match else None
        if crm_num_match:
            numero = crm_num_match.group(2)
            uf = crm_num_match.group(1) or "SP"
            crm = Crm(numero=numero, uf=uf)
        else:
            crm = None
        return Medico(nome=nome, crm=crm)

    def _extrair_diagnostico_e_cid(self, texto: str) -> tuple[Optional[str], Optional[str]]:
        diag_match = re.search(r"Diagn[oó]stico(?:\s+Principal)?:\s*([^\n\r]+)", texto, re.IGNORECASE)
        cid_match = re.search(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b", texto)
        diag = diag_match.group(1).strip() if diag_match else None
        cid = cid_match.group(1).strip() if cid_match else None
        return diag, cid

    def _extrair_medicamentos(self, texto: str) -> list:
        return []

    def _extrair_exames(self, texto: str) -> list:
        return []


# Instância global singleton do serviço
triagem_service = TriagemService()
