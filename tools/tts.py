#!/usr/bin/env python3
"""Make MP3 voice-overs from <slug>/audio/scripts.json (written by build.py).

Needs internet access to Microsoft's neural TTS (pip install edge-tts).
Runs in the cloud (speech.platform.bing.com is allowed; uses HTTPS_PROXY) or on the Mac.
Usage: python3 tts.py <scripts.json> <out_dir>
"""
import asyncio, json, os, pathlib, sys
import edge_tts


async def main(src, out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for lang, item in json.loads(pathlib.Path(src).read_text()).items():
        target = out / f"{lang}.mp3"
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        await edge_tts.Communicate(item["text"], item["voice"], rate="-10%", proxy=proxy).save(str(target))
        print(lang, target.stat().st_size)


asyncio.run(main(sys.argv[1], sys.argv[2]))
