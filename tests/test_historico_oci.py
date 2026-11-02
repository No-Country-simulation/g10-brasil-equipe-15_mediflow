"""Testes do histórico OCI com armazenamento somente em memória."""

import json

import pytest

from src.api.service import TriagemService
from src.schemas import StatusTriagem


class StorageEmMemoria:
    """Simula o conector sem SDK, credenciais ou acesso à rede."""

    def __init__(self):
        self.objetos = {}
        self.tentativas = []
        self.falhar_historico = False
        self.sem_confirmacao = False

    def enviar_bytes(
        self,
        caminho,
        conteudo,
        tipo_conteudo="application/octet-stream",
    ):
        self.tentativas.append(caminho)

        if caminho.startswith("historico/"):
            if self.falhar_historico:
                raise TimeoutError(
                    "Falha simulada na gravação do histórico."
                )

            if self.sem_confirmacao:
                return None

        if caminho in self.objetos:
            raise AssertionError(
                "O teste detectou tentativa de sobrescrita."
            )

        self.objetos[caminho] = bytes(conteudo)

        return {
            "bucket": "mediflow-documentos",
            "caminho_objeto": caminho,
            "status_backup": "sucesso",
        }

    def ler_bytes(self, caminho):
        return self.objetos[caminho]


@pytest.fixture
def preparar(monkeypatch):
    """Configura o serviço com um conector fictício."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("OCI_OBRIGATORIO", "true")
    monkeypatch.setenv("OCI_SIMULACAO_HABILITADA", "false")
    monkeypatch.setenv(
        "OCI_BUCKET_NAME",
        "mediflow-documentos",
    )
    monkeypatch.setenv("LIMIAR_CONFIANCA", "0.85")

    from src.storage.oci_storage import OCIStorage

    def proibir_conector_real(*args, **kwargs):
        raise AssertionError(
            "Conector real proibido neste teste."
        )

    monkeypatch.setattr(
        OCIStorage,
        "das_configuracoes",
        proibir_conector_real,
    )

    storage = StorageEmMemoria()
    service = TriagemService(storage=storage)

    documento_id = service.submeter_texto(
        texto=(
            "LAUDO DE RADIOGRAFIA\n"
            "Paciente: Pessoa Fictícia\n"
            "Idade: 42\n"
            "Médico: Profissional Fictício\n"
            "CRM/SP: 123456\n"
            "Diagnóstico: Exame sem alterações.\n"
        ),
        documento_id="DOC-TESTE-HISTORICO",
    )

    return service, storage, documento_id


def test_grava_original_resultado_e_historico(preparar):
    service, storage, documento_id = preparar

    triagem = service.executar_triagem(documento_id)

    assert triagem.status != StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.armazenamento_oci.status_backup == "sucesso"

    assert any(
        caminho.startswith(f"recebidos/{documento_id}/")
        for caminho in storage.objetos
    )
    assert any(
        caminho.endswith("/resultado.json")
        for caminho in storage.objetos
    )

    referencia = service.obter_referencia_historico_oci(
        documento_id
    )

    assert referencia is not None
    assert referencia.startswith(
        f"historico/{documento_id}/"
    )

    payload = json.loads(
        storage.objetos[referencia].decode("utf-8")
    )

    assert payload["documento_id"] == documento_id
    assert payload["versao_esquema"] == "2.0.0"

    assert payload["eventos"] == [
        evento.model_dump(mode="json")
        for evento in service.obter_historico(documento_id)
    ]

    tipos = [
        evento["tipo_evento"]
        for evento in payload["eventos"]
    ]

    assert tipos[0:2] == ["RECEBIDO", "PROCESSANDO"]
    assert "ROTEADO" in tipos


def test_sem_eventos_novos_nao_grava_outro_snapshot(preparar):
    service, storage, documento_id = preparar

    service.executar_triagem(documento_id)

    quantidade_anterior = len(storage.tentativas)
    referencia_anterior = (
        service.obter_referencia_historico_oci(documento_id)
    )

    referencia = service.persistir_historico_oci(
        documento_id
    )

    assert referencia == referencia_anterior
    assert len(storage.tentativas) == quantidade_anterior


def test_evento_novo_cria_snapshot_sem_sobrescrever(preparar):
    service, storage, documento_id = preparar

    service.executar_triagem(documento_id)

    referencia_anterior = (
        service.obter_referencia_historico_oci(documento_id)
    )
    bytes_anteriores = storage.objetos[referencia_anterior]

    service.registrar_evento(
        documento_id=documento_id,
        tipo_evento="CONSULTA_TESTE",
        status_novo=service.obter_status(documento_id),
        ator="TESTE",
        motivo="Evento fictício adicional.",
    )

    nova_referencia = service.persistir_historico_oci(
        documento_id
    )

    assert nova_referencia != referencia_anterior
    assert (
        storage.objetos[referencia_anterior]
        == bytes_anteriores
    )

    anterior = json.loads(bytes_anteriores)
    atual = json.loads(
        storage.objetos[nova_referencia]
    )

    assert len(atual["eventos"]) == (
        len(anterior["eventos"]) + 1
    )
    assert atual["eventos"][:-1] == anterior["eventos"]
    assert (
        atual["eventos"][-1]["tipo_evento"]
        == "CONSULTA_TESTE"
    )


def test_falha_historico_preserva_decisao_e_recupera_sem_reenvio(
    preparar,
    monkeypatch,
):
    service, storage, documento_id = preparar
    storage.falhar_historico = True

    triagem = service.executar_triagem(documento_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.armazenamento_oci.status_backup == "falha"
    assert (
        service.obter_referencia_historico_oci(documento_id)
        is None
    )

    decisao_anterior = (
        triagem.decisao_roteamento.model_dump(mode="json")
    )
    qualidade_anterior = triagem.qualidade.model_dump(
        mode="json"
    )

    documentos_antes = {
        caminho: conteudo
        for caminho, conteudo in storage.objetos.items()
        if not caminho.startswith("historico/")
    }

    # Confirma que original e resultado foram preservados
    # antes de testar a recuperação exclusiva do histórico.
    assert any(
        caminho.startswith("recebidos/")
        for caminho in documentos_antes
    )
    assert any(
        caminho.endswith("/resultado.json")
        for caminho in documentos_antes
    )

    tentativas_antes = len(storage.tentativas)

    def proibir_reanalise(*args, **kwargs):
        raise AssertionError(
            "A recuperação não pode repetir a análise "
            "ou o fluxo de gravação dos documentos."
        )

    monkeypatch.setattr(
        service,
        "_executar_triagem_existente",
        proibir_reanalise,
    )
    monkeypatch.setattr(
        service,
        "_reprocessar_persistencia_existente",
        proibir_reanalise,
    )

    storage.falhar_historico = False

    recuperada = service.reprocessar_persistencia_oci(
        documento_id
    )

    assert (
        recuperada.status
        != StatusTriagem.ERRO_PERSISTENCIA
    )
    assert (
        recuperada.armazenamento_oci.status_backup
        == "sucesso"
    )
    assert recuperada.erro is None

    assert (
        recuperada.decisao_roteamento.model_dump(mode="json")
        == decisao_anterior
    )
    assert (
        recuperada.qualidade.model_dump(mode="json")
        == qualidade_anterior
    )

    novas_tentativas = storage.tentativas[
        tentativas_antes:
    ]

    assert novas_tentativas
    assert all(
        caminho.startswith("historico/")
        for caminho in novas_tentativas
    )

    for caminho, conteudo in documentos_antes.items():
        assert storage.objetos[caminho] == conteudo

    referencia = service.obter_referencia_historico_oci(
        documento_id
    )
    assert referencia is not None

    eventos = json.loads(
        storage.objetos[referencia]
    )["eventos"]

    tipos = [
        evento["tipo_evento"]
        for evento in eventos
    ]

    assert "HISTORICO_PERSISTENCIA_FALHA" in tipos
    assert (
        tipos[-1]
        == "HISTORICO_PERSISTENCIA_RECUPERADA"
    )


def test_nova_falha_mantem_erro_sem_recuperacao_falsa(
    preparar,
):
    service, storage, documento_id = preparar
    storage.falhar_historico = True

    service.executar_triagem(documento_id)

    with pytest.raises(
        RuntimeError,
        match="continua pendente",
    ):
        service.reprocessar_persistencia_oci(
            documento_id
        )

    assert (
        service.obter_status(documento_id)
        == StatusTriagem.ERRO_PERSISTENCIA
    )
    assert (
        service.obter_triagem(documento_id).status
        == StatusTriagem.ERRO_PERSISTENCIA
    )
    assert (
        service.obter_referencia_historico_oci(documento_id)
        is None
    )

    assert not any(
        evento.tipo_evento
        == "HISTORICO_PERSISTENCIA_RECUPERADA"
        for evento in service.obter_historico(documento_id)
    )


def test_retorno_sem_confirmacao_nao_vira_sucesso(preparar):
    service, storage, documento_id = preparar
    storage.sem_confirmacao = True

    triagem = service.executar_triagem(documento_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.armazenamento_oci.status_backup == "falha"
    assert (
        service.obter_referencia_historico_oci(documento_id)
        is None
    )
    assert not any(
        caminho.startswith("historico/")
        for caminho in storage.objetos
    )