"""Testes locais: nao acessam OCI, credenciais nem Gemini."""
from types import SimpleNamespace
from unittest.mock import Mock

import oci
import pytest

from src.storage.oci_storage import OCIStorage


@pytest.fixture
def storage():
    return OCIStorage(Mock(), "namespace-ficticio", "mediflow-documentos")


def test_envio_impede_sobrescrita_e_confirma_retorno(storage):
    storage.cliente.put_object.return_value = SimpleNamespace(
        status=200, headers={"etag": "etag-ficticio"}
    )
    resultado = storage.enviar_bytes("recebidos/teste.txt", b"ficticio", "text/plain")
    argumentos = storage.cliente.put_object.call_args.kwargs
    assert argumentos["if_none_match"] == "*"
    assert argumentos["bucket_name"] == "mediflow-documentos"
    assert argumentos["put_object_body"] == b"ficticio"
    assert resultado["status_backup"] == "sucesso"
    assert resultado["caminho_objeto"] == "recebidos/teste.txt"


def test_leitura_preserva_bytes_e_fecha_resposta(storage):
    corpo = Mock()
    corpo.content = b"conteudo ficticio"
    storage.cliente.get_object.return_value = SimpleNamespace(data=corpo)
    assert storage.ler_bytes("recebidos/teste.txt") == b"conteudo ficticio"
    corpo.close.assert_called_once()


def test_listagem_consulta_todas_as_paginas(storage):
    storage.cliente.list_objects.side_effect = [
        SimpleNamespace(data=SimpleNamespace(
            objects=[SimpleNamespace(name="recebidos/a.txt")],
            next_start_with="recebidos/b.txt",
        )),
        SimpleNamespace(data=SimpleNamespace(
            objects=[SimpleNamespace(name="recebidos/b.txt")],
            next_start_with=None,
        )),
    ]
    assert storage.listar("recebidos/") == ["recebidos/a.txt", "recebidos/b.txt"]
    assert storage.cliente.list_objects.call_args.kwargs["start"] == "recebidos/b.txt"


@pytest.mark.parametrize("status", [403, 404, 412])
def test_falha_nao_vira_sucesso_nem_fallback_local(storage, status):
    storage.cliente.put_object.side_effect = oci.exceptions.ServiceError(
        status=status, code="ErroFicticio", headers={}, message="Falha simulada"
    )
    with pytest.raises(oci.exceptions.ServiceError):
        storage.enviar_bytes("recebidos/teste.txt", b"ficticio")


def test_nome_vazio_e_rejeitado_antes_do_sdk(storage):
    with pytest.raises(ValueError):
        storage.enviar_bytes("   ", b"ficticio")
    storage.cliente.put_object.assert_not_called()


def test_retorno_sem_confirmacao_nao_e_sucesso(storage):
    storage.cliente.put_object.return_value = SimpleNamespace(status=500, headers={})
    with pytest.raises(RuntimeError):
        storage.enviar_bytes("recebidos/teste.txt", b"ficticio")
