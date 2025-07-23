# camera_manager/consumers.py
import json
from channels.generic.websocket import WebsocketConsumer
# Import the global manager instance we just created
from .stream_manager import stream_manager

class CameraStreamConsumer(WebsocketConsumer):
    def connect(self):
        # Get the serial number from the URL
        self.serial_number = self.scope['url_route']['kwargs']['serial_number']
        self.accept()
        
        # Register this consumer with the manager
        stream_manager.start_stream(self.serial_number, self)

    def disconnect(self, close_code):
        # Unregister this consumer from the manager
        stream_manager.stop_stream(self.serial_number, self)

    def receive(self, text_data):
        # We don't need to handle incoming messages for this app
        pass