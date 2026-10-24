"""
MediFlow — Contrato de Dados Canônico e Harmonizado (v2.0)
Define o contrato de dados oficial para toda a aplicação.
Alinhado à Especificação Funcional v1.0, Análise de Requisitos v1.1 (William)
e aos schemas clínicos (Luciana).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# ENUMS OFICIAIS CANÔNICOS (COM RESILIÊNCIA E MAPEAMENTO AUTOMÁTICO)
# ==============================================================================

class TipoArquivoEnum(str, Enum):
    PDF = "PDF"
    PNG = "PNG"
    JPG = "JPG"
    JPEG = "JPEG"
    TXT = "TXT"


class TipoDocumento(str, Enum):
    """8 Categorias Oficiais do MediFlow (Seção 5.1 da Especificação Funcional v1.0)."""
    RECEITUARIO_MEDICO = "RECEITUARIO_MEDICO"
    LAUDO_EXAME_LABORATORIAL = "LAUDO_EXAME_LABORATORIAL"
    LAUDO_EXAME_IMAGEM = "LAUDO_EXAME_IMAGEM"
    GUIA_PROCEDIMENTO = "GUIA_PROCEDIMENTO"
    RELATORIO_ALTA_INTERNACAO = "RELATORIO_ALTA_INTERNACAO"
    ATESTADO_MEDICO = "ATESTADO_MEDICO"
    OUTRO = "OUTRO"
    NAO_IDENTIFICADO = "NAO_IDENTIFICADO"

    # Aliases de compatibilidade para código legado (v2.0)
    LAUDO_IMAGEM = "LAUDO_EXAME_IMAGEM"
    LAUDO_LABORATORIAL = "LAUDO_EXAME_LABORATORIAL"
    GUIA_SOLICITACAO = "GUIA_PROCEDIMENTO"
    RELATORIO_ALTA = "RELATORIO_ALTA_INTERNACAO"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_clean = value.strip().upper().replace(" ", "_").replace("/", "_").replace("-", "_")
            label_map = {
                "LAUDO_DE_EXAME_DE_IMAGEM": cls.LAUDO_EXAME_IMAGEM,
                "LAUDO_IMAGEM": cls.LAUDO_EXAME_IMAGEM,
                "LAUDO_LABORATORIAL": cls.LAUDO_EXAME_LABORATORIAL,
                "LAUDO_DE_EXAME_LABORATORIAL": cls.LAUDO_EXAME_LABORATORIAL,
                "RECEITUARIO_MEDICO": cls.RECEITUARIO_MEDICO,
                "RECEITA_MEDICA": cls.RECEITUARIO_MEDICO,
                "GUIA_DE_SOLICITACAO_DE_PROCEDIMENTO": cls.GUIA_PROCEDIMENTO,
                "GUIA_DE_SOLICITAÇÃO_DE_PROCEDIMENTO": cls.GUIA_PROCEDIMENTO,
                "GUIA_SOLICITACAO": cls.GUIA_PROCEDIMENTO,
                "GUIA_PROCEDIMENTO": cls.GUIA_PROCEDIMENTO,
                "ATESTADO_MEDICO": cls.ATESTADO_MEDICO,
                "RELATORIO_DE_ALTA_INTERNACAO": cls.RELATORIO_ALTA_INTERNACAO,
                "RELATORIO_DE_ALTA_INTERNAÇÃO": cls.RELATORIO_ALTA_INTERNACAO,
                "RELATORIO_ALTA": cls.RELATORIO_ALTA_INTERNACAO,
                "OUTRO": cls.OUTRO,
                "NAO_IDENTIFICADO": cls.NAO_IDENTIFICADO,
                "NÃO_IDENTIFICADO": cls.NAO_IDENTIFICADO,
            }
            if val_clean in label_map:
                return label_map[val_clean]
            for member in cls:
                if member.value == val_clean or member.name == val_clean:
                    return member
        return None


# Alias de compatibilidade
TipoDocumentoEnum = TipoDocumento


class NivelPrioridade(str, Enum):
    """Níveis de prioridade clínica oficiais (Seção 5.2 da Especificação Funcional)."""
    URGENTE = "URGENTE"
    ROTINA = "ROTINA"
    NAO_IDENTIFICADA = "NAO_IDENTIFICADA"

    # Aliases de compatibilidade legada
    POUCO_URGENTE = "ROTINA"
    AMBIGUO = "NAO_IDENTIFICADA"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_clean = value.strip().upper().replace(" ", "_").replace("/", "_")
            if val_clean in ("URGENTE", "EMERGENCIA"):
                return cls.URGENTE
            if val_clean in ("ROTINA", "POUCO_URGENTE", "ELETIVO"):
                return cls.ROTINA
            if val_clean in ("NAO_IDENTIFICADA", "AMBIGUIDADE/REVISAO_HUMANA", "AMBIGUO", "N/A"):
                return cls.NAO_IDENTIFICADA
            for member in cls:
                if member.value == val_clean or member.name == val_clean:
                    return member
        return None


# Alias de compatibilidade
NivelPrioridadeEnum = NivelPrioridade


class StatusTriagem(str, Enum):
    """Status de processamento da triagem (Seção 5.3 da Especificação Funcional)."""
    RECEBIDO = "RECEBIDO"
    PROCESSANDO = "PROCESSANDO"
    PROCESSADO = "PROCESSADO"
    EM_REVISAO = "EM_REVISAO"
    ERRO_PROCESSAMENTO = "ERRO_PROCESSAMENTO"
    ERRO_PERSISTENCIA = "ERRO_PERSISTENCIA"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_clean = value.strip().upper().replace(" ", "_")
            mapping = {
                "PROCESSADO": cls.PROCESSADO,
                "EM_REVISAO": cls.EM_REVISAO,
                "PENDENTE_AUDITORIA": cls.EM_REVISAO,
                "RECEBIDO": cls.RECEBIDO,
                "PROCESSANDO": cls.PROCESSANDO,
                "ERRO": cls.ERRO_PROCESSAMENTO,
                "ERRO_PROCESSAMENTO": cls.ERRO_PROCESSAMENTO,
                "ERRO_PERSISTENCIA": cls.ERRO_PERSISTENCIA,
            }
            if val_clean in mapping:
                return mapping[val_clean]
        return None


class Destino(str, Enum):
    """Filas e destinos lógicos oficiais (Seção 5.4 da Especificação Funcional)."""
    FILA_URGENCIA_MEDICA = "FILA_URGENCIA_MEDICA"
    FARMACIA_HOSPITALAR = "FARMACIA_HOSPITALAR"
    AUDITORIA_AUTORIZACOES = "AUDITORIA_AUTORIZACOES"
    PRONTUARIO_ELETRONICO = "PRONTUARIO_ELETRONICO"
    FILA_REVISAO_HUMANA = "FILA_REVISAO_HUMANA"

    # Aliases de compatibilidade apontando diretamente para os tokens oficiais
    EMERGENCIA = "FILA_URGENCIA_MEDICA"
    EMERGENCIA_MEDICA = "FILA_URGENCIA_MEDICA"
    AUDITORIA = "AUDITORIA_AUTORIZACOES"
    FARMACIA = "FARMACIA_HOSPITALAR"
    PRONTUARIO = "PRONTUARIO_ELETRONICO"
    REVISAO_HUMANA = "FILA_REVISAO_HUMANA"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_clean = value.strip().upper().replace(" ", "_").replace("/", "_")
            mapping = {
                "FILA_EMERGENCIA_MEDICA": cls.FILA_URGENCIA_MEDICA,
                "EMERGENCIA_MEDICA": cls.FILA_URGENCIA_MEDICA,
                "EMERGENCIA": cls.FILA_URGENCIA_MEDICA,
                "PRONTUARIO_ELETRONICO": cls.PRONTUARIO_ELETRONICO,
                "PRONTUARIO": cls.PRONTUARIO_ELETRONICO,
                "PRONTUARIO_ELETRONICO_PACIENTE": cls.PRONTUARIO_ELETRONICO,
                "FILA_REVISAO_HUMANA": cls.FILA_REVISAO_HUMANA,
                "REVISAO_HUMANA": cls.FILA_REVISAO_HUMANA,
                "FARMACIA": cls.FARMACIA_HOSPITALAR,
                "FARMACIA_HOSPITALAR": cls.FARMACIA_HOSPITALAR,
                "AUDITORIA": cls.AUDITORIA_AUTORIZACOES,
                "AUDITORIA_AUTORIZACOES": cls.AUDITORIA_AUTORIZACOES,
            }
            if val_clean in mapping:
                return mapping[val_clean]
        return None


# Aliases de compatibilidade
DestinoRoteamento = Destino
DestinoRoteamentoEnum = Destino


class Urgencia(str, Enum):
    SIM = "SIM"
    NAO = "NAO"
    INDETERMINADO = "INDETERMINADO"


class Gravidade(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAIXA = "BAIXA"


class CodigoErro(str, Enum):
    FORMATO_NAO_SUPORTADO = "FORMATO_NAO_SUPORTADO"
    CAMPOS_INVALIDOS = "CAMPOS_INVALIDOS"
    REQUISICAO_INVALIDA = "REQUISICAO_INVALIDA"
    ARQUIVO_MAIOR_QUE_LIMITE = "ARQUIVO_MAIOR_QUE_LIMITE"
    MIME_INVALIDO = "MIME_INVALIDO"
    PDF_PROTEGIDO = "PDF_PROTEGIDO"
    PDF_CORROMPIDO = "PDF_CORROMPIDO"


DESTINO_POR_TIPO: Dict[TipoDocumento, Destino] = {
    TipoDocumento.RECEITUARIO_MEDICO: Destino.FARMACIA_HOSPITALAR,
    TipoDocumento.LAUDO_EXAME_LABORATORIAL: Destino.PRONTUARIO_ELETRONICO,
    TipoDocumento.LAUDO_EXAME_IMAGEM: Destino.PRONTUARIO_ELETRONICO,
    TipoDocumento.GUIA_PROCEDIMENTO: Destino.AUDITORIA_AUTORIZACOES,
    TipoDocumento.RELATORIO_ALTA_INTERNACAO: Destino.PRONTUARIO_ELETRONICO,
    TipoDocumento.ATESTADO_MEDICO: Destino.PRONTUARIO_ELETRONICO,
}

CAMPOS_OBRIGATORIOS = frozenset({
    "paciente.nome",
    "paciente.idade",
    "medico.nome",
    "medico.crm",
    "diagnostico",
})

GRAVIDADES_IMPEDITIVAS = frozenset({"ALTA", "MEDIA"})


# ==============================================================================
# SUB-MODELOS DE ENTIDADES CLÍNICAS (v2.0)
# ==============================================================================

class Paciente(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nome: Optional[str] = Field(None, description="Nome completo do paciente")
    idade: Optional[int] = Field(None, ge=0, le=120, description="Idade do paciente em anos")
    cpf: Optional[str] = Field(None, description="CPF do paciente (opcional)")


class Crm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    numero: Optional[str] = Field(None, description="Número do CRM normalizado")
    uf: Optional[str] = Field("SP", description="UF do CRM (padrão SP)")


# Alias
CrmEstruturado = Crm


class Medico(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nome: Optional[str] = Field(None, description="Nome do médico solicitante")
    crm: Optional[Union[Crm, str]] = Field(None, description="CRM estruturado ou string")

    @field_validator("crm", mode="before")
    @classmethod
    def normalizar_crm(cls, v):
        if isinstance(v, str):
            partes = v.strip().replace("/", "-").split("-")
            num = partes[0].strip()
            uf = partes[1].strip().upper() if len(partes) > 1 else "SP"
            return Crm(numero=num, uf=uf)
        return v

    @property
    def crm_detalhado(self) -> Optional[Crm]:
        return self.crm if isinstance(self.crm, Crm) else None


# Alias
MedicoSolicitante = Medico


class Medicamento(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nome: str = Field(..., description="Nome do medicamento")
    dosagem: Optional[str] = Field(None, description="Dosagem prescrita")
    frequencia: Optional[str] = Field(None, description="Frequência de administração")


# Alias
MedicamentoPrescrito = Medicamento


class ItemExameLaboratorial(BaseModel):
    """Sub-modelo dedicado para exames laboratoriais e bioquímicos (RF-12 e Seção 5.3)."""
    model_config = ConfigDict(extra="ignore")

    analito: str = Field(..., description="Nome do analito/parâmetro (ex: Hemoglobina, Glicemia)")
    valor_medido: str = Field(..., description="Valor obtido no exame (ex: 14.2, 95)")
    unidade: Optional[str] = Field(None, description="Unidade de medida impressa (ex: g/dL, mg/dL)")
    referencia_impressa: Optional[str] = Field(None, description="Intervalo ou referência do laboratório")
    alterado: Optional[bool] = Field(None, description="Sinalização de alteração (*, Negrito, Alto/Baixo)")


class Conflito(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tipo: str = Field(..., description="Tipo do conflito detectado")
    campos: List[str] = Field(default_factory=list, description="Campos envolvidos")
    gravidade: Gravidade = Field(default=Gravidade.ALTA, description="Gravidade do conflito")
    descricao: str = Field(default="", description="Descrição explicativa")


# ==============================================================================
# CLASSIFICAÇÃO, EXTRAÇÃO E QUALIDADE
# ==============================================================================

class Classificacao(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tipo_documento: Union[TipoDocumento, str] = Field(..., description="Categoria estável do documento")
    especialidade: Optional[Union[List[str], str]] = Field(default_factory=list, description="Especialidade(s) médica(s)")
    nivel_prioridade: NivelPrioridade = Field(..., description="Nível de urgência da triagem")
    score_classificacao: float = Field(..., ge=0.0, le=1.0, description="Score de confiança na classificação")

    @model_validator(mode="before")
    @classmethod
    def normalizar_campos_classificacao(cls, values):
        if isinstance(values, dict):
            if "score_confianca_classificacao" in values and "score_classificacao" not in values:
                values["score_classificacao"] = values.pop("score_confianca_classificacao")
            esp = values.get("especialidade")
            if isinstance(esp, str):
                values["especialidade"] = [esp]
        return values

    @property
    def score_confianca_classificacao(self) -> float:
        return self.score_classificacao


# Aliases
ClassificacaoClinica = Classificacao
ClassificacaoDocumento = Classificacao


class DadosExtraidos(BaseModel):
    model_config = ConfigDict(extra="ignore")

    paciente: Paciente = Field(default_factory=Paciente)
    medico: Medico = Field(default_factory=Medico)
    diagnostico: Optional[str] = Field(None, description="Diagnóstico ou achado clínico principal")
    cid: Optional[str] = Field(None, description="Código CID-10 extraído")
    exames: List[str] = Field(default_factory=list, description="Lista de exames realizados/solicitados")
    exames_laboratoriais: List[ItemExameLaboratorial] = Field(default_factory=list, description="Parâmetros laboratoriais detalhados")
    medicamentos: List[Union[Medicamento, str]] = Field(default_factory=list, description="Medicamentos prescritos")
    urgencia: Urgencia = Field(default=Urgencia.INDETERMINADO, description="Indicador estruturado de urgência")
    score_confianca_extracao: float = Field(default=0.90, ge=0.0, le=1.0)
    achados_criticos: Optional[str] = Field(None, description="Achados críticos ou de alerta")
    inconsistencias_detectadas: List[str] = Field(default_factory=list, description="Inconsistências observadas")

    @model_validator(mode="before")
    @classmethod
    def normalizar_aliases_extraidos(cls, values):
        if isinstance(values, dict):
            if "medico_solicitante" in values and "medico" not in values:
                values["medico"] = values.pop("medico_solicitante")
            if "diagnostico_principal" in values and "diagnostico" not in values:
                values["diagnostico"] = values.pop("diagnostico_principal")
            if "cid_extraido" in values and "cid" not in values:
                values["cid"] = values.pop("cid_extraido")
            elif "cid_sugerido" in values and "cid" not in values:
                values["cid"] = values.pop("cid_sugerido")
            if "exame_ou_procedimento" in values and "exames" not in values:
                val = values.pop("exame_ou_procedimento")
                values["exames"] = [val] if val else []
            elif "exame_realizado" in values and "exames" not in values:
                val = values.pop("exame_realizado")
                values["exames"] = [val] if val else []
        return values

    # Propriedades de compatibilidade com versões iniciais
    @property
    def medico_solicitante(self) -> Medico:
        return self.medico

    @property
    def diagnostico_principal(self) -> Optional[str]:
        return self.diagnostico

    @property
    def cid_extraido(self) -> Optional[str]:
        return self.cid

    @property
    def cid_sugerido(self) -> Optional[str]:
        return self.cid

    @property
    def exame_ou_procedimento(self) -> Optional[str]:
        return self.exames[0] if self.exames else None

    @property
    def exame_realizado(self) -> Optional[str]:
        return self.exames[0] if self.exames else None


# Aliases
DadosClinicosExtraidos = DadosExtraidos


class Qualidade(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score_extracao: float = Field(default=0.90, ge=0.0, le=1.0)
    score_combinado: float = Field(default=0.90, ge=0.0, le=1.0)
    limiar_aplicado: float = Field(default=0.85, ge=0.0, le=1.0)
    campos_ausentes: List[str] = Field(default_factory=list)
    campos_incertos: List[str] = Field(default_factory=list)
    conflitos: List[Conflito] = Field(default_factory=list)

    @property
    def score_classificacao(self) -> float:
        return self.score_combinado


# Alias
QualidadeExtracao = Qualidade


# ==============================================================================
# DECISÃO, NOTIFICAÇÃO E ARMAZENAMENTO OCI
# ==============================================================================

class Notificacao(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gerada: bool = Field(default=True, description="Indica se o alerta foi gerado")
    canal: str = Field(default="SIMULADO_SLACK_PLANTAO", description="Canal de notificação")
    mensagem: Optional[str] = Field(None, description="Mensagem de alerta")
    status: str = Field(default="REGISTRADA", description="Status do envio")


class DecisaoRoteamento(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destino_principal: Optional[Destino] = None
    destinos: List[Destino] = Field(default_factory=list)
    requer_auditoria_humana: bool = False
    justificativa_roteamento: str = ""
    notificacao: Optional[Notificacao] = None

    @model_validator(mode="before")
    @classmethod
    def normalizar_notificacao(cls, values):
        if isinstance(values, dict):
            if "notificacao_gerada" in values and "notificacao" not in values:
                values["notificacao"] = values.pop("notificacao_gerada")
        return values

    @property
    def notificacao_gerada(self) -> Optional[Notificacao]:
        return self.notificacao


class ArmazenamentoOCI(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bucket: str = Field(default="mediflow-documentos-clinicos")
    caminho_objeto: Optional[str] = Field(None, description="Caminho do objeto no bucket OCI")
    status_backup: str = Field(default="sucesso", description="Status da persistência na nuvem")


class ErroProcessamento(BaseModel):
    model_config = ConfigDict(extra="ignore")

    codigo: CodigoErro
    mensagem: str


class ErroResposta(BaseModel):
    """Rejeição de requisição — não chega a virar triagem."""
    model_config = ConfigDict(extra="ignore")

    http: int = Field(..., ge=400, le=499)
    codigo_funcional: CodigoErro
    mensagem: str


# ==============================================================================
# MODELO PRINCIPAL (PAYLOAD FINAL DA TRIAGEM v2.0 COM REGRAS R1 A R8)
# ==============================================================================

class TriagemMediFlow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: StatusTriagem = StatusTriagem.PROCESSADO
    documento_id: str
    canal_origem: Optional[str] = Field(None, description="Canal de entrada (ex: Pronto_Socorro, Web)")
    classificacao: Optional[Classificacao] = None
    dados_extraidos: Optional[DadosExtraidos] = None
    qualidade: Optional[Qualidade] = None
    decisao_roteamento: Optional[DecisaoRoteamento] = None
    armazenamento_oci: Optional[ArmazenamentoOCI] = None
    erro: Optional[ErroProcessamento] = None

    @model_validator(mode="after")
    def aplicar_regras(self) -> "TriagemMediFlow":
        """
        Regras de Negócio Oficiais MediFlow (R1 a R8 - Especificação Funcional v1.0).
        """
        # 1. Tratamento de Erro de Leitura
        em_erro = self.status in (StatusTriagem.ERRO_PROCESSAMENTO, StatusTriagem.ERRO_PERSISTENCIA)
        if em_erro:
            if self.erro is None:
                self.erro = ErroProcessamento(
                    codigo=CodigoErro.PDF_CORROMPIDO,
                    mensagem="Erro no processamento do documento clínico."
                )
            self.decisao_roteamento = None
            self.qualidade = None
            return self

        if self.classificacao is None or self.dados_extraidos is None:
            return self

        c = self.classificacao
        d = self.dados_extraidos

        # 2. Configura ou recupera Qualidade
        if self.qualidade is None:
            score_class = c.score_classificacao
            score_ext = getattr(d, "score_confianca_extracao", 0.90)
            self.qualidade = Qualidade(
                score_extracao=score_ext,
                score_combinado=min(score_class, score_ext),
                limiar_aplicado=0.85,
            )
        q = self.qualidade
        limiar = q.limiar_aplicado
        q.score_combinado = min(c.score_classificacao, q.score_extracao)

        # 3. Verificação de Campos Obrigatórios Vitais (RF-21)
        ausentes = set(q.campos_ausentes)
        if not d.paciente or not d.paciente.nome:
            ausentes.add("paciente.nome")
        if not d.paciente or d.paciente.idade is None:
            ausentes.add("paciente.idade")
        if not d.medico or not d.medico.nome:
            ausentes.add("medico.nome")
        if not d.medico or not d.medico.crm or (isinstance(d.medico.crm, Crm) and not d.medico.crm.numero):
            ausentes.add("medico.crm")
        if not d.diagnostico and not d.exames:
            ausentes.add("diagnostico")
        q.campos_ausentes = sorted(list(ausentes))

        # 4. Avaliação de Ambiguidade e Regras
        urgente = (c.nivel_prioridade == NivelPrioridade.URGENTE) or (d.urgencia == Urgencia.SIM)
        fora_da_taxonomia = c.tipo_documento in (TipoDocumento.OUTRO, TipoDocumento.NAO_IDENTIFICADO)
        abaixo_do_limiar = q.score_combinado < limiar
        falta_obrigatorio = bool(set(q.campos_ausentes) & CAMPOS_OBRIGATORIOS)
        impeditivos = [x for x in q.conflitos if getattr(x.gravidade, "value", x.gravidade) in GRAVIDADES_IMPEDITIVAS]
        prioridade_indefinida = (c.nivel_prioridade == NivelPrioridade.NAO_IDENTIFICADA)

        ambiguidade = bool(
            falta_obrigatorio or q.campos_incertos or impeditivos or abaixo_do_limiar
            or fora_da_taxonomia or prioridade_indefinida
        )

        # 5. Destinos (R1, R3, R4)
        destinos: List[Destino] = []
        if urgente:
            destinos.append(Destino.FILA_URGENCIA_MEDICA)
        elif not ambiguidade:
            dest_tipo = DESTINO_POR_TIPO.get(c.tipo_documento, Destino.PRONTUARIO_ELETRONICO)
            destinos.append(dest_tipo)

        if ambiguidade:
            if urgente:
                destinos = [Destino.FILA_URGENCIA_MEDICA, Destino.FILA_REVISAO_HUMANA]
            else:
                destinos = [Destino.FILA_REVISAO_HUMANA]

        # Sincroniza decisão
        if self.decisao_roteamento is None:
            self.decisao_roteamento = DecisaoRoteamento()

        self.decisao_roteamento.destinos = destinos
        self.decisao_roteamento.destino_principal = destinos[0]
        self.decisao_roteamento.requer_auditoria_humana = ambiguidade

        # Justificativa
        motivos = []
        if abaixo_do_limiar:
            motivos.append(f"score combinado {q.score_combinado:.2f} < limiar {limiar:.2f}")
        if falta_obrigatorio:
            motivos.append("campos obrigatórios ausentes: " + ", ".join(sorted(set(q.campos_ausentes) & CAMPOS_OBRIGATORIOS)))
        if q.campos_incertos:
            motivos.append("campos incertos: " + ", ".join(q.campos_incertos))
        if impeditivos:
            motivos.append("conflitos impeditivos: " + ", ".join(x.tipo for x in impeditivos))
        if fora_da_taxonomia:
            motivos.append(f"tipo fora da taxonomia: {getattr(c.tipo_documento, 'value', c.tipo_documento)}")

        if urgente and ambiguidade:
            self.decisao_roteamento.justificativa_roteamento = (
                "Urgência com ambiguidade: mantém FILA_URGENCIA_MEDICA e acrescenta FILA_REVISAO_HUMANA. " + "; ".join(motivos) + "."
            )
        elif urgente:
            self.decisao_roteamento.justificativa_roteamento = (
                "Urgência clínica: FILA_URGENCIA_MEDICA com alerta registrado. Sem ambiguidade, segue sem revisão humana."
            )
        elif ambiguidade:
            self.decisao_roteamento.justificativa_roteamento = "Revisão humana obrigatória: " + "; ".join(motivos) + "."
        else:
            tipo_txt = getattr(c.tipo_documento, "value", c.tipo_documento)
            dest_txt = getattr(self.decisao_roteamento.destino_principal, "value", self.decisao_roteamento.destino_principal)
            self.decisao_roteamento.justificativa_roteamento = (
                f"Classificação de rotina: {tipo_txt} encaminhado para {dest_txt}."
            )

        # 6. Notificação Automática de Urgência
        if urgente and not self.decisao_roteamento.notificacao:
            diag = d.diagnostico or (d.exames[0] if d.exames else "achado crítico em triagem")
            self.decisao_roteamento.notificacao = Notificacao(
                gerada=True,
                canal="SIMULADO_SLACK_PLANTAO",
                mensagem=f"🚨 ALERTA URGENTE [{self.documento_id}]: {diag}",
                status="REGISTRADA",
            )

        # 7. Status Final
        if self.status != StatusTriagem.ERRO_PROCESSAMENTO:
            if self.decisao_roteamento.requer_auditoria_humana:
                self.status = StatusTriagem.EM_REVISAO
            else:
                self.status = StatusTriagem.PROCESSADO

        return self


# Alias de compatibilidade
ResultadoTriagemClinica = TriagemMediFlow
