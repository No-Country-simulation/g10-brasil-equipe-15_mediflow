"""
Grafo inicial de qualidade e roteamento.

Recebe sinais estruturados.
Não chama Gemini, não persiste na OCI e não envia alertas externos.
"""

import unicodedata

from langgraph.graph import END, START, StateGraph

from src.schemas import DestinoRoteamento, NivelPrioridade

from .state import (
    DecisaoWorkflow,
    EntradaWorkflow,
    EstadoWorkflow,
    QualidadeWorkflow,
)

def normalizar_tipo(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor)

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = texto.replace("_", " ").replace("/", " ")

    return " ".join(texto.upper().split())


# Compatibilidade temporária com códigos e rótulos existentes.
# Confirmar e centralizar os valores com o backend.
DESTINOS_ROTINA = {
    "RECEITUARIO MEDICO": DestinoRoteamento.FARMACIA,
    "GUIA PROCEDIMENTO": DestinoRoteamento.AUDITORIA,
    "GUIA DE SOLICITACAO DE PROCEDIMENTO": DestinoRoteamento.AUDITORIA,
    "LAUDO EXAME IMAGEM": DestinoRoteamento.PRONTUARIO,
    "LAUDO DE EXAME DE IMAGEM": DestinoRoteamento.PRONTUARIO,
    "LAUDO EXAME LABORATORIAL": DestinoRoteamento.PRONTUARIO,
    "LAUDO DE EXAME LABORATORIAL": DestinoRoteamento.PRONTUARIO,
    "LAUDO LABORATORIAL": DestinoRoteamento.PRONTUARIO,
    "RELATORIO ALTA INTERNACAO": DestinoRoteamento.PRONTUARIO,
    "RELATORIO DE ALTA INTERNACAO": DestinoRoteamento.PRONTUARIO,
    "ATESTADO MEDICO": DestinoRoteamento.PRONTUARIO,
}


def obter_destino_rotina(
    entrada: EntradaWorkflow,
) -> DestinoRoteamento | None:
    tipo = normalizar_tipo(
        entrada.classificacao.tipo_documento
    )

    return DESTINOS_ROTINA.get(tipo)


def vazio(valor) -> bool:
    return valor is None or (
        isinstance(valor, str) and not valor.strip()
    )


def tem_urgencia(entrada: EntradaWorkflow) -> bool:
    return (
        entrada.urgencia == "SIM"
        or entrada.classificacao.nivel_prioridade
        == NivelPrioridade.URGENTE
    )


def avaliar_qualidade(estado: EstadoWorkflow) -> dict:
    entrada = estado["entrada"]
    dados = entrada.dados_extraidos

    obrigatorios = {
        "paciente.nome": dados.paciente.nome,
        "paciente.idade": dados.paciente.idade,
        "medico_solicitante.nome": dados.medico_solicitante.nome,
        "medico_solicitante.crm": dados.medico_solicitante.crm,
        "diagnostico_principal": dados.diagnostico_principal,
    }

    ausentes = [
        campo
        for campo, valor in obrigatorios.items()
        if vazio(valor)
    ]

    incertos = set(entrada.campos_incertos)

    # Compatibilidade temporária:
    # o contrato local usa AMBIGUO em vez de NAO_IDENTIFICADA.
    prioridade_indeterminada = (
        entrada.classificacao.nivel_prioridade
        == NivelPrioridade.AMBIGUO
    )

    if prioridade_indeterminada:
        incertos.add("classificacao.nivel_prioridade")

    if entrada.urgencia == "INDETERMINADO":
        incertos.add("urgencia")

    # Evita penalizar novamente um conflito exatamente repetido.
    # Conflitos com descrições diferentes continuam distintos.
    conflitos_unicos = {}

    for conflito in entrada.conflitos:
        campos = tuple(
            sorted(
                {
                    campo.strip()
                    for campo in conflito.campos
                    if campo.strip()
                }
            )
        )

        chave = (
            conflito.tipo.strip().upper(),
            conflito.gravidade,
            campos,
            conflito.descricao.strip(),
        )

        conflitos_unicos[chave] = conflito

    penalidades = {
        "ALTA": 0.30,
        "MEDIA": 0.20,
        "BAIXA": 0.10,
    }

    desconto_conflitos = sum(
        penalidades[conflito.gravidade]
        for conflito in conflitos_unicos.values()
    )

    score_extracao = max(
        0.0,
        min(
            1.0,
            1.0
            - 0.20 * len(ausentes)
            - 0.10 * len(incertos)
            - desconto_conflitos,
        ),
    )

    # Evita resíduos numéricos como 0.7999999999999999.
    score_extracao = round(score_extracao, 10)

    score_classificacao = (
        entrada.classificacao.score_confianca_classificacao
    )

    score_combinado = min(
        score_classificacao,
        score_extracao,
    )

    motivos = []

    if ausentes:
        motivos.append(
            "Campos obrigatórios ausentes: "
            + ", ".join(ausentes)
        )

    if incertos:
        motivos.append(
            "Campos ou sinais incertos: "
            + ", ".join(sorted(incertos))
        )

    impeditivos = [
        conflito.tipo
        for conflito in conflitos_unicos.values()
        if conflito.gravidade in {"ALTA", "MEDIA"}
    ]

    if impeditivos:
        motivos.append(
            "Conflitos impeditivos: "
            + ", ".join(impeditivos)
        )

    # Preserva urgência e exige revisão quando os sinais divergem.
    # Este comportamento deve ser registrado com a equipe.
    if (
        entrada.urgencia == "NAO"
        and entrada.classificacao.nivel_prioridade
        == NivelPrioridade.URGENTE
    ):
        motivos.append(
            "Sinais contraditórios: prioridade urgente "
            "com urgência marcada como NAO."
        )

    if score_combinado < entrada.limiar:
        motivos.append(
            "Score combinado abaixo do limiar configurado."
        )

    tipo = normalizar_tipo(
        entrada.classificacao.tipo_documento
    )

    if tipo in {"OUTRO", "NAO IDENTIFICADO"}:
        motivos.append(
            "Tipo documental exige revisão humana."
        )
    elif obter_destino_rotina(entrada) is None:
        motivos.append(
            "Tipo documental sem mapeamento conhecido."
        )

    qualidade = QualidadeWorkflow(
        campos_ausentes=ausentes,
        campos_incertos=sorted(incertos),
        score_classificacao=score_classificacao,
        score_extracao=score_extracao,
        score_combinado=score_combinado,
        limiar_aplicado=entrada.limiar,
        motivos_revisao=motivos,
    )

    return {"qualidade": qualidade}


def escolher_caminho(estado: EstadoWorkflow) -> str:
    entrada = estado["entrada"]

    # Necessidade de revisão não impede encaminhamento urgente.
    if tem_urgencia(entrada):
        return "urgencia"

    if estado["qualidade"].motivos_revisao:
        return "revisao"

    return "rotina"


def decidir_urgencia(estado: EstadoWorkflow) -> dict:
    motivos = estado["qualidade"].motivos_revisao
    requer_revisao = bool(motivos)

    destinos = [DestinoRoteamento.EMERGENCIA]

    if requer_revisao:
        destinos.append(
            DestinoRoteamento.REVISAO_HUMANA
        )

    justificativa = (
        "Sinal estruturado de urgência identificado."
    )

    if requer_revisao:
        justificativa += (
            " Revisão simultânea: "
            + "; ".join(motivos)
        )

    return {
        "decisao": DecisaoWorkflow(
            destinos=destinos,
            requer_auditoria_humana=requer_revisao,
            justificativa=justificativa,
            regras_acionadas=(
                ["URGENCIA", "REVISAO"]
                if requer_revisao
                else ["URGENCIA"]
            ),
            alerta_simulado=True,
        )
    }


def decidir_revisao(estado: EstadoWorkflow) -> dict:
    return {
        "decisao": DecisaoWorkflow(
            destinos=[
                DestinoRoteamento.REVISAO_HUMANA
            ],
            requer_auditoria_humana=True,
            justificativa="; ".join(
                estado["qualidade"].motivos_revisao
            ),
            regras_acionadas=["REVISAO"],
            alerta_simulado=False,
        )
    }


def decidir_rotina(estado: EstadoWorkflow) -> dict:
    destino = obter_destino_rotina(
        estado["entrada"]
    )

    if destino is None:
        raise ValueError(
            "Destino de rotina não mapeado."
        )

    return {
        "decisao": DecisaoWorkflow(
            destinos=[destino],
            requer_auditoria_humana=False,
            justificativa=(
                "Documento de rotina sem impedimentos "
                "para encaminhamento."
            ),
            regras_acionadas=["ROTINA"],
            alerta_simulado=False,
        )
    }


def criar_grafo():
    grafo = StateGraph(EstadoWorkflow)

    grafo.add_node(
        "qualidade",
        avaliar_qualidade,
    )
    grafo.add_node(
        "urgencia",
        decidir_urgencia,
    )
    grafo.add_node(
        "revisao",
        decidir_revisao,
    )
    grafo.add_node(
        "rotina",
        decidir_rotina,
    )

    grafo.add_edge(START, "qualidade")

    grafo.add_conditional_edges(
        "qualidade",
        escolher_caminho,
        {
            "urgencia": "urgencia",
            "revisao": "revisao",
            "rotina": "rotina",
        },
    )

    for nome in ("urgencia", "revisao", "rotina"):
        grafo.add_edge(nome, END)

    return grafo.compile()