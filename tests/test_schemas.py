"""
Testes unitários para validação dos schemas Pydantic do MediFlow.
Garante que o contrato de dados atende às exigências do Hackathon ONE G10.
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
            exame_realizado="Tomografia de Torax com contraste",
            diagnostico_principal="Tromboembolismo Pulmonar Agudo (TEP)",
            cid_sugerido="I26.9",
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamento.EMERGENCIA,
            requer_auditoria_humana=False,
            justificativa_roteamento="Achado critico de alta gravidade (TEP agudo) detectado em paciente sintomatico.",
            notificacao_gerada=Notificacao(
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
            paciente=Paciente(nome="João da Silva"),
            medico_solicitante=MedicoSolicitante(nome=None, crm=None),
            medicamentos=["Morfina [Dosagem ilegível]"],
            inconsistencias_detectadas=["CRM ausente", "Dosagem de opioide ilegível"],
        ),
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=DestinoRoteamento.REVISAO_HUMANA,
            requer_auditoria_humana=True,
            justificativa_roteamento="Dosagem ilegível e ausência de identificação do médico solicitante.",
        ),
    )

    assert resultado.decisao_roteamento.requer_auditoria_humana is True
    assert resultado.decisao_roteamento.destino_principal == DestinoRoteamento.REVISAO_HUMANA
