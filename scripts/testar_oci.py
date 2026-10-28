"""Teste real: cria um TXT ficticio no bucket e confere a leitura."""

import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import oci

from src.storage.oci_storage import OCIStorage


RAIZ = Path(__file__).resolve().parents[1]


def main():
    storage = OCIStorage.das_configuracoes()

    if storage.bucket != "mediflow-documentos":
        raise ValueError(
            "Defina OCI_BUCKET_NAME=mediflow-documentos no .env."
        )

    execucao = uuid4().hex
    prefixo = f"recebidos/testes-conexao/{execucao}/"
    nome = prefixo + "teste_conexao.txt"

    conteudo = (
        "Documento ficticio para teste do MediFlow.\n"
    ).encode("utf-8")

    pasta = RAIZ / "temp" / "teste_oci" / execucao
    pasta.mkdir(parents=True, exist_ok=True)

    arquivo_original = pasta / "teste_conexao.txt"
    arquivo_original.write_bytes(conteudo)

    confirmado = storage.enviar_bytes(
        nome=nome,
        conteudo=conteudo,
        tipo_conteudo="text/plain; charset=utf-8",
    )

    print(
        "UPLOAD OK:",
        confirmado["caminho_objeto"],
        flush=True,
    )

    baixado = storage.ler_bytes(nome)

    if baixado != conteudo:
        raise RuntimeError(
            "O conteudo lido difere do conteudo enviado."
        )

    arquivo_baixado = pasta / "teste_conexao_baixado.txt"
    arquivo_baixado.write_bytes(baixado)

    print(
        "LEITURA OK: conteudo identico ao original.",
        flush=True,
    )

    print(
        "SHA-256:",
        sha256(baixado).hexdigest(),
        flush=True,
    )

    objetos = storage.listar(prefixo)

    if nome not in objetos:
        raise RuntimeError(
            "O objeto enviado nao apareceu na listagem."
        )

    print(
        "LISTAGEM OK: objeto encontrado.",
        flush=True,
    )

    print("BUCKET:", storage.bucket)
    print("ARQUIVOS LOCAIS:", pasta)
    print("TESTE REAL OCI CONCLUIDO COM SUCESSO.")


if __name__ == "__main__":
    try:
        main()

    except oci.exceptions.ServiceError as erro:
        dicas = {
            401: (
                "Confira usuario, tenancy, fingerprint, "
                "chave e horario do computador."
            ),
            403: (
                "Confira as permissoes IAM do usuario e do grupo."
            ),
            404: (
                "Confira regiao, namespace, bucket "
                "e permissoes IAM."
            ),
            412: (
                "O nome do objeto ja existe "
                "e a sobrescrita foi bloqueada."
            ),
        }

        print(
            f"FALHA OCI: HTTP {erro.status} ({erro.code})."
        )

        print(
            dicas.get(
                erro.status,
                "Confira a disponibilidade do servico OCI.",
            )
        )

        sys.exit(1)

    except (ValueError, FileNotFoundError, RuntimeError) as erro:
        print("FALHA:", str(erro))
        sys.exit(1)

    except Exception as erro:
        print(
            f"FALHA: {type(erro).__name__}. "
            "Confira rede e configuracao local."
        )
        sys.exit(1)