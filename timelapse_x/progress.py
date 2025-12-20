"""
Progress indicator system for Timelapse X.
Provides visual feedback for long-running operations.
"""

import bpy
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ========================================================================================
# Progress Data Classes
# ========================================================================================

@dataclass
class ProgressState:
    """Progress state for an operation."""
    current: int = 0
    total: int = 0
    message: str = ""
    detail: str = ""
    start_time: float = 0.0
    last_update: float = 0.0
    cancelled: bool = False
    
    @property
    def percentage(self) -> float:
        """Get percentage complete (0.0 to 1.0)."""
        if self.total <= 0:
            return 0.0
        return min(1.0, self.current / self.total)
    
    @property
    def percentage_int(self) -> int:
        """Get percentage as integer (0 to 100)."""
        return int(self.percentage * 100)
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def estimated_remaining(self) -> float:
        """Estimate remaining time in seconds."""
        if self.current <= 0 or self.total <= 0:
            return 0.0
        
        elapsed = self.elapsed_time
        rate = self.current / elapsed if elapsed > 0 else 0
        
        if rate <= 0:
            return 0.0
        
        remaining = self.total - self.current
        return remaining / rate


# ========================================================================================
# Progress Manager
# ========================================================================================

class ProgressManager:
    """
    Manages progress indicators for operations.
    
    Features:
    - Header text updates
    - Console progress bars
    - Time estimates
    - Cancellation support
    """
    
    def __init__(self):
        """Initialize progress manager."""
        self.state = ProgressState()
        self.active = False
        self.context = None
        self.area = None
        self.update_interval = 0.1  # Update UI every 100ms
    
    def start(
        self,
        context,
        total: int,
        message: str = "Processing...",
        show_header: bool = True
    ):
        """
        Start a progress operation.
        
        Args:
            context: Blender context
            total: Total number of steps
            message: Progress message
            show_header: Show progress in area header
        """
        self.state = ProgressState(
            total=total,
            message=message,
            start_time=time.time(),
            last_update=time.time()
        )
        self.active = True
        self.context = context
        
        # Find area for header updates
        if show_header:
            self.area = self._find_best_area(context)
        
        logger.info(f"Progress started: {message} (0/{total})")
    
    def update(
        self,
        current: int,
        detail: str = "",
        force: bool = False
    ) -> bool:
        """
        Update progress.
        
        Args:
            current: Current progress value
            detail: Optional detail message
            force: Force UI update even if interval not elapsed
        
        Returns:
            True to continue, False if cancelled
        """
        if not self.active:
            return True
        
        self.state.current = current
        self.state.detail = detail
        
        # Check if should update UI
        now = time.time()
        elapsed_since_update = now - self.state.last_update
        
        if force or elapsed_since_update >= self.update_interval:
            self._update_ui()
            self.state.last_update = now
        
        # Check for cancellation (ESC key)
        if self._check_cancelled():
            self.state.cancelled = True
            logger.info("Progress cancelled by user")
            return False
        
        return True
    
    def finish(self, message: str = "Complete"):
        """
        Finish progress operation.
        
        Args:
            message: Completion message
        """
        if not self.active:
            return
        
        self.state.message = message
        self.state.current = self.state.total
        
        # Final UI update
        self._update_ui()
        
        # Clear header after short delay
        if self.area:
            self.area.header_text_set(None)
        
        elapsed = self.state.elapsed_time
        logger.info(
            f"Progress complete: {message} "
            f"({self.state.total} items in {elapsed:.1f}s)"
        )
        
        self.active = False
        self.context = None
        self.area = None
    
    def cancel(self):
        """Cancel the progress operation."""
        self.state.cancelled = True
        self.finish("Cancelled")
    
    def _update_ui(self):
        """Update UI with current progress."""
        # Update header text
        if self.area:
            header_text = self._format_header()
            try:
                self.area.header_text_set(header_text)
            except (AttributeError, RuntimeError):
                self.area = None
        
        # Print console progress
        self._print_progress()
        
        # Redraw UI
        if self.context:
            try:
                for window in self.context.window_manager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()
            except (AttributeError, RuntimeError):
                pass
    
    def _format_header(self) -> str:
        """Format header text with progress info."""
        parts = [self.state.message]
        
        # Add percentage
        parts.append(f"{self.state.percentage_int}%")
        
        # Add counts
        parts.append(f"({self.state.current}/{self.state.total})")
        
        # Add time estimate
        if self.state.current > 0:
            remaining = self.state.estimated_remaining
            if remaining > 0:
                if remaining < 60:
                    parts.append(f"~{remaining:.0f}s")
                else:
                    parts.append(f"~{remaining/60:.1f}m")
        
        # Add detail
        if self.state.detail:
            parts.append(f"- {self.state.detail}")
        
        return " ".join(parts)
    
    def _print_progress(self):
        """Print progress bar to console."""
        # Only print every few updates to avoid spam
        if self.state.current % max(1, self.state.total // 20) != 0:
            if self.state.current != self.state.total:
                return
        
        # Create progress bar
        bar_width = 40
        filled = int(bar_width * self.state.percentage)
        bar = "[" + "=" * filled + ">" + " " * (bar_width - filled - 1) + "]"
        
        # Format message
        msg = f"\r{self.state.message}: {bar} {self.state.percentage_int}% "
        msg += f"({self.state.current}/{self.state.total})"
        
        if self.state.detail:
            msg += f" - {self.state.detail}"
        
        print(msg, end="" if self.state.current < self.state.total else "\n")
    
    def _find_best_area(self, context):
        """Find best area for header text."""
        # Try current area first
        if context.area:
            return context.area
        
        # Find VIEW_3D area
        try:
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        return area
        except (AttributeError, RuntimeError):
            pass
        
        return None
    
    def _check_cancelled(self) -> bool:
        """Check if user cancelled (ESC key)."""
        # Note: Proper cancellation requires modal operator
        # This is a simple check for now
        return self.state.cancelled


# Global progress manager instance
_progress_manager = ProgressManager()


# ========================================================================================
# Convenience Functions
# ========================================================================================

def start_progress(
    context,
    total: int,
    message: str = "Processing...",
    show_header: bool = True
):
    """
    Start a progress operation.
    
    Args:
        context: Blender context
        total: Total number of steps
        message: Progress message
        show_header: Show progress in area header
    
    Example:
        start_progress(context, 100, "Rendering cameras...")
        for i in range(100):
            if not update_progress(i + 1, f"Camera {i}"):
                break  # Cancelled
        finish_progress("Done!")
    """
    _progress_manager.start(context, total, message, show_header)


def update_progress(current: int, detail: str = "", force: bool = False) -> bool:
    """
    Update progress.
    
    Args:
        current: Current progress value
        detail: Optional detail message
        force: Force UI update
    
    Returns:
        True to continue, False if cancelled
    """
    return _progress_manager.update(current, detail, force)


def finish_progress(message: str = "Complete"):
    """
    Finish progress operation.
    
    Args:
        message: Completion message
    """
    _progress_manager.finish(message)


def cancel_progress():
    """Cancel the current progress operation."""
    _progress_manager.cancel()


def get_progress_state() -> ProgressState:
    """Get current progress state."""
    return _progress_manager.state


def is_progress_active() -> bool:
    """Check if progress is currently active."""
    return _progress_manager.active


# ========================================================================================
# Context Manager
# ========================================================================================

class Progress:
    """
    Context manager for progress operations.
    
    Example:
        with Progress(context, 100, "Processing") as progress:
            for i in range(100):
                if not progress.update(i + 1, f"Item {i}"):
                    break  # Cancelled
    """
    
    def __init__(
        self,
        context,
        total: int,
        message: str = "Processing...",
        show_header: bool = True
    ):
        """
        Initialize progress context.
        
        Args:
            context: Blender context
            total: Total steps
            message: Progress message
            show_header: Show in header
        """
        self.context = context
        self.total = total
        self.message = message
        self.show_header = show_header
    
    def __enter__(self):
        """Enter context."""
        start_progress(self.context, self.total, self.message, self.show_header)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        if exc_type is None:
            finish_progress("Complete")
        else:
            finish_progress("Failed")
        return False
    
    def update(self, current: int, detail: str = "", force: bool = False) -> bool:
        """Update progress."""
        return update_progress(current, detail, force)


# ========================================================================================
# Decorator
# ========================================================================================

def with_progress(message: str = "Processing...", show_header: bool = True):
    """
    Decorator to add progress tracking to a function.
    
    The decorated function must:
    - Take 'context' as first parameter
    - Yield progress updates as (current, total, detail)
    
    Example:
        @with_progress("Rendering cameras...")
        def render_cameras(context, cameras):
            for i, cam in enumerate(cameras):
                # Do work
                yield i + 1, len(cameras), cam.name
    """
    def decorator(func: Callable):
        def wrapper(context, *args, **kwargs):
            generator = func(context, *args, **kwargs)
            
            # Get first yield to determine total
            try:
                current, total, detail = next(generator)
                start_progress(context, total, message, show_header)
                
                # Continue with progress updates
                update_progress(current, detail)
                
                for current, total, detail in generator:
                    if not update_progress(current, detail):
                        break  # Cancelled
                
                finish_progress("Complete")
            
            except StopIteration:
                pass
            except Exception as e:
                finish_progress("Failed")
                raise
        
        return wrapper
    return decorator


# ========================================================================================
# Progress Bar Widget (for UI panels)
# ========================================================================================

def draw_progress_bar(layout, progress: ProgressState, width: int = 300):
    """
    Draw a progress bar in UI layout.
    
    Args:
        layout: UI layout
        progress: Progress state
        width: Width in pixels
    """
    # Main progress info
    row = layout.row()
    row.label(text=progress.message)
    row.label(text=f"{progress.percentage_int}%")
    
    # Progress bar
    box = layout.box()
    col = box.column()
    
    # Use progress bar widget if available
    if hasattr(col, 'progress'):
        col.progress(
            factor=progress.percentage,
            text=f"{progress.current}/{progress.total}",
            type='BAR'
        )
    else:
        # Fallback: text representation
        bar_width = 30
        filled = int(bar_width * progress.percentage)
        bar = "[" + "=" * filled + ">" + " " * (bar_width - filled - 1) + "]"
        col.label(text=bar)
    
    # Detail text
    if progress.detail:
        col.label(text=progress.detail, icon='INFO')
    
    # Time estimate
    if progress.current > 0:
        remaining = progress.estimated_remaining
        if remaining > 0:
            if remaining < 60:
                time_str = f"{remaining:.0f}s remaining"
            else:
                time_str = f"{remaining/60:.1f}m remaining"
            
            col.label(text=time_str, icon='TIME')


# ========================================================================================
# Recording Progress Tracking
# ========================================================================================

class RecordingProgress:
    """Progress tracking specifically for recording operations."""
    
    def __init__(self):
        """Initialize recording progress."""
        self.frame_count = 0
        self.start_time = 0.0
        self.last_capture_time = 0.0
        self.session_size_bytes = 0
    
    def start(self):
        """Start recording progress."""
        self.frame_count = 0
        self.start_time = time.time()
        self.last_capture_time = time.time()
        self.session_size_bytes = 0
    
    def add_frame(self, file_size_bytes: int = 0):
        """Add a captured frame."""
        self.frame_count += 1
        self.last_capture_time = time.time()
        self.session_size_bytes += file_size_bytes
    
    def get_stats_text(self) -> str:
        """Get formatted stats text."""
        elapsed = time.time() - self.start_time
        
        if elapsed < 60:
            duration = f"{elapsed:.0f}s"
        elif elapsed < 3600:
            duration = f"{elapsed/60:.1f}m"
        else:
            duration = f"{elapsed/3600:.1f}h"
        
        # Format size
        size_mb = self.session_size_bytes / (1024 * 1024)
        
        parts = [
            f"Frames: {self.frame_count}",
            f"Duration: {duration}",
        ]
        
        if size_mb > 0:
            parts.append(f"Size: {size_mb:.1f}MB")
        
        # Calculate FPS
        if elapsed > 0:
            fps = self.frame_count / elapsed
            parts.append(f"Rate: {fps:.2f} fps")
        
        return " | ".join(parts)
    
    def get_header_text(self, mode: str = "CAMERA_LIST") -> str:
        """Get text for area header."""
        return f"RECORDING [{mode}] - {self.get_stats_text()}"


# Global recording progress
_recording_progress = RecordingProgress()


def get_recording_progress() -> RecordingProgress:
    """Get global recording progress tracker."""
    return _recording_progress


# ========================================================================================
# Registration
# ========================================================================================

def register():
    """Register progress system."""
    logger.info("Progress system registered")


def unregister():
    """Unregister progress system."""
    # Cleanup active progress
    if _progress_manager.active:
        _progress_manager.cancel()
    
    logger.info("Progress system unregistered")