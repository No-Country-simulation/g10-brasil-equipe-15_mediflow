"""Regressões de persistência: sem Gemini e sem bucket real."""

import socket
from types import SimpleNamespace
from unittest.mock import Mock

import oci
import pytest


@pytest.fixture
def ambiente_isolado(monkeypatch):
    def bloquear_rede(*args, **kwargs):
        raise AssertionError("Rede bloqueada nestes testes")

    monkeypatch.setattr(
        socket.socket, "connect", bloquear_rede
    )
    monkeypatch.setattr(
        socket.socket, "connect_ex", bloquear_rede
    )
    monkeypatch.setenv("OCI_OBRIGATORIO", "true")
    monkeypatch.setenv(
        "OCI_BUCKET_NAME", "mediflow-documentos"
    )
    monkeypatch.setenv("LIMIAR_CONFIANCA", "0.85")

    from src.storage.oci_storage import OCIStorage

    cliente_real = Mock(
        side_effect=AssertionError(
            "Cliente OCI real bloqueado"
        )
    )
    fabrica_real = Mock(
        side_effect=AssertionError(
            "Configuração OCI real bloqueada"
        )
    )

    monkeypatch.setattr(
        oci.object_storage,
        "ObjectStorageClient",
        cliente_real,
    )
    monkeypatch.setattr(
        OCIStorage,
        "das_configuracoes",
        fabrica_real,
    )

    from src.api.service import TriagemService

    yield TriagemService, OCIStorage

    cliente_real.assert_not_called()
    fabrica_real.assert_not_called()


@pytest.fixture
def armazenamento_em_memoria(ambiente_isolado):
    _, OCIStorage = ambiente_isolado
    objetos = {}
    cliente = Mock()

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
                message="Objeto fictício já existente",
            )

        objetos[nome] = argumentos["put_object_body"]

        return SimpleNamespace(
            status=200,
            headers={"etag": "etag-ficticio"},
        )

    def ler(**argumentos):
        corpo = Mock()
        corpo.content = objetos[
            argumentos["object_name"]
        ]
        return SimpleNamespace(data=corpo)

    cliente.put_object.side_effect = enviar
    cliente.get_object.side_effect = ler

    storage = OCIStorage(
        cliente,
        "namespace-ficticio",
        "mediflow-documentos",
    )

    return storage, cliente, objetos


def texto_ficticio():
    return (
        "Laudo de Exame de Imagem\n"
        "Paciente: Pessoa Ficticia\n"
        "Idade: 30\n"
        "Medico: Profissional Ficticio\n"
        "CRM/SP: 12345\n"
        "Diagnostico: Conclusao ficticia"
    )


def tentar_novamente(servico, documento_id):
    # A falha pode ser sinalizada por exceção
    # ou pelo estado retornado pelo serviço.
    try:
        return servico.reprocessar_persistencia_oci(
            documento_id
        )
    except (
        RuntimeError,
        ValueError,
        oci.exceptions.ServiceError,
    ):
        return servico.obter_triagem(documento_id)


def test_pr13_nome_simulacao_nao_confirma_gravacao_real(
    ambiente_isolado,
):
    TriagemService, _ = ambiente_isolado
    servico = TriagemService()

    # Nenhum conector está disponível.
    servico._obter_storage = Mock(return_value=None)

    documento_id = servico.submeter_texto(
        texto_ficticio(),
        metadados={
            "nome_arquivo": "simulacao_exame.txt"
        },
    )

    inicial = servico.executar_triagem(documento_id)

    assert inicial.status.value == "ERRO_PERSISTENCIA"

    final = tentar_novamente(
        servico,
        documento_id,
    )

    assert final is not None

    assert (
        final.armazenamento_oci.status_backup
        != "sucesso"
    ), (
        "O nome do arquivo acionou sucesso "
        "sem conector nem gravação real."
    )

    assert final.status.value == "ERRO_PERSISTENCIA"
    assert final.erro is not None


def test_pr13_412_com_original_diferente_nao_salva_resultado(
    ambiente_isolado,
    armazenamento_em_memoria,
):
    TriagemService, _ = ambiente_isolado
    storage, cliente, objetos = (
        armazenamento_em_memoria
    )

    servico = TriagemService(storage=storage)

    documento_id = servico.submeter_texto(
        texto_ficticio()
    )

    caminho_original = (
        f"recebidos/{documento_id}/original.txt"
    )

    # Já existe um documento diferente nesse caminho.
    original_divergente = (
        b"OUTRO DOCUMENTO FICTICIO"
    )
    objetos[caminho_original] = original_divergente

    inicial = servico.executar_triagem(documento_id)

    assert inicial.status.value == "ERRO_PERSISTENCIA"

    assert objetos[caminho_original] != (
        texto_ficticio().encode("utf-8")
    )

    qualidade_antes = inicial.qualidade.model_dump(
        mode="json"
    )
    decisao_antes = (
        inicial.decisao_roteamento.model_dump(
            mode="json"
        )
    )

    final = tentar_novamente(
        servico,
        documento_id,
    )

    assert final is not None

    assert (
        final.armazenamento_oci.status_backup
        != "sucesso"
    ), (
        "A retentativa confirmou sucesso "
        "apesar do original divergente."
    )

    assert final.status.value == "ERRO_PERSISTENCIA"
    assert final.erro is not None

    # O original deve permanecer intacto.
    # Nenhum JSON novo deve ser associado a ele.
    assert objetos == {
        caminho_original: original_divergente
    }, (
        "Não deve gravar o resultado nem alterar "
        "o original divergente."
    )

    assert all(
        not chamada.kwargs["object_name"].endswith(
            ".json"
        )
        for chamada in (
            cliente.put_object.call_args_list
        )
    )

    assert final.qualidade.model_dump(
        mode="json"
    ) == qualidade_antes

    assert final.decisao_roteamento.model_dump(
        mode="json"
    ) == decisao_antes

