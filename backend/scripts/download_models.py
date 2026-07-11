"""
One-shot script to pre-download all classifier models to the local HF cache.
Run this before starting the server on a fresh machine:

    cd backend
    uv run python scripts/download_models.py
"""
from transformers import pipeline

MODELS = [
    ("image-classification", "dima806/deepfake_vs_real_image_detection"),
    ("audio-classification", "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification"),
]

if __name__ == "__main__":
    for task, model_id in MODELS:
        print(f"Downloading {model_id} ...")
        pipeline(task, model=model_id)
        print(f"  Done.")
    print("\nAll models cached in ~/.cache/huggingface/ and ready for local inference.")
