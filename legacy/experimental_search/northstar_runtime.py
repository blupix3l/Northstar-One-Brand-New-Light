
"""
NorthStar Runtime - Execution Domain Infrastructure
Core architectural principles:
- Explicit lifecycle ownership
- Isolated execution
- Deterministic completion boundaries
- Graceful degradation
- Machine respect
"""
import threading
import concurrent.futures
import time
import logging
from typing import Callable, Optional, Dict, Any, Set
from enum import Enum, auto


class ExecutionDomainType(Enum):
    CORE = auto()
    MEDIA = auto()
    SEMANTIC = auto()


class DomainState(Enum):
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    SHUTTING_DOWN = auto()
    SHUTDOWN = auto()


class ExecutionDomain:
    """
    Encapsulates an isolated execution domain with:
    - Independent thread pool
    - Lifecycle management
    - Cancellation authority
    - Resource budgeting
    """

    def __init__(
        self,
        domain_type: ExecutionDomainType,
        max_workers: int = 4,
        max_queue_size: int = 32,
        name: Optional[str] = None
    ):
        self.domain_type = domain_type
        self.name = name or domain_type.name
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        self.state: DomainState = DomainState.UNINITIALIZED
        self._state_lock = threading.Lock()
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._active_tasks: Set[concurrent.futures.Future] = set()
        self._task_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._creation_time = time.time()

    def initialize(self) -> None:
        """Initialize the domain's thread pool"""
        with self._state_lock:
            if self.state != DomainState.UNINITIALIZED:
                return
            self.state = DomainState.INITIALIZING

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=f"NS-{self.name}-"
        )
        with self._state_lock:
            self.state = DomainState.RUNNING
        self._log(f"Initialized with {self.max_workers} workers")

    def submit(
        self,
        fn: Callable,
        *args,
        **kwargs
    ) -> Optional[concurrent.futures.Future]:
        """
        Submit a task to this domain's executor.
        Returns None if the domain is shutting down.
        """
        with self._state_lock:
            if self.state not in (DomainState.INITIALIZING, DomainState.RUNNING):
                self._log(f"Rejected task, state is {self.state}")
                return None

        if self._shutdown_event.is_set():
            return None

        future = self._executor.submit(fn, *args, **kwargs)

        with self._task_lock:
            self._active_tasks.add(future)
            future.add_done_callback(lambda f: self._task_complete(f))

        return future

    def _task_complete(self, future: concurrent.futures.Future) -> None:
        """Internal callback for task completion tracking"""
        with self._task_lock:
            self._active_tasks.discard(future)

        if future.exception():
            self._log(f"Task exception: {future.exception()}", level=logging.ERROR)

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Deterministic shutdown of this domain
        """
        with self._state_lock:
            if self.state in (DomainState.SHUTTING_DOWN, DomainState.SHUTDOWN):
                return
            self.state = DomainState.SHUTTING_DOWN

        self._log(f"Starting shutdown (wait={wait}, timeout={timeout}s)")
        self._shutdown_event.set()

        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=True)

        with self._task_lock:
            remaining = len(self._active_tasks)
            if remaining > 0:
                self._log(f"Forcing cancellation of {remaining} remaining tasks")
                for fut in self._active_tasks:
                    fut.cancel()
                self._active_tasks.clear()

        with self._state_lock:
            self.state = DomainState.SHUTDOWN

        self._log("Shutdown complete")

    def is_active(self) -> bool:
        with self._state_lock:
            return self.state == DomainState.RUNNING

    def get_stats(self) -> Dict[str, Any]:
        with self._state_lock:
            with self._task_lock:
                return {
                    "name": self.name,
                    "domain_type": self.domain_type.name,
                    "state": self.state.name,
                    "uptime_seconds": time.time() - self._creation_time,
                    "active_tasks": len(self._active_tasks)
                }

    def _log(self, message: str, level: int = logging.INFO) -> None:
        """Internal logger for domain events"""
        from .northstar_search import _log
        _log(f"RUNTIME:{self.name}", message)


class NorthStarRuntime:
    """
    Master runtime orchestrator for all Execution Domains
    Manages lifecycle and coordination between domains
    """
    def __init__(self):
        self.domains: Dict[ExecutionDomainType, ExecutionDomain] = {}
        self._domains_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self.creation_time = time.time()
        self._active_query_token: Optional[str] = None

    def get_domain(self, domain_type: ExecutionDomainType) -> ExecutionDomain:
        with self._domains_lock:
            if domain_type not in self.domains:
                domain = self._create_domain(domain_type)
                self.domains[domain_type] = domain
                domain.initialize()
            return self.domains[domain_type]

    def _create_domain(self, domain_type: ExecutionDomainType) -> ExecutionDomain:
        """Factory method for creating ExecutionDomains"""
        configs = {
            ExecutionDomainType.CORE: {"max_workers": 4},
            ExecutionDomainType.MEDIA: {"max_workers": 2},
            ExecutionDomainType.SEMANTIC: {"max_workers": 2}
        }
        return ExecutionDomain(
            domain_type=domain_type,
            **configs.get(domain_type, {"max_workers": 2})
        )

    def set_active_query_token(self, token: str) -> None:
        """Invalidate all previous tasks when starting a new query"""
        import uuid
        self._active_query_token = str(uuid.uuid4()) if token is None else token
        self._log(f"New active query token: {self._active_query_token}")

    def shutdown_all(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Shutdown all domains in order"""
        self._log("Starting full runtime shutdown")
        self._shutdown_event.set()

        shutdown_order = [
            ExecutionDomainType.MEDIA,
            ExecutionDomainType.SEMANTIC,
            ExecutionDomainType.CORE
        ]

        for domain_type in shutdown_order:
            with self._domains_lock:
                domain = self.domains.get(domain_type)
                if domain:
                    domain.shutdown(wait=wait, timeout=timeout)

        self._log("Full runtime shutdown complete")

    def get_all_stats(self) -> Dict[str, Any]:
        with self._domains_lock:
            return {
                "uptime_seconds": time.time() - self.creation_time,
                "domains": {
                    dt.name: domain.get_stats()
                    for dt, domain in self.domains.items()
                }
            }

    def _log(self, message: str, level: int = logging.INFO) -> None:
        from .northstar_search import _log
        _log("RUNTIME", message)


# Global runtime singleton (initialized lazily)
_runtime: Optional[NorthStarRuntime] = None


def get_runtime() -> NorthStarRuntime:
    """Get or initialize the global NorthStar runtime"""
    global _runtime
    if _runtime is None:
        _runtime = NorthStarRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset runtime (for testing only)"""
    global _runtime
    if _runtime is not None:
        _runtime.shutdown_all(wait=False)
    _runtime = None

