from functools import lru_cache
from pathlib import Path

import numpy as np

from django.conf import settings
from PIL import Image, UnidentifiedImageError
import traceback
import logging

logger = logging.getLogger(__name__)


class PredictionError(Exception):
    """Raised when the ML predictor cannot process an uploaded image."""


def _clean_label(raw_label):
    label = raw_label.strip()
    if " " in label:
        prefix, value = label.split(" ", 1)
        if prefix.isdigit():
            return value.strip()
    return label


@lru_cache(maxsize=1)
def load_labels():
    labels_path = Path(settings.ML_LABELS_PATH)
    if not labels_path.exists():
        raise PredictionError(f"Labels file not found: {labels_path}")
    return [_clean_label(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def load_model():
    # TensorFlow/Keras is imported inside the cached loader so Django can start
    # cleanly for non-prediction commands and the model is still loaded only once.
    model_path = Path(settings.ML_MODEL_PATH)
    if not model_path.exists():
        raise PredictionError(f"Model file not found: {model_path}")

    from tensorflow.keras.layers import DepthwiseConv2D
    from tensorflow.keras.models import load_model as keras_load_model

    class TeachableMachineDepthwiseConv2D(DepthwiseConv2D):
        def __init__(self, *args, **kwargs):
            # Older Teachable Machine H5 exports may include this Keras 2 config
            # key, which modern Keras 3 DepthwiseConv2D no longer accepts.
            kwargs.pop("groups", None)
            super().__init__(*args, **kwargs)

    return keras_load_model(
        model_path,
        compile=False,
        custom_objects={"DepthwiseConv2D": TeachableMachineDepthwiseConv2D},
    )


def _preprocess_image(image_path):
    try:
        with Image.open(image_path) as image:
            # Teachable Machine image models expect RGB 224x224 tensors.
            image = image.convert("RGB").resize((224, 224))
            image_array = np.asarray(image, dtype=np.float32)
    except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
        raise PredictionError("Invalid or corrupted image upload.") from exc

    # Teachable Machine Keras exports commonly use [-1, 1] normalization.
    normalized_image = (image_array / 127.5) - 1
    return np.expand_dims(normalized_image, axis=0)


def predict_waste(image_path):
    """Return the predicted waste category and confidence for an image path."""
    try:
        model = load_model()
        labels = load_labels()
        input_tensor = _preprocess_image(image_path)
        predictions = model.predict(input_tensor, verbose=0)
    except PredictionError:
        raise
    except Exception as exc:
    logger.exception("TensorFlow prediction failed")
    traceback.print_exc()
    raise PredictionError(str(exc)) from exc

    scores = np.asarray(predictions)[0]
    predicted_index = int(np.argmax(scores))
    if predicted_index >= len(labels):
        raise PredictionError("Model output does not match labels.txt.")

    return {
        "category": labels[predicted_index],
        "confidence": float(scores[predicted_index]),
    }
