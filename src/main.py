import uasyncio as asyncio
from stripalerts.app import App

if __name__ == "__main__":
    app = App()
    asyncio.run(app.start())

