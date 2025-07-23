import pypylon.pylon as pylon
import time
import logging
import sys

# Set up basic logging
logging.basicConfig(level=logging.INFO)

def discover_cameras():
    """Scans the network and returns a list of dictionaries with camera info."""
    tl_factory = pylon.TlFactory.GetInstance()
    devices = tl_factory.EnumerateDevices()
    found_cameras = []
    
    for device_info in devices:
        # Check if the device is a GigE camera, as only they have IP addresses
        if "GigE" in device_info.GetDeviceClass():
            ip_address = tl_factory.GetDeviceAccessibilityInfo(device_info.GetFullName()).GetAddress()
        else:
            ip_address = None # For USB or other camera types

        found_cameras.append({
            'friendly_name': device_info.GetFriendlyName(),
            'model_name': device_info.GetModelName(),
            'serial_number': device_info.GetSerialNumber(),
            'ip_address': ip_address,
        })
        
    return found_cameras


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_valid_node(node):
    return all([
        hasattr(node, "IsAvailable") and node.IsAvailable(),
        hasattr(node, "IsReadable") and node.IsReadable()
    ])

def extract_feature(node):
    try:
        feature = {"name": node.GetName(), "type": "Unknown", "value": None, "details": {}}

        if pylon.IInteger.IsImplementedBy(node):
            feature["type"] = "Integer"
            feature["value"] = node.GetValue()
            feature["details"] = {"min": node.GetMin(), "max": node.GetMax()}
        elif pylon.IFloat.IsImplementedBy(node):
            feature["type"] = "Float"
            feature["value"] = node.GetValue()
            feature["details"] = {"min": node.GetMin(), "max": node.GetMax()}
        elif pylon.IEnumeration.IsImplementedBy(node):
            feature["type"] = "Enum"
            feature["value"] = node.GetCurrentEntry().GetSymbolic()
            entries = [entry.GetSymbolic() for entry in node.GetEntries()
                       if hasattr(entry, 'IsAvailable') and entry.IsAvailable()]
            feature["details"] = {"options": entries}
        elif pylon.IBoolean.IsImplementedBy(node):
            feature["type"] = "Boolean"
            feature["value"] = node.GetValue()
        else:
            return None
        return feature
    except Exception as e:
        logging.warning(f"Failed to extract feature from node {node.GetName()}: {e}")
        return None

def get_camera_features(serial_number):
    logging.info(f"Attempting to get features for camera SN: {serial_number}")
    try:
        tl_factory = pylon.TlFactory.GetInstance()
        info = pylon.CDeviceInfo()
        info.SetSerialNumber(serial_number)
        camera = pylon.InstantCamera(tl_factory.CreateDevice(info))
        camera.Open()
        logging.info(f"Successfully opened camera SN: {serial_number}")

        nodemap = camera.GetNodeMap()
        features_list = []

        for node_name in nodemap.GetNodeNames():
            node = nodemap.GetNode(node_name)
            if node is None or not is_valid_node(node):
                continue
            feature = extract_feature(node)
            if feature:
                features_list.append(feature)

        camera.Close()
        logging.info(f"Successfully retrieved {len(features_list)} features for SN: {serial_number}")
        return features_list

    except pylon.GenericException as e:
        logging.error(f"PYLON_ERROR for SN {serial_number}: {e.GetDescription()}")
        raise Exception(f"Pylon-Error: {e.GetDescription()}")
    except Exception as e:
        logging.error(f"GENERAL_ERROR for SN {serial_number}: {e}")
        raise Exception(f"A general error occurred: {e}")
    
def apply_configuration(serial_number, settings_dict):
    """
    Applies a dictionary of settings to a camera by dynamically finding each feature.
    
    Example settings_dict: {"Gain": 15.0, "PixelFormat": "Mono8", "ReverseX": True}
    """
    try:
        tl_factory = pylon.TlFactory.GetInstance()
        info = pylon.CDeviceInfo()
        info.SetSerialNumber(serial_number)
        camera = pylon.InstantCamera(tl_factory.CreateDevice(info))
        camera.Open()
        nodemap = camera.GetNodeMap()

        for feature_name, new_value in settings_dict.items():
            node = nodemap.GetNode(feature_name)
            if pylon.IsWritable(node):
                # This dynamically sets the value regardless of feature type
                node.SetValue(new_value)
        
        camera.Close()
        return True, "Settings applied successfully."
    except Exception as e:
        return False, str(e)


def start_grabbing_frames(serial_number, frame_queue):
    """Grabs frames from a camera and puts them in a queue."""
    # This function will run in a separate thread managed by the consumer.
    try:
        tl_factory = pylon.TlFactory.GetInstance()
        camera = pylon.InstantCamera(tl_factory.CreateDevice(pylon.CDeviceInfo().SetSerialNumber(serial_number)))
        camera.Open()

        # Set camera to continuous frame acquisition
        camera.StartGrabbing(pylon.GrabStrategy_LatestOneOnly)
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        while camera.IsGrabbing():
            grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grab_result.GrabSucceeded():
                image = converter.Convert(grab_result)
                frame = image.GetArray()
                # Put the frame into the queue for the WebSocket to send
                frame_queue.put(frame)

            grab_result.Release()
            time.sleep(0.03) # Adjust for desired frame rate

        camera.Close()
    except Exception as e:
        logging.error(f"Error in grabbing frames for {serial_number}: {e}")
        frame_queue.put(None) # Signal error/end