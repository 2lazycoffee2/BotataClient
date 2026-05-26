#serveur de simulation (Mock) pour tester le projet Botata Client
import sys
import socket
import threading
import json
import time
import random

# Port réseau par défaut
PORT = 9559


class MockRobot:
    def __init__(self, host="127.0.0.1", port=PORT):
        self.host = host
        self.port = port
        self.running = False
        self.tcp_client = None
        
        # Données de simulation du robot
        self.battery_level = 100
        self.color_name = "vert"
        self.current_color = [0, 255, 0]  # RGB pour le vert

    def start(self):
        self.running = True

        #Répondre à la détection automatique (UDP)
        udp_thread = threading.Thread(target=self._run_udp_server, daemon=True)
        udp_thread.start()

        #Gérer la connexion du client (TCP)
        tcp_thread = threading.Thread(target=self._run_tcp_server, daemon=True)
        tcp_thread.start()

        #Simuler la vie interne du robot
        sim_thread = threading.Thread(target=self._run_simulation, daemon=True)
        sim_thread.start()

        print(f"\n[OK] Simulateur lancé sur {self.host} (Port TCP/UDP {self.port})")
        print("[INFO] Lancez l'application client PyQt et connectez-vous sur 127.0.0.1.\n")

    def _run_udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_sock.bind(("", self.port))
        except Exception as e:
            print(f"[ERREUR UDP] Impossible de lier le port UDP {self.port} : {e}")
            return

        while self.running:
            try:
                data, addr = udp_sock.recvfrom(1024)
                if b"BOTATA_DISCOVER" in data:
                    print(f"[UDP] Détection reçue de {addr[0]}:{addr[1]}")
                    # Réponse au client que le robot est disponible
                    response = b"BOTATA_HERE MockRobot"
                    udp_sock.sendto(response, addr)
            except Exception:
                break
        udp_sock.close()

    def _run_tcp_server(self):
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            tcp_sock.bind((self.host, self.port))
            tcp_sock.listen(1)
        except Exception as e:
            print(f"[ERREUR TCP] Impossible de lier le port TCP {self.port} : {e}")
            return

        while self.running:
            try:
                client_sock, addr = tcp_sock.accept()
                print(f"\n[TCP] Client connecté depuis {addr[0]}:{addr[1]} !")
                self.tcp_client = client_sock
                
                # Envoie immédiatement l'état initial
                self._send_state()
                
                # Écoute les commandes envoyées par le client connecté
                self._handle_client()
            except Exception:
                break
        tcp_sock.close()

    def _handle_client(self):
        buffer = ""
        while self.running and self.tcp_client:
            try:
                data = self.tcp_client.recv(1024)
                if not data:
                    print("\n[TCP] Client déconnecté.")
                    break

                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            cmd_data = json.loads(line)
                            self._process_command(cmd_data)
                        except json.JSONDecodeError:
                            print(f"[ERREUR] Commande non-JSON reçue : {line}")
            except Exception:
                break
        self.tcp_client = None

    def _process_command(self, cmd_data):
        command = cmd_data.get("command")
        print(f"[COMMANDE REÇUE] {cmd_data}")

        if command == "stop":
            print(" >> ARRET D'URGENCE DECLENCHE !")
        elif command == "move":
            direction = cmd_data.get("direction", "forward")
            speed = cmd_data.get("speed", 50)
            print(f" >> Déplacement : {direction} à {speed}% de vitesse")
        elif command == "expression":
            expr = cmd_data.get("name", "neutral")
            print(f" >> Expression du visage : {expr}")

        # Renvoyer l'état mis à jour après la commande
        self._send_state()

    def _send_state(self):
        if not self.tcp_client:
            return

        state = {
            "battery_level": self.battery_level,
            "current_color": self.current_color,
            "detected_color_name": self.color_name,
            "is_moving": False
        }

        try:
            msg = json.dumps(state) + "\n"
            self.tcp_client.sendall(msg.encode("utf-8"))
        except Exception:
            self.tcp_client = None

    def _run_simulation(self):
        colors = [
            ([255, 0, 0], "rouge"),
            ([0, 255, 0], "vert"),
            ([0, 0, 255], "bleu"),
            ([255, 255, 0], "jaune")
        ]

        while self.running:
            time.sleep(3.0)
            if self.tcp_client:
                # Simuler une baisse aléatoire de la batterie
                if random.random() < 0.1:
                    self.battery_level = max(0, self.battery_level - 1)
                    if self.battery_level <= 0:
                        self.battery_level = 100

                # Simuler un changement aléatoire de couleur détectée sur la plaque
                if random.random() < 0.2:
                    self.current_color, self.color_name = random.choice(colors)
                    print(f"[SIMULATEUR] Nouvelle couleur détectée sur plaque : {self.color_name}")

                self._send_state()


def main():
    host = "127.0.0.1"
    if len(sys.argv) > 1:
        host = sys.argv[1]

    robot = MockRobot(host=host)
    robot.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt du simulateur...")
        robot.running = False


if __name__ == "__main__":
    main()
