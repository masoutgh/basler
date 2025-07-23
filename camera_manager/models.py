from django.db import models

class Camera(models.Model):
    # A unique identifier from the camera itself
    serial_number = models.CharField(max_length=100, unique=True)
    # A user-friendly name, e.g., "Conveyor Belt Camera"
    friendly_name = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100)
    current_ip = models.GenericIPAddressField(blank=True, null=True)
    # e.g., 'Online', 'Offline'
    status = models.CharField(max_length=20, default='Offline')

    def __str__(self):
        return f"{self.friendly_name} ({self.serial_number})"

class ConfigurationProfile(models.Model):
    # Link this profile to a specific camera
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='profiles')
    # Name for the profile, e.g., "High Speed Inspection"
    name = models.CharField(max_length=100)
    # Store all camera settings (gain, exposure, etc.) as a flexible JSON object
    settings_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} for {self.camera.friendly_name}"