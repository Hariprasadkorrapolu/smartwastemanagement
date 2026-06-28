# Smart Waste Management System

A Django MVP for ML-powered waste image submissions. Users upload images, TensorFlow/Keras classifies them, invalid uploads are rejected, and valid uploads receive category-based points automatically.

## Run Locally

```powershell
.\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/.

## Admin Access

Create an admin user when needed:

```powershell
.\\.venv\\Scripts\\python.exe manage.py createsuperuser
```

Then open http://127.0.0.1:8000/admin/ to review submissions and inspect category, status, and points.

## ML Integration

The Teachable Machine model files live in:

```text
ml_model/keras_model.h5
ml_model/labels.txt
```

Prediction logic is in:

```text
ml_model/predictor.py
```

Reusable function:

```python
def predict_waste(image_path):
    ...
```

## Verification

```powershell
.\\.venv\\Scripts\\python.exe manage.py test
.\\.venv\\Scripts\\python.exe manage.py check
```
