"""
Camera scheduling logic for Timelapse X addon.
"""

import time
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Inline constants for consolidated file
MIN_INTERVAL = 0.2
DEFAULT_INTERVAL = 2.0
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')

def init_camera_schedulers(scene, base_dir: str, prefs):
    now = time.time()
    
    default_interval = DEFAULT_INTERVAL
    if prefs:
        default_interval = max(MIN_INTERVAL, float(getattr(prefs, 'default_interval', DEFAULT_INTERVAL)))
    
    scene_interval = getattr(scene, 'tlx_capture_interval', None)
    if scene_interval is not None:
        default_interval = max(MIN_INTERVAL, float(scene_interval))
    
    for camera_item in scene.tlx_cameras:
        camera = camera_item.camera
        
        if not camera or camera.type != 'CAMERA':
            continue
        
        import re
        camera_name = re.sub(r'[^A-Za-z0-9_\-]+', '_', camera.name)
        camera_dir = os.path.join(base_dir, f"CAM_{camera_name}")
        os.makedirs(camera_dir, exist_ok=True)
        
        try:
            existing_images = [
                f for f in os.listdir(camera_dir)
                if f.lower().endswith(IMAGE_EXTENSIONS)
            ]
            start_index = len(existing_images)
        except OSError as e:
            logger.warning(f"Cannot read camera dir {camera_dir}: {e}")
            start_index = 0
        
        camera_item["_tlx_idx"] = start_index
        
        if camera_item.use_interval_override:
            interval = float(camera_item.interval_override)
        else:
            interval = default_interval
        
        interval = max(MIN_INTERVAL, interval)
        
        camera_item["_tlx_itv"] = interval
        camera_item["_tlx_last"] = 0.0
        camera_item["_tlx_due"] = now

def pick_due_cameras(scene, prefs, round_robin: bool = False) -> List[int]:
    now = time.time()
    
    if round_robin:
        num_cameras = len(scene.tlx_cameras)
        if num_cameras == 0:
            return []
        
        # Need state - using simple approach
        start_index = 0  # In real code, use state.TLX_State.rr_index
        
        for offset in range(num_cameras):
            index = (start_index + offset) % num_cameras
            camera_item = scene.tlx_cameras[index]
            
            due_time = float(camera_item.get("_tlx_due", 0.0))
            
            if now >= due_time:
                return [index]
        
        return []
    
    else:
        due_indices = []
        
        for index, camera_item in enumerate(scene.tlx_cameras):
            due_time = float(camera_item.get("_tlx_due", 0.0))
            
            if now >= due_time:
                due_indices.append(index)
        
        return due_indices

def update_camera_due(camera_item, now: Optional[float] = None):
    if now is None:
        now = time.time()
    
    interval = float(camera_item.get("_tlx_itv", DEFAULT_INTERVAL))
    interval = max(MIN_INTERVAL, interval)
    
    camera_item["_tlx_last"] = now
    camera_item["_tlx_due"] = now + interval
    
    current_index = int(camera_item.get("_tlx_idx", 0))
    camera_item["_tlx_idx"] = current_index + 1

def compute_min_timer_interval(scene, prefs) -> float:
    default_interval = DEFAULT_INTERVAL
    
    if prefs:
        default_interval = float(getattr(prefs, 'default_interval', DEFAULT_INTERVAL))
    
    scene_interval = getattr(scene, 'tlx_capture_interval', None)
    if scene_interval is not None:
        default_interval = float(scene_interval)
    
    min_interval = max(MIN_INTERVAL, default_interval)
    
    for camera_item in scene.tlx_cameras:
        if camera_item.use_interval_override:
            interval = float(camera_item.interval_override)
            
            if interval >= MIN_INTERVAL and interval < min_interval:
                min_interval = interval
    
    return max(MIN_INTERVAL, min_interval)

def register():
    logger.info("Scheduler module registered")

def unregister():
    logger.info("Scheduler module unregistered")
