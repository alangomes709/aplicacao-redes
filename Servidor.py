import json
import socket
import threading
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ARQUIVO_BANCO = Path(__file__).with_name("banco.txt")
CONTAS = {}
TRAVA = threading.Lock()
CENTAVO = Decimal("0.01")


def dinheiro(valor):
    """Converte um valor para Decimal com duas casas decimais."""
    try:
        numero = Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Valor monetário inválido.")
    if not numero.is_finite():
        raise ValueError("Valor monetário inválido.")
    return numero


def carregar_banco():
    """Carrega as contas salvas. Se o arquivo não existir, inicia vazio."""
    global CONTAS
    if not ARQUIVO_BANCO.exists():
        CONTAS = {}
        return
    try:
        with ARQUIVO_BANCO.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        if not isinstance(dados, dict):
            raise ValueError("Formato inválido")
        CONTAS = dados
        for numero, conta in CONTAS.items():
            conta.setdefault("saldo", "0.00")
            conta.setdefault("historico", [])
            conta["historico"] = conta["historico"][-3:]
    except (OSError, json.JSONDecodeError, ValueError) as erro:
        print(f"[ERRO] Não foi possível carregar banco.txt: {erro}")
        CONTAS = {}


def salvar_banco():
    """Salva as contas e seus saldos em banco.txt."""
    temporario = ARQUIVO_BANCO.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(CONTAS, arquivo, ensure_ascii=False, indent=4)
    temporario.replace(ARQUIVO_BANCO)


def obter_conta(numero):
    """Obtém uma conta ou cria uma nova com saldo zero."""
    if numero not in CONTAS:
        CONTAS[numero] = {"saldo": "0.00", "historico": []}
    return CONTAS[numero]


def registrar(conta, descricao, valor):
    historico = conta.setdefault("historico", [])
    historico.append({
        "operacao": descricao,
        "valor": f"{valor:.2f}"
    })
    conta["historico"] = historico[-3:]


def processar_requisicao(requisicao):
    if not isinstance(requisicao, dict):
        return {"status": "ERRO", "mensagem": "Requisição inválida."}

    numero = str(requisicao.get("conta", "")).strip()
    acao = requisicao.get("acao")

    if not numero or not numero.isdigit():
        return {"status": "ERRO", "mensagem": "Número da conta inválido."}

    with TRAVA:
        conta = obter_conta(numero)
        saldo = dinheiro(conta["saldo"])

        if acao == "saldo":
            return {
                "status": "OK",
                "mensagem": f"Saldo disponível: R$ {saldo:.2f}"
            }

        if acao in ("deposito", "saque"):
            try:
                valor = dinheiro(requisicao.get("valor"))
            except ValueError as erro:
                return {"status": "ERRO", "mensagem": str(erro)}

            if valor <= 0:
                return {"status": "ERRO", "mensagem": "O valor deve ser maior que zero."}

            if acao == "deposito":
                saldo += valor
                conta["saldo"] = f"{saldo:.2f}"
                registrar(conta, "Depósito", valor)
                return {
                    "status": "OK",
                    "mensagem": f"Depósito de R$ {valor:.2f} realizado. Novo saldo: R$ {saldo:.2f}"
                }

            if saldo < valor:
                return {"status": "ERRO", "mensagem": "Saldo insuficiente para realizar o saque."}

            saldo -= valor
            conta["saldo"] = f"{saldo:.2f}"
            registrar(conta, "Saque", valor)
            return {
                "status": "OK",
                "mensagem": f"Saque de R$ {valor:.2f} realizado. Novo saldo: R$ {saldo:.2f}"
            }

        if acao == "extrato":
            historico = conta.get("historico", [])[-3:]
            if not historico:
                return {"status": "OK", "mensagem": "Nenhuma operação registrada."}
            linhas = ["Últimas operações:"]
            for item in historico:
                linhas.append(f"- {item['operacao']}: R$ {dinheiro(item['valor']):.2f}")
            return {"status": "OK", "mensagem": "\n".join(linhas)}

        return {"status": "ERRO", "mensagem": "Operação desconhecida."}


def atender_cliente(conexao, endereco):
    print(f"Cliente conectado: {endereco[0]}:{endereco[1]}")
    try:
        with conexao:
            arquivo = conexao.makefile("rwb")
            with arquivo:
                for linha in arquivo:
                    try:
                        requisicao = json.loads(linha.decode("utf-8"))
                        resposta = processar_requisicao(requisicao)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        resposta = {"status": "ERRO", "mensagem": "Mensagem recebida em formato inválido."}
                    resposta_bytes = (json.dumps(resposta, ensure_ascii=False) + "\n").encode("utf-8")
                    arquivo.write(resposta_bytes)
                    arquivo.flush()
    except OSError as erro:
        print(f"[ERRO] Conexão com {endereco[0]} encerrada: {erro}")
    finally:
        print(f"Cliente desconectado: {endereco[0]}:{endereco[1]}")


def main():
    carregar_banco()

    ip = input("IP de escuta (Enter para 0.0.0.0 = todas as interfaces): ").strip() or "0.0.0.0"
    try:
        porta = int(input("Porta de escuta (1024-65535): ").strip())
        if not 1024 <= porta <= 65535:
            raise ValueError
    except ValueError:
        print("[ERRO] Informe uma porta entre 1024 e 65535.")
        return

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        servidor.bind((ip, porta))
        servidor.listen()
        print(f"[OK] Servidor bancário escutando em {ip}:{porta}.")
        print("Pressione Ctrl+C para encerrar o servidor.")
        while True:
            conexao, endereco = servidor.accept()
            thread = threading.Thread(
                target=atender_cliente,
                args=(conexao, endereco),
                daemon=True
            )
            thread.start()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    except OSError as erro:
        print(f"[ERRO] Não foi possível iniciar o servidor: {erro}")
    finally:
        servidor.close()
        with TRAVA:
            try:
                salvar_banco()
                print("[OK] Contas salvas em banco.txt.")
            except OSError as erro:
                print(f"[ERRO] Não foi possível salvar o banco: {erro}")


if __name__ == "__main__":
    main()
