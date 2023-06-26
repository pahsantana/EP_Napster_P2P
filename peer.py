import os
import threading
import queue
import signal
import sys
import socket

class Peer:
    def __init__(self, server_ip, server_port, folder_path):
        self.server_ip = server_ip
        self.server_port = server_port
        self.folder_path = folder_path
        self.paired_peer_socket = None
        self.peer_port = None
        self.q = None # Necessário inicializar a fila q

    def send_request(self, request): # Envia uma solicitação para o servidor e retorna a resposta recebida
        try:
            if self.peer_socket is None:
                raise ValueError("Socket do peer não inicializado")

            self.peer_socket.send(request.encode())
            response = self.peer_socket.recv(1024).decode()
            self.peer_socket.close()
            return response
        except Exception as err:
            print(f"Erro ao solicitar: {str(err)}")

    def join_server(self): # Envia uma solicitação JOIN para o servidor com as informações do peer
        try:
            files = os.listdir(self.folder_path)
            full_path = resultado = [os.path.join(self.folder_path, file) for file in files]
            full_path_formatted = '|'.join(full_path)
            
            request = f"JOIN {self.server_ip},{self.peer_port},{full_path_formatted}"
            response = self.send_request(request)
            self.handle_join_response(response, files)
        except Exception as err:
            print(f"Erro ao realizar a requisição JOIN: {str(err)}")

    def handle_join_response(self, response, files):
        if response == "JOIN_OK": # Manipula a resposta recebida após a solicitação JOIN
            if len(files) != 0:
                print(f'Sou peer {self.server_ip}:{self.peer_port} com os arquivos {" ".join(files)}')
            else:
                print(f'Sou peer {self.server_ip}:{self.peer_port} sem arquivos')
        else:
            print("Falha na requisição JOIN.")

    def search_path(self, port, file_name): # Envia uma solicitação SEARCH para um peer específico
        if self.peer_socket is None:
            print("Socket do peer não inicializado")
            return
        if len(file_name) != 0:
            request = f"SEARCH {port},{file_name}"
            response = self.send_request(request)
            return response
    
    def search_file(self):  # Solicita ao usuário o nome do arquivo a ser buscado e envia uma solicitação SEARCH para o servidor
        if self.peer_socket is None:
            print("Socket do peer não inicializado")
            return
        
        file_name = input("Insira o nome do arquivo a ser buscado: ")

        if len(file_name) != 0:
            request = f"SEARCH {file_name}"
            response = self.send_request(request)
            self.handle_search_response(response)
        else:
            print('Não foi inserido o nome do arquivo buscado')

    def handle_search_response(self, response):  # Manipula a resposta recebida após a solicitação SEARCH
        if response:
            print(f"Peers com arquivo solicitado: {self.server_ip}:{response}")
        else:
            print("Arquivo não encontrado nos peers")

    def download_request(self):  # Solicita ao usuário o endereço IP e a porta de um peer para realizar o download de um arquivo
        if self.peer_socket is None:
            print("Socket do peer não inicializado")
            return

        paired_peer_ip = input("Digite o endereço IP do peer a ser pareado (padrão: 127.0.0.1): ").strip() or "127.0.0.1"
        paired_peer_port = int(input("Digite a porta do peer a ser pareado (padrão: 1099): ").strip() or 1099)
        file_name = input("Insira o nome do arquivo a ser buscado: ")
        file_request_path = self.search_path(paired_peer_port, file_name)

        try:
            self.paired_peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.paired_peer_socket.bind((paired_peer_ip, paired_peer_port))
            request = f"DOWNLOAD {file_request_path}"
            self.paired_peer_socket.connect((paired_peer_ip, paired_peer_port))
            self.paired_peer_socket.send(request.encode())
            response = self.paired_peer_socket.recv(1024).decode()
            request_parts = response.split()
            operation = request_parts[0]
            file_response_path = request_parts[1]
            if operation == "DOWNLOAD":
                path, file_name = os.path.split(file_response_path)
                self.upload_file(self.paired_peer_socket, file_response_path, file_name)
                self.download_file(self.paired_peer_socket, file_name)
                print(f"Arquivo '{file_name}' baixado com sucesso na pasta {self.folder_path}")
                self.update_file(file_name)
        except Exception as err:
            print(f"Erro ao baixar o arquivo: {str(err)}")
        finally:
            if self.paired_peer_socket is not None:
                self.paired_peer_socket.close()


    def download_file(self, paired_peer_socket, file_name):  # Baixa o arquivo recebido do peer em partes e salva no diretório do peer
        try:
            buffer_size = 4096 

            with open(os.path.join(self.folder_path, file_name), "wb") as file:
                file_data = paired_peer_socket.recv(buffer_size)
                while file_data:
                    file.write(file_data)
                    file.flush()
                    file_data = paired_peer_socket.recv(buffer_size)
            self.q.put(file_name) # Adicionar item relevante à fila q
        except Exception as err:
            print(f"Falha ao baixar o arquivo: {str(err)}")

    def upload_file(self, peer_socket, file_path, file_name): # Faz o upload de um arquivo para um peer conectado
        try:
            if os.path.isfile(file_path):
                buffer_size, chunk_size = 4096, 1000 * 1024 * 1024 # 1000MB = 1GB
                with open(file_path, "rb") as file:
                    while True:
                        file_data = file.read(chunk_size)
                        if not file_data:
                            break
                        peer_socket.send(file_data)
            else:
                print(f"Arquivo '{file_name}' não foi encontrado.")
        except Exception as err:
            print(f"Erro ao processar upload: {str(err)}")

    def update_file(self, file_name): # Atualiza a lista de arquivos do peer no servidor
        files = os.listdir(file_name)
        files_formatted = '|'.join(files)
        request = f"UPDATE {self.server_ip},{self.peer_port},{files_formatted}"
        response = self.send_request(request)
        self.handle_update_response(response)
    
    def handle_update_response(self, response):
        if response != "UPDATE_OK": 
            print("Falha na requisição JOIN.")

    def start_signal_handler(self):
        signal.signal(signal.SIGINT, self.signal_handler)  # Inicia o manipulador de sinal para capturar o sinal SIGINT (Ctrl+C)

    def main(self): # Função principal do programa que exibe o menu e executa as ações selecionadas pelo usuário
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.connect((self.server_ip, self.server_port))
        self.peer_port = self.peer_socket.getsockname()[1]

        self.q = queue.Queue()

        t = threading.Thread(target=self.file_transfer_thread)  
        t.daemon = True
        t.start()

        while True:
            print("---- MENU ----")
            print("1. JOIN")
            print("2. SEARCH")
            print("3. DOWNLOAD")
            print("4. EXIT")

            choice = input("Escolha um número dentro das opções: ")

            if choice == "1":
                self.join_server()
            elif choice == "2":
                self.search_file()
            elif choice == "3":
                self.download_request()
            elif choice == "4":
                self.q.join()
                break
            else:
                print("Opção inválida")

    def signal_handler(self, signal, frame): # Manipulador de sinal para encerrar o programa de forma adequada
        print("Saindo...") 
        self.q.join()
        sys.exit(0)

    def file_transfer_thread(self):
        while True: # Thread para processar itens da fila q (futuro processamento de arquivos baixados)
            item = self.q.get()
            print(f"Processando o item da fila: {item}") # Processar o item da fila aqui (exemplo: imprimir o nome do arquivo)
            self.q.task_done()

if __name__ == "__main__": # Solicita ao usuário informações do servidor, porta e caminho da pasta de arquivos
    server_ip = input("Digite o endereço IP do servidor (padrão: 127.0.0.1): ").strip() or '127.0.0.1'
    server_port = int(input("Digite a porta do servidor (padrão: 1099): ").strip() or 1099)
    folder_path = input("Digite o caminho da pasta: ")
    peer = Peer(server_ip, server_port, folder_path) # Cria uma instância do Peer e inicia o programa
    peer.start_signal_handler()
    peer.main()
