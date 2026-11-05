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

@pytest.mark.parametrize(
    "etapa_falha",
    ["original", "resultado"],
)
def test_recuperacao_documentos_grava_historico_sem_reanalise(
    preparar,
    monkeypatch,
    etapa_falha,
):
    """Recupera original/resultado e persiste o histórico."""
    from types import SimpleNamespace

    service, storage, documento_id = preparar

    enviar_existente = storage.enviar_bytes
    ler_existente = storage.ler_bytes

    falha_ativa = True
    leituras = []

    class ObjetoJaExiste(Exception):
        status = 412
        code = "PreconditionFailed"

    def enviar_controlado(
        caminho,
        conteudo,
        tipo_conteudo="application/octet-stream",
    ):
        eh_original = caminho.startswith("recebidos/")
        eh_resultado = caminho.endswith("/resultado.json")

        deve_falhar = (
            etapa_falha == "original" and eh_original
        ) or (
            etapa_falha == "resultado" and eh_resultado
        )

        if falha_ativa and deve_falhar:
            storage.tentativas.append(caminho)
            raise TimeoutError(
                f"Falha simulada na etapa {etapa_falha}"
            )

        # Reproduz o bloqueio de sobrescrita do conector.
        # O serviço deve ler e comparar o original antes de avançar.
        if caminho in storage.objetos:
            storage.tentativas.append(caminho)
            raise ObjetoJaExiste(
                "Objeto já existe no armazenamento simulado."
            )

        return enviar_existente(
            caminho,
            conteudo,
            tipo_conteudo=tipo_conteudo,
        )

    def ler_controlado(caminho):
        leituras.append(caminho)
        return ler_existente(caminho)

    monkeypatch.setattr(
        storage,
        "enviar_bytes",
        enviar_controlado,
    )
    monkeypatch.setattr(
        storage,
        "ler_bytes",
        ler_controlado,
    )

    inicial = service.executar_triagem(documento_id)

    assert inicial.status == StatusTriagem.ERRO_PERSISTENCIA
    assert inicial.armazenamento_oci.status_backup != "sucesso"
    assert (
        service.obter_referencia_historico_oci(documento_id)
        is None
    )

    doc = service._documentos_originais[documento_id]
    caminho_original = (
        f"recebidos/{documento_id}/original."
        f"{doc.formato.lower()}"
    )

    if etapa_falha == "original":
        assert caminho_original not in storage.objetos
    else:
        assert (
            storage.objetos[caminho_original]
            == doc.conteudo_bytes
        )

    assert not any(
        caminho.endswith("/resultado.json")
        for caminho in storage.objetos
    )

    qualidade_antes = inicial.qualidade.model_dump(mode="json")
    decisao_antes = inicial.decisao_roteamento.model_dump(
        mode="json"
    )
    dados_antes = inicial.dados_extraidos.model_dump(mode="json")

    eventos_antes = [
        evento.model_dump(mode="json")
        for evento in service.obter_historico(documento_id)
    ]

    def proibir_grafo(*args, **kwargs):
        raise AssertionError(
            "A retentativa não pode executar o grafo novamente."
        )

    monkeypatch.setattr(
        service,
        "_grafo",
        SimpleNamespace(invoke=proibir_grafo),
    )

    # Restaura apenas o armazenamento simulado.
    falha_ativa = False

    recuperada = service.reprocessar_persistencia_oci(
        documento_id
    )

    assert recuperada.status in (
        StatusTriagem.PROCESSADO,
        StatusTriagem.EM_REVISAO,
    )
    assert recuperada.erro is None
    assert recuperada.armazenamento_oci.status_backup == "sucesso"
    assert recuperada.armazenamento_oci.modo_simulacao is False

    assert recuperada.qualidade.model_dump(
        mode="json"
    ) == qualidade_antes
    assert recuperada.decisao_roteamento.model_dump(
        mode="json"
    ) == decisao_antes
    assert recuperada.dados_extraidos.model_dump(
        mode="json"
    ) == dados_antes

    assert (
        storage.objetos[caminho_original]
        == doc.conteudo_bytes
    )

    if etapa_falha == "resultado":
        assert caminho_original in leituras

    caminho_resultado = (
        recuperada.armazenamento_oci.caminho_objeto
    )
    resultado_salvo = json.loads(
        storage.objetos[caminho_resultado]
    )

    assert resultado_salvo["documento_id"] == documento_id
    assert resultado_salvo["qualidade"] == qualidade_antes
    assert resultado_salvo["decisao_roteamento"] == decisao_antes

    caminho_historico = (
        service.obter_referencia_historico_oci(documento_id)
    )
    assert caminho_historico is not None

    historico_salvo = json.loads(
        storage.objetos[caminho_historico]
    )
    eventos_salvos = historico_salvo["eventos"]

    assert historico_salvo["documento_id"] == documento_id
    assert eventos_salvos[:len(eventos_antes)] == eventos_antes
    assert eventos_salvos == [
        evento.model_dump(mode="json")
        for evento in service.obter_historico(documento_id)
    ]
    assert (
        eventos_salvos[-1]["tipo_evento"]
        == "RETRY_PERSISTENCIA_SUCESSO"
    )


def test_erro_processamento_persiste_resultado_e_historico(
    preparar, monkeypatch
):
    service, storage, documento_id = preparar
    chamadas_grafo = []

    def falhar_grafo(entrada):
        chamadas_grafo.append(entrada)
        raise RuntimeError("Detalhe interno fictício do grafo.")

    monkeypatch.setattr(service._grafo, "invoke", falhar_grafo)

    triagem = service.executar_triagem(documento_id)

    assert triagem.status == StatusTriagem.ERRO_PROCESSAMENTO
    assert triagem.armazenamento_oci.status_backup == "sucesso"
    assert service.obter_triagem(documento_id) == triagem
    assert service.obter_status(documento_id) == StatusTriagem.ERRO_PROCESSAMENTO
    assert len(chamadas_grafo) == 1

    caminho_resultado = triagem.armazenamento_oci.caminho_objeto
    assert caminho_resultado == f"processados/{documento_id}/resultado.json"

    resultado = json.loads(storage.objetos[caminho_resultado])
    assert resultado["documento_id"] == documento_id
    assert resultado["status"] == "ERRO_PROCESSAMENTO"
    assert resultado["erro"]["codigo"] == "FALHA_WORKFLOW"
    assert "Detalhe interno fictício" not in resultado["erro"]["mensagem"]

    referencia = service.obter_referencia_historico_oci(documento_id)
    assert referencia is not None
    assert referencia.startswith(f"historico/{documento_id}/")

    historico = json.loads(storage.objetos[referencia])
    assert historico["documento_id"] == documento_id
    assert historico["eventos"] == [
        evento.model_dump(mode="json")
        for evento in service.obter_historico(documento_id)
    ]
    assert [evento["tipo_evento"] for evento in historico["eventos"]] == [
        "RECEBIDO",
        "PROCESSANDO",
        "ERRO_PROCESSAMENTO",
    ]
    assert historico["eventos"][-1]["status_novo"] == "ERRO_PROCESSAMENTO"


def test_erro_processamento_sinaliza_falha_oci(preparar, monkeypatch):
    service, storage, documento_id = preparar
    chamadas_grafo = []
    tentativas_resultado = []
    enviar_bytes_original = storage.enviar_bytes

    def falhar_grafo(entrada):
        chamadas_grafo.append(entrada)
        raise RuntimeError("Detalhe interno fictício do grafo.")

    def falhar_gravacao_resultado(
        caminho, conteudo, tipo_conteudo="application/octet-stream"
    ):
        if caminho.endswith("/resultado.json"):
            tentativas_resultado.append(caminho)
            raise TimeoutError("Falha simulada na gravação do resultado.")
        return enviar_bytes_original(caminho, conteudo, tipo_conteudo)

    monkeypatch.setattr(service._grafo, "invoke", falhar_grafo)
    monkeypatch.setattr(storage, "enviar_bytes", falhar_gravacao_resultado)

    triagem = service.executar_triagem(documento_id)

    caminho_resultado = f"processados/{documento_id}/resultado.json"
    assert tentativas_resultado == [caminho_resultado]
    assert len(chamadas_grafo) == 1
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.armazenamento_oci.status_backup == "falha"
    assert service.obter_triagem(documento_id) == triagem
    assert service.obter_status(documento_id) == StatusTriagem.ERRO_PERSISTENCIA

    assert f"recebidos/{documento_id}/original.txt" in storage.objetos
    assert caminho_resultado not in storage.objetos
    assert service.obter_referencia_historico_oci(documento_id) is None

    eventos = service.obter_historico(documento_id)
    assert any(evento.tipo_evento == "ERRO_PROCESSAMENTO" for evento in eventos)
    assert eventos[-1].status_novo == StatusTriagem.ERRO_PERSISTENCIA


@pytest.mark.parametrize(
    "cenario",
    ["identico", "divergente", "leitura_indisponivel", "erro_processamento"],
)
def test_retry_412_resultado_mesmo_documento(preparar, monkeypatch, cenario):
    service, storage, documento_id = preparar
    caminho_resultado = f"processados/{documento_id}/resultado.json"
    enviar_bytes = storage.enviar_bytes
    ler_bytes = storage.ler_bytes
    executar_grafo = service._grafo.invoke
    chamadas_grafo = []
    leituras = []

    class ObjetoJaExiste(Exception):
        status = 412
        code = "PreconditionFailed"

    def grafo_controlado(entrada):
        chamadas_grafo.append(entrada)
        if cenario == "erro_processamento":
            raise RuntimeError("Falha fictícia do grafo.")
        return executar_grafo(entrada)

    def enviar_com_timeout(caminho, conteudo, tipo_conteudo="application/octet-stream"):
        if caminho in storage.objetos:
            raise ObjetoJaExiste("Objeto já existe.")
        confirmacao = enviar_bytes(caminho, conteudo, tipo_conteudo)
        if caminho == caminho_resultado:
            raise TimeoutError("Objeto gravado, mas a confirmação se perdeu.")
        return confirmacao

    def ler_objeto(caminho):
        leituras.append(caminho)
        if caminho == caminho_resultado and cenario == "leitura_indisponivel":
            raise TimeoutError("Não foi possível ler o resultado existente.")
        return ler_bytes(caminho)

    monkeypatch.setattr(service._grafo, "invoke", grafo_controlado)
    monkeypatch.setattr(storage, "enviar_bytes", enviar_com_timeout)
    monkeypatch.setattr(storage, "ler_bytes", ler_objeto)

    primeira_triagem = service.executar_triagem(documento_id)

    assert primeira_triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert primeira_triagem.armazenamento_oci.status_backup == "falha"
    assert service.obter_referencia_historico_oci(documento_id) is None

    caminho_original = f"recebidos/{documento_id}/original.txt"
    original_antes = storage.objetos[caminho_original]
    resultado_esperado = json.loads(storage.objetos[caminho_resultado])

    if cenario == "divergente":
        storage.objetos[caminho_resultado] = b'{"documento_id": "OUTRO-DOCUMENTO"}'

    resultado_antes_do_retry = storage.objetos[caminho_resultado]

    if cenario in {"divergente", "leitura_indisponivel"}:
        with pytest.raises(RuntimeError):
            service.reprocessar_persistencia_oci(documento_id)

        triagem = service.obter_triagem(documento_id)
        assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
        assert triagem.armazenamento_oci.status_backup == "falha"
        assert service.obter_referencia_historico_oci(documento_id) is None
    else:
        triagem = service.reprocessar_persistencia_oci(documento_id)

        assert triagem.status.value == resultado_esperado["status"]
        assert triagem.armazenamento_oci.status_backup == "sucesso"
        assert service.obter_triagem(documento_id) == triagem

        referencia = service.obter_referencia_historico_oci(documento_id)
        assert referencia is not None
        historico = json.loads(storage.objetos[referencia])
        assert historico["documento_id"] == documento_id
        assert historico["eventos"][-1]["status_novo"] == triagem.status.value

        if cenario == "erro_processamento":
            assert triagem.status == StatusTriagem.ERRO_PROCESSAMENTO
            assert triagem.erro.codigo.value == "FALHA_WORKFLOW"
            assert triagem.classificacao is None
            assert triagem.decisao_roteamento is None

    assert caminho_resultado in leituras
    assert storage.objetos[caminho_original] == original_antes
    assert storage.objetos[caminho_resultado] == resultado_antes_do_retry
    assert len(chamadas_grafo) == 1


@pytest.mark.parametrize(
    "cenario",
    ["identico", "divergente", "leitura_indisponivel"],
)
def test_retry_412_snapshot_historico(preparar, monkeypatch, cenario):
    service, storage, documento_id = preparar
    enviar_bytes = storage.enviar_bytes
    ler_bytes = storage.ler_bytes
    envios_historico = []
    leituras = []

    class ObjetoJaExiste(Exception):
        status = 412
        code = "PreconditionFailed"

    def enviar_com_timeout(
        caminho, conteudo, tipo_conteudo="application/octet-stream"
    ):
        if not caminho.startswith("historico/"):
            return enviar_bytes(caminho, conteudo, tipo_conteudo)

        envios_historico.append(caminho)
        if caminho in storage.objetos:
            raise ObjetoJaExiste("Snapshot já existe.")

        confirmacao = enviar_bytes(caminho, conteudo, tipo_conteudo)
        if len(envios_historico) == 1:
            raise TimeoutError("Snapshot gravado, mas a confirmação se perdeu.")
        return confirmacao

    def ler_objeto(caminho):
        leituras.append(caminho)
        if cenario == "leitura_indisponivel":
            raise TimeoutError("Leitura do snapshot indisponível.")
        return ler_bytes(caminho)

    monkeypatch.setattr(storage, "enviar_bytes", enviar_com_timeout)
    monkeypatch.setattr(storage, "ler_bytes", ler_objeto)

    triagem = service.executar_triagem(documento_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.armazenamento_oci.status_backup == "falha"
    assert service.obter_referencia_historico_oci(documento_id) is None
    assert len(envios_historico) == 1

    primeiro_snapshot = envios_historico[0]
    documentos_salvos = {
        caminho: conteudo
        for caminho, conteudo in storage.objetos.items()
        if not caminho.startswith("historico/")
    }

    if cenario == "divergente":
        storage.objetos[primeiro_snapshot] = b'{"documento_id": "OUTRO"}'

    bytes_antes_do_retry = storage.objetos[primeiro_snapshot]

    if cenario == "identico":
        recuperada = service.reprocessar_persistencia_oci(documento_id)

        assert recuperada.status != StatusTriagem.ERRO_PERSISTENCIA
        assert recuperada.armazenamento_oci.status_backup == "sucesso"

        referencia = service.obter_referencia_historico_oci(documento_id)
        assert referencia is not None
        assert referencia != primeiro_snapshot
        assert envios_historico == [
            primeiro_snapshot,
            primeiro_snapshot,
            referencia,
        ]

        historico = json.loads(storage.objetos[referencia])
        assert historico["documento_id"] == documento_id
        assert historico["eventos"] == [
            evento.model_dump(mode="json")
            for evento in service.obter_historico(documento_id)
        ]
        assert (
            historico["eventos"][-1]["tipo_evento"]
            == "HISTORICO_PERSISTENCIA_RECUPERADA"
        )
    else:
        with pytest.raises(RuntimeError):
            service.reprocessar_persistencia_oci(documento_id)

        assert service.obter_status(documento_id) == StatusTriagem.ERRO_PERSISTENCIA
        assert service.obter_referencia_historico_oci(documento_id) is None
        assert envios_historico == [primeiro_snapshot, primeiro_snapshot]

    assert leituras == [primeiro_snapshot]
    assert storage.objetos[primeiro_snapshot] == bytes_antes_do_retry
    assert all(
        storage.objetos[caminho] == conteudo
        for caminho, conteudo in documentos_salvos.items()
    )


def test_retry_412_snapshot_recuperacao_preserva_evento(preparar, monkeypatch):
    service, storage, documento_id = preparar
    enviar_bytes = storage.enviar_bytes
    ler_bytes = storage.ler_bytes
    envios_historico = []
    envios_recuperacao = []
    leituras = []
    tipo_recuperacao = "HISTORICO_PERSISTENCIA_RECUPERADA"

    class ObjetoJaExiste(Exception):
        status = 412
        code = "PreconditionFailed"

    def enviar_com_falhas(
        caminho, conteudo, tipo_conteudo="application/octet-stream"
    ):
        if not caminho.startswith("historico/"):
            return enviar_bytes(caminho, conteudo, tipo_conteudo)

        envios_historico.append(caminho)
        if len(envios_historico) == 1:
            raise TimeoutError("Primeira tentativa falhou antes da gravação.")

        payload = json.loads(conteudo)
        contem_recuperacao = any(
            evento["tipo_evento"] == tipo_recuperacao
            for evento in payload["eventos"]
        )
        if contem_recuperacao:
            envios_recuperacao.append((caminho, bytes(conteudo)))

        if caminho in storage.objetos:
            raise ObjetoJaExiste("Snapshot já existe.")

        confirmacao = enviar_bytes(caminho, conteudo, tipo_conteudo)
        if contem_recuperacao and len(envios_recuperacao) == 1:
            raise TimeoutError("Snapshot de recuperação gravado sem confirmação.")

        return confirmacao

    def ler_objeto(caminho):
        leituras.append(caminho)
        return ler_bytes(caminho)

    monkeypatch.setattr(storage, "enviar_bytes", enviar_com_falhas)
    monkeypatch.setattr(storage, "ler_bytes", ler_objeto)

    # A primeira gravação do histórico falha antes de criar o objeto.
    triagem = service.executar_triagem(documento_id)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert service.obter_referencia_historico_oci(documento_id) is None

    # A primeira retentativa grava o snapshot de recuperação, mas perde a confirmação.
    with pytest.raises(RuntimeError, match="histórico continua pendente"):
        service.reprocessar_persistencia_oci(documento_id)

    assert service.obter_status(documento_id) == StatusTriagem.ERRO_PERSISTENCIA
    assert len(envios_recuperacao) == 1

    caminho_recuperacao, bytes_recuperacao = envios_recuperacao[0]
    assert storage.objetos[caminho_recuperacao] == bytes_recuperacao
    assert service.obter_referencia_historico_oci(documento_id) != caminho_recuperacao

    historico_gravado = json.loads(bytes_recuperacao)
    eventos_recuperacao = [
        evento
        for evento in historico_gravado["eventos"]
        if evento["tipo_evento"] == tipo_recuperacao
    ]
    assert len(eventos_recuperacao) == 1
    evento_id = eventos_recuperacao[0]["evento_id"]

    # A segunda retentativa recebe 412 e confirma o snapshot existente.
    recuperada = service.reprocessar_persistencia_oci(documento_id)

    assert recuperada.status != StatusTriagem.ERRO_PERSISTENCIA
    assert recuperada.armazenamento_oci.status_backup == "sucesso"
    assert service.obter_referencia_historico_oci(documento_id) == caminho_recuperacao
    assert leituras == [caminho_recuperacao]
    assert envios_recuperacao == [
        (caminho_recuperacao, bytes_recuperacao),
        (caminho_recuperacao, bytes_recuperacao),
    ]
    assert storage.objetos[caminho_recuperacao] == bytes_recuperacao

    eventos_finais = service.obter_historico(documento_id)
    assert [
        evento.evento_id
        for evento in eventos_finais
        if evento.tipo_evento == tipo_recuperacao
    ] == [evento_id]
    assert [evento.model_dump(mode="json") for evento in eventos_finais] == (
        historico_gravado["eventos"]
    )