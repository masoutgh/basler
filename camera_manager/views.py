from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Camera, ConfigurationProfile
from .serializers import CameraSerializer, ConfigurationProfileSerializer
from . import camera_interface

# --- View to serve the HTML shell for our single-page app ---
def index(request):
    """
    Serves the main single-page application shell (index.html).
    """
    return render(request, 'camera_manager/index.html')


# --- API ViewSets for the backend ---

class CameraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    lookup_field = 'serial_number'

    @action(detail=False, methods=['post'])
    def scan(self, request):
        # This function remains the same
        found_cameras = camera_interface.discover_cameras()
        found_serials = {cam['serial_number'] for cam in found_cameras}
        for cam_data in found_cameras:
            Camera.objects.update_or_create(
                serial_number=cam_data['serial_number'],
                defaults={'model_name': cam_data['model_name'], 'current_ip': cam_data.get('ip_address'), 'status': 'Online'}
            )
        Camera.objects.exclude(serial_number__in=found_serials).update(status='Offline')
        return Response({'status': 'Scan complete'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def features(self, request, serial_number=None):
        """
        Gets features for a camera.
        If online, gets live features.
        If offline, gets features from the last saved profile.
        """
        try:
            # Try to get live features first
            live_features = camera_interface.get_camera_features(serial_number)
            return Response({
                "status": "online",
                "features": live_features
            })
        except Exception:
            # If it fails, camera is likely offline. Try to find the last saved profile.
            camera = self.get_object()
            last_profile = camera.profiles.order_by('-created_at').first()
            
            if last_profile:
                # Convert the saved JSON into the same list format as live features
                stale_features = [{'name': name, 'value': value} for name, value in last_profile.settings_json.items()]
                return Response({
                    "status": "offline",
                    "message": f"Camera is offline. Showing settings from profile '{last_profile.name}'.",
                    "features": stale_features
                })
            else:
                # Camera is offline and has no saved profiles
                return Response({
                    "status": "offline",
                    "message": "Camera is offline and has no saved configurations.",
                    "features": []
                }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def save_profile(self, request, serial_number=None):
        """Saves the camera's current settings as a new named profile."""
        camera = self.get_object()
        profile_name = request.data.get('name')
        if not profile_name:
            return Response({'error': 'Profile name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            current_features = camera_interface.get_camera_features(serial_number)
            settings_dict = {feature['name']: feature['value'] for feature in current_features}
            profile = ConfigurationProfile.objects.create(
                camera=camera, name=profile_name, settings_json=settings_dict
            )
            # Use the full serializer for the response
            serializer = ConfigurationProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': f"Could not save profile. Is the camera online? Error: {e}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class ConfigurationProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing configuration profiles.
    """
    queryset = ConfigurationProfile.objects.all()
    serializer_class = ConfigurationProfileSerializer

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Applies this profile's settings to its camera."""
        profile = self.get_object()
        success, message = camera_interface.apply_configuration(
            profile.camera.serial_number, profile.settings_json
        )
        if success:
            return Response({'status': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)