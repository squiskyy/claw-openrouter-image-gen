#!/usr/bin/env python3
"""OpenRouter image generation script.

Generates images via OpenRouter's API with automatic fallback for different
modalities. Supports multiple models and produces a gallery HTML page.
"""

from __future__ import annotations

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
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path
from typing import NamedTuple

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google/gemini-3.1-flash-image-preview"
API_URL = os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
API_TIMEOUT = 300

# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ImageResult:
    """Result from the OpenRouter API."""
    prompt: str
    filename: str
    file_path: Path


@dataclass
class GalleryItem:
    """Item for the HTML gallery."""
    prompt: str
    filename: str


# ============================================================================
# Utilities
# ============================================================================

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "image"


def default_out_dir() -> Path:
    """Get default output directory."""
    now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    preferred = Path.home() / "Projects" / "tmp"
    base = preferred if preferred.is_dir() else Path("./tmp")
    base.mkdir(parents=True, exist_ok=True)
    return base / f"claw-openrouter-image-gen-{now}"


def pick_prompts(count: int) -> list[str]:
    """Generate random creative prompts."""
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
    
    return [
        f"{random.choice(styles)} of {random.choice(subjects)}, {random.choice(lighting)}"
        for _ in range(count)
    ]


# ============================================================================
# API Functions
# ============================================================================

class OpenRouterAPI:
    """OpenRouter API client with fallback handling."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _make_request(self, model: str, prompt: str, modalities: list[str]) -> dict:
        """Make a request to the OpenRouter API."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": modalities,
        }

        req = urllib.request.Request(
            API_URL,
            method="POST",
            headers=self.headers,
            data=json.dumps(payload).encode("utf-8"),
        )

        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate_image(self, model: str, prompt: str) -> dict:
        """
        Generate an image via OpenRouter API.

        Tries modalities in order:
        1. ["image", "text"] - Full multimodal
        2. ["image"] - Image only fallback

        Raises:
            RuntimeError: If all attempts fail.
        """
        for modalities in [["image", "text"], ["image"]]:
            try:
                return self._make_request(model, prompt, modalities)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # Try next modality
                # Other errors (429, etc.) - raise immediately
                payload = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"OpenRouter API failed ({e.code}): {payload}") from e

        # If we get here, all modalities failed
        msg = "OpenRouter API failed: no supported modalities available"
        raise RuntimeError(msg)


def extract_image_url(response: dict) -> str | None:
    """Extract the image URL from the API response."""
    message = response.get("choices", [{}])[0].get("message", {})
    images = message.get("images", [])
    
    if not images:
        return None
    
    return images[0].get("image_url", {}).get("url")


# ============================================================================
# File Handling
# ============================================================================

def download_image(image_url: str, filepath: Path) -> None:
    """Download an image from a URL or base64 data URL."""
    if image_url.startswith("data:"):
        # Extract base64 data from data URL
        _, b64data = image_url.split(",", 1)
        filepath.write_bytes(base64.b64decode(b64data))
    else:
        urllib.request.urlretrieve(image_url, filepath)


def write_gallery(out_dir: Path, items: list[GalleryItem]) -> None:
    """Write an HTML gallery page."""
    thumbs = "\n".join(
        f"""<figure>
  <a href="{html_escape(item.filename, quote=True)}"><img src="{html_escape(item.filename, quote=True)}" loading="lazy" /></a>
  <figcaption>{html_escape(item.prompt)}</figcaption>
</figure>"""
        for item in items
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


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate images via OpenRouter API.")
    parser.add_argument("--prompt", help="Single prompt. If omitted, random prompts are generated.")
    parser.add_argument("--count", type=int, default=8, help="How many images to generate.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Image model id (default: {DEFAULT_MODEL}).")
    parser.add_argument("--out-dir", default="", help="Output directory (default: ./tmp/claw-openrouter-image-gen-<ts>).")
    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("Missing OPENROUTER_API_KEY", file=sys.stderr)
        return 2

    # Setup
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    api = OpenRouterAPI(api_key)
    prompts = [args.prompt] * args.count if args.prompt else pick_prompts(args.count)

    # Generate images
    items: list[GalleryItem] = []
    for idx, prompt in enumerate(prompts, start=1):
        print(f"[{idx}/{len(prompts)}] {prompt}")

        res = api.generate_image(args.model, prompt)
        image_url = extract_image_url(res)

        if not image_url:
            raise RuntimeError(f"Unexpected response: {json.dumps(res)[:400]}")

        filename = f"{idx:03d}-{slugify(prompt)[:40]}.png"
        filepath = out_dir / filename
        download_image(image_url, filepath)

        items.append(GalleryItem(prompt=prompt, filename=filename))

    # Save metadata
    (out_dir / "prompts.json").write_text(
        json.dumps([{"prompt": item.prompt, "file": item.filename} for item in items], indent=2),
        encoding="utf-8"
    )
    write_gallery(out_dir, items)

    print(f"\nWrote: {(out_dir / 'index.html').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
