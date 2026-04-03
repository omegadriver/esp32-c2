import asyncio
import serial_asyncio
import datetime
import socket

PORT = "COM5"
BAUD = 115200

class SerialProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        print("Porta serial aberta")

    def data_received(self, data):
        msg = data.decode(errors="ignore").strip()
        print(f"ESP32: {msg}")

        if msg == "PRONTO":
            heartbeat = self._build_heartbeat()
            print(f"Enviando: {heartbeat}")
            self.transport.write(f"{heartbeat}\n".encode())

    def _build_heartbeat(self):
        hostname = socket.gethostname()
        dt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"//{hostname}-{dt}"

    def connection_lost(self, exc):
        print("Porta serial fechada")
        asyncio.get_event_loop().stop()

async def main():
    loop = asyncio.get_event_loop()
    await serial_asyncio.create_serial_connection(
        loop, SerialProtocol, PORT, baudrate=BAUD
    )
    await asyncio.sleep(9999)

asyncio.run(main())
