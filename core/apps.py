import os

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return
        try:
            from ml_model.predictor import load_labels, load_model

            # Warm the cached TensorFlow/Keras model once when the dev server starts.
            load_labels()
            load_model()
        except Exception:
            # Upload handling reports model errors to users without crashing Django startup.
            pass
