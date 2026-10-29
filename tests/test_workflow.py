import pytest
from pydantic import ValidationError

from src.schemas.clinical import (
    ClassificacaoClinica,
    DadosExtraidos,
    DestinoRoteamento,
    MedicoSolicitante,
    NivelPrioridade,
    Paciente,
)
from src.workflow.graph import criar_grafo
from src.workflow.state import (
    ConflitoWorkflow,
    EntradaWorkflow,
)


@pytest.fixture
def montar_entrada():
    """Cria entrada fictícia completa e permite variar cada condição."""

    def montar(
        *,
        documento_id="DOC-TESTE-001",
        score=0.96,
        prioridade=NivelPrioridade.ROTINA,
        urgencia="NAO",
        tipo="Laudo de Exame de Imagem",
        nome="Paciente Fictício",
        idade=40,
        nome_medico="Profissional Fictício",
        crm="000000-SP",
        diagnostico="Conclusão fictícia explícita",
        incertos=None,
        conflitos=None,
        limiar=0.85,
    ):
        return EntradaWorkflow(
            documento_id=documento_id,
            classificacao=ClassificacaoClinica(
                tipo_documento=tipo,
                nivel_prioridade=prioridade,
                score_confianca_classificacao=score,
            ),
            dados_extraidos=DadosExtraidos(
                paciente=Paciente(
                    nome=nome,
                    idade=idade,
                ),
                medico_solicitante=MedicoSolicitante(
                    nome=nome_medico,
                    crm=crm,
                ),
                diagnostico_principal=diagnostico,
                cid_sugerido=None,
            ),
            urgencia=urgencia,
            campos_incertos=incertos or [],
            conflitos=conflitos or [],
            limiar=limiar,
        )

    return montar


@pytest.fixture
def executar(montar_entrada):
    grafo = criar_grafo()

    def rodar(**parametros):
        entrada = montar_entrada(**parametros)
        return grafo.invoke({"entrada": entrada})

    return rodar


def test_rotina_sem_penalidades(executar):
    resultado = executar()

    assert resultado["qualidade"].score_extracao == 1.0
    assert resultado["qualidade"].score_combinado == 0.96
    assert resultado["qualidade"].motivos_revisao == []

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.PRONTUARIO
    ]
    assert not resultado["decisao"].requer_auditoria_humana
    assert not resultado["decisao"].alerta_simulado


@pytest.mark.parametrize(
    "score,revisao",
    [
        (0.84, True),
        (0.85, False),
        (0.86, False),
    ],
)
def test_limiar_estrito(executar, score, revisao):
    resultado = executar(score=score)

    assert resultado["qualidade"].score_combinado == score
    assert (
        resultado["decisao"].requer_auditoria_humana
        is revisao
    )


def test_limiar_recebido_na_entrada_e_aplicado(executar):
    resultado = executar(
        score=0.86,
        limiar=0.90,
    )

    assert resultado["qualidade"].limiar_aplicado == 0.90
    assert resultado["decisao"].requer_auditoria_humana


@pytest.mark.parametrize(
    "parametro,campo",
    [
        ("nome", "paciente.nome"),
        ("idade", "paciente.idade"),
        ("nome_medico", "medico.nome"),
        ("crm", "medico.crm"),
        ("diagnostico", "diagnostico"),
    ],
)
def test_campo_obrigatorio_ausente(
    executar,
    parametro,
    campo,
):
    resultado = executar(**{parametro: None})

    assert resultado["qualidade"].score_extracao == 0.80
    assert campo in resultado["qualidade"].campos_ausentes

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.REVISAO_HUMANA
    ]
    assert resultado["decisao"].requer_auditoria_humana


def test_nome_apenas_com_espacos_e_ausente(executar):
    resultado = executar(nome="   ")

    assert (
        "paciente.nome"
        in resultado["qualidade"].campos_ausentes
    )
    assert resultado["decisao"].requer_auditoria_humana


def test_idade_zero_nao_e_tratada_como_ausente(executar):
    resultado = executar(idade=0)

    assert (
        "paciente.idade"
        not in resultado["qualidade"].campos_ausentes
    )
    assert not resultado["decisao"].requer_auditoria_humana


def test_cid_ausente_isoladamente_nao_exige_revisao(executar):
    resultado = executar()

    assert (
        resultado["entrada"].dados_extraidos.cid_sugerido
        is None
    )
    assert not resultado["decisao"].requer_auditoria_humana


def test_campo_incerto_exige_revisao_com_score_suficiente(
    executar,
):
    resultado = executar(
        incertos=["medicamentos[0].dosagem"],
    )

    assert resultado["qualidade"].score_extracao == 0.90
    assert resultado["qualidade"].score_combinado == 0.90
    assert resultado["decisao"].requer_auditoria_humana


def test_campos_incertos_duplicados_contam_uma_vez(executar):
    resultado = executar(
        incertos=[
            " medico_solicitante.crm ",
            "medico.crm",
            "",
            "   ",
        ],
    )

    assert resultado["qualidade"].campos_incertos == [
        "medico.crm"
    ]
    assert resultado["qualidade"].score_extracao == 0.90


@pytest.mark.parametrize(
    "gravidade,esperado,revisao",
    [
        ("ALTA", 0.70, True),
        ("MEDIA", 0.80, True),
        ("BAIXA", 0.90, False),
    ],
)
def test_penalidade_por_conflito(
    executar,
    gravidade,
    esperado,
    revisao,
):
    conflito = ConflitoWorkflow(
        tipo="CONFLITO_CONTROLADO",
        gravidade=gravidade,
        descricao="Exemplo fictício para testar a regra.",
        campos=["diagnostico"],
    )

    resultado = executar(conflitos=[conflito])

    assert resultado["qualidade"].score_extracao == esperado
    assert (
        resultado["decisao"].requer_auditoria_humana
        is revisao
    )


def test_conflito_repetido_nao_duplica_penalidade(executar):
    conflito = ConflitoWorkflow(
        tipo="CONFLITO_CONTROLADO",
        gravidade="BAIXA",
        descricao="Mesmo conflito repetido.",
        campos=["diagnostico"],
    )

    resultado = executar(
        conflitos=[
            conflito,
            conflito.model_copy(deep=True),
        ],
    )

    assert resultado["qualidade"].score_extracao == 0.90
    assert not resultado["decisao"].requer_auditoria_humana


def test_penalidades_distintas_sao_somadas(executar):
    conflito = ConflitoWorkflow(
        tipo="CONFLITO_CONTROLADO",
        gravidade="BAIXA",
        descricao="Conflito fictício.",
        campos=["diagnostico"],
    )

    resultado = executar(
        nome=None,
        incertos=["medico.crm"],
        conflitos=[conflito],
    )

    # 1 - 0,20 - 0,10 - 0,10 = 0,60
    assert resultado["qualidade"].score_extracao == 0.60
    assert resultado["decisao"].requer_auditoria_humana


def test_score_extracao_tem_piso_zero(executar):
    conflitos = [
        ConflitoWorkflow(
            tipo=f"CONFLITO_{indice}",
            gravidade="ALTA",
            descricao="Conflito fictício distinto.",
        )
        for indice in range(4)
    ]

    resultado = executar(conflitos=conflitos)

    assert resultado["qualidade"].score_extracao == 0.0
    assert resultado["decisao"].requer_auditoria_humana


def test_urgencia_isolada_nao_exige_revisao(executar):
    resultado = executar(
        prioridade=NivelPrioridade.URGENTE,
        urgencia="SIM",
    )

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.EMERGENCIA
    ]
    assert not resultado["decisao"].requer_auditoria_humana
    assert resultado["decisao"].alerta_simulado


def test_urgencia_com_ambiguidade_tem_dois_destinos(executar):
    resultado = executar(
        prioridade=NivelPrioridade.URGENTE,
        urgencia="SIM",
        incertos=["medico.crm"],
    )

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.EMERGENCIA,
        DestinoRoteamento.REVISAO_HUMANA,
    ]
    assert resultado["decisao"].requer_auditoria_humana
    assert resultado["decisao"].alerta_simulado


def test_urgencia_com_score_baixo_preserva_emergencia(executar):
    resultado = executar(
        prioridade=NivelPrioridade.URGENTE,
        urgencia="SIM",
        score=0.70,
    )

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.EMERGENCIA,
        DestinoRoteamento.REVISAO_HUMANA,
    ]
    assert resultado["decisao"].requer_auditoria_humana
    assert resultado["decisao"].alerta_simulado


def test_sinais_contraditorios_preservam_urgencia_e_revisao(
    executar,
):
    resultado = executar(
        prioridade=NivelPrioridade.URGENTE,
        urgencia="NAO",
    )

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.EMERGENCIA,
        DestinoRoteamento.REVISAO_HUMANA,
    ]
    assert resultado["decisao"].alerta_simulado
    assert resultado["decisao"].requer_auditoria_humana

    assert any(
        "contraditórios" in motivo
        for motivo in resultado["qualidade"].motivos_revisao
    )


def test_urgencia_indeterminada_exige_revisao(executar):
    resultado = executar(urgencia="INDETERMINADO")

    assert "urgencia" in (
        resultado["qualidade"].campos_incertos
    )
    assert resultado["decisao"].requer_auditoria_humana
    assert not resultado["decisao"].alerta_simulado


def test_prioridade_ambigua_exige_revisao(executar):
    resultado = executar(
        prioridade=NivelPrioridade.AMBIGUO,
        urgencia="INDETERMINADO",
    )

    assert (
        "classificacao.nivel_prioridade"
        in resultado["qualidade"].campos_incertos
    )
    assert resultado["decisao"].requer_auditoria_humana


@pytest.mark.parametrize(
    "tipo,destino",
    [
        ("Receituário Médico", DestinoRoteamento.FARMACIA),
        ("RECEITUARIO_MEDICO", DestinoRoteamento.FARMACIA),
        (
            "Guia de Solicitação de Procedimento",
            DestinoRoteamento.AUDITORIA,
        ),
        ("GUIA_PROCEDIMENTO", DestinoRoteamento.AUDITORIA),
        (
            "Laudo de Exame de Imagem",
            DestinoRoteamento.PRONTUARIO,
        ),
        ("Laudo Laboratorial", DestinoRoteamento.PRONTUARIO),
        (
            "Relatório de Alta/Internação",
            DestinoRoteamento.PRONTUARIO,
        ),
        ("Atestado Médico", DestinoRoteamento.PRONTUARIO),
    ],
)
def test_destino_de_rotina_por_tipo(executar, tipo, destino):
    resultado = executar(tipo=tipo)

    assert resultado["decisao"].destinos == [destino]
    assert not resultado["decisao"].requer_auditoria_humana


@pytest.mark.parametrize(
    "tipo",
    [
        "OUTRO",
        "NAO_IDENTIFICADO",
        "Tipo sem mapeamento",
    ],
)
def test_tipo_nao_mapeado_exige_revisao(executar, tipo):
    resultado = executar(tipo=tipo)

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.REVISAO_HUMANA
    ]
    assert resultado["decisao"].requer_auditoria_humana


@pytest.mark.parametrize("documento_id", ["", "   "])
def test_documento_id_vazio_e_rejeitado(
    montar_entrada,
    documento_id,
):
    with pytest.raises(ValidationError):
        montar_entrada(documento_id=documento_id)


@pytest.mark.parametrize(
    "limiar",
    [-0.01, 1.01, float("nan"), float("inf")],
)
def test_limiar_invalido_e_rejeitado(montar_entrada, limiar):
    with pytest.raises(ValidationError):
        montar_entrada(limiar=limiar)


def test_decisao_tem_justificativa_e_regra(executar):
    resultado = executar()
    decisao = resultado["decisao"]

    assert decisao.justificativa.strip()
    assert decisao.regras_acionadas


def test_grafo_nao_confirma_persistencia(executar):
    resultado = executar()

    assert resultado["decisao"].etapa == "DECISAO_CALCULADA"
    assert "armazenamento_oci" not in resultado

# Regressões A1/A3/A5 e integração com o contrato harmonizado de 24–25/10.
@pytest.mark.parametrize("gravidade", ["ALTA", "MEDIA", "BAIXA"])
def test_conflitos_preservados_em_qualidade(executar, gravidade):
    conflito = ConflitoWorkflow(tipo="DOSE_SUSPEITA", gravidade=gravidade,
                               descricao="Dado fictício", campos=["diagnostico_principal"])
    resultado = executar(conflitos=[conflito])
    registrados = resultado["qualidade"].conflitos
    assert len(registrados) == 1
    assert registrados[0].gravidade == gravidade
    assert registrados[0].campos == ["diagnostico"]
    assert conflito.campos == ["diagnostico_principal"]  # sem mutação da entrada


@pytest.mark.parametrize("urgente", [False, True])
def test_conflito_baixo_visivel_sem_bloqueio(executar, urgente):
    resultado = executar(
        prioridade=NivelPrioridade.URGENTE if urgente else NivelPrioridade.ROTINA,
        urgencia="SIM" if urgente else "NAO",
        conflitos=[ConflitoWorkflow(tipo="DADOS_PACIENTE", gravidade="BAIXA",
                                   descricao="Observação fictícia")],
    )
    assert resultado["qualidade"].score_extracao == .90
    assert resultado["qualidade"].conflitos[0].gravidade == "BAIXA"
    assert "DADOS_PACIENTE" in resultado["decisao"].justificativa
    assert not resultado["decisao"].requer_auditoria_humana


def test_conflitos_baixos_acumulados_podem_baixar_score(executar):
    r = executar(conflitos=[ConflitoWorkflow(tipo=f"OBS_{i}", gravidade="BAIXA") for i in range(2)])
    assert r["qualidade"].score_extracao == .8
    assert len(r["qualidade"].conflitos) == 2
    assert r["decisao"].requer_auditoria_humana


def test_opcionais_ausentes_registrados_sem_penalidade(executar):
    r = executar()
    assert {"cid", "medicamentos", "exames"} <= set(r["qualidade"].campos_ausentes)
    assert r["qualidade"].score_extracao == 1
    assert not r["decisao"].requer_auditoria_humana


def test_sinais_ausentes_de_extracao_canonizados(montar_entrada):
    entrada = montar_entrada().model_copy(update={
        "campos_ausentes": ["medico_solicitante.nome", "medico.nome"]
    })
    r = criar_grafo().invoke({"entrada": entrada})
    assert r["qualidade"].campos_ausentes.count("medico.nome") == 1
    assert r["qualidade"].score_extracao == .8
    assert r["decisao"].requer_auditoria_humana


def test_incertezas_legadas_canonizadas(montar_entrada):
    entrada = montar_entrada(incertos=["medico_solicitante.crm", "medico.crm"])
    r = criar_grafo().invoke({"entrada": entrada})
    assert r["qualidade"].campos_incertos == ["medico.crm"]
    assert r["qualidade"].score_extracao == .9


NOVO_CONTRATO = "medico" in DadosExtraidos.model_fields


@pytest.mark.skipif(not NOVO_CONTRATO, reason="CRM estruturado depende do contrato harmonizado")
@pytest.mark.parametrize("crm", [
    {"numero": None, "uf": "SP"},
    {"numero": "  ", "uf": "SP"},
    {"numero": "ABC", "uf": "SP"},
    {"numero": "12345", "uf": None},
    {"numero": "12345", "uf": "XX"},
    {"numero": "12345"},
])
def test_crm_estruturado_incompleto_exige_revisao(montar_entrada, crm):
    entrada = montar_entrada()
    dados = entrada.dados_extraidos.model_dump()
    dados["medico"]["crm"] = crm
    entrada = EntradaWorkflow.model_validate({**entrada.model_dump(), "dados_extraidos": dados})
    r = criar_grafo().invoke({"entrada": entrada})
    assert "medico.crm" in r["qualidade"].campos_ausentes
    assert r["qualidade"].score_extracao == .8
    assert r["decisao"].requer_auditoria_humana


@pytest.mark.skipif(not NOVO_CONTRATO, reason="Requer blocos do contrato harmonizado")
def test_adapter_usa_urgencia_da_extracao_e_ignora_decisao(montar_entrada):
    entrada = montar_entrada()
    payload = entrada.model_dump()
    payload.pop("urgencia")
    payload["dados_extraidos"]["urgencia"] = "SIM"
    payload["qualidade"] = {"score_extracao": .01, "limiar_aplicado": .01,
                            "conflitos": [{"tipo": "OBS", "gravidade": "BAIXA"}]}
    payload["decisao_roteamento"] = {"destinos": ["PRONTUARIO_ELETRONICO"]}
    e = EntradaWorkflow.de_extracao(payload, limiar=.85)
    r = criar_grafo().invoke({"entrada": e})
    assert e.urgencia == "SIM"
    assert r["qualidade"].score_extracao == .9
    assert r["qualidade"].limiar_aplicado == .85
    assert r["decisao"].destinos == [DestinoRoteamento.EMERGENCIA]
    assert not r["decisao"].requer_auditoria_humana


@pytest.mark.skipif(not NOVO_CONTRATO, reason="Requer urgência no contrato harmonizado")
def test_fontes_de_urgencia_divergentes_sao_rejeitadas(montar_entrada):
    payload = montar_entrada().model_dump()
    payload["dados_extraidos"]["urgencia"] = "SIM"
    payload["urgencia"] = "NAO"
    with pytest.raises(ValidationError, match="Urgência divergente"):
        EntradaWorkflow.model_validate(payload)


@pytest.mark.skipif(not NOVO_CONTRATO, reason="Requer lista de exames do contrato harmonizado")
@pytest.mark.parametrize("tipo,revisao", [
    ("LAUDO_EXAME_LABORATORIAL", False),
    ("RECEITUARIO_MEDICO", True),
    ("GUIA_PROCEDIMENTO", True),
    ("LAUDO_EXAME_IMAGEM", True),
])
def test_excecao_diagnostico_restrita_a_laboratorio(montar_entrada, tipo, revisao):
    payload = montar_entrada(tipo=tipo).model_dump()
    payload["dados_extraidos"]["diagnostico"] = None
    payload["dados_extraidos"]["exames"] = ["Hemograma fictício"]
    entrada = EntradaWorkflow.model_validate(payload)
    r = criar_grafo().invoke({"entrada": entrada})
    assert r["decisao"].requer_auditoria_humana is revisao


@pytest.mark.skipif(not NOVO_CONTRATO, reason="Requer lista de exames do contrato harmonizado")
def test_diagnostico_declarado_ausente_nao_e_ocultado(montar_entrada):
    payload = montar_entrada(tipo="LAUDO_EXAME_LABORATORIAL").model_dump()
    payload["dados_extraidos"]["diagnostico"] = None
    payload["dados_extraidos"]["exames"] = ["Hemograma fictício"]
    payload["campos_ausentes"] = ["diagnostico"]
    r = criar_grafo().invoke({"entrada": EntradaWorkflow.model_validate(payload)})
    assert r["decisao"].requer_auditoria_humana


@pytest.mark.skipif(not NOVO_CONTRATO, reason="Requer urgência do contrato harmonizado")
def test_urgencia_interna_indeterminada_gera_incerteza(montar_entrada):
    payload = montar_entrada().model_dump()
    payload.pop("urgencia")
    payload["dados_extraidos"]["urgencia"] = "INDETERMINADO"
    e = EntradaWorkflow.de_extracao(payload)
    r = criar_grafo().invoke({"entrada": e})
    assert "urgencia" in r["qualidade"].campos_incertos
    assert r["decisao"].requer_auditoria_humana
    assert not r["decisao"].alerta_simulado


@pytest.mark.skipif(NOVO_CONTRATO, reason="Proteção exclusiva do contrato legado")
def test_adapter_nao_descarta_campos_novos_no_contrato_legado(montar_entrada):
    payload = montar_entrada().model_dump()
    payload["dados_extraidos"]["urgencia"] = "SIM"
    with pytest.raises(ValueError, match="contrato harmonizado"):
        EntradaWorkflow.de_extracao(payload)


def test_adapter_preserva_sinais_sem_usar_score_ilustrativo(montar_entrada):
    payload = montar_entrada().model_dump()
    payload["qualidade"] = {"score_extracao": .01, "campos_incertos": ["paciente.nome"],
                            "conflitos": [{"tipo": "OBS", "gravidade": "BAIXA"}]}
    entrada = EntradaWorkflow.de_extracao(payload)
    r = criar_grafo().invoke({"entrada": entrada})
    assert r["qualidade"].score_extracao == .8
    assert r["qualidade"].campos_incertos == ["paciente.nome"]
    assert len(r["qualidade"].conflitos) == 1
    assert r["decisao"].requer_auditoria_humana

@pytest.mark.parametrize("campo_ausente", ["medicamentos", "exames"])
def test_ausencia_opcional_isolada(montar_entrada, campo_ausente):
    entrada = montar_entrada()
    dados = entrada.dados_extraidos.model_dump()

    contrato_novo = "exames" in DadosExtraidos.model_fields
    chave_exame = "exames" if contrato_novo else "exame_realizado"
    chave_cid = "cid" if contrato_novo else "cid_sugerido"

    dados["medicamentos"] = ["Medicamento fictício"]
    dados[chave_exame] = (
        ["Exame fictício"] if contrato_novo else "Exame fictício"
    )
    dados[chave_cid] = "Z00.0"

    if campo_ausente == "medicamentos":
        dados["medicamentos"] = []
    else:
        dados[chave_exame] = [] if contrato_novo else None

    payload = entrada.model_dump()
    payload["dados_extraidos"] = dados
    entrada = EntradaWorkflow.model_validate(payload)

    resultado = criar_grafo().invoke({"entrada": entrada})
    qualidade = resultado["qualidade"]

    outro_campo = (
        "exames" if campo_ausente == "medicamentos" else "medicamentos"
    )

    assert campo_ausente in qualidade.campos_ausentes
    assert outro_campo not in qualidade.campos_ausentes
    assert qualidade.score_extracao == 1.0
    assert not resultado["decisao"].requer_auditoria_humana


import json
from types import SimpleNamespace
from unittest.mock import Mock

import oci

from src.storage.oci_storage import OCIStorage


def _json_workflow_para_teste(resultado):
    """Snapshot interno de teste; não é a resposta final da API."""
    payload = {
        "documento_id": resultado["entrada"].documento_id,
        "qualidade": resultado["qualidade"].model_dump(mode="json"),
        "decisao": resultado["decisao"].model_dump(mode="json"),
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@pytest.fixture
def oci_workflow_simulado():
    """Substitui o cliente OCI por armazenamento em memória."""
    cliente = Mock()
    objetos = {}

    def enviar(**argumentos):
        nome = argumentos["object_name"]

        if (
            nome in objetos
            and argumentos.get("if_none_match") == "*"
        ):
            raise oci.exceptions.ServiceError(
                status=412,
                code="PreconditionFailed",
                headers={},
                message="Objeto fictício já existe",
            )

        objetos[nome] = argumentos["put_object_body"]

        return SimpleNamespace(
            status=200,
            headers={"etag": "etag-ficticio"},
        )

    def ler(**argumentos):
        nome = argumentos["object_name"]
        corpo = Mock()
        corpo.content = objetos[nome]
        return SimpleNamespace(data=corpo)

    cliente.put_object.side_effect = enviar
    cliente.get_object.side_effect = ler

    storage = OCIStorage(
        cliente,
        "namespace-ficticio",
        "mediflow-documentos",
    )

    return storage, cliente, objetos


@pytest.mark.parametrize(
    "cenario",
    [
        "rotina",
        "baixa_confianca",
        "urgencia_ambigua",
        "conflito_baixo",
    ],
)
def test_workflow_json_oci_simulado_preserva_saida(
    executar,
    oci_workflow_simulado,
    cenario,
):
    parametros = {}
    destinos_esperados = [
        DestinoRoteamento.PRONTUARIO.value,
    ]
    revisao_esperada = False

    if cenario == "baixa_confianca":
        parametros = {"score": 0.84}
        destinos_esperados = [
            DestinoRoteamento.REVISAO_HUMANA.value,
        ]
        revisao_esperada = True

    elif cenario == "urgencia_ambigua":
        parametros = {
            "prioridade": NivelPrioridade.URGENTE,
            "urgencia": "SIM",
            "incertos": ["paciente.nome"],
        }
        destinos_esperados = [
            DestinoRoteamento.EMERGENCIA.value,
            DestinoRoteamento.REVISAO_HUMANA.value,
        ]
        revisao_esperada = True

    elif cenario == "conflito_baixo":
        parametros = {
            "conflitos": [
                ConflitoWorkflow(
                    tipo="OBS_TESTE",
                    gravidade="BAIXA",
                    descricao="Observação fictícia preservada",
                )
            ]
        }

    # Executa o agente real, usando a fixture existente.
    resultado = executar(**parametros)

    # Converte a saída interna para JSON em UTF-8.
    conteudo = _json_workflow_para_teste(resultado)
    esperado = json.loads(conteudo)

    storage, cliente, objetos = oci_workflow_simulado

    # Caminho exclusivo do teste em memória.
    nome = f"testes-workflow/{cenario}/resultado.json"

    # Usa o conector real com o cliente OCI simulado.
    confirmacao = storage.enviar_bytes(
        nome,
        conteudo,
        "application/json; charset=utf-8",
    )

    baixado = storage.ler_bytes(nome)
    recuperado = json.loads(baixado)

    assert confirmacao["status_backup"] == "sucesso"
    assert confirmacao["caminho_objeto"] == nome

    # Compara os bytes e todos os campos do JSON.
    assert objetos[nome] == conteudo == baixado
    assert recuperado == esperado

    assert (
        recuperado["decisao"]["destinos"]
        == destinos_esperados
    )
    assert (
        recuperado["decisao"]["requer_auditoria_humana"]
        is revisao_esperada
    )
    assert (
        recuperado["decisao"]["etapa"]
        == "DECISAO_CALCULADA"
    )

    # O armazenamento não deve alterar a saída do agente.
    assert _json_workflow_para_teste(resultado) == conteudo

    if cenario == "conflito_baixo":
        assert (
            recuperado["qualidade"]["conflitos"][0]["gravidade"]
            == "BAIXA"
        )

    argumentos = cliente.put_object.call_args.kwargs

    assert (
        argumentos["content_type"]
        == "application/json; charset=utf-8"
    )
    assert argumentos["content_length"] == len(conteudo)
    assert argumentos["if_none_match"] == "*"

    cliente.put_object.assert_called_once()
    cliente.get_object.assert_called_once()


@pytest.mark.parametrize(
    "falha",
    [403, 412, 503, "timeout"],
)
def test_workflow_falha_oci_preserva_decisao(
    montar_entrada,
    oci_workflow_simulado,
    falha,
):
    # Envolve o grafo real para contar suas execuções.
    grafo = Mock(wraps=criar_grafo())

    entrada = montar_entrada(
        prioridade=NivelPrioridade.URGENTE,
        urgencia="SIM",
        incertos=["paciente.nome"],
    )

    # A decisão é calculada antes da tentativa de gravação.
    resultado = grafo.invoke({"entrada": entrada})
    conteudo = _json_workflow_para_teste(resultado)

    storage, cliente, objetos = oci_workflow_simulado
    nome = "testes-workflow/falha/resultado.json"

    if falha == 412:
        # Simula objeto existente: deve impedir sobrescrita.
        objetos[nome] = b'{"anterior": true}'
        tipo_erro = oci.exceptions.ServiceError

    elif falha == "timeout":
        cliente.put_object.side_effect = TimeoutError(
            "Timeout simulado"
        )
        tipo_erro = TimeoutError

    else:
        cliente.put_object.side_effect = (
            oci.exceptions.ServiceError(
                status=falha,
                code="ErroFicticio",
                headers={},
                message="Falha simulada de armazenamento",
            )
        )
        tipo_erro = oci.exceptions.ServiceError

    confirmacao = None

    with pytest.raises(tipo_erro) as erro:
        confirmacao = storage.enviar_bytes(
            nome,
            conteudo,
            "application/json; charset=utf-8",
        )

    # A falha não pode produzir confirmação de sucesso.
    assert confirmacao is None

    if falha != "timeout":
        assert erro.value.status == falha

    # Qualidade, conflitos e decisão continuam intactos.
    assert _json_workflow_para_teste(resultado) == conteudo

    assert resultado["decisao"].destinos == [
        DestinoRoteamento.EMERGENCIA,
        DestinoRoteamento.REVISAO_HUMANA,
    ]
    assert resultado["decisao"].requer_auditoria_humana
    assert resultado["decisao"].etapa == "DECISAO_CALCULADA"

    # Neste fluxo de teste, a falha não reexecuta o agente.
    grafo.invoke.assert_called_once()
    cliente.put_object.assert_called_once()
    cliente.get_object.assert_not_called()

    if falha == 412:
        assert objetos[nome] == b'{"anterior": true}'
    else:
        assert nome not in objetos

@pytest.fixture
def servico_pr13_isolado(monkeypatch):
    """Bloqueia a criação de cliente OCI real nestas regressões."""
    from src.api.service import TriagemService

    monkeypatch.setenv("OCI_BUCKET_NAME", "mediflow-documentos")
    monkeypatch.setenv("LIMIAR_CONFIANCA", "0.85")
    monkeypatch.setenv("OCI_OBRIGATORIO", "false")

    fabrica = Mock(side_effect=RuntimeError("OCI real desativado no teste"))
    cliente_real = Mock(side_effect=AssertionError("Cliente OCI real bloqueado"))
    monkeypatch.setattr(OCIStorage, "das_configuracoes", fabrica)
    monkeypatch.setattr(oci.object_storage, "ObjectStorageClient", cliente_real)

    yield TriagemService

    cliente_real.assert_not_called()


def _texto_ficticio_regressao_pr13():
    return (
        "Laudo de Exame de Imagem\n"
        "Paciente: Paciente Fictício\n"
        "Idade: 40\n"
        "Médico: Profissional Fictício\n"
        "CRM/SP: 000000\n"
        "Diagnóstico: Conclusão fictícia explícita"
    )


def test_pr13_sem_conector_nao_confirma_persistencia(
    servico_pr13_isolado, oci_workflow_simulado, monkeypatch
):
    storage, cliente, _ = oci_workflow_simulado
    cliente.put_object.side_effect = oci.exceptions.ServiceError(
        status=503, code="Unavailable", headers={}, message="Falha simulada"
    )
    servico = servico_pr13_isolado(storage=storage)
    documento_id = servico.submeter_texto(_texto_ficticio_regressao_pr13())
    inicial = servico.executar_triagem(documento_id)
    assert inicial.status.value == "ERRO_PERSISTENCIA"
    qualidade_antes = inicial.qualidade.model_dump(mode="json")
    decisao_antes = inicial.decisao_roteamento.model_dump(mode="json")

    # Na tentativa seguinte, o conector fica indisponível.
    monkeypatch.setattr(servico, "_storage", None)
    try:
        final = servico.reprocessar_persistencia_oci(documento_id)
    except (RuntimeError, oci.exceptions.ServiceError):
        final = servico.obter_triagem(documento_id)

    assert final.status.value == "ERRO_PERSISTENCIA", (
        "Sem conector real, a retentativa não pode confirmar persistência. "
        f"Recebido: {final.status.value}, "
        f"backup={final.armazenamento_oci.status_backup}"
    )
    assert final.armazenamento_oci.status_backup != "sucesso"
    assert final.erro is not None
    assert final.qualidade.model_dump(mode="json") == qualidade_antes
    assert final.decisao_roteamento.model_dump(mode="json") == decisao_antes


def test_pr13_retry_json_preserva_original_existente(
    servico_pr13_isolado, oci_workflow_simulado
):
    storage, cliente, objetos = oci_workflow_simulado
    enviar_normal = cliente.put_object.side_effect
    pendente = {"falhar_json": True}

    def enviar_com_falha_unica(**argumentos):
        nome = argumentos["object_name"]
        if nome.endswith(".json") and pendente["falhar_json"]:
            pendente["falhar_json"] = False
            raise oci.exceptions.ServiceError(
                status=503, code="Unavailable", headers={},
                message="Falha única no JSON; original já foi salvo",
            )
        return enviar_normal(**argumentos)

    cliente.put_object.side_effect = enviar_com_falha_unica
    servico = servico_pr13_isolado(storage=storage)
    servico._grafo = Mock(wraps=servico._grafo)
    documento_id = servico.submeter_texto(_texto_ficticio_regressao_pr13())
    inicial = servico.executar_triagem(documento_id)
    assert inicial.status.value == "ERRO_PERSISTENCIA"

    caminho_original = f"recebidos/{documento_id}/original.txt"
    assert caminho_original in objetos
    original_antes = objetos[caminho_original]
    qualidade_antes = inicial.qualidade.model_dump(mode="json")
    decisao_antes = inicial.decisao_roteamento.model_dump(mode="json")
    execucoes_antes = servico._grafo.invoke.call_count

    try:
        final = servico.reprocessar_persistencia_oci(documento_id)
    except oci.exceptions.ServiceError as erro:
        pytest.fail(
            "A recuperação deveria salvar o JSON pendente sem bloquear "
            f"no original existente. Recebido HTTP {erro.status}: {erro.code}"
        )

    assert final.status.value in {"PROCESSADO", "EM_REVISAO"}
    assert final.armazenamento_oci.status_backup == "sucesso"
    assert final.erro is None
    assert objetos[caminho_original] == original_antes
    caminho_json = final.armazenamento_oci.caminho_objeto
    assert caminho_json in objetos
    assert json.loads(objetos[caminho_json])["documento_id"] == documento_id
    assert final.qualidade.model_dump(mode="json") == qualidade_antes
    assert final.decisao_roteamento.model_dump(mode="json") == decisao_antes
    assert servico._grafo.invoke.call_count == execucoes_antes


def test_pr13_retry_json_com_original_divergente_rejeita_recuperacao(
    servico_pr13_isolado, oci_workflow_simulado
):
    """
    Valida a conferência de integridade antes de ignorar o HTTP 412:
    Se o objeto já existente no bucket tiver conteúdo divergente do documento atual,
    a recuperação DEVE abortar com erro de integridade e NÃO salvar o resultado.json.
    """
    from src.schemas import StatusTriagem
    storage, cliente, objetos = oci_workflow_simulado
    servico = servico_pr13_isolado(storage=storage)

    # 1. Submete o documento clínico
    documento_id = servico.submeter_texto(_texto_ficticio_regressao_pr13())
    caminho_original = f"recebidos/{documento_id}/original.txt"

    # 2. Simula colisão no OCI: objeto já existe lá, mas com conteúdo divergente!
    objetos[caminho_original] = b"CONTEUDO_DIVERGENTE_DE_OUTRO_PACIENTE_12345"

    # Marca inicialmente em ERRO_PERSISTENCIA para permitir retry
    servico._status_em_andamento[documento_id] = StatusTriagem.ERRO_PERSISTENCIA
    inicial = servico.executar_triagem(documento_id)
    assert inicial.status.value == "ERRO_PERSISTENCIA"

    # 3. Dispara retentativa de persistência
    with pytest.raises(RuntimeError) as exc_info:
        servico.reprocessar_persistencia_oci(documento_id)

    assert "Conflito de integridade OCI" in str(exc_info.value)
    assert "conteúdo divergente" in str(exc_info.value)

    # 4. Confirma que o JSON NÃO foi gravado e o estado não confirmou sucesso
    caminho_json = f"processados/{documento_id}/resultado.json"
    caminho_json_urgente = f"processados/urgentes/{documento_id}/resultado.json"
    assert caminho_json not in objetos
    assert caminho_json_urgente not in objetos

    final = servico.obter_triagem(documento_id)
    assert final.status.value == "ERRO_PERSISTENCIA" 


def test_pr13_resposta_preserva_justificativa_do_workflow(
    servico_pr13_isolado, oci_workflow_simulado, montar_entrada
):
    storage, _, _ = oci_workflow_simulado
    servico = servico_pr13_isolado(storage=storage)
    documento_id = servico.submeter_texto(_texto_ficticio_regressao_pr13())
    entrada = montar_entrada(
        documento_id=documento_id,
        conflitos=[ConflitoWorkflow(
            tipo="OBS_TESTE", gravidade="BAIXA",
            descricao="Observação fictícia para preservar",
        )],
    )
    saida = criar_grafo().invoke({"entrada": entrada})
    qualidade_esperada = saida["qualidade"].model_dump(mode="json")
    decisao_esperada = saida["decisao"].model_dump(mode="json")
    servico._grafo = Mock()
    servico._grafo.invoke.return_value = saida

    final = servico.executar_triagem(documento_id)

    assert final.qualidade.score_extracao == qualidade_esperada["score_extracao"]
    assert final.qualidade.score_combinado == qualidade_esperada["score_combinado"]
    assert [c.model_dump(mode="json") for c in final.qualidade.conflitos] == qualidade_esperada["conflitos"]
    assert [d.value for d in final.decisao_roteamento.destinos] == decisao_esperada["destinos"]
    assert final.decisao_roteamento.requer_auditoria_humana == decisao_esperada["requer_auditoria_humana"]
    assert final.decisao_roteamento.justificativa_roteamento == decisao_esperada["justificativa"], (
        "A resposta final substituiu a justificativa calculada pelo workflow."
    )
