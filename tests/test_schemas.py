"""
Testes unitários para validação dos schemas Pydantic do MediFlow.
Garante que o contrato de dados atende às exigências do Hackathon ONE G10,
ao CONTRATO_DE_DADOS_v2.md e aos 79 fixtures de validação (William / Luciana).
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
    # Nomes e classes canônicas v2.0 (William / Luciana)
    TipoArquivoEnum,
    TipoDocumento,
    TipoDocumentoEnum,
    NivelPrioridadeEnum,
    StatusTriagem,
    Destino,
    DestinoRoteamentoEnum,
    Urgencia,
    Gravidade,
    CodigoErro,
    Crm,
    CrmEstruturado,
    Medico,
    Medicamento,
    MedicamentoPrescrito,
    ItemExameLaboratorial,
    Conflito,
    Classificacao,
    ClassificacaoDocumento,
    DadosClinicosExtraidos,
    Qualidade,
    QualidadeExtracao,
    ErroProcessamento,
    ErroResposta,
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
    medico = MedicoSolicitante(nome="Dr. Roberto Santos", crm="123456-SP")
    assert medico.crm.uf == "SP"

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

    assert triagem.status == StatusTriagem.PROCESSADO
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
    assert triagem.status == StatusTriagem.EM_REVISAO


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

    assert triagem.decisao_roteamento.notificacao is not None
    assert triagem.decisao_roteamento.notificacao.gerada is True
    assert "AVCi" in triagem.decisao_roteamento.notificacao.mensagem


def test_contrato_v2_analitos_laboratoriais_rf12():
    """Valida suporte a ItemExameLaboratorial conforme RF-12 e Seção 5.3 da Especificação Funcional"""
    hemoglobina = ItemExameLaboratorial(
        analito="Hemoglobina",
        valor_medido="8.5",
        unidade="g/dL",
        referencia_impressa="12.0 a 16.0 g/dL",
        alterado=True,
    )
    plaquetas = ItemExameLaboratorial(
        analito="Plaquetas",
        valor_medido="250.000",
        unidade="/mm3",
        referencia_impressa="150.000 a 450.000 /mm3",
        alterado=False,
    )

    triagem = TriagemMediFlow(
        documento_id="DOC-LAB-001",
        classificacao=Classificacao(
            tipo_documento=TipoDocumento.LAUDO_EXAME_LABORATORIAL,
            especialidade=["Hematologia"],
            nivel_prioridade=NivelPrioridade.ROTINA,
            score_classificacao=0.97,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Beatriz Santos", idade=34),
            medico=Medico(nome="Dr. Fernando", crm="55443-SP"),
            diagnostico="Anemia moderada a esclarecer",
            exames=["Hemograma Completo"],
            exames_laboratoriais=[hemoglobina, plaquetas],
            urgencia=Urgencia.NAO,
        ),
    )

    assert triagem.status == StatusTriagem.PROCESSADO
    assert len(triagem.dados_extraidos.exames_laboratoriais) == 2
    assert triagem.dados_extraidos.exames_laboratoriais[0].alterado is True
    assert triagem.decisao_roteamento.destino_principal == Destino.PRONTUARIO_ELETRONICO


def test_contrato_v2_erros_leitura_e_requisicao():
    """Valida os dois níveis de erro definidos no CONTRATO_DE_DADOS_v2.md"""
    # 1. Erro de requisição (HTTP 413)
    erro_req = ErroResposta(
        http=413,
        codigo_funcional=CodigoErro.ARQUIVO_MAIOR_QUE_LIMITE,
        mensagem="O arquivo possui 25.00MB, excedendo o limite de 20.00MB."
    )
    assert erro_req.http == 413
    assert erro_req.codigo_funcional == CodigoErro.ARQUIVO_MAIOR_QUE_LIMITE

    # 2. Erro de leitura de documento na triagem (PDF protegido)
    triagem_erro = TriagemMediFlow(
        status=StatusTriagem.ERRO_PROCESSAMENTO,
        documento_id="DOC-SENHA-999",
        erro=ErroProcessamento(
            codigo=CodigoErro.PDF_PROTEGIDO,
            mensagem="Documento protegido por senha."
        )
    )
    assert triagem_erro.status == StatusTriagem.ERRO_PROCESSAMENTO
    assert triagem_erro.erro.codigo == CodigoErro.PDF_PROTEGIDO
    assert triagem_erro.classificacao is None
    assert triagem_erro.dados_extraidos is None
