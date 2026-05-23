#!/usr/bin/env python3
"""
F.R.I.D.A.Y. Tool Loop Reliability Benchmark

Executes a series of 20 distinct calendar queries to profile the reliability
and self-termination characteristics of the unified think_full() reasoning cycle.
Isolates each query's conversation history to prevent cross-contamination.

Outputs:
    docs/research-paper/benchmarks/tool-loop-benchmark.json
"""

import os
import sys
import time
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force memory buffer override to guarantee model loading
os.environ["FRIDAY_MEM_BUFFER"] = "0.0"

from src.core.brain import FridayBrain
from src.tools.server import MCPToolServer

CALENDAR_QUERIES = [
    "What meetings do I have today?",
    "Do I have any events this afternoon?",
    "What's on my calendar for today?",
    "Any meetings coming up?",
    "What time is my next meeting?",
    "Am I free this morning?",
    "What events do I have scheduled?",
    "Check my calendar for today",
    "Do I have anything planned today?",
    "What's my schedule like today?",
    "Any appointments today?",
    "What meetings are coming up today?",
    "Is my afternoon free?",
    "Show me today's events",
    "What do I have on today?",
    "Any events in the next few hours?",
    "What's on today?",
    "Check today's schedule",
    "Am I busy today?",
    "What's planned for today?",
]


def run_benchmark():
    print("============================================================")
    print("F.R.I.D.A.Y. Tool Loop Reliability Benchmark")
    print("============================================================")
    
    # Load model
    brain = FridayBrain()
    try:
        brain.load_model()
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

    results = []
    
    # Prune existing test RAG data so it doesn't skew benchmarks
    if brain.memory_store:
        try:
            # Add calendar test events so the calendar tool works
            from src.tools.calendar_tool import CalendarTool
            # No manual addition needed — CalendarTool reads native Apple Calendar database
            pass
        except Exception:
            pass

    print(f"\nFiring {len(CALENDAR_QUERIES)} calendar queries through think_full()...\n")

    for i, query in enumerate(CALENDAR_QUERIES, 1):
        print(f"[{i:02d}/20] Query: '{query}'")
        
        # Monkey patch MCPToolServer inside the query iteration to track call details
        tool_calls_made = []
        
        # Create a fresh tool server instance to reset rate limits
        tool_server = MCPToolServer()
        original_execute = tool_server.execute_tool
        
        def counting_execute(tc, _orig=original_execute):
            tool_calls_made.append(tc.get("name"))
            return _orig(tc)
            
        tool_server.execute_tool = counting_execute
        
        # Temporarily override MCPToolServer inside build_full_system_prompt or other flows
        # by patching the class inside brain's flow.
        # Since MCPToolServer is loaded dynamically inside think_full, we can patch it.
        with patch_tool_server(tool_server):
            start = time.perf_counter()
            try:
                response = brain.think_full(query)
                latency = time.perf_counter() - start
                
                call_count = len(tool_calls_made)
                if call_count == 0:
                    status = "FAILURE"  # Hallucinated response or failed to call calendar tool
                elif call_count == 1:
                    status = "SUCCESS"  # Correct single tool execution
                else:
                    status = "LOOP"     # Multi-turn tool call loops
                    
                results.append({
                    "query": query,
                    "status": status,
                    "tool_calls": tool_calls_made,
                    "response_chars": len(response),
                    "latency_s": latency,
                })
                
                print(f"  → Status: {status} | Calls: {call_count} | Latency: {latency:.1f}s | Chars: {len(response)}")
            except Exception as e:
                latency = time.perf_counter() - start
                results.append({
                    "query": query,
                    "status": "ERROR",
                    "error": str(e),
                    "latency_s": latency,
                })
                print(f"  → ERROR: {e}")
                
        # Isolate history turns
        brain.clear_history()

    # Calculate summaries
    counts = {
        "SUCCESS": sum(1 for r in results if r["status"] == "SUCCESS"),
        "LOOP":    sum(1 for r in results if r["status"] == "LOOP"),
        "FAILURE": sum(1 for r in results if r["status"] == "FAILURE"),
        "ERROR":   sum(1 for r in results if r["status"] == "ERROR"),
    }
    
    total = len(results)
    avg_latency = sum(r.get("latency_s", 0) for r in results) / total if total > 0 else 0.0

    print("\n" + "="*60)
    print("BENCHMARK COMPLETED")
    print("="*60)
    print(f"Success Rate (Exactly 1 Call):  {counts['SUCCESS']}/{total} ({counts['SUCCESS']/total*100:.1f}%)")
    print(f"Looping Rate (>1 Calls):        {counts['LOOP']}/{total} ({counts['LOOP']/total*100:.1f}%)")
    print(f"Failure Rate (No Calls):        {counts['FAILURE']}/{total} ({counts['FAILURE']/total*100:.1f}%)")
    print(f"Error Rate:                     {counts['ERROR']}/{total} ({counts['ERROR']/total*100:.1f}%)")
    print(f"Average Turn Latency:            {avg_latency:.2f}s")
    print("="*60)

    # Save outputs
    output_dir = PROJECT_ROOT / "docs" / "research-paper" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "tool-loop-benchmark.json"
    
    with open(output_file, "w") as f:
        json.dump({
            "summary": counts,
            "success_rate_percent": (counts['SUCCESS'] / total * 100) if total > 0 else 0,
            "avg_latency_s": avg_latency,
            "results": results
        }, f, indent=2)
        
    print(f"\nReport saved successfully to: {output_file}")


class patch_tool_server:
    """Helper context manager to inject our monkey-patched tool server into think_full."""
    def __init__(self, patched_instance):
        self.patched = patched_instance
        self.original_import = sys.modules.get('src.tools.server')

    def __enter__(self):
        # We patch the MCPToolServer class in its module
        import src.tools.server
        self.original_class = src.tools.server.MCPToolServer
        src.tools.server.MCPToolServer = lambda *args, **kwargs: self.patched

    def __exit__(self, exc_type, exc_val, exc_tb):
        import src.tools.server
        src.tools.server.MCPToolServer = self.original_class


if __name__ == "__main__":
    run_benchmark()
