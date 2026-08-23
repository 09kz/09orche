import asyncio
import os
import sys
import time

sys.path.insert(0, r"C:\Users\zydek\coding\09orche\src")

from orche.client import ask
from orche.config import ModelSpec

SPEC = ModelSpec(alias="ox_alpha", id="stealth/ox-alpha", description="d")

DOCS = {
    "doc1": r"C:\Users\zydek\AppData\Local\Temp\sources\doc1.md",
    "doc2": r"C:\Users\zydek\AppData\Local\Temp\sources\doc2.md",
    "doc3": r"C:\Users\zydek\AppData\Local\Temp\sources\doc3.md",
    "doc4": r"C:\Users\zydek\AppData\Local\Temp\sources\doc4.md",
}

SYSTEM_PROMPT = (
    "You summarize technical READMEs into a tight structured brief: what it "
    "does, key tools/features, notable technical details, license. "
    "Target ~100-150 words. Output the summary only, no preamble."
)


async def summarize_one(api_key, name, path):
    text = open(path, encoding="utf-8").read()
    prompt = f"Summarize this README:\n\n{text}"
    t0 = time.time()
    result = await ask(
        api_key, SPEC, {"ox_alpha": SPEC}, prompt, SYSTEM_PROMPT, reasoning_effort="low"
    )
    return name, result, time.time() - t0


async def main():
    api_key = os.environ["OPENROUTER_API_KEY"]
    t_start = time.time()
    results = await asyncio.gather(
        *(summarize_one(api_key, name, path) for name, path in DOCS.items())
    )
    t_total = time.time() - t_start

    print(f"TOTAL WALL CLOCK: {t_total:.2f}s\n")
    for name, result, elapsed in results:
        print(f"=== {name} ({elapsed:.2f}s) ===")
        print(result)
        print()


asyncio.run(main())
