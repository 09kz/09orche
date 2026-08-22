import asyncio
import os
import sys
import time

sys.path.insert(0, r"C:\Users\zydek\coding\claude-openrouter-subagents\src")

from conclave.client import ask
from conclave.config import ModelSpec

SPEC = ModelSpec(alias="ox_alpha", id="stealth/ox-alpha", description="d")

SYSTEM_PROMPT = (
    "You write clean, correct, idiomatic Python. Output the module code, then "
    "a line containing only '# --- TESTS ---', then the pytest test code that "
    "imports from it. No markdown fences, no commentary."
)

TASKS = {
    "lru_cache": (
        "Write lru_cache.py: a thread-safe LRU cache class LRUCache(capacity) "
        "with get(key)/put(key, value), no external dependencies, using "
        "threading.Lock. Then write pytest tests in the same response covering "
        "basic get/put, eviction order (least-recently-used evicted first), and "
        "a concurrency stress test with multiple threads. The tests must import "
        "`from lru_cache import LRUCache`."
    ),
    "rate_limiter": (
        "Write rate_limiter.py: a token-bucket rate limiter class "
        "RateLimiter(rate, burst) with a try_acquire() method, no external "
        "dependencies. Then write pytest tests in the same response covering "
        "burst capacity, refill timing (inject a fake clock if your "
        "implementation needs one — the tests and implementation must agree "
        "with each other on this), and capacity capping. The tests must import "
        "`from rate_limiter import RateLimiter`."
    ),
}


async def gen_one(api_key, name, prompt):
    t0 = time.time()
    result = await ask(
        api_key, SPEC, {"ox_alpha": SPEC}, prompt, SYSTEM_PROMPT, reasoning_effort="low"
    )
    return name, result, time.time() - t0


async def main():
    api_key = os.environ["OPENROUTER_API_KEY"]
    t_start = time.time()
    results = await asyncio.gather(
        *(gen_one(api_key, name, prompt) for name, prompt in TASKS.items())
    )
    t_total = time.time() - t_start

    out_dir = (
        r"C:\Users\zydek\coding\claude-openrouter-subagents\examples"
        r"\python-modules-recreation-v3-bundled\sonnet5-conclave"
    )
    os.makedirs(out_dir, exist_ok=True)
    print(f"TOTAL WALL CLOCK: {t_total:.2f}s\n")
    for name, result, elapsed in results:
        code = result.rsplit("\n\n---\n", 1)[0]
        if "# --- TESTS ---" not in code:
            print(f"=== {name} ({elapsed:.2f}s) -- NO TEST MARKER FOUND, dumping raw ===")
            with open(f"{out_dir}\\{name}_RAW.txt", "w", encoding="utf-8") as f:
                f.write(code)
            continue
        module_code, test_code = code.split("# --- TESTS ---", 1)
        with open(f"{out_dir}\\{name}.py", "w", encoding="utf-8") as f:
            f.write(module_code.strip() + "\n")
        with open(f"{out_dir}\\test_{name}.py", "w", encoding="utf-8") as f:
            f.write(test_code.strip() + "\n")
        print(f"=== {name} ({elapsed:.2f}s, {len(code.splitlines())} total lines) ===")


asyncio.run(main())
