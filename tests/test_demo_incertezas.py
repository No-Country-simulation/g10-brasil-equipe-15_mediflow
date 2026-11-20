from copy import deepcopy

import pytest

from src.services.gemini_service import normalizar_payload_extracao


@pytest.mark.parametrize("alias", ["dosagem_nitroprussiato_de_sodio", "dose_Nitroprussiato de sódio"])
def test_alias_de_dose_identifica_somente_o_medicamento_correspondente(alias):
    payload = {
        "medicamentos": [
            {"nome": "Outro medicamento", "dosagem": "10 mg"},
            {"nome": "Nitroprussiato de sódio", "dosagem": None},
        ],
        "campos_incertos": [alias, "paciente.idade"],
    }
    original = deepcopy(payload)
    saida = normalizar_payload_extracao(payload)
    assert saida["campos_incertos"] == ["medicamentos[1].dosagem", "paciente.idade"]
    assert saida["medicamentos"] == payload["medicamentos"]
    assert payload == original


def test_alias_ambiguo_ou_desconhecido_nao_e_atribuido_a_uma_dose():
    payload = {
        "medicamentos": [{"nome": "Dipirona"}, {"nome": "Dipirona"}],
        "campos_incertos": ["dosagem_dipirona", "dose_outro", "medicamentos[1].dosagem"],
    }
    assert normalizar_payload_extracao(payload)["campos_incertos"] == payload["campos_incertos"]
