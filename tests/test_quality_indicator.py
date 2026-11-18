"""
Testes TDD para indicadores de qualidade (R5 / Fórmula A3), RN-08 e montagem canônica de TriagemMediFlow.

Cobre os 3 cenários obrigatórios (rotina, urgência isolada, ambíguo/misto) e todas as bordas críticas:
- Borda exata 0.85 (score == limiar NÃO exige revisão por score).
- Borda inferior 0.84 (score < limiar exige revisão).
- RN-08: urgência isolada dispensa revisão humana; urgência com ambiguidade exige revisão sem atribuir a causa à mera urgência.
- Urgência extraída (urgencia == SIM com nivel_prioridade == ROTINA) NUNCA vira rotina na UI nem em TriagemMediFlow.
- Decisão A6: LAUDO_EXAME_LABORATORIAL com exames preenchidos dispensa diagnóstico sem forçar revisão.
- Campo obrigatório ausente aciona revisão; ausência isolada de CID-10 mantém PROCESSADO.
- Falha OCI reflete StatusTriagem.ERRO_PERSISTENCIA com mensagem segura.
"""
from src.app.oci_persistence import MENSAGEM_PUBLICA_FALHA_OCI
from src.app.quality_indicator import (
    IndicadoresQualidadeRoteamento,
    MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO,
    calcular_indicadores_qualidade_e_roteamento,
    eh_decisao_urgente,
    executar_modo_simulado_documento,
    montar_triagem_canonica,
    montar_triagem_erro_processamento,
)
from src.schemas import (
    Classificacao,
    CodigoErro,
    Crm,
    DadosExtraidos,
    Destino,
    Medico,
    NivelPrioridade,
    Paciente,
    StatusTriagem,
    TipoDocumento,
    Urgencia,
)
from src.workflow.graph import criar_grafo
from src.workflow.state import (
    ConflitoWorkflow,
    DecisaoWorkflow,
    EntradaWorkflow,
    QualidadeWorkflow,
)


def _qualidade_wf(
    *,
    score_classif: float = 0.96,
    score_ext: float = 0.98,
    limiar: float = 0.85,
    ausentes: list[str] | None = None,
    incertos: list[str] | None = None,
    motivos: list[str] | None = None,
) -> QualidadeWorkflow:
    return QualidadeWorkflow(
        score_classificacao=score_classif,
        score_extracao=score_ext,
        score_combinado=min(score_classif, score_ext),
        limiar_aplicado=limiar,
        campos_ausentes=ausentes or [],
        campos_incertos=incertos or [],
        motivos_revisao=motivos or [],
    )


def test_rotina_score_alto_dispensa_revisao():
    """Score 0.96 >= 0.85 sem pendências dispensa revisão humana e preserva score_classificacao distinto."""
    qualidade = _qualidade_wf(score_classif=0.96, score_ext=0.98, limiar=0.85)
    decisao = DecisaoWorkflow(
        destinos=[Destino.PRONTUARIO_ELETRONICO],
        requer_auditoria_humana=False,
        justificativa="Critérios de rotina aprovados.",
        regras_acionadas=["ROTINA"],
        alerta_simulado=False,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert isinstance(indicador, IndicadoresQualidadeRoteamento)
    assert indicador.limiar_aplicado == 0.85
    assert indicador.score_classificacao == 0.96
    assert indicador.score_extracao == 0.98
    assert indicador.score_combinado == 0.96
    assert indicador.atingiu_limiar is True
    assert indicador.delta_score == "≥ 0.85"
    assert indicador.delta_score_cor == "normal"
    assert indicador.revisao_humana_status == "Dispensada"
    assert indicador.revisao_humana_motivo == "Aprovação Direta"
    assert indicador.requer_atencao_mista is False
    assert indicador.aviso_misto is None


def test_borda_exata_085_nao_exige_revisao_por_score():
    """Com score_combinado == 0.85 exato, o comparador estrito '<' NÃO aciona revisão humana."""
    qualidade = _qualidade_wf(score_classif=0.85, score_ext=0.90, limiar=0.85)
    decisao = DecisaoWorkflow(
        destinos=[Destino.FARMACIA_HOSPITALAR],
        requer_auditoria_humana=False,
        justificativa="Borda 0.85 aprovada.",
        regras_acionadas=["ROTINA"],
        alerta_simulado=False,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert indicador.score_combinado == 0.85
    assert indicador.atingiu_limiar is True
    assert indicador.delta_score == "≥ 0.85"
    assert indicador.revisao_humana_status == "Dispensada"


def test_urgencia_isolada_rn08_dispensa_revisao_humana():
    """RN-08: Urgência isolada com score >= 0.85 e dados completos NÃO exige revisão humana."""
    qualidade = _qualidade_wf(score_classif=0.99, score_ext=0.98, limiar=0.85)
    decisao = DecisaoWorkflow(
        destinos=[Destino.FILA_URGENCIA_MEDICA],
        requer_auditoria_humana=False,
        justificativa="Sinal estruturado de urgência identificado.",
        regras_acionadas=["URGENCIA"],
        alerta_simulado=True,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert indicador.atingiu_limiar is True
    assert indicador.revisao_humana_status == "Dispensada"
    assert indicador.requer_atencao_mista is False
    assert indicador.aviso_misto is None


def test_urgencia_com_ambiguidade_score_suficiente_exige_revisao_sem_violar_rn08():
    """RN-08 / R4: Urgência com campo incerto (score 0.90 >= 0.85) exige revisão por ambiguidade, sem citar 'caso crítico' como causa."""
    qualidade = _qualidade_wf(
        score_classif=0.95,
        score_ext=0.90,
        limiar=0.85,
        incertos=["medicamentos[0].dosagem"],
        motivos=["Campos ou sinais incertos: medicamentos[0].dosagem"],
    )
    decisao = DecisaoWorkflow(
        destinos=[Destino.FILA_URGENCIA_MEDICA, Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa="Urgência com revisão simultânea.",
        regras_acionadas=["URGENCIA", "REVISAO"],
        alerta_simulado=True,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert indicador.atingiu_limiar is True
    assert indicador.revisao_humana_status == "Exigida"
    assert indicador.revisao_humana_motivo == "Por Regra Clínica"
    assert indicador.requer_atencao_mista is True
    assert indicador.aviso_misto is not None
    assert "caso crítico" not in indicador.aviso_misto.lower()


def test_ambiguo_score_baixo_exige_revisao_por_score():
    """Score 0.65 < 0.85 marca score abaixo do limiar e revisão exigida por score insuficiente."""
    qualidade = _qualidade_wf(
        score_classif=0.80,
        score_ext=0.65,
        limiar=0.85,
        motivos=["Score combinado abaixo do limiar configurado."],
    )
    decisao = DecisaoWorkflow(
        destinos=[Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa="Score abaixo do limiar oficial.",
        regras_acionadas=["REVISAO"],
        alerta_simulado=False,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert indicador.score_classificacao == 0.80
    assert indicador.score_combinado == 0.65
    assert indicador.atingiu_limiar is False
    assert indicador.delta_score == "< 0.85"
    assert indicador.revisao_humana_status == "Exigida"
    assert indicador.revisao_humana_motivo == "Score Insuficiente"
    assert indicador.requer_atencao_mista is False


def test_limiar_customizado_dinamico():
    """Respeita limiar dinâmico configurado (ex: 0.90) sem fixar 0.85."""
    qualidade = _qualidade_wf(score_classif=0.90, score_ext=0.88, limiar=0.90)
    decisao = DecisaoWorkflow(
        destinos=[Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa="Abaixo do limiar customizado.",
        regras_acionadas=["REVISAO"],
        alerta_simulado=False,
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
    )

    assert indicador.limiar_aplicado == 0.90
    assert indicador.atingiu_limiar is False
    assert indicador.delta_score == "< 0.90"
    assert "0.85" not in indicador.delta_score


def test_urgencia_vinda_da_extracao_nunca_vira_rotina_em_triagem_canonica():
    """Se nivel_prioridade == ROTINA mas dados_extraidos.urgencia == SIM, preserva urgência e FILA_URGENCIA_MEDICA."""
    entrada = EntradaWorkflow(
        documento_id="DOC-URG-EXT",
        classificacao=Classificacao(
            tipo_documento=TipoDocumento.LAUDO_EXAME_IMAGEM,
            especialidade=["Pneumologia"],
            nivel_prioridade=NivelPrioridade.ROTINA,
            score_classificacao=0.95,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Ana Paula", idade=58),
            medico=Medico(nome="Dr. Marcos", crm=Crm(numero="554433", uf="SP")),
            diagnostico="Pneumotórax hipertensivo",
            cid=None,
            urgencia=Urgencia.SIM,
        ),
        urgencia="SIM",
        limiar=0.85,
    )
    estado = criar_grafo().invoke({"entrada": entrada})

    assert eh_decisao_urgente(
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        decisao_wf=estado["decisao"],
    ) is True

    triagem = montar_triagem_canonica(
        documento_id="DOC-URG-EXT",
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        qualidade_wf=estado["qualidade"],
        decisao_wf=estado["decisao"],
        urgencia_efetiva=entrada.urgencia,
        caminho_alvo="processados/urgentes/DOC-URG-EXT/resultado.json",
    )

    assert triagem.status == StatusTriagem.PROCESSADO
    assert triagem.decisao_roteamento.destinos == [Destino.FILA_URGENCIA_MEDICA]
    assert triagem.decisao_roteamento.requer_auditoria_humana is False
    assert triagem.decisao_roteamento.notificacao is not None
    assert triagem.dados_extraidos.cid is None  # CID ausente não bloqueia nem é inventado


def test_laudo_laboratorial_sem_diagnostico_com_exames_preserva_decisao_a6():
    """Decisão A6: LAUDO_EXAME_LABORATORIAL com exames preenchidos e diagnostico=None permanece PROCESSADO."""
    entrada = EntradaWorkflow(
        documento_id="DOC-LAB-A6",
        classificacao=Classificacao(
            tipo_documento=TipoDocumento.LAUDO_EXAME_LABORATORIAL,
            especialidade=["Patologia Clínica"],
            nivel_prioridade=NivelPrioridade.ROTINA,
            score_classificacao=0.94,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Pedro Alves", idade=34),
            medico=Medico(nome="Dra. Helena", crm=Crm(numero="112233", uf="SP")),
            diagnostico=None,
            cid=None,
            exames=["Hemograma completo", "Glicemia de jejum"],
            urgencia=Urgencia.NAO,
        ),
        urgencia="NAO",
        limiar=0.85,
    )
    estado = criar_grafo().invoke({"entrada": entrada})

    triagem = montar_triagem_canonica(
        documento_id="DOC-LAB-A6",
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        qualidade_wf=estado["qualidade"],
        decisao_wf=estado["decisao"],
        urgencia_efetiva=entrada.urgencia,
        caminho_alvo="processados/DOC-LAB-A6/resultado.json",
    )

    assert triagem.status == StatusTriagem.PROCESSADO
    assert triagem.decisao_roteamento.requer_auditoria_humana is False
    assert triagem.decisao_roteamento.destinos == [Destino.PRONTUARIO_ELETRONICO]
    assert triagem.dados_extraidos.exames == ["Hemograma completo", "Glicemia de jejum"]


def test_campo_obrigatorio_ausente_aciona_revisao_e_falha_oci_vira_erro_persistencia():
    """Falta de campo obrigatório gera EM_REVISAO; se o OCI falhar, vira ERRO_PERSISTENCIA com mensagem segura."""
    entrada = EntradaWorkflow(
        documento_id="DOC-SEM-CRM",
        classificacao=Classificacao(
            tipo_documento=TipoDocumento.RECEITUARIO_MEDICO,
            nivel_prioridade=NivelPrioridade.NAO_IDENTIFICADA,
            score_classificacao=0.92,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Clara Nunes", idade=41),
            medico=Medico(nome="Dr. João", crm=None),
            diagnostico="Enxaqueca sem aura",
            urgencia=Urgencia.NAO,
        ),
        urgencia="NAO",
        conflitos=[
            ConflitoWorkflow(
                tipo="DOSE_SUSPEITA",
                gravidade="ALTA",
                descricao="Dose acima da faixa usual",
                campos=["medicamentos[0].dosagem"],
            )
        ],
        limiar=0.85,
    )
    estado = criar_grafo().invoke({"entrada": entrada})

    triagem_revisao = montar_triagem_canonica(
        documento_id="DOC-SEM-CRM",
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        qualidade_wf=estado["qualidade"],
        decisao_wf=estado["decisao"],
        urgencia_efetiva=entrada.urgencia,
        caminho_alvo="auditoria_humana/DOC-SEM-CRM/resultado.json",
    )
    assert triagem_revisao.status == StatusTriagem.EM_REVISAO
    assert triagem_revisao.classificacao.nivel_prioridade == NivelPrioridade.NAO_IDENTIFICADA
    assert triagem_revisao.decisao_roteamento.destinos == [Destino.FILA_REVISAO_HUMANA]

    triagem_falha_oci = montar_triagem_canonica(
        documento_id="DOC-SEM-CRM",
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        qualidade_wf=estado["qualidade"],
        decisao_wf=estado["decisao"],
        urgencia_efetiva=entrada.urgencia,
        res_oci={
            "status_backup": "falha",
            "modo_simulacao": False,
            "bucket": "mediflow-documentos",
            "caminho_objeto": None,
            "erro": MENSAGEM_PUBLICA_FALHA_OCI,
        },
        caminho_alvo="auditoria_humana/DOC-SEM-CRM/resultado.json",
    )
    assert triagem_falha_oci.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem_falha_oci.erro.codigo == CodigoErro.ERRO_PERSISTENCIA
    assert triagem_falha_oci.erro.mensagem == MENSAGEM_PUBLICA_FALHA_OCI
    assert triagem_falha_oci.armazenamento_oci.caminho_objeto is None


def test_imports_internos_do_streamlit_app_resolvem_sem_erro():
    """Valida via AST + importlib que todos os símbolos importados de 'src.*' em streamlit_app.py existem."""
    import ast
    import importlib
    from pathlib import Path

    caminho_app = (
        Path(__file__).resolve().parent.parent / "src" / "app" / "streamlit_app.py"
    )
    arvore = ast.parse(caminho_app.read_text(encoding="utf-8"), filename=str(caminho_app))

    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("src"):
            modulo = importlib.import_module(no.module)
            for alias in no.names:
                assert hasattr(modulo, alias.name), (
                    f"Símbolo '{alias.name}' não encontrado no módulo '{no.module}'"
                )


def test_modo_simulado_borda_urgencia_indeterminada_aciona_revisao_decisao_a5():
    """Garante que Borda_Urgencia_Indeterminada.txt no Modo Simulado resulta em EM_REVISAO (Nilo Sérgio Amarante)."""
    from pathlib import Path
    from src.ingestion import DocumentLoader

    caminho_txt = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "catalogo"
        / "Borda_Urgencia_Indeterminada"
        / "Borda_Urgencia_Indeterminada.txt"
    )
    doc = DocumentLoader.carregar_arquivo(caminho_txt)
    estado = executar_modo_simulado_documento(doc, limiar=0.85)

    entrada = estado["entrada"]
    decisao = estado["decisao"]
    qualidade = estado["qualidade"]

    assert entrada.dados_extraidos.paciente.nome == "Nilo Sérgio Amarante"
    assert entrada.urgencia == "INDETERMINADO"
    assert decisao.requer_auditoria_humana is True
    assert [d.value for d in decisao.destinos] == ["FILA_REVISAO_HUMANA"]
    assert "urgencia" in qualidade.campos_incertos


def test_modo_simulado_respeita_score_forcado_borda_084_e_085():
    """Valida que fixtures de fronteira com score_forcado respeitam 0.84 (< 0.85) e 0.85 (== 0.85)."""
    from pathlib import Path
    from src.ingestion import DocumentLoader

    doc_084 = DocumentLoader.carregar_arquivo(
        Path(__file__).resolve().parent / "fixtures" / "demo" / "Borda_Score_084" / "Borda_Score_084.txt"
    )
    est_084 = executar_modo_simulado_documento(doc_084, limiar=0.85)
    assert est_084["qualidade"].score_combinado == 0.84
    assert est_084["decisao"].requer_auditoria_humana is True

    doc_085 = DocumentLoader.carregar_arquivo(
        Path(__file__).resolve().parent / "fixtures" / "catalogo" / "Borda_Score_085" / "Borda_Score_085.txt"
    )
    est_085 = executar_modo_simulado_documento(doc_085, limiar=0.85)
    assert est_085["qualidade"].score_combinado == 0.85
    assert est_085["decisao"].requer_auditoria_humana is False


def test_modo_simulado_arquivo_arbitrario_nao_inventa_dados_ficticios():
    """Arquivos fora do catálogo extraem apenas o texto real, sem inventar 'Carlos Drummond'."""
    from src.ingestion import DocumentLoader

    texto = (
        "RECEITUÁRIO MÉDICO\n"
        "Paciente: Marina Torres\n"
        "Idade: 31\n"
        "Médico: Dr. Paulo Prado\n"
        "CRM/SP: 654321\n"
        "Diagnóstico: Sinusite bacteriana aguda\n"
    ).encode("utf-8")
    doc = DocumentLoader.carregar_bytes(texto, nome_arquivo="receita_propria_avulsa.txt")
    estado = executar_modo_simulado_documento(doc, limiar=0.85)

    assert estado["entrada"].dados_extraidos.paciente.nome == "Marina Torres"
    assert estado["entrada"].dados_extraidos.paciente.nome != "Carlos Drummond"
    assert estado["decisao"].requer_auditoria_humana is False
    assert [d.value for d in estado["decisao"].destinos] == ["FARMACIA_HOSPITALAR"]


def test_contradicao_prioridade_urgente_e_urgencia_nao_preserva_em_revisao_em_triagem_canonica():
    """RF-16 / RNF-02: prioridade URGENTE + urgencia NAO mantém EM_REVISAO e dois destinos no JSON final."""
    entrada = EntradaWorkflow(
        documento_id="DOC-CONTRADICAO",
        classificacao=Classificacao(
            tipo_documento=TipoDocumento.LAUDO_EXAME_IMAGEM,
            especialidade=["Radiologia"],
            nivel_prioridade=NivelPrioridade.URGENTE,
            score_classificacao=0.95,
        ),
        dados_extraidos=DadosExtraidos(
            paciente=Paciente(nome="Renato Russo", idade=45),
            medico=Medico(nome="Dra. Rita", crm=Crm(numero="998877", uf="SP")),
            diagnostico="Pneumotórax em reavaliação",
            urgencia=Urgencia.NAO,
        ),
        urgencia="NAO",
        limiar=0.85,
    )
    estado = criar_grafo().invoke({"entrada": entrada})
    assert estado["decisao"].requer_auditoria_humana is True

    triagem = montar_triagem_canonica(
        documento_id="DOC-CONTRADICAO",
        classificacao=entrada.classificacao,
        dados_extraidos=entrada.dados_extraidos,
        qualidade_wf=estado["qualidade"],
        decisao_wf=estado["decisao"],
        urgencia_efetiva=entrada.urgencia,
        caminho_alvo="auditoria_humana/DOC-CONTRADICAO/resultado.json",
    )
    assert triagem.status == StatusTriagem.EM_REVISAO
    assert triagem.decisao_roteamento.requer_auditoria_humana is True
    assert triagem.decisao_roteamento.destinos == [
        Destino.FILA_URGENCIA_MEDICA,
        Destino.FILA_REVISAO_HUMANA,
    ]
    assert triagem.qualidade.score_combinado == 0.95


def test_modo_simulado_fixture_erro_processamento_nao_extrai_travessao_como_paciente():
    """Qualidade_Pdf_ComSenha.txt retorna erro_processamento (PDF_PROTEGIDO) sem ler '—' como nome."""
    from pathlib import Path
    from src.ingestion import DocumentLoader

    caminho_txt = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "catalogo"
        / "Qualidade_Pdf_ComSenha"
        / "Qualidade_Pdf_ComSenha.txt"
    )
    doc = DocumentLoader.carregar_arquivo(caminho_txt)
    estado = executar_modo_simulado_documento(doc, limiar=0.85)

    assert "erro_processamento" in estado
    assert estado["erro_processamento"]["codigo"] == CodigoErro.PDF_PROTEGIDO


def test_modo_simulado_avulso_crm_sem_uf_e_vitamina_b12_nao_inventa_uf_nem_cid():
    """RF-09 / RF-10: CRM sem UF explícita aciona EM_REVISAO e 'Vitamina B12' nunca vira CID='B12'."""
    from src.ingestion import DocumentLoader

    texto = (
        "RECEITUÁRIO MÉDICO\n"
        "Paciente: Fernanda Montenegro\n"
        "Idade: 68\n"
        "Médico: Dr. Ariano Suassuna\n"
        "CRM: 123456\n"
        "Diagnóstico: Deficiência de Vitamina B12 em acompanhamento\n"
    ).encode("utf-8")
    doc = DocumentLoader.carregar_bytes(texto, nome_arquivo="receita_sem_uf.txt")
    estado = executar_modo_simulado_documento(doc, limiar=0.85)

    entrada = estado["entrada"]
    assert entrada.dados_extraidos.cid is None
    assert "uf" not in entrada.dados_extraidos.medico.crm.model_fields_set
    assert "medico.crm" in estado["qualidade"].campos_ausentes
    assert estado["decisao"].requer_auditoria_humana is True
    assert [d.value for d in estado["decisao"].destinos] == ["FILA_REVISAO_HUMANA"]


def test_modo_simulado_laudo_laboratorial_avulso_com_analitos_preserva_decisao_a6():
    """Decisão A6 no Modo Simulado: laudo laboratorial avulso com analitos e sem diagnóstico aprova em rotina."""
    from src.ingestion import DocumentLoader

    texto = (
        "LAUDO DE EXAME LABORATORIAL\n"
        "Paciente: Lázaro Ramos\n"
        "Idade: 44\n"
        "Solicitante: Dra. Taís Araújo - CRM: 445566-SP\n"
        "Hemoglobina: 14.2 g/dL\n"
        "Leucócitos: 6100 mm3\n"
    ).encode("utf-8")
    doc = DocumentLoader.carregar_bytes(texto, nome_arquivo="hemograma_avulso.txt")
    estado = executar_modo_simulado_documento(doc, limiar=0.85)

    assert estado["entrada"].dados_extraidos.diagnostico is None
    assert len(estado["entrada"].dados_extraidos.exames_laboratoriais) == 2
    assert estado["decisao"].requer_auditoria_humana is False
    assert [d.value for d in estado["decisao"].destinos] == ["PRONTUARIO_ELETRONICO"]


def test_montar_triagem_erro_processamento_nivel_2_e_falha_oci():
    """Contrato §4 (Nível 2) / EF v1.2 §12: ERRO_PROCESSAMENTO zera blocos clínicos e preenche erro."""
    triagem_erro = montar_triagem_erro_processamento(
        documento_id="DOC-ERR-01",
        codigo=CodigoErro.FALHA_WORKFLOW,
        mensagem=MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO,
        caminho_alvo="processados/DOC-ERR-01/resultado.json",
        modo_simulacao_padrao=True,
    )
    assert triagem_erro.status == StatusTriagem.ERRO_PROCESSAMENTO
    assert triagem_erro.classificacao is None
    assert triagem_erro.dados_extraidos is None
    assert triagem_erro.qualidade is None
    assert triagem_erro.decisao_roteamento is None
    assert triagem_erro.erro.codigo == CodigoErro.FALHA_WORKFLOW

    triagem_erro_oci = montar_triagem_erro_processamento(
        documento_id="DOC-ERR-01",
        codigo=CodigoErro.FALHA_WORKFLOW,
        res_oci={"status_backup": "falha", "bucket": "mediflow-documentos", "caminho_objeto": None},
    )
    assert triagem_erro_oci.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem_erro_oci.erro.codigo == CodigoErro.ERRO_PERSISTENCIA




