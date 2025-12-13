"""
State management for Timelapse X addon.
"""

import time
import logging
from typing import Optional, Any, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class TimelapseState:
    timer: Optional[Any] = None
    recording: bool = False
    paused: bool = False
    counter: int = 0
    dirty: bool = True
    handler_installed: bool = False
    capture_mode: str = 'CAMERA_LIST'
    last_capture_time: float = 0.0
    session_dir: str = ""
    ignore_depsgraph: bool = False
    suppress_until: float = 0.0
    last_window_image: str = ""
    _shading_backup: List[Tuple] = field(default_factory=list)
    rr_index: int = 0
    _win_async_pending: bool = False
    
    def reset(self):
        self.recording = False
        self.paused = False
        self.counter = 0
        self.dirty = True
        self.capture_mode = 'CAMERA_LIST'
        self.last_capture_time = 0.0
        self.session_dir = ""
        self.ignore_depsgraph = False
        self.suppress_until = 0.0
        self.last_window_image = ""
        self._shading_backup.clear()
        self.rr_index = 0
        self._win_async_pending = False
    
    def is_suppressed(self) -> bool:
        return self.suppress_until > time.time()
    
    def set_suppression(self, milliseconds: int):
        self.suppress_until = time.time() + max(0.0, float(milliseconds)) / 1000.0
    
    def should_capture(self, require_dirty: bool = True) -> bool:
        if not self.recording or self.paused:
            return False
        if self.is_suppressed():
            return False
        if require_dirty and not self.dirty:
            return False
        return True
    
    def mark_captured(self):
        self.counter += 1
        self.last_capture_time = time.time()
        self.dirty = False

TLX_State = TimelapseState()

def mark_scene_dirty(scene, depsgraph):
    if TLX_State.ignore_depsgraph:
        return
    if TLX_State.is_suppressed():
        return
    TLX_State.dirty = True

def start_recording(capture_mode: str, session_dir: str):
    logger.info(f"Starting recording session: mode={capture_mode}")
    TLX_State.reset()
    TLX_State.recording = True
    TLX_State.capture_mode = capture_mode
    TLX_State.session_dir = session_dir
    TLX_State.dirty = True

def stop_recording():
    logger.info("Stopping recording session")
    TLX_State.recording = False
    TLX_State.paused = False
    TLX_State._shading_backup.clear()

def pause_recording():
    if not TLX_State.recording:
        logger.warning("Cannot pause: not recording")
        return False
    TLX_State.paused = True
    logger.info("Recording paused")
    return True

def resume_recording():
    if not TLX_State.recording:
        logger.warning("Cannot resume: not recording")
        return False
    TLX_State.paused = False
    logger.info("Recording resumed")
    return True

def is_recording() -> bool:
    return TLX_State.recording and not TLX_State.paused

def get_session_info() -> dict:
    return {
        'recording': TLX_State.recording,
        'paused': TLX_State.paused,
        'mode': TLX_State.capture_mode,
        'counter': TLX_State.counter,
        'session_dir': TLX_State.session_dir,
        'last_capture': TLX_State.last_capture_time,
    }

def backup_shading_settings(space, shading, overlay, show_gizmo):
    backup_tuple = (
        space,
        shading.type if shading else None,
        getattr(shading, 'show_xray', None) if shading else None,
        getattr(shading, 'shadow_intensity', None) if shading else None,
        overlay.show_overlays if overlay else None,
        getattr(overlay, 'show_wireframes', None) if overlay else None,
        show_gizmo,
    )
    TLX_State._shading_backup.append(backup_tuple)

def get_shading_backup() -> List[Tuple]:
    return TLX_State._shading_backup.copy()

def clear_shading_backup():
    TLX_State._shading_backup.clear()

def set_window_async_pending(pending: bool):
    TLX_State._win_async_pending = pending

def is_window_async_pending() -> bool:
    return TLX_State._win_async_pending

def register():
    logger.info("State module registered")

def unregister():
    logger.info("State module unregistered")
    TLX_State.reset()