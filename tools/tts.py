#!/usr/bin/env python3
"""Make MP3 voice-overs from <slug>/audio/scripts.json (written by build.py).

Needs internet access to Microsoft's neural TTS (pip install edge-tts).
Runs on the user's Mac, because the cloud container cannot reach the TTS service.
Usage: python3 tts.py <scripts.json> <out_dir>
"""
import asyncio, json, pathlib, sys
import edge_tts


async def main(src, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for lang, item in json.loads(pathlib.Path(src).read_text()).items():
        target = out / f"{lang}.mp3"
        await edge_tts.Communicate(item["text"], item["voice"], rate="-10%").save(str(target))
        print(lang, target.stat().st_size)


asyncio.run(main(sys.argv[1], sys.argv[2]))
