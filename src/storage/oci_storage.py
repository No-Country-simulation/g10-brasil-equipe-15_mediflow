"""Conector OCI: envia, le e lista objetos, sem regras de triagem."""
from pathlib import Path
import os

import oci


class OCIStorage:
    def __init__(self, cliente, namespace: str, bucket: str):
        if not namespace.strip() or not bucket.strip():
            raise ValueError("Namespace e bucket precisam estar preenchidos.")
        self.cliente = cliente
        self.namespace = namespace.strip()
        self.bucket = bucket.strip()

    @classmethod
    def das_configuracoes(cls):
        from src import config

        valores = {
            "OCI_USER_OCID": config.OCI_USER_OCID,
            "OCI_TENANCY_OCID": config.OCI_TENANCY_OCID,
            "OCI_FINGERPRINT": config.OCI_FINGERPRINT,
            "OCI_KEY_FILE": config.OCI_KEY_FILE,
            "OCI_REGION": config.OCI_REGION,
            "OCI_NAMESPACE": config.OCI_NAMESPACE,
            "OCI_BUCKET_NAME": config.OCI_BUCKET_NAME,
        }
        faltantes = [nome for nome, valor in valores.items() if not valor.strip()]
        if faltantes:
            raise ValueError("Preencha no .env: " + ", ".join(faltantes))

        chave = Path(config.OCI_KEY_FILE).expanduser()
        if not chave.is_absolute():
            chave = config.BASE_DIR / chave
        if not chave.is_file():
            raise FileNotFoundError("O arquivo indicado em OCI_KEY_FILE nao existe.")

        credenciais = {
            "user": config.OCI_USER_OCID.strip(),
            "tenancy": config.OCI_TENANCY_OCID.strip(),
            "fingerprint": config.OCI_FINGERPRINT.strip(),
            "key_file": str(chave),
            "region": config.OCI_REGION.strip(),
        }
        senha = os.getenv("OCI_KEY_PASSPHRASE")
        if senha:
            credenciais["pass_phrase"] = senha
        oci.config.validate_config(credenciais)
        cliente = oci.object_storage.ObjectStorageClient(
            credenciais,
            timeout=(10, 30),
            retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        return cls(cliente, config.OCI_NAMESPACE, config.OCI_BUCKET_NAME)

    @staticmethod
    def _validar_nome(nome: str):
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("O nome do objeto nao pode estar vazio.")

    def enviar_bytes(
        self, nome: str, conteudo: bytes,
        tipo_conteudo: str = "application/octet-stream",
    ) -> dict:
        self._validar_nome(nome)
        if not isinstance(conteudo, bytes):
            raise TypeError("O conteudo precisa ser bytes.")
        resposta = self.cliente.put_object(
            namespace_name=self.namespace,
            bucket_name=self.bucket,
            object_name=nome,
            put_object_body=conteudo,
            content_length=len(conteudo),
            content_type=tipo_conteudo,
            if_none_match="*",  # Nao sobrescreve objeto existente.
        )
        if not 200 <= resposta.status < 300:
            raise RuntimeError("OCI nao confirmou o envio do objeto.")
        return {
            "bucket": self.bucket,
            "caminho_objeto": nome,
            "etag": resposta.headers.get("etag"),
            "status_backup": "sucesso",
        }

    def ler_bytes(self, nome: str) -> bytes:
        self._validar_nome(nome)
        resposta = self.cliente.get_object(
            namespace_name=self.namespace,
            bucket_name=self.bucket,
            object_name=nome,
        )
        try:
            return resposta.data.content
        finally:
            resposta.data.close()

    def listar(self, prefixo: str = "") -> list[str]:
        nomes = []
        inicio = None
        while True:
            argumentos = {
                "namespace_name": self.namespace,
                "bucket_name": self.bucket,
                "prefix": prefixo,
            }
            if inicio is not None:
                argumentos["start"] = inicio
            resposta = self.cliente.list_objects(**argumentos)
            nomes.extend(objeto.name for objeto in resposta.data.objects)
            proximo = resposta.data.next_start_with
            if not proximo:
                return nomes
            if proximo == inicio:
                raise RuntimeError("OCI repetiu o cursor da listagem.")
            inicio = proximo
