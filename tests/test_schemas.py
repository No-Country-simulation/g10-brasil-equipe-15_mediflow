"""
Testes unitários para validação dos schemas Pydantic do MediFlow.
Garante que o contrato de dados atende às exigências do Hackathon ONE G10
e às especificações oficiais da equipe (Luciana / William v2.0).
"""
import pytest
from src.schemas import (
    NivelPrioridade,
    DestinoRoteamento,
    Paciente,
    MedicoSolicitante,
    ClassificacaoClinica,
    DadosExtraidos,
    Notificacao,
    DecisaoRoteamento,
    ArmazenamentoOCI,
    ResultadoTriagemClinica,
    # Nomes e classes v2.0 (Luciana / William)
    TipoArquivoEnum,
    NivelPrioridadeEnum,
    TipoDocumentoEnum,
    DestinoRoteamentoEnum,
    CrmEstruturado,
    MedicamentoPrescrito,
    ClassificacaoDocumento,
    DadosClinicosExtraidos,
    QualidadeExtracao,
    TriagemMediFlow,
)


def test_schema_cenario_urgencia_edital():
    """Valida o payload de exemplo do edital (Tromboembolismo Pulmonar Agudo - TEP)"""
    resultado = ResultadoTriagemClinica(
        status="processado",
        documento_id="DOC-CLIN-2026-8942",
        canal_origem="Pronto_Socorro",
        classificacao=ClassificacaoClinica(
            tipo_documento="Laudo de Exame de Imagem",
            especialidade="Radiologia / Pneumologia",
            nivel_prioridade=NivelPrioridade.URGENTE,
            score_confianca_classificacao=0.99,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Carlos Eduardo Mendes", idade=52),
            medico_solicitante=MedicoSolicitante(nome="Dra. Renata Silveira", crm="145892-SP"),
            exame_ou_procedimento="Tomografia de Torax com contraste",
            diagnostico_principal="Tromboembolismo Pulmonar Agudo (TEP)",
            cid_extraido="I26.9",
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamento.EMERGENCIA,
            requer_auditoria_humana=False,
            justificativa_roteamento="Achado critico de alta gravidade (TEP agudo) detectado em paciente sintomatico.",
            notificacao_gerada=Notificacao(
                gerada=True,
                canal="Alerta_Plantao_Medico",
                mensagem="ALERTA URGENTE: Laudo critico de TEP Agudo para paciente Carlos Eduardo Mendes no Pronto-Socorro.",
            ),
        ),
        armazenamento_oci=ArmazenamentoOCI(
            bucket="mediflow-documentos-clinicos",
            caminho_objeto="processados/urgentes/DOC-CLIN-2026-8942.json",
            status_backup="sucesso",
        ),
    )

    assert resultado.documento_id == "DOC-CLIN-2026-8942"
    assert resultado.classificacao.nivel_prioridade == NivelPrioridade.URGENTE
    assert resultado.decisao_roteamento.destino_principal == DestinoRoteamento.EMERGENCIA
    assert resultado.dados_extraidos.paciente.nome == "Carlos Eduardo Mendes"
    assert resultado.armazenamento_oci.status_backup == "sucesso"


def test_schema_cenario_ambiguo_human_in_the_loop():
    """Valida cenário de ambiguidade com acionamento de auditoria humana"""
    resultado = ResultadoTriagemClinica(
        status="pendente_auditoria",
        documento_id="DOC-CLIN-2026-3391",
        canal_origem="Recepcao_Hospitalar",
        classificacao=ClassificacaoClinica(
            tipo_documento="Receituário Médico",
            especialidade="Clínica Médica / Farmácia",
            nivel_prioridade=NivelPrioridade.AMBIGUO,
            score_confianca_classificacao=0.45,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="João da Silva", idade=40),
            medico_solicitante=MedicoSolicitante(nome=None, crm=None),
            medicamentos=["Morfina [Dosagem ilegível]"],
            diagnostico_principal="Dor crônica",
            inconsistencias_detectadas=["CRM ausente", "Dosagem de opioide ilegível"],
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamento.REVISAO_HUMANA,
            requer_auditoria_humana=True,
            justificativa_roteamento="Dosagem ilegível e ausência de identificação do médico solicitante.",
        ),
    )

    assert resultado.decisao_roteamento.requer_auditoria_humana is True
    assert DestinoRoteamentoEnum.REVISAO_HUMANA in resultado.decisao_roteamento.destinos


def test_schema_luciana_v2_com_medicamento_e_crm_estruturado():
    """Valida modelos ricos da v2.0: MedicamentoPrescrito e CrmEstruturado"""
    med = MedicamentoPrescrito(nome="Amoxicilina + Clavulanato", dosagem="875mg + 125mg", frequencia="12/12h por 10 dias")
    assert med.nome == "Amoxicilina + Clavulanato"
    assert med.dosagem == "875mg + 125mg"

    crm = CrmEstruturado(numero="123456", uf="SP")
    medico = MedicoSolicitante(nome="Dr. Roberto Santos", crm="123456-SP", crm_detalhado=crm)
    assert medico.crm_detalhado.uf == "SP"

    triagem = TriagemMediFlow(
        documento_id="DOC-FARMA-001",
        classificacao=ClassificacaoDocumento(
            tipo_documento=TipoDocumentoEnum.RECEITUARIO_MEDICO,
            especialidade="Infectologia",
            nivel_prioridade=NivelPrioridadeEnum.ROTINA,
            score_confianca_classificacao=0.96,
        ),
        dados_extraidos=DadosClinicosExtraidos(
            paciente=Paciente(nome="Maria Aparecida", idade=64),
            medico_solicitante=medico,
            medicamentos=[med],
            diagnostico_principal="Sinusite bacteriana aguda",
            score_confianca_extracao=0.95,
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamentoEnum.FARMACIA_HOSPITALAR,
            requer_auditoria_humana=False,
            justificativa_roteamento="Prescrição eletiva válida e estruturada",
        ),
        armazenamento_oci=ArmazenamentoOCI(
            caminho_objeto="processados/farmacia/DOC-FARMA-001.json"
        )
    )

    assert triagem.status == "PROCESSADO"
    assert triagem.qualidade.score_combinado == 0.95
    assert triagem.decisao_roteamento.requer_auditoria_humana is False


def test_regras_negocio_trava_seguranca_score_baixo():
    """Valida se o model_validator ativa Human-in-the-Loop quando score < 0.85"""
    triagem = TriagemMediFlow(
        documento_id="DOC-BAIXO-SCORE",
        classificacao=ClassificacaoDocumento(
            tipo_documento=TipoDocumentoEnum.LAUDO_LABORATORIAL,
            nivel_prioridade=NivelPrioridadeEnum.ROTINA,
            score_confianca_classificacao=0.72,  # Abaixo de 0.85!
        ),
        dados_extraidos=DadosClinicosExtraidos(
            paciente=Paciente(nome="Ana Paula Souza", idade=29),
            medico_solicitante=MedicoSolicitante(nome="Dr. Carlos", crm="999-RJ"),
            diagnostico_principal="Hemograma com plaquetopenia leve",
            score_confianca_extracao=0.80,
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamentoEnum.PRONTUARIO_ELETRONICO,
            requer_auditoria_humana=False,
            justificativa_roteamento="Roteamento preliminar",
        )
    )

    # O validador deve ter forçado auditoria humana por score baixo
    assert triagem.qualidade.score_combinado == 0.72
    assert triagem.decisao_roteamento.requer_auditoria_humana is True
    assert DestinoRoteamentoEnum.REVISAO_HUMANA in triagem.decisao_roteamento.destinos
    assert triagem.status == "EM_REVISAO"


def test_regras_negocio_alerta_urgencia_automatico():
    """Valida se caso URGENTE dispara notificação automática"""
    triagem = TriagemMediFlow(
        documento_id="DOC-URG-999",
        classificacao=ClassificacaoDocumento(
            tipo_documento=TipoDocumentoEnum.LAUDO_IMAGEM,
            nivel_prioridade=NivelPrioridadeEnum.URGENTE,
            score_confianca_classificacao=0.98,
        ),
        dados_extraidos=DadosClinicosExtraidos(
            paciente=Paciente(nome="Jose da Silva", idade=67),
            medico_solicitante=MedicoSolicitante(nome="Dra. Lucia", crm="111-SP"),
            diagnostico_principal="Acidente Vascular Cerebral Isquêmico (AVCi)",
            score_confianca_extracao=0.95,
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamentoEnum.EMERGENCIA_MEDICA,
            requer_auditoria_humana=False,
            justificativa_roteamento="Achado crítico urgente",
        )
    )

    assert triagem.decisao_roteamento.notificacao_gerada is not None
    assert triagem.decisao_roteamento.notificacao_gerada.gerada is True
    assert "AVCi" in triagem.decisao_roteamento.notificacao_gerada.mensagem
