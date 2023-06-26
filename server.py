import socket
import threading
import signal
from queue import Queue
import sys
import os


class Server:
    def __init__(self, ip='127.0.0.1', port=1099):
        self.ip = ip
        self.port = port
        self.peer_files = {}  # Dicionário para armazenar os arquivos de cada peer
        self.request_queue = Queue()  # Fila para armazenar as requisições recebidas
        self.queue_lock = threading.Lock()  # Lock para sincronização da fila
        self.peer_files_lock = threading.Lock()  # Lock para sincronização do dicionário de arquivos dos peers
        self.server_socket = None  # Socket do servidor
        self.request_thread = None  # Thread para processar as requisições

    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Criação do socket do servidor
            print("Servidor criado")
        except socket.error as err:
            print(f"Erro ao criar o servidor: {err}")
            sys.exit(1)

        self.server_socket.bind((self.ip, self.port))  # Vincula o socket a um endereço IP e porta
        self.server_socket.listen(5)  # Inicia a escuta por conexões

        print(f"Servidor inicializado. Aguardando conexões na porta {self.port}...")

        self.request_thread = threading.Thread(target=self.handle_request)  # Criação da thread para processar as requisições
        self.request_thread.daemon = True  # Define a thread como daemon para finalizar junto com o programa principal
        self.request_thread.start()

        signal.signal(signal.SIGINT, self.handle_interrupt_signal)  # Configuração do tratamento do sinal SIGINT (Ctrl+C)

        while True:
            client_socket, client_address = self.server_socket.accept()  # Aceita uma conexão do peer
            print(f"Conexão estabelecida com o peer: {client_address}")
            with self.queue_lock:
                self.request_queue.put((client_socket, client_address))  # Adiciona a requisição do peer na fila

    def handle_request(self):
        while True:
            client_socket, client_address = self.request_queue.get()  # Obtém uma requisição da fila
            self.handle_connection(client_socket, client_address)  # Processa a requisição
            self.request_queue.task_done()  # Marca a requisição como concluída na fila

    def handle_connection(self, client_socket, client_address):
        try:
            request = client_socket.recv(1024).decode()  # Recebe a requisição do peer
            request_parts = request.split()  # Divide a requisição em partes

            if len(request_parts) < 2:
                response = 'INVALID_REQUEST'  # Resposta para requisição inválida
            else:
                operation = request_parts[0]  # Operação solicitada
                payload = request_parts[1]  # Carga útil da requisição

                if operation == 'JOIN':
                    response = self.join_peer(payload)  # Chama o método para tratar a operação JOIN
                elif operation == 'SEARCH':
                    response = self.search_request(payload)  # Chama o método para tratar a operação SEARCH
                elif operation == 'UPDATE':
                    response = self.update_file(payload)  # Chama o método para tratar a operação UPDATE
                else:
                    response = 'INVALID_OPERATION'  # Resposta para operação inválida

            client_socket.send(response.encode())  # Envia a resposta para o peer
        except Exception as err:
            print(f'Erro de conexão: {err}')
        finally:
            client_socket.close()  # Encerra a conexão com o peer
            print(f"Conexão encerrada com o peer: {client_address}")

    def join_peer(self, peer_info):
        ip, port, files = peer_info.split(',')  # Divide as informações do peer em IP, porta e arquivos
        full_path_names = files.split('|')  # Divide os nomes completos dos arquivos
        file_names = []
        full_file_path = []
        for file in full_path_names:
            path, file_name =  os.path.split(file)  # Obtém o caminho e o nome do arquivo
            file_names.append(file_name)  # Adiciona o nome do arquivo à lista
            full_file_path.append(file)  # Adiciona o nome completo do arquivo à lista
        print(f'Peer {ip}:{port} adicionado com arquivos: {" ".join(file_names)}')
        with self.peer_files_lock:
            self.peer_files[port] = full_file_path  # Adiciona os arquivos do peer ao dicionário
        return 'JOIN_OK'  # Resposta de sucesso para a operação JOIN

    def search_request(self, payload):
        request_parts = payload.split(',')  # Divide a carga útil da requisição em partes
        if len(request_parts) == 2:
            return self.search_path(request_parts[0], request_parts[1])  # Chama o método para tratar a busca por caminho
        else:
            return self.search_file(request_parts[0])  # Chama o método para tratar a busca por arquivo
    
    def search_path(self, port, file_name):
        file_path = ''
        with self.peer_files_lock:
            if port in self.peer_files.keys():
                for file in self.peer_files[port]:
                    path, name =  os.path.split(file)  # Obtém o caminho e o nome do arquivo
                    if file_name == name:
                        file_path = file  # Armazena o caminho completo do arquivo
        return file_path  # Retorna o caminho completo do arquivo (ou vazio se não encontrado)
    
    def search_file(self, file_name):
        peers_with_file = []
        with self.peer_files_lock:
            for peer, files in self.peer_files.items():
                for file in files:
                    path, name =  os.path.split(file)  # Obtém o caminho e o nome do arquivo
                    if file_name == name:
                        peers_with_file.append(peer)  # Armazena o peer que possui o arquivo
        peers_with_file_formatted = ' '.join(peers_with_file)  # Formata os peers com o arquivo encontrado
        ip_formatted = self.ip.replace("'", '')  # Formata o IP do servidor
        print(f'Peer {ip_formatted}:{peers_with_file_formatted} adicionado com arquivos: {file_name}')
        return peers_with_file_formatted  # Retorna a lista de peers que possuem o arquivo

    def update_file(self, file_name):
        ip, port, files = peer_info.split(',')  # Divide as informações do peer em IP, porta e arquivos
        file_names = files.split('|')  # Divide os nomes dos arquivos
        with self.peer_files_lock:
            self.peer_files[port] = file_names  # Atualiza a lista de arquivos do peer
        return 'UPDATE_OK'  # Resposta de sucesso para a operação UPDATE

    def handle_interrupt_signal(self, signum, frame):
        print("Recebido sinal SIGINT (Ctrl+C). Encerrando servidor...")
        self.request_queue.join()  # Aguarda a conclusão de todas as requisições na fila
        sys.exit(0)


if __name__ == "__main__":
    ip = input("Digite o endereço IP do servidor (padrão: 127.0.0.1): ").strip() or '127.0.0.1'
    port = int(input("Digite a porta do servidor (padrão: 1099): ").strip() or 1099)

    server = Server(ip, port)
    server.start()
