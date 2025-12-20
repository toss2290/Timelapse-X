"""
Thread Safety Module for Timelapse X - BLENDER API MAIN THREAD ENFORCEMENT

CRITICAL: Blender API is NOT thread-safe!
All bpy.* calls MUST happen from the main thread.

This module provides:
1. Thread detection and validation
2. Main thread queue for cross-thread communication
3. Safe wrappers for Blender API calls
4. Decorators for automatic thread safety
5. Modal executor for deferred execution

USAGE:
    from thread_safety import ensure_main_thread, run_in_main_thread
    
    @ensure_main_thread
    def my_blender_function():
        bpy.ops.mesh.primitive_cube_add()  # Safe!
    
    # Or explicit:
    def my_function():
        if not is_main_thread():
            return run_in_main_thread(my_function)
        # Execute normally
"""

import bpy
import threading
import queue
import logging
import time
import functools
from typing import Callable, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ========================================================================================
# Thread Detection
# ========================================================================================

# Store main thread ID at module load time
_MAIN_THREAD_ID: Optional[int] = None
_MAIN_THREAD_IDENT: Optional[int] = None


def _initialize_main_thread():
    """
    Initialize main thread identification.
    
    MUST be called from main thread during addon registration.
    """
    global _MAIN_THREAD_ID, _MAIN_THREAD_IDENT
    
    _MAIN_THREAD_ID = threading.get_ident()
    _MAIN_THREAD_IDENT = threading.current_thread().ident
    
    logger.info(
        f"Main thread initialized: ID={_MAIN_THREAD_ID}, "
        f"Ident={_MAIN_THREAD_IDENT}"
    )


def is_main_thread() -> bool:
    """
    Check if currently running on main thread.
    
    Returns:
        True if main thread, False otherwise
    """
    if _MAIN_THREAD_ID is None:
        # Not initialized - assume main thread and initialize
        _initialize_main_thread()
        return True
    
    current_ident = threading.get_ident()
    return current_ident == _MAIN_THREAD_ID


def get_current_thread_info() -> dict:
    """
    Get information about current thread.
    
    Returns:
        Dictionary with thread information
    """
    current = threading.current_thread()
    
    return {
        'name': current.name,
        'ident': current.ident,
        'daemon': current.daemon,
        'is_alive': current.is_alive(),
        'is_main': is_main_thread(),
        'main_thread_id': _MAIN_THREAD_ID,
    }


def require_main_thread(function_name: str = "operation"):
    """
    Raise exception if not on main thread.
    
    Args:
        function_name: Name of function for error message
    
    Raises:
        RuntimeError: If not on main thread
    """
    if not is_main_thread():
        thread_info = get_current_thread_info()
        raise RuntimeError(
            f"THREAD SAFETY VIOLATION: {function_name} called from "
            f"non-main thread '{thread_info['name']}' "
            f"(ident={thread_info['ident']}). "
            f"Blender API calls MUST be on main thread "
            f"(ident={_MAIN_THREAD_ID})."
        )


# ========================================================================================
# Task Queue System
# ========================================================================================

class TaskPriority(Enum):
    """Priority levels for queued tasks."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class QueuedTask:
    """
    A task to be executed on main thread.
    """
    func: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    result_queue: Optional[queue.Queue]
    task_id: str
    created_at: float
    timeout: float
    
    def execute(self) -> Tuple[bool, Any, Optional[Exception]]:
        """
        Execute the task.
        
        Returns:
            Tuple of (success, result, exception)
        """
        try:
            result = self.func(*self.args, **self.kwargs)
            return True, result, None
        except Exception as e:
            logger.error(f"Task {self.task_id} failed: {e}", exc_info=True)
            return False, None, e
    
    def is_expired(self) -> bool:
        """Check if task has expired."""
        if self.timeout <= 0:
            return False
        return time.time() - self.created_at > self.timeout


class MainThreadQueue:
    """
    Thread-safe queue for executing tasks on main thread.
    
    USAGE:
        queue = MainThreadQueue()
        
        # From any thread:
        result = queue.enqueue(my_function, arg1, arg2, kwarg=value)
        
        # From main thread (in modal operator or timer):
        queue.process_tasks()
    """
    
    def __init__(self):
        """Initialize queue."""
        self._queue = queue.PriorityQueue()
        self._task_counter = 0
        self._lock = threading.Lock()
        self._stats = {
            'enqueued': 0,
            'executed': 0,
            'failed': 0,
            'expired': 0,
        }
    
    def enqueue(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        wait: bool = True,
        timeout: float = 5.0,
        **kwargs
    ) -> Any:
        """
        Enqueue a function to be executed on main thread.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            priority: Task priority
            wait: If True, block until result available
            timeout: Timeout in seconds
            **kwargs: Keyword arguments
        
        Returns:
            Result of function execution (if wait=True)
        
        Raises:
            TimeoutError: If wait=True and timeout exceeded
            RuntimeError: If execution failed
        """
        # Check if already on main thread
        if is_main_thread():
            # Execute immediately
            return func(*args, **kwargs)
        
        # Create result queue if waiting
        result_queue = queue.Queue() if wait else None
        
        # Create task
        with self._lock:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}"
        
        task = QueuedTask(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            result_queue=result_queue,
            task_id=task_id,
            created_at=time.time(),
            timeout=timeout
        )
        
        # Enqueue with priority (lower number = higher priority)
        priority_value = 3 - priority.value  # Invert for PriorityQueue
        self._queue.put((priority_value, task))
        
        with self._lock:
            self._stats['enqueued'] += 1
        
        logger.debug(
            f"Enqueued {task_id}: {func.__name__}, "
            f"priority={priority.name}, wait={wait}"
        )
        
        # Wait for result if requested
        if wait:
            try:
                success, result, exception = result_queue.get(timeout=timeout)
                
                if success:
                    return result
                else:
                    raise RuntimeError(
                        f"Task {task_id} failed: {exception}"
                    ) from exception
            
            except queue.Empty:
                raise TimeoutError(
                    f"Task {task_id} timed out after {timeout}s"
                )
        
        return None
    
    def process_tasks(self, max_tasks: int = 10) -> int:
        """
        Process queued tasks (MUST be called from main thread).
        
        Args:
            max_tasks: Maximum number of tasks to process
        
        Returns:
            Number of tasks processed
        
        Raises:
            RuntimeError: If not on main thread
        """
        require_main_thread("process_tasks")
        
        processed = 0
        
        while processed < max_tasks and not self._queue.empty():
            try:
                # Get task (non-blocking)
                priority_value, task = self._queue.get_nowait()
            except queue.Empty:
                break
            
            # Check if expired
            if task.is_expired():
                logger.warning(f"Task {task.task_id} expired, skipping")
                
                if task.result_queue:
                    task.result_queue.put((
                        False,
                        None,
                        TimeoutError("Task expired in queue")
                    ))
                
                with self._lock:
                    self._stats['expired'] += 1
                
                processed += 1
                continue
            
            # Execute task
            success, result, exception = task.execute()
            
            # Update stats
            with self._lock:
                if success:
                    self._stats['executed'] += 1
                else:
                    self._stats['failed'] += 1
            
            # Send result if waiting
            if task.result_queue:
                task.result_queue.put((success, result, exception))
            
            processed += 1
        
        return processed
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                **self._stats,
                'pending': self._queue.qsize(),
            }
    
    def clear(self):
        """Clear all pending tasks."""
        require_main_thread("clear")
        
        cleared = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                cleared += 1
            except queue.Empty:
                break
        
        logger.info(f"Cleared {cleared} pending tasks")
        return cleared


# Global queue instance
_main_thread_queue = MainThreadQueue()


def get_main_thread_queue() -> MainThreadQueue:
    """Get global main thread queue."""
    return _main_thread_queue


# ========================================================================================
# Convenience Functions
# ========================================================================================

def run_in_main_thread(
    func: Callable,
    *args,
    wait: bool = True,
    timeout: float = 5.0,
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs
) -> Any:
    """
    Run function in main thread.
    
    Convenience wrapper for queue.enqueue().
    
    Args:
        func: Function to execute
        *args: Positional arguments
        wait: Block until complete
        timeout: Timeout in seconds
        priority: Task priority
        **kwargs: Keyword arguments
    
    Returns:
        Result of function (if wait=True)
    """
    return _main_thread_queue.enqueue(
        func,
        *args,
        wait=wait,
        timeout=timeout,
        priority=priority,
        **kwargs
    )


def defer_to_main_thread(
    func: Callable,
    *args,
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs
):
    """
    Defer function execution to main thread (non-blocking).
    
    Args:
        func: Function to execute
        *args: Positional arguments
        priority: Task priority
        **kwargs: Keyword arguments
    """
    _main_thread_queue.enqueue(
        func,
        *args,
        wait=False,
        priority=priority,
        **kwargs
    )


# ========================================================================================
# Decorators
# ========================================================================================

def ensure_main_thread(func: Callable) -> Callable:
    """
    Decorator to ensure function runs on main thread.
    
    If called from non-main thread, automatically defers to main thread.
    
    Usage:
        @ensure_main_thread
        def my_blender_function():
            bpy.ops.mesh.primitive_cube_add()  # Safe!
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if is_main_thread():
            # Already on main thread, execute directly
            return func(*args, **kwargs)
        else:
            # Defer to main thread
            logger.debug(
                f"Auto-deferring {func.__name__} to main thread from "
                f"{threading.current_thread().name}"
            )
            return run_in_main_thread(func, *args, **kwargs)
    
    return wrapper


def require_main_thread_decorator(func: Callable) -> Callable:
    """
    Decorator to require main thread (raises exception if not).
    
    Usage:
        @require_main_thread_decorator
        def critical_function():
            # Must be on main thread or exception raised
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        require_main_thread(func.__name__)
        return func(*args, **kwargs)
    
    return wrapper


def thread_safe_property(func: Callable) -> property:
    """
    Create thread-safe property that defers to main thread.
    
    Usage:
        @thread_safe_property
        def my_property(self):
            return bpy.context.scene.frame_current
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if is_main_thread():
            return func(*args, **kwargs)
        else:
            return run_in_main_thread(func, *args, **kwargs)
    
    return property(wrapper)


# ========================================================================================
# Modal Executor
# ========================================================================================

class ModalExecutor(bpy.types.Operator):
    """
    Modal operator for executing queued tasks on main thread.
    
    This operator runs in modal mode and processes the task queue
    at regular intervals, ensuring all tasks execute on main thread.
    """
    bl_idname = "tlx.modal_executor"
    bl_label = "Thread-Safe Task Executor"
    
    _timer = None
    _running = False
    
    def modal(self, context, event):
        """Modal event handler."""
        if not self._running:
            return {'FINISHED'}
        
        if event.type == 'TIMER':
            # Process tasks
            try:
                processed = _main_thread_queue.process_tasks(max_tasks=10)
                
                if processed > 0:
                    logger.debug(f"Processed {processed} tasks")
            
            except Exception as e:
                logger.error(f"Task processing error: {e}", exc_info=True)
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        """Start modal executor."""
        if ModalExecutor._running:
            self.report({'WARNING'}, "Modal executor already running")
            return {'CANCELLED'}
        
        # Add timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        
        # Start modal
        wm.modal_handler_add(self)
        ModalExecutor._running = True
        
        logger.info("Modal executor started")
        self.report({'INFO'}, "Thread-safe executor started")
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        """Cancel modal executor."""
        self._stop(context)
    
    def _stop(self, context):
        """Stop modal executor."""
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        
        ModalExecutor._running = False
        logger.info("Modal executor stopped")
    
    @classmethod
    def stop_executor(cls, context):
        """Stop the modal executor (class method)."""
        if cls._running:
            # Try to cancel via operator
            try:
                # This is a bit hacky but works
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            with context.temp_override(window=window, area=area):
                                # Trigger ESC to cancel modal
                                pass
            except:
                pass
            
            cls._running = False
            logger.info("Modal executor force stopped")


def start_modal_executor(context) -> bool:
    """
    Start the modal executor for processing tasks.
    
    Args:
        context: Blender context
    
    Returns:
        True if started, False if already running
    """
    if ModalExecutor._running:
        return False
    
    bpy.ops.tlx.modal_executor()
    return True


def stop_modal_executor(context):
    """Stop the modal executor."""
    ModalExecutor.stop_executor(context)


# ========================================================================================
# Safe Blender API Wrappers
# ========================================================================================

class SafeBlenderAPI:
    """
    Thread-safe wrappers for common Blender API operations.
    
    All methods automatically defer to main thread if needed.
    """
    
    @staticmethod
    @ensure_main_thread
    def add_mesh(name: str = "Mesh") -> object:
        """Create mesh data block."""
        return bpy.data.meshes.new(name)
    
    @staticmethod
    @ensure_main_thread
    def add_object(name: str, data) -> object:
        """Create object."""
        return bpy.data.objects.new(name, data)
    
    @staticmethod
    @ensure_main_thread
    def link_to_scene(obj, scene=None):
        """Link object to scene."""
        if scene is None:
            scene = bpy.context.scene
        scene.collection.objects.link(obj)
    
    @staticmethod
    @ensure_main_thread
    def remove_object(obj):
        """Remove object."""
        bpy.data.objects.remove(obj, do_unlink=True)
    
    @staticmethod
    @ensure_main_thread
    def remove_mesh(mesh):
        """Remove mesh."""
        bpy.data.meshes.remove(mesh, do_unlink=True)
    
    @staticmethod
    @ensure_main_thread
    def screenshot(filepath: str, full: bool = False):
        """Take screenshot."""
        if full:
            bpy.ops.screen.screenshot(filepath=filepath)
        else:
            bpy.ops.screen.screenshot_area(filepath=filepath)
    
    @staticmethod
    @ensure_main_thread
    def render(write_still: bool = True, use_viewport: bool = False):
        """Render scene."""
        bpy.ops.render.render(
            write_still=write_still,
            use_viewport=use_viewport
        )
    
    @staticmethod
    @ensure_main_thread
    def get_context_copy() -> dict:
        """Get copy of context (main thread only)."""
        return {
            'scene': bpy.context.scene,
            'window': bpy.context.window,
            'screen': bpy.context.screen if bpy.context.window else None,
            'area': bpy.context.area,
            'region': bpy.context.region,
        }


# Global instance
safe_bpy = SafeBlenderAPI()


# ========================================================================================
# Thread Safety Verification
# ========================================================================================

class ThreadSafetyChecker:
    """
    Utility for checking thread safety of operations.
    """
    
    def __init__(self):
        self.violations = []
        self.enabled = True
    
    def check_call(self, function_name: str, args_info: str = ""):
        """
        Check if call is thread-safe.
        
        Args:
            function_name: Name of function being called
            args_info: Information about arguments
        """
        if not self.enabled:
            return
        
        if not is_main_thread():
            thread_info = get_current_thread_info()
            violation = {
                'function': function_name,
                'args_info': args_info,
                'thread_name': thread_info['name'],
                'thread_ident': thread_info['ident'],
                'timestamp': time.time(),
            }
            self.violations.append(violation)
            
            logger.error(
                f"⚠ THREAD SAFETY VIOLATION: {function_name} called from "
                f"thread '{thread_info['name']}' (not main thread)"
            )
    
    def get_violations(self) -> list:
        """Get recorded violations."""
        return self.violations.copy()
    
    def clear_violations(self):
        """Clear violation history."""
        self.violations.clear()
    
    def print_report(self):
        """Print thread safety report."""
        if not self.violations:
            print("\n✓ No thread safety violations detected")
            return
        
        print(f"\n⚠ {len(self.violations)} THREAD SAFETY VIOLATIONS:")
        print("="*70)
        
        for i, v in enumerate(self.violations, 1):
            print(f"\n{i}. {v['function']}")
            print(f"   Thread: {v['thread_name']} (ident={v['thread_ident']})")
            print(f"   Args: {v['args_info']}")
            print(f"   Time: {v['timestamp']:.2f}")
        
        print("="*70)


# Global checker
_thread_checker = ThreadSafetyChecker()


def get_thread_checker() -> ThreadSafetyChecker:
    """Get global thread checker."""
    return _thread_checker


# ========================================================================================
# Integration Helpers
# ========================================================================================

def make_thread_safe_wrapper(blender_func: Callable) -> Callable:
    """
    Create thread-safe wrapper for any Blender function.
    
    Args:
        blender_func: Blender function to wrap
    
    Returns:
        Thread-safe wrapper function
    """
    @functools.wraps(blender_func)
    def wrapper(*args, **kwargs):
        if is_main_thread():
            return blender_func(*args, **kwargs)
        else:
            return run_in_main_thread(blender_func, *args, **kwargs)
    
    return wrapper


def patch_module_thread_safe(module, function_names: list):
    """
    Patch module functions to be thread-safe.
    
    Args:
        module: Module to patch
        function_names: List of function names to patch
    """
    for name in function_names:
        if hasattr(module, name):
            original_func = getattr(module, name)
            wrapped_func = make_thread_safe_wrapper(original_func)
            setattr(module, name, wrapped_func)
            logger.info(f"Patched {module.__name__}.{name} for thread safety")


# ========================================================================================
# Registration
# ========================================================================================

classes = (
    ModalExecutor,
)


def register():
    """Register thread safety system."""
    logger.info("Registering thread safety system")
    
    # Initialize main thread
    _initialize_main_thread()
    
    # Register classes
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            logger.error(f"Failed to register {cls.__name__}: {e}")
    
    logger.info(
        f"Thread safety system registered. "
        f"Main thread: {_MAIN_THREAD_ID}"
    )


def unregister():
    """Unregister thread safety system."""
    logger.info("Unregistering thread safety system")
    
    # Stop modal executor if running
    if ModalExecutor._running:
        try:
            ModalExecutor._running = False
        except:
            pass
    
    # Clear queue
    _main_thread_queue.clear()
    
    # Unregister classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.warning(f"Failed to unregister {cls.__name__}: {e}")
    
    # Print report if violations detected
    if _thread_checker.violations:
        _thread_checker.print_report()
    
    logger.info("Thread safety system unregistered")


# ========================================================================================
# Testing & Examples
# ========================================================================================

def example_usage():
    """
    Example usage of thread safety system.
    """
    print("\n" + "="*70)
    print("THREAD SAFETY SYSTEM - EXAMPLES")
    print("="*70)
    
    # Example 1: Decorator
    print("\nExample 1: Using @ensure_main_thread decorator")
    
    @ensure_main_thread
    def create_cube():
        bpy.ops.mesh.primitive_cube_add()
        return bpy.context.active_object
    
    # This works from any thread
    cube = create_cube()
    print(f"✓ Created cube: {cube.name}")
    
    # Example 2: Explicit check
    print("\nExample 2: Explicit thread check")
    
    def my_function():
        if not is_main_thread():
            print(f"  Not on main thread, deferring...")
            return run_in_main_thread(my_function)
        
        print(f"  Executing on main thread")
        bpy.ops.mesh.primitive_sphere_add()
        return bpy.context.active_object
    
    sphere = my_function()
    print(f"✓ Created sphere: {sphere.name}")
    
    # Example 3: Safe API
    print("\nExample 3: Using SafeBlenderAPI")
    
    mesh = safe_bpy.add_mesh("TestMesh")
    obj = safe_bpy.add_object("TestObject", mesh)
    safe_bpy.link_to_scene(obj)
    print(f"✓ Created object: {obj.name}")
    
    # Example 4: Queue statistics
    print("\nExample 4: Queue statistics")
    stats = _main_thread_queue.get_stats()
    print(f"  Enqueued: {stats['enqueued']}")
    print(f"  Executed: {stats['executed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Pending: {stats['pending']}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    # Run examples if executed directly
    example_usage()