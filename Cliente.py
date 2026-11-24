import json
import socket
from decimal import Decimal, InvalidOperation

def ler_valor():
    while True:
        texto = input("Valor (ex.: 25,50): ").strip().replace(",", ".")
        try:
            valor = Decimal(texto)
            if not valor.is_finite() or valor <= 0:
                print("[ERRO] Digite um valor maior que zero.")
                continue
            return f"{valor:.2f}"
        except InvalidOperation:
            print("[ERRO] Digite apenas um valor numérico válido.")


def enviar_requisicao(arquivo, conta, acao, valor=None):
    requisicao = {"conta": conta, "acao": acao}
    if valor is not None:
        requisicao["valor"] = valor

    arquivo.write((json.dumps(requisicao, ensure_ascii=False) + "\n").encode("utf-8"))
    arquivo.flush()

    resposta_linha = arquivo.readline()
    if not resposta_linha:
        raise ConnectionError("O servidor encerrou a conexão.")
    resposta = json.loads(resposta_linha.decode("utf-8"))

    prefixo = "[OK]" if resposta.get("status") == "OK" else "[ERRO]"
    print(f"{prefixo} {resposta.get('mensagem', 'Resposta inválida do servidor.')}")


def main():
    ip = input("IP do servidor: ").strip()
    try:
        porta = int(input("Porta do servidor: ").strip())
        if not 1024 <= porta <= 65535:
            raise ValueError
    except ValueError:
        print("[ERRO] Informe uma porta entre 1024 e 65535.")
        return

    conta = input("Número da conta: ").strip()
    if not conta.isdigit():
        print("[ERRO] O número da conta deve conter apenas números.")
        return

    try:
        with socket.create_connection((ip, porta), timeout=10) as sock:
            print(f"[OK] Conectado ao servidor {ip}:{porta}.")
            sock.settimeout(None)
            with sock.makefile("rwb") as arquivo:
                while True:
                    print("\n===== MINI BANCO =====")
                    print("1 - Consultar saldo")
                    print("2 - Depositar")
                    print("3 - Sacar")
                    print("4 - Consultar extrato")
                    print("0 - Sair")
                    opcao = input("Escolha uma opção: ").strip()

                    if opcao == "0":
                        print("Você saiu do sistema.")
                        break
                    elif opcao == "1":
                        enviar_requisicao(arquivo, conta, "saldo")
                    elif opcao == "2":
                        valor = ler_valor()
                        enviar_requisicao(arquivo, conta, "deposito", valor)
                    elif opcao == "3":
                        valor = ler_valor()
                        enviar_requisicao(arquivo, conta, "saque", valor)
                    elif opcao == "4":
                        enviar_requisicao(arquivo, conta, "extrato")
                    else:
                        print("[ERRO] Opção inválida. Escolha de 0 a 4.")
    except ConnectionRefusedError:
        print("[ERRO] Conexão recusada. Confira se o servidor está ligado e o IP/porta estão corretos.")
    except (TimeoutError, socket.timeout):
        print("[ERRO] Tempo esgotado. Confira o IP e a rede do VirtualBox.")
    except (OSError, ConnectionError, json.JSONDecodeError) as erro:
        print(f"[ERRO] Falha na comunicação: {erro}")


if __name__ == "__main__":
    main()
