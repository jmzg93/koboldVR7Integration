class WebSocketService:
    def __init__(self, websocket_client):
        self.client = websocket_client

    async def start(self):
        await self.client.connect()

    async def stop(self):
        await self.client.disconnect()
