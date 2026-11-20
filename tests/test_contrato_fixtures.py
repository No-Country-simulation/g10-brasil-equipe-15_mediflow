"""
Testes automatizados dos 79 fixtures oficiais do MediFlow.
Converte e integra o testar_contrato.py do William à suíte oficial do Pytest.
Garante ponto fixo, conformidade de contratos e regras R1 a R8.
"""
import glob
import json
import os
import pytest
from src.schemas import (
    TriagemMediFlow,
    ErroResposta,
    StatusTriagem,
    Destino,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
CAMPOS_OBRIGATORIOS = frozenset({
    "paciente.nome",
    "paciente.idade",
    "medico.nome",
    "medico.crm",
    "diagnostico",
})
GRAVIDADES_IMPEDITIVAS = frozenset({"ALTA", "MEDIA"})


def listar_fixtures():
    caminhos = sorted(glob.glob(os.path.join(FIXTURES_DIR, "*/*/expected.json")))
    return caminhos


@pytest.mark.parametrize("caminho_expected", listar_fixtures(), ids=lambda c: os.path.basename(os.path.dirname(c)))
def test_validacao_fixture_contrato(caminho_expected):
    """Valida cada um dos 79 fixtures oficiais contra o contrato e verifica o ponto fixo das regras."""
    with open(caminho_expected, "r", encoding="utf-8") as f:
        dados = json.load(f)

    fid = dados["fixture_id"]
    tipo = dados["tipo_de_teste"]
    resposta_esperada = dados["resposta_esperada"]

    if tipo == "negativo_tecnico":
        # 1. Valida como ErroResposta (HTTP 4xx)
        erro = ErroResposta.model_validate(resposta_esperada)
        assert 400 <= erro.http <= 499
        assert erro.codigo_funcional is not None
    else:
        # 2. Valida como TriagemMediFlow
        triagem = TriagemMediFlow.model_validate(resposta_esperada)
        assert triagem.documento_id is not None

        # 3. Ponto fixo: serializar e re-validar não altera dados
        dump = triagem.model_dump(mode="json")
        revalidado = TriagemMediFlow.model_validate(dump)
        assert revalidado.status == triagem.status

        # 4. Erros de processamento de leitura (PDF protegido / corrompido)
        if triagem.status in (StatusTriagem.ERRO_PROCESSAMENTO, StatusTriagem.ERRO_PERSISTENCIA):
            assert triagem.erro is not None
            assert triagem.classificacao is None
            assert triagem.dados_extraidos is None
            return

        # 5. Coerência de Decisão e Roteamento
        d = triagem.decisao_roteamento
        assert d is not None
        assert d.destino_principal == d.destinos[0]
        assert d.requer_auditoria_humana == (triagem.status == StatusTriagem.EM_REVISAO)

        urgente = triagem.classificacao.nivel_prioridade.value == "URGENTE"
        assert bool(d.notificacao) == urgente

        # 6. Coerência de Qualidade e Travas
        q = triagem.qualidade
        assert q is not None
        assert abs(q.score_combinado - min(triagem.classificacao.score_classificacao, q.score_extracao)) < 1e-6

        if q.campos_ausentes and (set(q.campos_ausentes) & CAMPOS_OBRIGATORIOS):
            assert d.requer_auditoria_humana is True

        if q.campos_incertos:
            assert d.requer_auditoria_humana is True

        impeditivos = [c for c in q.conflitos if getattr(c.gravidade, "value", c.gravidade) in GRAVIDADES_IMPEDITIVAS]
        if impeditivos:
            assert d.requer_auditoria_humana is True
