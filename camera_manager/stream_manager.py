import threading
import time
import logging
import cv2
import base64
import json
import pypylon.pylon as pylon

class CameraStreamManager:
    def __init__(self):
        self._streams = {}
        self._lock = threading.Lock()

    def start_stream(self, serial_number, consumer):
        with self._lock:
            if serial_number not in self._streams:
                self._streams[serial_number] = self._StreamHandler(serial_number)
                self._streams[serial_number].start()
            self._streams[serial_number].add_consumer(consumer)

    def stop_stream(self, serial_number, consumer):
        with self._lock:
            if serial_number in self._streams:
                handler = self._streams[serial_number]
                handler.remove_consumer(consumer)
                if handler.get_consumer_count() == 0:
                    handler.stop()
                    del self._streams[serial_number]

    class _StreamHandler:
        def __init__(self, serial_number):
            self.serial_number = serial_number
            self._consumers = set()
            self._lock = threading.Lock()
            self._thread = None
            self._is_running = False

        def get_consumer_count(self):
            return len(self._consumers)

        def add_consumer(self, consumer):
            with self._lock:
                self._consumers.add(consumer)
            logging.info(f"[{self.serial_number}] Consumer joined. Total: {self.get_consumer_count()}.")

        def remove_consumer(self, consumer):
            with self._lock:
                self._consumers.discard(consumer)
            logging.info(f"[{self.serial_number}] Consumer left. Total: {self.get_consumer_count()}.")

        def start(self):
            if self._is_running: return
            self._is_running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logging.info(f"[{self.serial_number}] Stream thread started.")

        def stop(self):
            self._is_running = False
            if self._thread: self._thread.join()
            logging.info(f"[{self.serial_number}] Stream thread stopped.")

        def _run(self):
            camera = None
            try:
                tl_factory = pylon.TlFactory.GetInstance()
                camera = pylon.InstantCamera(tl_factory.CreateDevice(pylon.CDeviceInfo().SetSerialNumber(self.serial_number)))
                camera.Open()
                camera.StartGrabbing(pylon.GrabStrategy_LatestOneOnly)
                converter = pylon.ImageFormatConverter()
                converter.OutputPixelFormat = pylon.PixelType_BGR8packed

                while self._is_running and camera.IsGrabbing():
                    try:
                        grab_result = camera.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
                        if not grab_result.GrabSucceeded(): continue
                        
                        image = converter.Convert(grab_result).GetArray()
                        grab_result.Release()
                        
                        ret, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if not ret: continue
                        
                        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                        payload = json.dumps({'image': jpg_as_text})

                        with self._lock:
                            for consumer in self._consumers:
                                consumer.send(text_data=payload)
                        
                        time.sleep(0.033) # ~30fps
                    except pylon.TimeoutException:
                        logging.warning(f"[{self.serial_number}] Frame grab timeout.")
                        continue
            except Exception as e:
                logging.error(f"[{self.serial_number}] FATAL STREAM ERROR: {e}")
            finally:
                if camera and camera.IsOpen(): camera.Close()
                logging.info(f"[{self.serial_number}] Camera connection closed.")
                # If there was a fatal error, we should inform any remaining clients
                with self._lock:
                    for consumer in self._consumers:
                        consumer.close(code=4000)

stream_manager = CameraStreamManager()