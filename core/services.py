from django.conf import settings

from ml_model.predictor import PredictionError, predict_waste

from .models import Submission


def points_for_category(category):
    """Return the configured score for a final ML category."""
    return settings.ML_CATEGORY_POINTS.get(category, 0)


def classify_submission(submission, uploaded_image=None):
    """Run ML prediction and persist status, category, internal confidence, and points."""
    try:
        prediction = predict_waste(uploaded_image or submission.image)
        category = prediction["category"]
        confidence = prediction["confidence"]
    except PredictionError as exc:
        submission.status = Submission.STATUS_REJECTED
        submission.points = 0
        submission.waste_type = ""
        submission.waste_category = ""
        submission.prediction_confidence = None
        submission.rejection_reason = str(exc)
        submission.save()
        return submission

    submission.waste_type = category
    submission.waste_category = category
    submission.prediction_confidence = confidence

    # Check for duplicate submission (same user, same image_hash, within 24 hours)
    from django.utils import timezone
    from datetime import timedelta
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    is_duplicate = False
    if submission.image_hash:
        is_duplicate = Submission.objects.filter(
            user=submission.user,
            image_hash=submission.image_hash,
            timestamp__gte=twenty_four_hours_ago
        ).exclude(pk=submission.pk).exists()

    if is_duplicate:
        submission.status = Submission.STATUS_DUPLICATE
        submission.points = 0
        submission.rejection_reason = "Image analyzed successfully. This image was already submitted within the last 24 hours. No additional points were awarded."
    else:
        # Confidence is stored for backend auditing but is not shown to users.
        # Low-confidence or explicit Invalid predictions are rejected automatically.
        if confidence < settings.ML_CONFIDENCE_THRESHOLD or category == Submission.CATEGORY_INVALID:
            submission.status = Submission.STATUS_REJECTED
            submission.points = 0
            submission.rejection_reason = "Submission could not be classified confidently."
        else:
            submission.status = Submission.STATUS_APPROVED
            submission.points = points_for_category(category)
            submission.rejection_reason = ""

    submission.save()
    return submission
