"""
MediFlow — Script de Teste e Demonstração da Simulação de Erros do OCI (EPT §12, RF-28, RF-30).

Executa os cenários formais da Especificação de Procedimento de Teste:
1. Simulacao_OciFalhaNoOriginal: Nuvem OCI indisponível ao salvar o original -> ERRO_PERSISTENCIA.
2. Recuperação / Retry: Reprocessamento sem reexecutar LLM -> Restaura para PROCESSADO.
3. Simulacao_OciFalhaNoResultado: Quota OCI excedida ao persistir o JSON final -> ERRO_PERSISTENCIA.
"""
import sys
import time
from pathlib import Path

# Configura encoding UTF-8 seguro para terminais Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Garante a raiz no sys.path
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.api.service import TriagemService
from src.schemas import StatusTriagem, CodigoErro


def imprimir_cabecalho(texto: str):
    print("\n" + "=" * 70)
    print(f"  {texto}")
    print("=" * 70)


def testar_cenario_falha_original():
    imprimir_cabecalho("CENARIO 1: Simulacao_OciFalhaNoOriginal (EPT §12 / RF-28)")
    print("-> Submetendo documento com gatilho EPT: 'Simulacao_OciFalhaNoOriginal.txt'")
    
    service = TriagemService()
    conteudo = (
        "Receita Médica de Emergência\n"
        "Paciente: Lucas Andrade, 34 anos\n"
        "Médico: Dra. Fernanda (CRM: 67890/SP)\n"
        "Diagnóstico: Crise Asmática Grave\n"
        "Medicamento: Salbutamol Spray 100mcg"
    ).encode("utf-8")
    
    doc_id = service.submeter_arquivo(
        conteudo=conteudo,
        nome_arquivo="Simulacao_OciFalhaNoOriginal.txt",
        canal_origem="Upload_Simulacao",
    )
    print(f"-> Documento registrado com ID: {doc_id} (Status: RECEBIDO)")
    
    print("-> Executando motor de triagem com falha simulada no OCI...")
    triagem = service.executar_triagem(doc_id)
    
    print(f"\n[Resultado da Ingestão]")
    print(f"  Status: {triagem.status.value}")
    print(f"  Status Backup OCI: {triagem.armazenamento_oci.status_backup if triagem.armazenamento_oci else 'N/A'}")
    print(f"  Código do Erro: {triagem.erro.codigo.value if triagem.erro else 'N/A'}")
    print(f"  Mensagem: {triagem.erro.mensagem if triagem.erro else 'N/A'}")
    print(f"  Decisão Clínica Preservada: Destinos = {[d.value for d in triagem.decisao_roteamento.destinos] if triagem.decisao_roteamento else []}")
    
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA, "Deveria estar em ERRO_PERSISTENCIA"
    assert triagem.erro.codigo == CodigoErro.ERRO_PERSISTENCIA, "Código deveria ser ERRO_PERSISTENCIA"
    assert "FALHA_GRAVACAO_ORIGINAL" in triagem.erro.mensagem, "Mensagem deve indicar falha original"
    print("\n[OK] CENARIO 1 APROVADO: Falha no original gerou ERRO_PERSISTENCIA preservando decisão clínica.")

    # Retentativa (Retry)
    print("\n-> Disparando retentativa de persistência (RF-28 / RF-30)...")
    triagem_recuperada = service.reprocessar_persistencia_oci(doc_id)
    print(f"  Status Restaurado: {triagem_recuperada.status.value}")
    print(f"  Status Backup OCI: {triagem_recuperada.armazenamento_oci.status_backup}")
    print(f"  Erro: {triagem_recuperada.erro}")
    assert triagem_recuperada.status in (StatusTriagem.PROCESSADO, StatusTriagem.EM_REVISAO)
    assert triagem_recuperada.armazenamento_oci.status_backup == "sucesso"
    print("[OK] RETENTATIVA APROVADA: Estado restaurado para PROCESSADO com backup confirmado!")


def testar_cenario_falha_resultado():
    imprimir_cabecalho("CENARIO 2: Simulacao_OciFalhaNoResultado (EPT §12 / RF-30)")
    print("-> Submetendo documento com gatilho EPT: 'Simulacao_OciFalhaNoResultado.txt'")
    
    service = TriagemService()
    conteudo = (
        "Laudo de Exame Laboratorial\n"
        "Paciente: Juliana Santos, 50 anos\n"
        "Médico: Dr. Roberto (CRM: 11223/SP)\n"
        "Exame: Glicemia em Jejum: 95 mg/dL (Normal)"
    ).encode("utf-8")
    
    doc_id = service.submeter_arquivo(
        conteudo=conteudo,
        nome_arquivo="Simulacao_OciFalhaNoResultado.txt",
        canal_origem="Upload_Simulacao",
    )
    print(f"-> Documento registrado com ID: {doc_id}")
    
    print("-> Executando triagem (original salvo com sucesso, falha simulada no resultado.json)...")
    triagem = service.executar_triagem(doc_id)
    
    print(f"\n[Resultado da Ingestão]")
    print(f"  Status: {triagem.status.value}")
    print(f"  Status Backup OCI: {triagem.armazenamento_oci.status_backup if triagem.armazenamento_oci else 'N/A'}")
    print(f"  Código do Erro: {triagem.erro.codigo.value if triagem.erro else 'N/A'}")
    print(f"  Mensagem: {triagem.erro.mensagem if triagem.erro else 'N/A'}")
    print(f"  Paciente Extraído: {triagem.dados_extraidos.paciente.nome if triagem.dados_extraidos and triagem.dados_extraidos.paciente else 'N/A'}")
    
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_RESULTADO" in triagem.erro.mensagem
    print("\n[OK] CENARIO 2 APROVADO: Falha na gravação do resultado tratada com integridade de dados.")

    # Retentativa
    print("\n-> Disparando retentativa de persistência...")
    triagem_recuperada = service.reprocessar_persistencia_oci(doc_id)
    print(f"  Status Restaurado: {triagem_recuperada.status.value}")
    print(f"  Status Backup OCI: {triagem_recuperada.armazenamento_oci.status_backup}")
    assert triagem_recuperada.status in (StatusTriagem.PROCESSADO, StatusTriagem.EM_REVISAO)
    print("[OK] RETENTATIVA APROVADA: Artefatos persistidos com sucesso.")


def main():
    print("=" * 70)
    print("  MEDIFLOW - SUITE DE TESTE DA SIMULACAO DE ERROS OCI (EPT v1.0)")
    print("=" * 70)
    
    t0 = time.time()
    testar_cenario_falha_original()
    testar_cenario_falha_resultado()
    duracao = round(time.time() - t0, 2)
    
    imprimir_cabecalho(f"TODOS OS CENARIOS DE ERRO DO OCI FORAM VALIDADOS COM SUCESSO EM {duracao}s!")


if __name__ == "__main__":
    main()
