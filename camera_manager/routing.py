from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/camera_stream/<str:serial_number>/', consumers.CameraStreamConsumer.as_asgi()),
]