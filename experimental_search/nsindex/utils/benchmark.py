"""
Benchmark Suite
===============
Performance measurement tools for NSIndex.
"""

import time
import tracemalloc
from typing import List, Dict, Callable, Any
from ..models.page_document import PageDocument
from ..indexer.indexer import Indexer
from ..search.search_engine import SearchEngine


class Benchmark:
    """
    Measures and reports NSIndex performance metrics.
    """

    def __init__(self):
        self._results: Dict[str, List[float]] = {}

    def measure(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Measure execution time of a function."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000

        if name not in self._results:
            self._results[name] = []
        self._results[name].append(elapsed)

        return result

    def measure_indexing(self, indexer: Indexer, documents: List[PageDocument]) -> Dict:
        """Benchmark indexing performance."""
        tracemalloc.start()

        start = time.perf_counter()
        indexed = 0
        skipped = 0

        for doc in documents:
            result = indexer.index_document(doc)
            if result is not None:
                indexed += 1
            else:
                skipped += 1

        total_time = (time.perf_counter() - start) * 1000
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            "documents_indexed": indexed,
            "duplicates_skipped": skipped,
            "total_time_ms": round(total_time, 2),
            "avg_time_per_doc_ms": round(total_time / len(documents), 2) if documents else 0,
            "pages_per_minute": round(len(documents) / (total_time / 1000 / 60), 1) if total_time > 0 else 0,
            "memory_current_mb": round(current / 1024 / 1024, 2),
            "memory_peak_mb": round(peak / 1024 / 1024, 2),
        }

    def measure_search(self, engine: SearchEngine, queries: List[str]) -> Dict:
        """Benchmark search performance."""
        times = []
        for query in queries:
            start = time.perf_counter()
            results = engine.search(query, limit=10)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        return {
            "queries_tested": len(queries),
            "avg_search_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "min_search_time_ms": round(min(times), 2) if times else 0,
            "max_search_time_ms": round(max(times), 2) if times else 0,
            "total_time_ms": round(sum(times), 2),
        }

    def generate_report(self) -> str:
        """Generate a readable benchmark report."""
        lines = ["=== NSIndex Benchmark Report ===\n"]

        for name, times in self._results.items():
            avg = sum(times) / len(times)
            lines.append(f"{name}:")
            lines.append(f"  Calls: {len(times)}")
            lines.append(f"  Avg:   {avg:.2f} ms")
            lines.append(f"  Min:   {min(times):.2f} ms")
            lines.append(f"  Max:   {max(times):.2f} ms")
            lines.append("")

        return "\n".join(lines)
