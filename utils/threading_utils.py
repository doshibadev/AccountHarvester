"""
Advanced threading utilities for the AccountHarvester application.

This module provides thread management tools optimized for Steam client operations
with built-in error handling, resource management, and performance monitoring.
"""
import threading
import concurrent.futures
import time
import queue
import logging
import os
import signal
import weakref
import uuid
import psutil
import random
from typing import List, Dict, Any, Callable, Tuple, Optional, Union, Set
from dataclasses import dataclass, field
from enum import Enum

# Configure logger
logger = logging.getLogger("threading_utils")

class TaskPriority(Enum):
    """Priority levels for scheduled tasks"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class Task:
    """Represents a task to be executed by the thread pool"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    function: Callable = None
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 0
    retry_count: int = 0
    timeout: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    exception: Optional[Exception] = None
    result: Any = None
    # Backoff settings
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    next_retry_time: Optional[float] = None
    
    def __lt__(self, other):
        """Compare tasks based on priority for the priority queue"""
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority.value > other.priority.value  # Higher value = higher priority
    
    def calculate_next_retry_time(self):
        """Calculate the next retry time with exponential backoff and jitter"""
        if self.retry_count == 0:
            backoff = self.initial_backoff
        else:
            backoff = self.initial_backoff * (self.backoff_factor ** (self.retry_count - 1))
        
        # Add jitter to avoid thundering herd problem
        jitter_amount = random.uniform(-self.jitter, self.jitter) * backoff
        backoff_with_jitter = backoff + jitter_amount
        
        # Set the next retry time
        self.next_retry_time = time.time() + backoff_with_jitter
        return self.next_retry_time

class WorkerState(Enum):
    """States a worker thread can be in"""
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class ThreadPoolMetrics:
    """Collects and provides metrics about thread pool performance"""
    
    def __init__(self):
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_retried = 0
        self.total_execution_time = 0.0
        self.peak_queue_size = 0
        self.peak_active_workers = 0
        self._lock = threading.RLock()
        self._task_execution_times = {}  # task_id -> execution time
        self._task_types = {"cpu_bound": 0, "io_bound": 0}  # Count of task types
        self._recent_tasks = []  # Store recent task data for trend analysis
        self._max_recent_tasks = 100  # Maximum number of recent tasks to track
    
    def record_task_complete(self, task_id: str, execution_time: float, task_type: str):
        """Record metrics for a completed task"""
        with self._lock:
            self.tasks_completed += 1
            self.total_execution_time += execution_time
            self._task_execution_times[task_id] = execution_time
            
            # Track task type distribution
            if task_type in ("cpu_bound", "io_bound"):
                self._task_types[task_type] += 1
            
            # Store recent task data for trend analysis
            task_data = {
                "task_id": task_id,
                "execution_time": execution_time,
                "task_type": task_type,
                "timestamp": time.time()
            }
            self._recent_tasks.append(task_data)
            # Keep only the most recent tasks
            if len(self._recent_tasks) > self._max_recent_tasks:
                self._recent_tasks.pop(0)
    
    def record_task_failed(self, task_id: str):
        """Record metrics for a failed task"""
        with self._lock:
            self.tasks_failed += 1
    
    def record_task_retried(self, task_id: str):
        """Record metrics for a retried task"""
        with self._lock:
            self.tasks_retried += 1
    
    def update_queue_size(self, size: int):
        """Update the peak queue size metric"""
        with self._lock:
            self.peak_queue_size = max(self.peak_queue_size, size)
    
    def update_active_workers(self, count: int):
        """Update the peak active workers metric"""
        with self._lock:
            self.peak_active_workers = max(self.peak_active_workers, count)
    
    def get_average_execution_time(self) -> float:
        """Get the average task execution time"""
        with self._lock:
            if not self.tasks_completed:
                return 0.0
            return self.total_execution_time / self.tasks_completed
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """Get a comprehensive metrics report"""
        with self._lock:
            # Calculate trends based on recent tasks
            task_trend = "neutral"
            if len(self._recent_tasks) > 10:
                # Analyze recent execution times to detect trends
                recent_times = [t["execution_time"] for t in self._recent_tasks[-10:]]
                avg_recent = sum(recent_times) / len(recent_times)
                older_times = [t["execution_time"] for t in self._recent_tasks[:-10]]
                if older_times:
                    avg_older = sum(older_times) / len(older_times)
                    if avg_recent > avg_older * 1.25:
                        task_trend = "slower"  # Tasks are getting slower
                    elif avg_recent < avg_older * 0.75:
                        task_trend = "faster"  # Tasks are getting faster
            
            # Calculate task type ratio
            total_tasks = self._task_types["cpu_bound"] + self._task_types["io_bound"]
            cpu_bound_ratio = self._task_types["cpu_bound"] / max(1, total_tasks)
            io_bound_ratio = self._task_types["io_bound"] / max(1, total_tasks)
            
            # Create the report with extended metrics
            return {
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "tasks_retried": self.tasks_retried,
                "average_execution_time": self.get_average_execution_time(),
                "peak_queue_size": self.peak_queue_size,
                "peak_active_workers": self.peak_active_workers,
                "success_rate": (self.tasks_completed / (self.tasks_completed + self.tasks_failed)) 
                                if (self.tasks_completed + self.tasks_failed) > 0 else 0,
                "task_types": {
                    "cpu_bound": self._task_types["cpu_bound"],
                    "io_bound": self._task_types["io_bound"],
                    "cpu_bound_ratio": cpu_bound_ratio,
                    "io_bound_ratio": io_bound_ratio
                },
                "task_trend": task_trend
            }
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self.tasks_completed = 0
            self.tasks_failed = 0
            self.tasks_retried = 0
            self.total_execution_time = 0.0
            self.peak_queue_size = 0
            self.peak_active_workers = 0
            self._task_execution_times = {}
            self._task_types = {"cpu_bound": 0, "io_bound": 0}
            self._recent_tasks = []

class Worker(threading.Thread):
    """Advanced worker thread that processes tasks and reports its state"""
    
    def __init__(self, task_queue, result_callback, exception_callback, 
                 state_change_callback, worker_id, metrics):
        super().__init__()
        self.daemon = True
        self.id = worker_id
        self.task_queue = task_queue
        self.result_callback = result_callback
        self.exception_callback = exception_callback
        self.state_change_callback = state_change_callback
        self.metrics = metrics
        self._stop_event = threading.Event()
        self._state = WorkerState.IDLE
        self._current_task = None
        self._task_start_time = None
        self._cpu_usage_start = None  # Track CPU usage at task start
    
    @property
    def state(self) -> WorkerState:
        """Get the current state of the worker"""
        return self._state
    
    def _set_state(self, state: WorkerState):
        """Set the worker state and notify via callback"""
        old_state = self._state
        self._state = state
        if self.state_change_callback and old_state != state:
            self.state_change_callback(self.id, old_state, state)
    
    def stop(self):
        """Signal the worker to stop"""
        self._set_state(WorkerState.STOPPING)
        self._stop_event.set()
    
    def is_stopping(self) -> bool:
        """Check if the worker has been signaled to stop"""
        return self._stop_event.is_set()
    
    def get_current_task(self) -> Optional[Task]:
        """Get the task currently being processed by this worker"""
        return self._current_task
    
    def run(self):
        """Main worker loop that processes tasks from the queue"""
        logger.info(f"Worker {self.id} started")
        
        while not self.is_stopping():
            try:
                # Attempt to get a task with timeout to allow for checking stop flag
                try:
                    self._set_state(WorkerState.IDLE)
                    task = self.task_queue.get(timeout=0.5)
                    self._current_task = task
                    self._set_state(WorkerState.BUSY)
                except queue.Empty:
                    continue
                
                # Check if this is a delayed retry and we need to wait
                if task.retry_count > 0 and task.next_retry_time and task.next_retry_time > time.time():
                    # Calculate how long to wait before retry
                    wait_time = task.next_retry_time - time.time()
                    if wait_time > 0:
                        logger.debug(f"Waiting {wait_time:.2f}s before retry #{task.retry_count} for task {task.id}")
                        # Put the task back in the queue and continue
                        self.task_queue.put(task)
                        self.task_queue.task_done()
                        continue
                
                # Process the task
                task.started_at = time.time()
                self._task_start_time = task.started_at
                # Capture CPU usage at task start for workload characterization
                self._cpu_usage_start = psutil.Process(os.getpid()).cpu_percent(interval=0.05)
                
                try:
                    # Execute task with timeout if specified
                    if task.timeout:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(task.function, *task.args, **task.kwargs)
                            result = future.result(timeout=task.timeout)
                    else:
                        result = task.function(*task.args, **task.kwargs)
                    
                    # Record successful execution
                    task.completed_at = time.time()
                    task.result = result
                    execution_time = task.completed_at - task.started_at
                    
                    # Capture CPU usage metrics to determine if task was CPU or IO bound
                    cpu_usage_end = psutil.Process(os.getpid()).cpu_percent(interval=0.05)
                    cpu_usage_during_task = cpu_usage_end - self._cpu_usage_start if self._cpu_usage_start is not None else 0
                    
                    # Categorize the task as CPU-bound or IO-bound based on execution time and CPU usage
                    is_cpu_bound = execution_time > 0.5 and cpu_usage_during_task > 30.0
                    task_type = "cpu_bound" if is_cpu_bound else "io_bound"
                    
                    # Add task type to metrics
                    self.metrics.record_task_complete(task.id, execution_time, task_type)
                    
                    # Call result callback
                    if self.result_callback:
                        self.result_callback(task)
                
                except Exception as e:
                    # Handle task execution failure
                    task.exception = e
                    logger.exception(f"Worker {self.id} encountered an error executing task {task.id}: {e}")
                    
                    # Retry logic if retries are available
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        self.metrics.record_task_retried(task.id)
                        
                        # Calculate backoff time for next retry
                        next_retry = task.calculate_next_retry_time()
                        backoff_seconds = next_retry - time.time()
                        
                        logger.info(f"Retrying task {task.id} (attempt {task.retry_count}/{task.max_retries}) after {backoff_seconds:.2f}s backoff")
                        
                        # Re-queue the task
                        self.task_queue.put(task)
                    else:
                        # No retries left, mark as failed
                        task.completed_at = time.time()
                        self.metrics.record_task_failed(task.id)
                        
                        # Call exception callback
                        if self.exception_callback:
                            self.exception_callback(task)
                
                finally:
                    # Always mark task as done in the queue
                    self.task_queue.task_done()
                    self._current_task = None
                    self._task_start_time = None
            
            except Exception as e:
                # Catch any other exceptions in the worker loop
                logger.exception(f"Worker {self.id} encountered an unexpected error: {e}")
                self._set_state(WorkerState.ERROR)
                # Brief pause to prevent tight error loops
                time.sleep(0.5)
        
        # Worker is stopping
        self._set_state(WorkerState.STOPPED)
        logger.info(f"Worker {self.id} stopped")

class AdvancedThreadPool:
    """
    Advanced thread pool for managing worker threads with priority queue, 
    metrics, and sophisticated error handling.
    """
    
    def __init__(self, max_workers=None, thread_name_prefix="Worker", 
                 worker_timeout=30, dynamic_scaling=True):
        # Determine the number of workers
        if max_workers is None:
            # Default to number of CPU cores
            self.max_workers = os.cpu_count() or 4
        else:
            self.max_workers = max(1, max_workers)
        
        # Create a priority queue for tasks
        self.task_queue = queue.PriorityQueue()
        
        # Thread pool state
        self.thread_name_prefix = thread_name_prefix
        self.worker_timeout = worker_timeout
        self.dynamic_scaling = dynamic_scaling
        self.running = False
        self.workers = {}  # worker_id -> Worker instance
        self.metrics = ThreadPoolMetrics()
        self.results = {}  # task_id -> Task
        self._active_workers_count = 0
        self._worker_states = {}  # worker_id -> WorkerState
        self._management_thread = None
        self._stop_event = threading.Event()
        self._pool_lock = threading.RLock()
        
        # Callbacks
        self.on_task_complete = None
        self.on_task_failed = None
        self.on_task_added = None
        self.on_worker_state_change = None
    
    def _worker_state_changed(self, worker_id, old_state, new_state):
        """Handle worker state changes"""
        with self._pool_lock:
            self._worker_states[worker_id] = new_state
            
            # Update active workers count for metrics
            active_count = sum(1 for state in self._worker_states.values() 
                              if state == WorkerState.BUSY)
            self._active_workers_count = active_count
            self.metrics.update_active_workers(active_count)
            
            # Notify callback if registered
            if self.on_worker_state_change:
                self.on_worker_state_change(worker_id, old_state, new_state)
    
    def _task_completed(self, task):
        """Handle task completion"""
        with self._pool_lock:
            self.results[task.id] = task
            
            # Notify callback if registered
            if self.on_task_complete:
                self.on_task_complete(task)
    
    def _task_failed(self, task):
        """Handle task failure"""
        with self._pool_lock:
            self.results[task.id] = task
            
            # Notify callback if registered
            if self.on_task_failed:
                self.on_task_failed(task)
    
    def _create_worker(self, worker_id=None):
        """Create a new worker thread"""
        if worker_id is None:
            worker_id = f"{self.thread_name_prefix}-{len(self.workers) + 1}"
        
        worker = Worker(
            self.task_queue,
            self._task_completed,
            self._task_failed,
            self._worker_state_changed,
            worker_id,
            self.metrics
        )
        
        with self._pool_lock:
            self.workers[worker_id] = worker
            self._worker_states[worker_id] = WorkerState.IDLE
        
        return worker
    
    def _manage_worker_pool(self):
        """Management thread that monitors and maintains the worker pool"""
        logger.info("Thread pool management thread started")
        
        while not self._stop_event.is_set():
            try:
                # Check for stuck workers
                self._check_stuck_workers()
                
                # Dynamic scaling if enabled
                if self.dynamic_scaling:
                    self._scale_workers()
                
                # Update queue size metrics
                self.metrics.update_queue_size(self.task_queue.qsize())
                
                # Sleep briefly before next check
                time.sleep(1)
            
            except Exception as e:
                logger.exception(f"Error in thread pool management: {e}")
                time.sleep(5)  # Longer delay on error
        
        logger.info("Thread pool management thread stopped")
    
    def _check_stuck_workers(self):
        """Check for and handle workers that might be stuck on a task"""
        current_time = time.time()
        
        with self._pool_lock:
            for worker_id, worker in list(self.workers.items()):
                # Skip workers that aren't busy
                if self._worker_states.get(worker_id) != WorkerState.BUSY:
                    continue
                
                # Get the current task and check if it's running longer than timeout
                task = worker.get_current_task()
                if task and worker._task_start_time:
                    task_duration = current_time - worker._task_start_time
                    
                    if task_duration > self.worker_timeout:
                        logger.warning(
                            f"Worker {worker_id} appears stuck on task {task.id} "
                            f"for {task_duration:.1f}s (timeout: {self.worker_timeout}s)"
                        )
                        
                        # Strategy: Create a replacement worker and let the stuck one continue
                        # This way we don't lose the task result if it eventually completes
                        new_worker = self._create_worker()
                        new_worker.start()
                        logger.info(f"Created replacement worker {new_worker.id} for stuck worker {worker_id}")
    
    def _scale_workers(self):
        """Dynamically adjust the number of workers based on load and work type"""
        with self._pool_lock:
            current_worker_count = len(self.workers)
            queue_size = self.task_queue.qsize()
            active_workers = self._active_workers_count
            idle_workers = current_worker_count - active_workers
            
            # Get more detailed system metrics for better scaling decisions
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_percent = psutil.virtual_memory().percent
            
            # Get metrics about task characteristics
            metrics_report = self.metrics.get_metrics_report()
            avg_execution_time = metrics_report.get("average_execution_time", 0)
            task_types = metrics_report.get("task_types", {})
            cpu_bound_ratio = task_types.get("cpu_bound_ratio", 0)
            io_bound_ratio = task_types.get("io_bound_ratio", 1)  # Default to IO bound if no data
            task_trend = metrics_report.get("task_trend", "neutral")
            
            # Determine optimal thread count based on workload type
            if self.metrics.tasks_completed > 10:  # Only use task type data if we have enough samples
                # For I/O bound workloads (network/disk), more threads are beneficial
                # For CPU bound workloads, limit threads to CPU core count or less
                if io_bound_ratio > 0.7:  # Mostly I/O bound
                    # I/O bound tasks benefit from more threads than CPU cores
                    optimal_workers = min(self.max_workers, os.cpu_count() * 4)
                    logger.debug(f"Workload is primarily I/O bound ({io_bound_ratio:.2f}), optimal workers: {optimal_workers}")
                elif cpu_bound_ratio > 0.7:  # Mostly CPU bound
                    # CPU bound tasks should limit threads to CPU cores or less
                    optimal_workers = min(self.max_workers, max(1, int(os.cpu_count() * 0.75)))
                    logger.debug(f"Workload is primarily CPU bound ({cpu_bound_ratio:.2f}), optimal workers: {optimal_workers}")
                else:  # Mixed workload
                    # For mixed workloads, use a balanced approach
                    optimal_workers = min(self.max_workers, os.cpu_count() * 2)
                    logger.debug(f"Workload is mixed (CPU: {cpu_bound_ratio:.2f}, I/O: {io_bound_ratio:.2f}), optimal workers: {optimal_workers}")
            else:
                # Without enough task data, use execution time heuristic as before
                if avg_execution_time > 0:
                    is_io_bound = avg_execution_time < 0.5  # Less than 500ms suggests I/O bound
                    
                    if is_io_bound:
                        optimal_workers = min(self.max_workers, os.cpu_count() * 2)
                    else:
                        optimal_workers = min(self.max_workers, max(1, int(os.cpu_count() * 0.75)))
                else:
                    # Without execution time data, use conservative defaults
                    optimal_workers = min(self.max_workers, os.cpu_count())
            
            # Adjust based on task trends
            if task_trend == "slower":
                # Tasks are getting slower - reduce worker count to avoid overloading
                optimal_workers = max(1, int(optimal_workers * 0.8))
                logger.debug("Tasks are getting slower, reducing optimal worker count")
            elif task_trend == "faster":
                # Tasks are getting faster - we can use more workers
                optimal_workers = min(self.max_workers, int(optimal_workers * 1.2))
                logger.debug("Tasks are getting faster, increasing optimal worker count")
                
            # Adjust optimal count based on system resource usage
            if cpu_percent > 85:  # High CPU load
                optimal_workers = max(1, int(optimal_workers * 0.5))  # Reduce by 50%
                logger.debug(f"High CPU load ({cpu_percent}%), reducing worker count")
            elif cpu_percent > 70:  # Moderate CPU load
                optimal_workers = max(1, int(optimal_workers * 0.75))  # Reduce by 25%
                logger.debug(f"Moderate CPU load ({cpu_percent}%), slightly reducing worker count")
            
            # Also consider memory pressure
            if memory_percent > 85:  # High memory use
                optimal_workers = max(1, int(optimal_workers * 0.6))  # Reduce by 40%
                logger.debug(f"High memory usage ({memory_percent}%), reducing worker count")
            
            # Scaling up logic: We need more workers if there are tasks waiting
            if queue_size > idle_workers and current_worker_count < optimal_workers:
                workers_to_add = min(queue_size - idle_workers, optimal_workers - current_worker_count)
                
                # Don't add workers if system is already under heavy load
                if cpu_percent < 90 and memory_percent < 90:
                    for _ in range(workers_to_add):
                        new_worker = self._create_worker()
                        new_worker.start()
                        logger.info(f"Scaled up: Added worker {new_worker.id}, now at {len(self.workers)}/{self.max_workers}, optimal: {optimal_workers}")
            
            # More intelligent scaling down logic
            elif ((idle_workers > 2 and idle_workers > queue_size + 1) or 
                  cpu_percent > 90 or memory_percent > 90 or current_worker_count > optimal_workers):
                
                # Calculate how many workers to remove
                if cpu_percent > 90 or memory_percent > 90:
                    # Under high system load, be more aggressive in removing workers
                    workers_to_keep = max(1, current_worker_count // 2)
                    target_removal = current_worker_count - workers_to_keep
                elif current_worker_count > optimal_workers:
                    # We have more workers than our optimal target
                    target_removal = current_worker_count - optimal_workers
                else:
                    # Normal case - remove excess idle workers
                    target_removal = idle_workers - max(1, queue_size)
                
                # Find workers to remove (idle ones first)
                idle_worker_ids = [wid for wid, state in self._worker_states.items() 
                                 if state == WorkerState.IDLE]
                
                # Keep at least one idle worker
                workers_to_remove = idle_worker_ids[:target_removal]
                
                for worker_id in workers_to_remove:
                    worker = self.workers.get(worker_id)
                    if worker:
                        worker.stop()
                        # The worker will be fully removed when it actually stops
                        logger.info(f"Scaled down: Stopping idle worker {worker_id}, now at {len(self.workers) - 1}/{self.max_workers}, optimal: {optimal_workers}")
    
    def start(self):
        """Start the thread pool"""
        if self.running:
            return
        
        with self._pool_lock:
            self.running = True
            self._stop_event.clear()
            
            # Initialize the metrics
            self.metrics.reset()
            
            # Start initial workers
            for _ in range(min(self.max_workers, 2)):  # Start with at least 2 workers
                worker = self._create_worker()
                worker.start()
            
            # Start the management thread
            self._management_thread = threading.Thread(
                target=self._manage_worker_pool,
                name="ThreadPoolManager"
            )
            self._management_thread.daemon = True
            self._management_thread.start()
            
            logger.info(f"Thread pool started with {len(self.workers)} initial workers (max: {self.max_workers})")
    
    def stop(self, wait=True, timeout=10):
        """Stop the thread pool"""
        if not self.running:
            return
        
        logger.info("Stopping thread pool...")
        self._stop_event.set()
        
        # Stop all workers
        with self._pool_lock:
            for worker in list(self.workers.values()):
                worker.stop()
        
        if wait:
            # Wait for management thread to finish
            if self._management_thread and self._management_thread.is_alive():
                self._management_thread.join(timeout=timeout)
            
            # Wait for all workers to finish
            end_time = time.time() + timeout
            while time.time() < end_time:
                with self._pool_lock:
                    if not any(worker.is_alive() for worker in self.workers.values()):
                        break
                time.sleep(0.1)
        
        with self._pool_lock:
            # Clean up any remaining workers
            self.workers.clear()
            self._worker_states.clear()
            self.running = False
        
        logger.info("Thread pool stopped")
    
    def submit(self, func, *args, priority=TaskPriority.NORMAL, timeout=None, 
               max_retries=0, initial_backoff=1.0, backoff_factor=2.0, jitter=0.1, **kwargs) -> str:
        """
        Submit a task to the thread pool
        
        Args:
            func: The function to execute
            *args: Arguments to pass to the function
            priority: Priority level for the task
            timeout: Maximum execution time in seconds
            max_retries: Number of times to retry on failure
            initial_backoff: Initial backoff time in seconds (for exponential backoff)
            backoff_factor: Multiplier for backoff time on each retry
            jitter: Random factor to add to backoff (0.0-1.0)
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            task_id: Unique ID for the submitted task
        """
        # Create a new task
        task = Task(
            function=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
            initial_backoff=initial_backoff,
            backoff_factor=backoff_factor,
            jitter=jitter
        )
        
        # Add to queue
        self.task_queue.put(task)
        
        # Start the pool if not already running
        if not self.running:
            self.start()
        
        # Notify if callback registered
        if self.on_task_added:
            self.on_task_added(task)
        
        logger.debug(f"Submitted task {task.id} with priority {priority.name}")
        return task.id
    
    def map(self, func, iterable, timeout=None, max_retries=0, 
            initial_backoff=1.0, backoff_factor=2.0, jitter=0.1,
            priority=TaskPriority.NORMAL) -> List[Any]:
        """
        Submit multiple tasks and wait for all results
        
        Args:
            func: The function to execute for each item
            iterable: Items to process
            timeout: Maximum execution time per task in seconds
            max_retries: Number of times to retry on failure
            initial_backoff: Initial backoff time in seconds
            backoff_factor: Multiplier for backoff time on each retry
            jitter: Random factor to add to backoff (0.0-1.0)
            priority: Priority level for tasks
            
        Returns:
            List of results in the same order as the input iterable
        """
        # Submit all tasks
        task_ids = []
        for item in iterable:
            task_id = self.submit(
                func, item, 
                priority=priority,
                timeout=timeout,
                max_retries=max_retries,
                initial_backoff=initial_backoff,
                backoff_factor=backoff_factor,
                jitter=jitter
            )
            task_ids.append(task_id)
        
        # Wait for all tasks to complete and collect results
        return self.get_results(task_ids)
    
    def wait_for_completion(self, timeout=None):
        """Wait for all queued tasks to complete"""
        try:
            self.task_queue.join()
            return True
        except Exception as e:
            logger.error(f"Error waiting for task completion: {e}")
            return False
    
    def get_task(self, task_id) -> Optional[Task]:
        """Get a task by its ID"""
        with self._pool_lock:
            return self.results.get(task_id)
    
    def get_results(self, task_ids=None) -> List[Any]:
        """
        Get results for completed tasks
        
        Args:
            task_ids: List of task IDs to get results for, or None for all
            
        Returns:
            List of results in the same order as the task_ids list
        """
        with self._pool_lock:
            if task_ids is None:
                # Return all results
                return [task.result for task in self.results.values() 
                        if task.completed_at is not None]
            else:
                # Wait for specific tasks and return their results
                results = []
                for task_id in task_ids:
                    # Keep checking until the task is complete
                    while True:
                        task = self.results.get(task_id)
                        if task and task.completed_at is not None:
                            results.append(task.result)
                            break
                        time.sleep(0.1)
                return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current thread pool metrics"""
        with self._pool_lock:
            metrics = self.metrics.get_metrics_report()
            metrics.update({
                "current_workers": len(self.workers),
                "max_workers": self.max_workers,
                "active_workers": self._active_workers_count,
                "idle_workers": len(self.workers) - self._active_workers_count,
                "queue_size": self.task_queue.qsize(),
                "tasks_pending": self.task_queue.qsize(),
                "tasks_completed": len([t for t in self.results.values() if t.completed_at is not None]),
                "dynamic_scaling": self.dynamic_scaling
            })
            return metrics
    
    def get_worker_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed status information for all workers"""
        with self._pool_lock:
            statuses = {}
            for worker_id, worker in self.workers.items():
                if not worker.is_alive():
                    continue
                    
                current_task = worker.get_current_task()
                statuses[worker_id] = {
                    "state": self._worker_states.get(worker_id, WorkerState.UNKNOWN).value,
                    "alive": worker.is_alive(),
                    "current_task_id": current_task.id if current_task else None,
                    "task_running_time": (time.time() - worker._task_start_time) 
                                        if worker._task_start_time else 0
                }
            return statuses

# Convenient singleton instance
thread_pool = AdvancedThreadPool()

def submit_task(func, *args, **kwargs) -> str:
    """
    Submit a task to the default thread pool
    
    Args:
        func: The function to execute
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments for function and thread pool
        
    Thread pool kwargs:
        priority: TaskPriority enum value (default: NORMAL)
        timeout: Maximum execution time in seconds (default: None)
        max_retries: Number of times to retry on failure (default: 0)
        initial_backoff: Initial backoff time in seconds (default: 1.0)
        backoff_factor: Multiplier for backoff time on each retry (default: 2.0)
        jitter: Random factor to add to backoff (default: 0.1)
        
    Returns:
        task_id: Unique ID for the submitted task
    """
    # Extract thread pool specific kwargs
    priority = kwargs.pop('priority', TaskPriority.NORMAL)
    timeout = kwargs.pop('timeout', None)
    max_retries = kwargs.pop('max_retries', 0)
    initial_backoff = kwargs.pop('initial_backoff', 1.0)
    backoff_factor = kwargs.pop('backoff_factor', 2.0)
    jitter = kwargs.pop('jitter', 0.1)
    
    return thread_pool.submit(
        func, *args,
        priority=priority,
        timeout=timeout,
        max_retries=max_retries,
        initial_backoff=initial_backoff,
        backoff_factor=backoff_factor,
        jitter=jitter,
        **kwargs
    )

def parallel_map(func, iterable, **kwargs) -> List[Any]:
    """
    Process items in parallel and return results
    
    Args:
        func: The function to execute for each item
        iterable: Items to process
        **kwargs: Additional options for thread_pool.map
        
    Returns:
        List of results in the same order as the input iterable
    """
    return thread_pool.map(func, iterable, **kwargs)

def get_task_result(task_id) -> Any:
    """Get the result of a task by its ID"""
    task = thread_pool.get_task(task_id)
    if task:
        return task.result
    return None

def wait_for_tasks():
    """Wait for all tasks in the default thread pool to complete"""
    return thread_pool.wait_for_completion()

def shutdown_thread_pool(wait=True, timeout=10):
    """Shut down the default thread pool"""
    thread_pool.stop(wait=wait, timeout=timeout)

def initialize_thread_pool(max_workers=None, dynamic_scaling=True):
    """Initialize the default thread pool with custom settings"""
    # Shut down existing pool if running
    if thread_pool.running:
        shutdown_thread_pool()
    
    # Update settings
    thread_pool.max_workers = max_workers or os.cpu_count() or 4
    thread_pool.dynamic_scaling = dynamic_scaling

# Decorator for easy task submission
def async_task(priority=TaskPriority.NORMAL, timeout=None, max_retries=0):
    """
    Decorator to make a function run asynchronously in the thread pool
    
    Args:
        priority: Task priority level
        timeout: Maximum execution time in seconds
        max_retries: Number of times to retry on failure
        
    Returns:
        Decorated function that returns a task ID when called
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            return submit_task(
                func, *args,
                priority=priority,
                timeout=timeout,
                max_retries=max_retries,
                **kwargs
            )
        return wrapper
    return decorator

# Make sure to initialize thread pool with appropriate settings
initialize_thread_pool(dynamic_scaling=True)
