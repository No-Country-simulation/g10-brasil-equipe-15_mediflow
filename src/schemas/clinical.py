"""
MediFlow - Schemas e Modelos Pydantic para Documentos Clínicos (v2.0)
Define o contrato de dados oficial para toda a aplicação.
Alinhado às especificações do edital Hackathon ONE G10 e ao schema oficial (Luciana/William).
"""
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, model_validator


# ==============================================================================
# ENUMS - PADRONIZAÇÃO DE VALORES (v2.0)
# ==============================================================================

class TipoArquivoEnum(str, Enum):
    PDF = "PDF"
    PNG = "PNG"
    JPG = "JPG"
    JPEG = "JPEG"
    TXT = "TXT"


class NivelPrioridadeEnum(str, Enum):
    URGENTE = "Urgente"
    POUCO_URGENTE = "Pouco_Urgente"
    ROTINA = "Rotina"
    AMBIGUO = "Ambiguidade/Revisão Humana"


# Compatibilidade reversa com nomes anteriores
NivelPrioridade = NivelPrioridadeEnum


class TipoDocumentoEnum(str, Enum):
    LAUDO_IMAGEM = "Laudo de Exame de Imagem"
    LAUDO_LABORATORIAL = "Laudo Laboratorial"
    RECEITUARIO_MEDICO = "Receituario Medico"
    GUIA_SOLICITACAO = "Guia de Solicitação de Procedimento"
    ATESTADO_MEDICO = "Atestado Medico"
    RELATORIO_ALTA = "Relatorio de Alta/Internação"


class DestinoRoteamentoEnum(str, Enum):
    EMERGENCIA_MEDICA = "Fila_Emergencia_Medica"
    AUDITORIA_AUTORIZACOES = "Auditoria_Autorizacoes"
    FARMACIA_HOSPITALAR = "Farmacia_Hospitalar"
    PRONTUARIO_ELETRONICO = "Prontuario_Eletronico_Paciente"
    REVISAO_HUMANA = "Fila_Revisao_Humana"

    # Aliases de compatibilidade para código anterior
    EMERGENCIA = "Fila_Emergencia_Medica"
    AUDITORIA = "Auditoria_Autorizacoes"
    FARMACIA = "Farmacia_Hospitalar"
    PRONTUARIO = "Prontuario_Eletronico_Paciente"


# Compatibilidade reversa
DestinoRoteamento = DestinoRoteamentoEnum


# ==============================================================================
# SUB-MODELOS DE ENTIDADES CLÍNICAS (v2.0)
# ==============================================================================

class Paciente(BaseModel):
    nome: Optional[str] = Field(None, description="Nome completo do paciente (Obrigatório para rotina automática)")
    idade: Optional[int] = Field(None, ge=0, le=120, description="Idade do paciente em anos (Obrigatório para rotina automática)")
    cpf: Optional[str] = Field(None, description="CPF do paciente (Opcional)")


class CrmEstruturado(BaseModel):
    numero: Optional[str] = Field(None, description="Número do CRM")
    uf: Optional[str] = Field(None, description="UF do CRM (ex: SP, RJ)")


class MedicoSolicitante(BaseModel):
    nome: Optional[str] = Field(None, description="Nome completo do médico (Obrigatório para rotina automática)")
    crm: Optional[str] = Field(None, description="Número do CRM completo ou formatado (ex: 145892-SP)")
    crm_detalhado: Optional[CrmEstruturado] = Field(None, description="Objeto CRM detalhado com número e UF")


class MedicamentoPrescrito(BaseModel):
    nome: str = Field(..., description="Nome do medicamento")
    dosagem: str = Field(..., description="Dosagem prescrita (ex: 500mg, 10ml)")
    frequencia: Optional[str] = Field(None, description="Frequência de administração (ex: 8 em 8 horas)")


class ClassificacaoDocumento(BaseModel):
    tipo_documento: Union[TipoDocumentoEnum, str] = Field(..., description="Categoria do documento clínico")
    especialidade: Optional[str] = Field(None, description="Especialidade médica relacionada")
    nivel_prioridade: NivelPrioridadeEnum = Field(..., description="Nível de urgência da triagem")
    score_confianca_classificacao: float = Field(
        ..., ge=0.0, le=1.0, description="Score de confiança na classificação (0.0 a 1.0)"
    )


# Alias para compatibilidade reversa
ClassificacaoClinica = ClassificacaoDocumento


class DadosClinicosExtraidos(BaseModel):
    paciente: Paciente = Field(default_factory=Paciente)
    medico_solicitante: MedicoSolicitante = Field(default_factory=MedicoSolicitante)
    exame_ou_procedimento: Optional[str] = Field(None, description="Nome do exame ou procedimento realizado/solicitado")
    diagnostico_principal: Optional[str] = Field(None, description="Diagnóstico ou achado clínico principal")
    cid_extraido: Optional[str] = Field(None, description="Código CID-10 extraído literalmente do documento")
    medicamentos: Optional[List[Union[MedicamentoPrescrito, str]]] = Field(
        default_factory=list, description="Lista de medicamentos extraídos"
    )
    score_confianca_extracao: float = Field(
        default=0.90, ge=0.0, le=1.0, description="Score de confiança na extração dos dados (0.0 a 1.0)"
    )
    achados_criticos: Optional[str] = Field(None, description="Achados de urgência ou sinais de alerta")
    inconsistencias_detectadas: Optional[List[str]] = Field(
        default_factory=list, description="Lista de inconsistências ou rasuras detectadas"
    )

    # Propriedades de compatibilidade com versões iniciais
    @property
    def exame_realizado(self) -> Optional[str]:
        return self.exame_ou_procedimento

    @property
    def cid_sugerido(self) -> Optional[str]:
        return self.cid_extraido


# Alias de compatibilidade
DadosExtraidos = DadosClinicosExtraidos


class QualidadeExtracao(BaseModel):
    score_classificacao: float = Field(..., ge=0.0, le=1.0)
    score_extracao: float = Field(..., ge=0.0, le=1.0)
    score_combinado: float = Field(..., ge=0.0, le=1.0, description="Calculado como min(score_classificacao, score_extracao)")
    limiar_aplicado: float = Field(default=0.85, description="Limiar configurado para auditoria automática (0.85)")
    campos_ausentes: List[str] = Field(default_factory=list, description="Lista de campos obrigatórios ausentes")
    campos_incerto: List[str] = Field(default_factory=list, description="Lista de campos com leitura ambígua/rasura")
    conflitos: List[str] = Field(default_factory=list, description="Lista de inconsistências detectadas")


class Notificacao(BaseModel):
    gerada: bool = Field(default=False, description="Flag indicando se notificação de urgência foi gerada")
    canal: str = Field(default="SIMULADO_SLACK_PLANTAO", description="Canal de notificação (ex: SIMULADO_SLACK_PLANTAO, Alerta_Plantao_Medico)")
    mensagem: Optional[str] = Field(None, description="Conteúdo do alerta gerado para casos urgentes")
    status: str = Field(default="REGISTRADA", description="Status do envio da notificação (REGISTRADA, ENVIADA)")


class DecisaoRoteamento(BaseModel):
    destino_principal: DestinoRoteamentoEnum = Field(..., description="Destino primário do documento")
    destinos: List[DestinoRoteamentoEnum] = Field(default_factory=list, description="Lista de todos os destinos atribuídos")
    requer_auditoria_humana: bool = Field(
        ..., description="Flag ativada quando o score < 0.85, houver rasura ou dados vitais ausentes"
    )
    justificativa_roteamento: str = Field(..., description="Motivo técnico/clínico da escolha dos destinos")
    notificacao_gerada: Optional[Notificacao] = Field(None, description="Alerta de tempo real gerado para casos de urgência")


class ArmazenamentoOCI(BaseModel):
    bucket: str = Field(default="mediflow-documentos-clinicos", description="Nome do bucket no OCI Object Storage")
    caminho_objeto: str = Field(..., description="Caminho do arquivo no bucket (ex: processados/urgentes/DOC-123.json)")
    status_backup: str = Field(default="sucesso", description="Status da gravação na nuvem OCI")


# ==============================================================================
# MODELO PRINCIPAL (PAYLOAD FINAL DA TRIAGEM v2.0)
# ==============================================================================

class TriagemMediFlow(BaseModel):
    status: str = Field(default="PROCESSADO", description="Status do processamento (PROCESSADO, EM_REVISAO, ERRO)")
    documento_id: str = Field(..., description="Identificador único do documento (ex: DOC-8F31A92B)")
    canal_origem: Optional[str] = Field(None, description="Canal de entrada (ex: Pronto_Socorro, Ambulatorio, Web)")
    classificacao: ClassificacaoDocumento
    dados_extraidos: DadosClinicosExtraidos
    qualidade: Optional[QualidadeExtracao] = None
    decisao_roteamento: DecisaoRoteamento
    armazenamento_oci: Optional[ArmazenamentoOCI] = None

    @model_validator(mode='after')
    def aplicar_regras_de_negocio_especificacao_v1(self):
        """
        Regras de Negócio Oficiais MediFlow (Especificação Funcional v1.0 - William):
        1. Calcula o Score Combinado = min(score_classificacao, score_extracao).
        2. Verifica ausência de campos OBRIGATÓRIOS (Paciente, Idade, Médico, CRM, Diagnóstico/Exame).
        3. Se Score Combinado < 0.85 OU houver campo obrigatório ausente:
           -> Ativa requer_auditoria_humana = True
           -> Adiciona REVISAO_HUMANA em destinos
           -> Ajusta status para EM_REVISAO se não for Urgência Crítica pura.
        4. Trata Caso Misto (Urgência Crítica + Ambiguidade/Rasura):
           -> Mantém EMERGENCIA_MEDICA e adiciona REVISAO_HUMANA nos destinos.
        """
        score_class = self.classificacao.score_confianca_classificacao
        score_ext = getattr(self.dados_extraidos, 'score_confianca_extracao', 0.90)
        score_comb = min(score_class, score_ext)

        # 2. Verificação de Campos Obrigatórios Vitais
        campos_ausentes = []
        if not self.dados_extraidos.paciente or not self.dados_extraidos.paciente.nome:
            campos_ausentes.append("paciente.nome")
        if not self.dados_extraidos.paciente or self.dados_extraidos.paciente.idade is None:
            campos_ausentes.append("paciente.idade")
        if not self.dados_extraidos.medico_solicitante or not self.dados_extraidos.medico_solicitante.nome:
            campos_ausentes.append("medico_solicitante.nome")
        if not self.dados_extraidos.medico_solicitante or not self.dados_extraidos.medico_solicitante.crm:
            campos_ausentes.append("medico_solicitante.crm")
        if not self.dados_extraidos.diagnostico_principal and not self.dados_extraidos.exame_ou_procedimento:
            campos_ausentes.append("diagnostico_principal_ou_exame")

        # 3. Monta Objeto de Qualidade se não fornecido
        limiar = 0.85
        if self.qualidade is None:
            self.qualidade = QualidadeExtracao(
                score_classificacao=score_class,
                score_extracao=score_ext,
                score_combinado=score_comb,
                limiar_aplicado=limiar,
                campos_ausentes=campos_ausentes,
                campos_incerto=[],
                conflitos=[]
            )

        # 4. Avaliação das Travas de Segurança (Human-In-The-Loop)
        motivos_revisao = []
        if score_comb < limiar:
            motivos_revisao.append(f"Score combinado ({score_comb:.2f}) abaixo do limiar de segurança ({limiar}).")
        if len(campos_ausentes) > 0:
            motivos_revisao.append(f"Campos obrigatórios ausentes: {', '.join(campos_ausentes)}.")

        # Sincroniza lista de destinos
        if not self.decisao_roteamento.destinos:
            self.decisao_roteamento.destinos = [self.decisao_roteamento.destino_principal]

        if len(motivos_revisao) > 0:
            self.decisao_roteamento.requer_auditoria_humana = True
            if DestinoRoteamentoEnum.REVISAO_HUMANA not in self.decisao_roteamento.destinos:
                self.decisao_roteamento.destinos.append(DestinoRoteamentoEnum.REVISAO_HUMANA)

            # Ajusta status para EM_REVISAO se não for urgência médica estrita
            if self.status != "pendente_auditoria":
                self.status = "EM_REVISAO"
            if self.classificacao.nivel_prioridade != NivelPrioridadeEnum.URGENTE:
                self.decisao_roteamento.destino_principal = DestinoRoteamentoEnum.REVISAO_HUMANA

        # 5. Notificação Automática de Urgência
        if self.classificacao.nivel_prioridade == NivelPrioridadeEnum.URGENTE:
            if not self.decisao_roteamento.notificacao_gerada:
                self.decisao_roteamento.notificacao_gerada = Notificacao(
                    gerada=True,
                    canal="SIMULADO_SLACK_PLANTAO",
                    mensagem=f"🚨 ALERTA URGENTE [{self.documento_id}]: {self.dados_extraidos.diagnostico_principal or 'Achado crítico em triagem'}",
                    status="REGISTRADA"
                )

        return self


# Alias de compatibilidade
ResultadoTriagemClinica = TriagemMediFlow
