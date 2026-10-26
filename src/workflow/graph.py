"""
Grafo inicial de qualidade e roteamento.

Recebe sinais estruturados.
Não chama Gemini, não persiste na OCI e não envia alertas externos.
"""

import unicodedata
import re

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

    # Converte os nomes legados apenas na fronteira do workflow.
    payload = dados.model_dump()
    medico = payload.get("medico", payload.get("medico_solicitante")) or {}
    paciente = payload.get("paciente") or {}
    diagnostico = payload.get("diagnostico", payload.get("diagnostico_principal"))
    crm = medico.get("crm")
    if isinstance(crm, str):
        partes = re.split(r"[-/]", crm.strip())
        numero = partes[0].strip()
        uf = partes[1].strip().upper() if len(partes) == 2 else None
    else:
        numero = (crm or {}).get("numero")
        uf = (crm or {}).get("uf")
        # O default SP do schema não comprova que a UF estava no documento.
        medico_modelo = getattr(dados, "medico", None)
        crm_modelo = getattr(medico_modelo, "crm", None)
        if hasattr(crm_modelo, "model_fields_set") and "uf" not in crm_modelo.model_fields_set:
            uf = None
    ufs = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
    crm_valido = (
        isinstance(numero, str) and numero.strip().isdigit()
        and isinstance(uf, str) and uf.upper() in ufs
    )
    obrigatorios = {
        "paciente.nome": paciente.get("nome"),
        "paciente.idade": paciente.get("idade"),
        "medico.nome": medico.get("nome"),
        "medico.crm": crm if crm_valido else None,
        "diagnostico": diagnostico,
    }
    aliases = {
        "medico_solicitante.nome": "medico.nome",
        "medico_solicitante.crm": "medico.crm",
        "diagnostico_principal": "diagnostico",
        "cid_sugerido": "cid", "cid_extraido": "cid",
        "exame_realizado": "exames", "exame_ou_procedimento": "exames",
    }
    def campo_canonico(campo):
        for antigo, atual in aliases.items():
            if campo == antigo or campo.startswith(antigo + ".") or campo.startswith(antigo + "["):
                return atual + campo[len(antigo):]
        return campo

    ausentes = {campo_canonico(c) for c in entrada.campos_ausentes}
    exames = payload.get("exames", payload.get("exame_realizado"))
    tem_exames = bool(exames) and (not isinstance(exames, str) or bool(exames.strip()))
    tem_exames = tem_exames or bool(payload.get("exames_laboratoriais"))
    tipo = normalizar_tipo(entrada.classificacao.tipo_documento)
    # Exceção restrita à tipologia descrita no contrato, seção 5.2.
    laboratorio_sem_diagnostico = (
        tipo in {
            "LAUDO EXAME LABORATORIAL", 
            "LAUDO DE EXAME LABORATORIAL", 
            "LAUDO LABORATORIAL"
        }
        and tem_exames and "diagnostico" not in ausentes
    )
    for campo, valor in obrigatorios.items():
        if vazio(valor) and not (campo == "diagnostico" and laboratorio_sem_diagnostico):
            ausentes.add(campo)
    # Opcionais ficam rastreáveis, sem penalidade nem bloqueio por sua ausência.
    cid = payload.get("cid", payload.get("cid_sugerido"))
    if vazio(cid):
        ausentes.add("cid")
    if not payload.get("medicamentos"):
        ausentes.add("medicamentos")
    if not tem_exames:
        ausentes.add("exames")
    obrigatorios_ausentes = sorted(ausentes & obrigatorios.keys())
    ausentes = sorted(ausentes)

    incertos = {campo_canonico(c) for c in entrada.campos_incertos}

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
                    campo_canonico(campo.strip())
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

        conflitos_unicos[chave] = conflito.model_copy(update={"campos": list(campos)})

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
            - 0.20 * len(obrigatorios_ausentes)
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

    if obrigatorios_ausentes:
        motivos.append(
            "Campos obrigatórios ausentes: "
            + ", ".join(obrigatorios_ausentes)
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

    observacoes = [
        f"Conflito BAIXA registrado: {c.tipo}: {c.descricao}"
        for c in conflitos_unicos.values() if c.gravidade == "BAIXA"
    ]
    qualidade = QualidadeWorkflow(
        conflitos=list(conflitos_unicos.values()),
        observacoes=observacoes,
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

    observacoes = estado["qualidade"].observacoes
    return {
        "decisao": DecisaoWorkflow(
            destinos=destinos,
            requer_auditoria_humana=requer_revisao,
            justificativa=justificativa + (" Observações: " + "; ".join(observacoes) if observacoes else ""),
            regras_acionadas=(
                ["URGENCIA", "REVISAO"]
                if requer_revisao
                else ["URGENCIA"]
            ),
            alerta_simulado=True,
        )
    }


def decidir_revisao(estado: EstadoWorkflow) -> dict:
    observacoes = estado["qualidade"].observacoes
    return {
        "decisao": DecisaoWorkflow(
            destinos=[
                DestinoRoteamento.REVISAO_HUMANA
            ],
            requer_auditoria_humana=True,
            justificativa="; ".join(
                estado["qualidade"].motivos_revisao + observacoes
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

    observacoes = estado["qualidade"].observacoes
    return {
        "decisao": DecisaoWorkflow(
            destinos=[destino],
            requer_auditoria_humana=False,
            justificativa=(
                "Documento de rotina sem impedimentos "
                "para encaminhamento."
                + (" Observações: " + "; ".join(observacoes) if observacoes else "")
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