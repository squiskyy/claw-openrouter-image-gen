#!/usr/bin/env python3
"""OpenRouter image generation script.

Generates images via OpenRouter's API with support for multiple API methods:
- Chat Completions: Uses the chat/completions endpoint with modalities
- Images Generations: Uses the v1/images/generations endpoint

Supports local LiteLLM deployment by configuring the base URL.
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

# ============================================================================
# Constants
# ============================================================================

DEFAULT_MODEL = "google/gemini-3.1-flash-image-preview"
DEFAULT_IMAGE_SIZE = "1024x1024"
API_TIMEOUT = 300

# Default base URL - can be overridden via OPENROUTER_BASE_URL env var
# If not set, defaults to OpenRouter; append appropriate endpoint path
DEFAULT_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# ============================================================================
# Data Classes
# ============================================================================


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
# API Classes
# ============================================================================

class ChatCompletionsAPI:
    """Chat Completions API client (OpenRouter default)."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.url = f"{base_url}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def generate_image(self, model: str, prompt: str) -> dict:
        """Generate image via chat completions with modality fallback."""
        for modalities in [["image", "text"], ["image"]]:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "modalities": modalities,
                }

                req = urllib.request.Request(
                    self.url,
                    method="POST",
                    headers=self.headers,
                    data=json.dumps(payload).encode("utf-8"),
                )

                with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # Try next modality
                payload = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API failed ({e.code}): {payload}") from e

        raise RuntimeError("API failed: no supported modalities available")

    def extract_image_url(self, response: dict) -> str | None:
        """Extract image URL from chat completions response."""
        message = response.get("choices", [{}])[0].get("message", {})
        images = message.get("images", [])
        if not images:
            return None
        return images[0].get("image_url", {}).get("url")


class ImagesGenerationsAPI:
    """Images Generations API client (OpenAI-compatible)."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.url = f"{base_url}/images/generations"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def generate_image(self, model: str, prompt: str, size: str = DEFAULT_IMAGE_SIZE, seed: int = None) -> dict:
        """Generate image via images/generations endpoint."""
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            # Request base64 JSON response for embedded images
            "extra_body": {
                "response_format": "b64_json"
            }
        }
        
        # Add seed for variation if provided
        if seed is not None:
            payload["seed"] = seed

        req = urllib.request.Request(
            self.url,
            method="POST",
            headers=self.headers,
            data=json.dumps(payload).encode("utf-8"),
        )

        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def extract_image_url(self, response: dict) -> str | None:
        """Extract image from images/generations response.
        
        Handles both URL and base64 responses:
        - {"data": [{"url": "https://..."}]}
        - {"data": [{"b64_json": "base64data..."}]}
        """
        data = response.get("data", [])
        if not data:
            return None
        
        item = data[0]
        
        # Check for base64 first (preferred for local)
        if item.get("b64_json"):
            return item["b64_json"]
        
        # Fall back to URL
        if item.get("url"):
            return item["url"]
        
        return None


# ============================================================================
# File Handling
# ============================================================================

def download_image(image_url: str, filepath: Path) -> None:
    """Download an image from a URL or handle base64 data URL."""
    if image_url.startswith("data:"):
        # Extract base64 data from data URL
        _, b64data = image_url.split(",", 1)
        filepath.write_bytes(base64.b64decode(b64data))
    elif image_url.startswith("data:image"):  # Without prefix
        import base64 as b64_module
        header, b64data = image_url.split(",", 1)
        filepath.write_bytes(b64_module.b64decode(b64data))
    elif image_url.startswith("http"):
        urllib.request.urlretrieve(image_url, filepath)
    else:
        # Assume it's base64 without data URL prefix
        filepath.write_bytes(base64.b64decode(image_url))


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
    parser.add_argument("--count", type=int, default=1, help="How many images to generate (default: 1).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Image model id (default: {DEFAULT_MODEL}).")
    parser.add_argument("--out-dir", default="", help="Output directory (default: ./tmp/claw-openrouter-image-gen-<ts>).")
    parser.add_argument(
        "--api-method",
        choices=["chat", "images"],
        default="chat",
        help="API method to use: 'chat' for /v1/chat/completions (default), 'images' for /v1/images/generations"
    )
    parser.add_argument(
        "--image-size",
        default=DEFAULT_IMAGE_SIZE,
        help=f"Image size for 'images' API method (default: {DEFAULT_IMAGE_SIZE}). Examples: 1024x1024, 1792x1024, 1024x1792"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed for images/generations API to get reproducible results. Will increment for each image if count > 1."
    )
    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("Missing OPENROUTER_API_KEY", file=sys.stderr)
        return 2

    # Get base URL
    base_url = os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)

    # Select API method
    if args.api_method == "images":
        api = ImagesGenerationsAPI(api_key, base_url)
    else:
        api = ChatCompletionsAPI(api_key, base_url)

    # Setup
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = [args.prompt] * args.count if args.prompt else pick_prompts(args.count)

    # Calculate seeds if provided
    start_seed = args.seed if args.seed else None

    # Generate images
    items: list[GalleryItem] = []
    for idx, prompt in enumerate(prompts, start=1):
        print(f"[{idx}/{len(prompts)}] {prompt}")

        # Calculate seed for this image (increment if multiple)
        current_seed = start_seed + idx - 1 if start_seed is not None else None

        if args.api_method == "images":
            res = api.generate_image(args.model, prompt, args.image_size, current_seed)
        else:
            res = api.generate_image(args.model, prompt)
        
        image_url = api.extract_image_url(res)

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
