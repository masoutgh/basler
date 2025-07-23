# camera_manager/serializers.py
from rest_framework import serializers
from .models import Camera, ConfigurationProfile

# A lightweight serializer for nesting inside the camera list
class ProfileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationProfile
        fields = ['id', 'name', 'created_at']

# A full serializer for creating/retrieving a single profile
class ConfigurationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationProfile
        fields = ['id', 'camera', 'name', 'settings_json', 'created_at']
        read_only_fields = ['camera', 'settings_json', 'created_at']

class CameraSerializer(serializers.ModelSerializer):
    # Use the summary serializer for the nested list
    profiles = ProfileSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Camera
        fields = ['id', 'serial_number', 'friendly_name', 'model_name', 'current_ip', 'status', 'profiles']