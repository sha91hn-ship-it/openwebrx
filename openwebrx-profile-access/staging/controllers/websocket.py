from . import Controller
from owrx.websocket import WebSocketConnection
from owrx.connection import HandshakeMessageHandler


class WebSocketController(Controller):
    def indexAction(self):
        conn = WebSocketConnection(self.handler, HandshakeMessageHandler())
        conn.request = self.request
        # enter read loop
        conn.handle()
