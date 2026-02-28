#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from html import escape as html_escape
from pathlib import Path


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "image"


def default_out_dir() -> Path:
    now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    preferred = Path.home() / "Projects" / "tmp"
    base = preferred if preferred.is_dir() else Path("./tmp")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"claw-openrouter-image-gen-{now}"


def pick_prompts(count: int) -> list[str]:
    subjects = [
        "a lobster astronaut",
        "a brutalist lighthouse",
        "a cozy reading nook",
        "a cyberpunk noodle shop",
        "a Vienna street at dusk",
        "a minimalist product photo",
        "a surreal underwater library",
    ]
    styles = [
        "ultra-detailed studio photo",
        "35mm film still",
        "isometric illustration",
        "editorial photography",
        "soft watercolor",
        "architectural render",
        "high-contrast monochrome",
    ]
    lighting = [
        "golden hour",
        "overcast soft light",
        "neon lighting",
        "dramatic rim light",
        "candlelight",
        "foggy atmosphere",
    ]
    prompts: list[str] = []
    for _ in range(count):
        prompts.append(
            f"{random.choice(styles)} of {random.choice(subjects)}, {random.choice(lighting)}"
        )
    return prompts


def request_images(
    api_key: str,
    prompt: str,
    model: str = "google/gemini-3.1-flash-image-preview",
) -> dict:
    """Generate an image via OpenRouter API. Tries image+text modality first, falls back to image only."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # First try with image + text modality
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "modalities": ["image", "text"],
    }
    
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            method="POST",
            headers=headers,
            data=body,
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # If 404 or unsupported modality, fall back to image only
        if e.code == 404:
            # Retry with image-only modality
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "modalities": ["image"],
            }
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                method="POST",
                headers=headers,
                data=body,
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e2:
                payload = e2.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"OpenRouter API failed ({e2.code}): {payload}") from e2
        else:
            # Some other error (429 rate limit, etc.)
            payload = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter API failed ({e.code}): {payload}") from e


def write_gallery(out_dir: Path, items: list[dict]) -> None:
    thumbs = "\n".join(
        [
            f"""
<figure>
  <a href="{html_escape(it["file"], quote=True)}"><img src="{html_escape(it["file"], quote=True)}" loading="lazy" /></a>
  <figcaption>{html_escape(it["prompt"])}</figcaption>
</figure>
""".strip()
            for it in items
        ]
    )
    html = f"""<!doctype html>
<meta charset="utf-8" />
<title>claw-openrouter-image-gen</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 24px; font: 14px/1.4 ui-sans-serif, system-ui; background: #0b0f14; color: #e8edf2; }}
  h1 {{ font-size: 18px; margin: 0 0 16px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  figure {{ margin: 0; padding: 12px; border: 1px solid #1e2a36; border-radius: 14px; background: #0f1620; }}
  img {{ width: 100%; height: auto; border-radius: 10px; display: block; }}
  figcaption {{ margin-top: 10px; color: #b7c2cc; }}
  code {{ color: #9cd1ff; }}
</style>
<h1>claw-openrouter-image-gen</h1>
<p>Output: <code>{html_escape(out_dir.as_posix())}</code></p>
<div class="grid">
{thumbs}
</div>
"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate images via OpenRouter API.")
    ap.add_argument("--prompt", help="Single prompt. If omitted, random prompts are generated.")
    ap.add_argument("--count", type=int, default=8, help="How many images to generate.")
    ap.add_argument("--model", default="google/gemini-3.1-flash-image-preview", help="Image model id (default: google/gemini-3.1-flash-image-preview).")
    ap.add_argument("--out-dir", default="", help="Output directory (default: ./tmp/claw-openrouter-image-gen-<ts>).")
    args = ap.parse_args()

    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        print("Missing OPENROUTER_API_KEY", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = [args.prompt] * args.count if args.prompt else pick_prompts(args.count)

    items: list[dict] = []
    for idx, prompt in enumerate(prompts, start=1):
        print(f"[{idx}/{len(prompts)}] {prompt}")
        res = request_images(
            api_key,
            prompt,
            args.model,
        )

        # Parse response - OpenRouter returns images in the assistant message
        message = res.get("choices", [{}])[0].get("message", {})
        images = message.get("images", [])

        if not images:
            raise RuntimeError(f"Unexpected response: {json.dumps(res)[:400]}")

        # Get the image URL (can be base64 data URL or HTTP URL)
        image_data = images[0].get("image_url", {})
        image_url = image_data.get("url", "")

        filename = f"{idx:03d}-{slugify(prompt)[:40]}.png"
        filepath = out_dir / filename

        # Handle base64 data URLs
        if image_url.startswith("data:"):
            # Extract base64 data from data URL like "data:image/png;base64,..."
            header, b64data = image_url.split(",", 1)
            filepath.write_bytes(base64.b64decode(b64data))
        else:
            # Download from URL
            try:
                urllib.request.urlretrieve(image_url, filepath)
            except urllib.error.URLError as e:
                raise RuntimeError(f"Failed to download image from {image_url}: {e}") from e

        items.append({"prompt": prompt, "file": filename})

    (out_dir / "prompts.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    write_gallery(out_dir, items)
    print(f"\nWrote: {(out_dir / 'index.html').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
