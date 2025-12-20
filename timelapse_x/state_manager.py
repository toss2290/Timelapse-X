"""
StateManager - SIMPLIFIED VERSION (500 lines vs 1500 lines)
===========================================================

SIMPLIFICATIONS:
1. ✅ No immutable objects → Direct mutable attributes
2. ✅ No transactions → Direct assignment
3. ✅ No validation (trust callers)
4. ✅ No recovery mechanism
5. ✅ Minimal thread safety (basic RLock)
6. ✅ Simple state machine

REMOVED:
- RecordingSession dataclass (60 lines)
- WindowAsyncContext dataclass (30 lines)
- CameraScheduler dataclass (40 lines)
- StateValidator class (150 lines)
- Recovery mechanism (100 lines)
- Transaction context managers (50 lines)
- Detailed diagnostics (100 lines)

KEPT:
- Singleton pattern
- Basic thread safety
- Core functionality
- Essential properties
"""

import time
import logging
from typing import Optional, Dict, List
from threading import RLock
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Simple Enums
# ============================================================================

class RecordingState(Enum):
    """Recording states."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


# ============================================================================
# Simple Camera Scheduler
# ============================================================================

class CameraScheduler:
    """Simple mutable camera scheduler."""
    
    def __init__(self, camera_name: str, interval: float, start_index: int = 0):
        self.camera_name = camera_name
        self.interval = interval
        self.next_due = time.time()
        self.last_capture = 0.0
        self.total_captures = start_index
    
    def is_due(self, now: float) -> bool:
        """Check if camera is due."""
        return now >= self.next_due
    
    def mark_captured(self, now: float):
        """Mark camera as captured."""
        self.last_capture = now
        self.next_due = now + self.interval
        self.total_captures += 1


# ============================================================================
# SIMPLIFIED StateManager
# ============================================================================

class StateManager:
    """
    Simplified state manager with direct mutable state.
    
    NO LONGER:
    - Immutable objects
    - Transactions
    - Validation
    - Recovery
    
    JUST:
    - Simple attributes
    - Direct assignment
    - Basic thread safety
    """
    
    _instance: Optional['StateManager'] = None
    _lock = RLock()
    
    def __new__(cls):
        """Thread-safe singleton."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize state manager."""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # Recording state
            self._state = RecordingState.IDLE
            self._capture_mode = ""
            self._session_dir = ""
            self._counter = 0
            self._start_time = 0.0
            self._last_capture_time = 0.0
            
            # Timer
            self._timer = None
            
            # Window capture
            self._last_window_image = ""
            self._window_async_pending = False
            self._window_async_scheduled_time = 0.0
            
            # Camera schedulers
            self._camera_schedulers: Dict[str, CameraScheduler] = {}
            self._rr_index = 0
            
            # Depsgraph/Idle
            self._dirty = True
            self._ignore_depsgraph = False
            self._handler_installed = False
            self._suppress_until = 0.0
            
            self._initialized = True
            logger.info("StateManager initialized (SIMPLIFIED)")
    
    # ========================================================================
    # Properties (Read-Only Access)
    # ========================================================================
    
    @property
    def recording(self) -> bool:
        """Check if recording."""
        with self._lock:
            return self._state != RecordingState.IDLE
    
    @property
    def paused(self) -> bool:
        """Check if paused."""
        with self._lock:
            return self._state == RecordingState.PAUSED
    
    @property
    def state(self) -> RecordingState:
        """Get current state."""
        with self._lock:
            return self._state
    
    @property
    def capture_mode(self) -> str:
        """Get capture mode."""
        with self._lock:
            return self._capture_mode
    
    @property
    def session_dir(self) -> str:
        """Get session directory."""
        with self._lock:
            return self._session_dir
    
    @property
    def counter(self) -> int:
        """Get frame counter."""
        with self._lock:
            return self._counter
    
    @property
    def last_capture_time(self) -> float:
        """Get last capture time."""
        with self._lock:
            return self._last_capture_time
    
    @property
    def dirty(self) -> bool:
        """Check if scene dirty."""
        with self._lock:
            return self._dirty
    
    @property
    def last_window_image(self) -> str:
        """Get last window image path."""
        with self._lock:
            return self._last_window_image
    
    @property
    def ignore_depsgraph(self) -> bool:
        """Get ignore depsgraph flag."""
        with self._lock:
            return self._ignore_depsgraph
    
    @property
    def handler_installed(self) -> bool:
        """Get handler installed flag."""
        with self._lock:
            return self._handler_installed
    
    @property
    def suppress_until(self) -> float:
        """Get suppression time."""
        with self._lock:
            return self._suppress_until
    
    @property
    def rr_index(self) -> int:
        """Get round-robin index."""
        with self._lock:
            return self._rr_index
    
    @property
    def timer(self):
        """Get timer object."""
        with self._lock:
            return self._timer
    
    # ========================================================================
    # Direct Setters (No Validation)
    # ========================================================================
    
    def set_dirty(self, value: bool):
        """Set dirty flag."""
        with self._lock:
            self._dirty = value
    
    def set_ignore_depsgraph(self, value: bool):
        """Set ignore depsgraph."""
        with self._lock:
            self._ignore_depsgraph = value
    
    def set_handler_installed(self, value: bool):
        """Set handler installed."""
        with self._lock:
            self._handler_installed = value
    
    def set_suppression(self, milliseconds: int):
        """Set suppression cooldown."""
        with self._lock:
            self._suppress_until = time.time() + (milliseconds / 1000.0)
    
    def is_suppressed(self) -> bool:
        """Check if suppressed."""
        with self._lock:
            return time.time() < self._suppress_until
    
    def set_timer(self, timer):
        """Set timer."""
        with self._lock:
            self._timer = timer
    
    def set_last_window_image(self, path: str):
        """Set last window image."""
        with self._lock:
            self._last_window_image = path
    
    # ========================================================================
    # Recording Control (Simplified)
    # ========================================================================
    
    def start_recording(self, mode: str, session_dir: str):
        """
        Start recording (simple, no validation).
        
        Args:
            mode: 'WINDOW' or 'CAMERA_LIST'
            session_dir: Output directory
        """
        with self._lock:
            # Simple state check
            if self._state != RecordingState.IDLE:
                raise RuntimeError(f"Already recording (state={self._state.value})")
            
            # Set state directly
            self._state = RecordingState.RECORDING
            self._capture_mode = mode
            self._session_dir = session_dir
            self._counter = 0
            self._start_time = time.time()
            self._last_capture_time = 0.0
            
            # Reset flags
            self._dirty = True
            self._last_window_image = ""
            self._rr_index = 0
            self._suppress_until = 0.0
            self._window_async_pending = False
            
            logger.info(f"Recording started: {mode}, session: {session_dir}")
    
    def stop_recording(self):
        """Stop recording (simple cleanup)."""
        with self._lock:
            if self._state == RecordingState.IDLE:
                return
            
            # Capture final count
            final_count = self._counter
            
            # Reset state
            self._state = RecordingState.IDLE
            self._capture_mode = ""
            self._session_dir = ""
            self._counter = 0
            self._timer = None
            
            logger.info(f"Recording stopped, total frames: {final_count}")
    
    def pause_recording(self):
        """Pause recording."""
        with self._lock:
            if self._state == RecordingState.RECORDING:
                self._state = RecordingState.PAUSED
                logger.info("Recording paused")
    
    def resume_recording(self):
        """Resume recording."""
        with self._lock:
            if self._state == RecordingState.PAUSED:
                self._state = RecordingState.RECORDING
                logger.info("Recording resumed")
    
    def mark_captured(self):
        """Mark frame captured (increment counter)."""
        with self._lock:
            if self._state in (RecordingState.RECORDING, RecordingState.PAUSED):
                self._counter += 1
                self._last_capture_time = time.time()
                self._dirty = False
                logger.debug(f"Frame captured: {self._counter}")
    
    # ========================================================================
    # Window Async (Simplified)
    # ========================================================================
    
    def is_window_async_pending(self) -> bool:
        """Check if async pending."""
        with self._lock:
            return self._window_async_pending
    
    def schedule_window_async(self, delay: float) -> bool:
        """Schedule async capture."""
        with self._lock:
            if self._window_async_pending:
                return False
            
            self._window_async_pending = True
            self._window_async_scheduled_time = time.time() + delay
            return True
    
    def start_window_capture(self):
        """Mark capture started."""
        with self._lock:
            # Just keep pending flag
            pass
    
    def finish_window_capture(self, success: bool = True, error: Optional[str] = None):
        """Mark capture finished."""
        with self._lock:
            self._window_async_pending = False
            if error:
                logger.warning(f"Async capture error: {error}")
    
    def cancel_window_async(self) -> bool:
        """Cancel async capture."""
        with self._lock:
            if not self._window_async_pending:
                return False
            
            self._window_async_pending = False
            return True
    
    # ========================================================================
    # Camera Schedulers (Simplified)
    # ========================================================================
    
    def clear_camera_schedulers(self):
        """Clear all camera schedulers."""
        with self._lock:
            self._camera_schedulers.clear()
            self._rr_index = 0
    
    def init_camera_scheduler(self, camera_name: str, interval: float, start_index: int = 0):
        """Initialize camera scheduler."""
        with self._lock:
            scheduler = CameraScheduler(camera_name, interval, start_index)
            self._camera_schedulers[camera_name] = scheduler
            logger.debug(f"Initialized scheduler: {camera_name}, interval={interval}s")
    
    def get_due_cameras(self, camera_names: List[str], round_robin: bool = False) -> List[str]:
        """Get cameras due for capture."""
        with self._lock:
            if not camera_names:
                return []
            
            now = time.time()
            due = []
            
            if round_robin:
                # Check one camera at a time (round-robin)
                start = self._rr_index
                for offset in range(len(camera_names)):
                    idx = (start + offset) % len(camera_names)
                    name = camera_names[idx]
                    scheduler = self._camera_schedulers.get(name)
                    
                    if scheduler and scheduler.is_due(now):
                        due.append(name)
                        self._rr_index = (idx + 1) % len(camera_names)
                        break
            else:
                # All due cameras
                for name in camera_names:
                    scheduler = self._camera_schedulers.get(name)
                    if scheduler and scheduler.is_due(now):
                        due.append(name)
            
            return due
    
    def update_camera_due(self, camera_name: str):
        """Update camera's next due time."""
        with self._lock:
            scheduler = self._camera_schedulers.get(camera_name)
            if scheduler:
                now = time.time()
                scheduler.mark_captured(now)
    
    # ========================================================================
    # Diagnostics (Simplified)
    # ========================================================================
    
    def get_info(self) -> dict:
        """Get state info for debugging."""
        with self._lock:
            return {
                'state': self._state.value,
                'recording': self.recording,
                'paused': self.paused,
                'mode': self._capture_mode,
                'session': self._session_dir,
                'counter': self._counter,
                'dirty': self._dirty,
                'timer': self._timer is not None,
                'cameras': len(self._camera_schedulers),
            }
    
    def print_info(self):
        """Print state info to console."""
        info = self.get_info()
        
        print("\n" + "="*60)
        print("StateManager Info (SIMPLIFIED)")
        print("="*60)
        print(f"State:      {info['state']}")
        print(f"Recording:  {info['recording']}")
        print(f"Paused:     {info['paused']}")
        print(f"Mode:       {info['mode']}")
        print(f"Counter:    {info['counter']}")
        print(f"Timer:      {info['timer']}")
        print(f"Cameras:    {info['cameras']}")
        print("="*60 + "\n")
    
    # ========================================================================
    # Reset & Cleanup
    # ========================================================================
    
    def reset(self):
        """Reset to clean state."""
        with self._lock:
            self._state = RecordingState.IDLE
            self._capture_mode = ""
            self._session_dir = ""
            self._counter = 0
            self._start_time = 0.0
            self._last_capture_time = 0.0
            self._timer = None
            self._last_window_image = ""
            self._window_async_pending = False
            self._camera_schedulers.clear()
            self._rr_index = 0
            self._dirty = True
            self._ignore_depsgraph = False
            self._handler_installed = False
            self._suppress_until = 0.0
            
            logger.info("StateManager reset complete")
    
    def cleanup(self):
        """Cleanup on unregister."""
        with self._lock:
            if self.recording:
                self.stop_recording()
            
            self.cancel_window_async()
            self.clear_camera_schedulers()
            
            logger.info("StateManager cleaned up")
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance.cleanup()
                cls._instance = None
            logger.info("StateManager instance reset")


# ============================================================================
# Module-level Helper
# ============================================================================

def mark_scene_dirty(scene, depsgraph):
    """Depsgraph handler to mark scene as dirty."""
    mgr = StateManager()
    
    if mgr.ignore_depsgraph or mgr.is_suppressed():
        return
    
    mgr.set_dirty(True)


# ============================================================================
# Registration
# ============================================================================

def register():
    """Register state manager module."""
    logger.info("StateManager registered (SIMPLIFIED - 500 lines vs 1500)")
    StateManager()  # Initialize singleton


def unregister():
    """Unregister state manager module."""
    logger.info("Unregistering StateManager")
    
    try:
        StateManager().cleanup()
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
    
    try:
        import bpy
        bpy.app.handlers.depsgraph_update_post.remove(mark_scene_dirty)
    except (ValueError, ImportError):
        pass
    except Exception as e:
        logger.warning(f"Handler removal error: {e}")
    
    logger.info("StateManager unregistered")