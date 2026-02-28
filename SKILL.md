name: openrouter-image-gen
description: Batch-generate images via OpenRouter API. Supports various image generation models including Google Gemini, Sourceful Riverflow, Black Forest Labs Flux, ByteDance Seedream, and OpenAI GPT-5.
homepage: https://openrouter.ai/docs/guides/overview/multimodal/image-generation
metadata:
  {
    "openclaw": {
      "emoji": "🖼️",
      "requires": { "bins": ["python3"], "env": ["OPENROUTER_API_KEY"] },
      "primaryEnv": "OPENROUTER_API_KEY",
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

Generate images via OpenRouter's image generation API.

## Run

```bash
python3 {baseDir}/scripts/gen.py
open ~/Projects/tmp/claw-openrouter-image-gen-*/index.html  # if ~/Projects/tmp exists; else ./tmp/...
```

Useful flags:

```bash
# Generate multiple images with random prompts
python3 {baseDir}/scripts/gen.py --count 16

# Single prompt
python3 {baseDir}/scripts/gen.py --prompt "ultra-detailed studio photo of a lobster astronaut" --count 4

# Custom output directory
python3 {baseDir}/scripts/gen.py --out-dir ./out/images
```

## Supported Models

The default model is `google/gemini-3.1-flash-image-preview`. Available models:

- `google/gemini-3.1-flash-image-preview` (default, fastest)
- `sourceful/riverflow-v2-pro`
- `sourceful/riverflow-v2-fast`
- `black-forest-labs/flux.2-klein-4b`
- `black-forest-labs/flux.2-max`
- `black-forest-labs/flux.2-pro`
- `black-forest-labs/flux.2-flex`
- `bytedance-seed/seedream-4.5`
- `openai/gpt-5-image`

Example with a specific model:

```bash
python3 {baseDir}/scripts/gen.py --model black-forest-labs/flux.2-pro --count 4
```

## Output

- `*.png` images
- `prompts.json` (prompt → file mapping)
- `index.html` (thumbnail gallery)

## API Reference

See [OpenRouter Image Generation Docs](https://openrouter.ai/docs/guides/overview/multimodal/image-generation) for more information.
