#!/usr/bin/env python3
"""Make MP3 voice-overs from a scripts.json ({name: {voice, text}}) written by build.py / build_termine.py.

Needs internet access to Microsoft's neural TTS (pip install edge-tts).
Runs in the cloud (speech.platform.bing.com is allowed; uses HTTPS_PROXY) or on the Mac.
Existing MP3s are kept, so re-running only makes the new clips. Delete an MP3 to remake it.
Usage: python3 tts.py <scripts.json> <out_dir>
"""
import asyncio, json, os, pathlib, sys
import edge_tts


async def main(src, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    sem = asyncio.Semaphore(4)

    async def one(name, item):
        target = out / f"{name}.mp3"
        if target.exists() and target.stat().st_size > 0:
            return
        async with sem:
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(item["text"], item["voice"], rate="-10%", proxy=proxy).save(str(target))
                    print(name, target.stat().st_size, flush=True)
                    return
                except Exception as e:  # network hiccup: retry
                    print(name, "retry", attempt + 1, e, flush=True)
                    await asyncio.sleep(3)

    await asyncio.gather(*(one(k, v) for k, v in json.loads(pathlib.Path(src).read_text()).items()))


asyncio.run(main(sys.argv[1], sys.argv[2]))
