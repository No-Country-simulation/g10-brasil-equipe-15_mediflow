"""
Configuração global do Pytest para a suíte MediFlow.
Otimiza a inicialização de bibliotecas C/C++ (onnxruntime, pymupdf) no Windows.
Garante compatibilidade de loopback sockets no Windows para TestClient.
"""
import os
import platform
import asyncio

# Evita que onnxruntime dispare subprocess 'ver' no Windows, acelerando a inicialização
platform.win32_ver = lambda *args, **kwargs: ("10", "10.0.22631", "SP0", "Multiprocessor Free")

# Desativa tracing remoto do LangSmith em testes automatizados
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TESTING"] = "1"

# No Windows, usa SelectorEventLoop para evitar bloqueios de socketpair do ProactorEventLoop
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
