import asyncio
import os
import sys
import time

sys.path.insert(0, r"C:\Users\zydek\coding\09orche\src")

from orche.client import ask
from orche.config import ModelSpec

SPEC = ModelSpec(alias="ox_alpha", id="stealth/ox-alpha", description="d")

SYSTEM_PROMPT = (
    "You write clean, correct, idiomatic Python. Output ONLY the file content "
    "(no markdown fences, no commentary) so it can be written directly to a .py file."
)

TASKS = {
    "lru_cache.py": (
        "Write a thread-safe LRU cache class in Python (get/put, configurable max "
        "size, no external dependencies, using threading.Lock)."
    ),
    "test_lru_cache.py": (
        "Write pytest tests for a thread-safe LRU cache class (in lru_cache.py, "
        "class LRUCache with get(key)/put(key, value), constructor LRUCache(capacity)). "
        "Cover: basic get/put, eviction order (least-recently-used evicted first), "
        "and a concurrency stress test with multiple threads."
    ),
    "rate_limiter.py": (
        "Write a token-bucket rate limiter class in Python (configurable rate + "
        "burst, a try_acquire() method, no external dependencies)."
    ),
    "test_rate_limiter.py": (
        "Write pytest tests for a token-bucket rate limiter class (in "
        "rate_limiter.py, class RateLimiter with constructor RateLimiter(rate, "
        "burst) and method try_acquire()). Cover: burst capacity, refill timing "
        "(use a manual/injectable clock if needed), and capacity capping."
    ),
}


async def gen_one(api_key, filename, prompt):
    t0 = time.time()
    result = await ask(
        api_key, SPEC, {"ox_alpha": SPEC}, prompt, SYSTEM_PROMPT, reasoning_effort="low"
    )
    return filename, result, time.time() - t0


async def main():
    api_key = os.environ["OPENROUTER_API_KEY"]
    t_start = time.time()
    results = await asyncio.gather(
        *(gen_one(api_key, name, prompt) for name, prompt in TASKS.items())
    )
    t_total = time.time() - t_start

    out_dir = (
        r"C:\Users\zydek\coding\09orche\examples"
        r"\python-modules-recreation-v2-fixed\sonnet5-orche"
    )
    print(f"TOTAL WALL CLOCK: {t_total:.2f}s\n")
    for filename, result, elapsed in results:
        # strip the "\n\n---\nmodel · N tokens" footer orche.client.ask appends
        code = result.rsplit("\n\n---\n", 1)[0]
        path = f"{out_dir}\\{filename}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"=== {filename} ({elapsed:.2f}s, {len(code.splitlines())} lines) ===")


asyncio.run(main())
