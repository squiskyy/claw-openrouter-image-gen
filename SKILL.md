name: openrouter-image-gen
description: Batch-generate images via OpenRouter API or local LiteLLM. Uses images/generations API by default with local LiteLLM for free inference.
homepage: https://openrouter.ai/docs/guides/overview/multimodal/image-generation
metadata:
  {
    "openclaw": {
      "emoji": "🖼️",
      "requires": { "bins": ["python3"], "env": ["OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"] },
      "primaryEnv": "OPENROUTER_API_KEY",
      "optionalEnv": ["OPENROUTER_BASE_URL"],
      "install": [
        {
          "id": "python-brew",
          "kind": "brew",
          "formula": "python",
          "bins": ["python3"],
          "label": "Install Python (brew)",
        }
      ],
    }
  }

# OpenRouter Image Gen

Generate images via OpenRouter's API or local LiteLLM deployment.

## Quick Start

```bash
cd {baseDir}
python3 scripts/gen.py --prompt "A cute cartoon penguin wearing sunglasses"
```

This uses the **local LiteLLM** endpoint by default (free!) via the `.env` file.

## Environment Setup

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your API key and base URL
```

Or set environment variables:

```bash
export OPENROUTER_API_KEY="your-key"
export OPENROUTER_BASE_URL="https://api.ai.create.kcl.ac.uk"
```

## Usage

```bash
# Generate an image (default: 1 image, local LiteLLM via .env)
python3 scripts/gen.py --prompt "cute cartoon penguin"

# Generate multiple images with different seeds
python3 scripts/gen.py --prompt "cute cartoon penguin" --count 4 --seed 1000

# Use a different model
python3 scripts/gen.py --prompt "cute cartoon penguin" --model flux-9b

# Use OpenRouter instead of local (costs money!)
OPENROUTER_BASE_URL="https://openrouter.ai/api/v1" python3 scripts/gen.py --api-method chat --model google/gemini-3.1-flash-image-preview --prompt "cute cartoon penguin"
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt` | (random) | Prompt for image generation |
| `--count` | 1 | Number of images to generate |
| `--seed` | none | Starting seed (increments for each image) |
| `--model` | arc:image | Model ID to use |
| `--api-method` | images | `chat` or `images` API method |
| `--image-size` | 1024x1024 | Image size (for images API) |
| `--out-dir` | ./tmp/... | Output directory |

## API Methods

### images (default, recommended)
Uses `/v1/images/generations` - compatible with local LiteLLM and OpenAI models.

Best for: Local deployment with Flux, Arc, DALL-E, etc.

### chat
Uses `/v1/chat/completions` with modalities parameter - OpenRouter-specific.

Best for: OpenRouter models like Gemini 3.1 Flash, Riverflow, Seedream.

## Supported Models

### Local LiteLLM (via .env):
- `arc:image` (default, works great for cartoons!)
- `flux-9b` (if deployed)
- `gpt-image-1` (via OpenRouter)
- Any model deployed behind your LiteLLM

### OpenRouter (chat completions):
- `google/gemini-3.1-flash-image-preview` (fastest)
- `sourceful/riverflow-v2-pro`
- `sourceful/riverflow-v2-fast`
- `black-forest-labs/flux.2-max`
- `bytedance-seed/seedream-4.5`
- `openai/gpt-5-image`

## Output

- `*.png` images
- `prompts.json` (prompt → file mapping)
- `index.html` (thumbnail gallery)

## Examples

### Penguin with laptop (simple prompt - works great with arc:image)
```bash
python3 scripts/gen.py --prompt "cute friendly cartoon penguin wearing sunglasses and sitting at a laptop computer, gradient colorful background, modern profile photo style"
```

### Penguin with sweater and geometric background (detailed prompt)
```bash
python3 scripts/gen.py --prompt "A cute, soft-3D cartoon illustration of a penguin wearing a cozy knitted sweater and sitting at a laptop, working. The background is a vibrant modern gradient transitioning from warm coral to cool teal, featuring subtle floating geometric vector shapes like triangles and circles, soft bokeh light effects"
```

### Sea otter (arc:image handles simple prompts beautifully!)
```bash
python3 scripts/gen.py --prompt "A cute baby sea otter"
```
