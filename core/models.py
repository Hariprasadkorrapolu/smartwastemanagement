from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone


BADGE_LEVELS = [
    {"name": "Beginner", "threshold": 0, "icon": "sprout"},
    {"name": "Eco Warrior", "threshold": 50, "icon": "shield"},
    {"name": "Recycler", "threshold": 150, "icon": "recycle"},
    {"name": "Eco Champion", "threshold": 500, "icon": "trophy"},
]


class Profile(models.Model):
    AREA_URBAN = "Urban"
    AREA_RURAL = "Rural"
    AREA_TYPE_CHOICES = [
        (AREA_URBAN, "Urban"),
        (AREA_RURAL, "Rural"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    total_points = models.PositiveIntegerField(default=0)
    mobile_number = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\d{10}$",
                message="Mobile number must contain exactly 10 digits.",
            )
        ],
    )
    door_number = models.CharField(max_length=80, blank=True)
    area_locality = models.CharField(max_length=180, blank=True)
    area_type = models.CharField(max_length=10, choices=AREA_TYPE_CHOICES, blank=True)
    district = models.CharField(max_length=120, blank=True)
    ward_number = models.CharField(max_length=40, blank=True)
    pincode = models.CharField(
        max_length=6,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\d{6}$",
                message="Pincode must contain exactly 6 digits.",
            )
        ],
    )
    preferred_waste_category = models.CharField(
        max_length=40,
        choices=[
            ("Wet Waste", "Wet Waste"),
            ("Dry Waste", "Dry Waste"),
            ("Sanitary Waste", "Sanitary Waste"),
            ("Special Waste", "Special Waste"),
        ],
        blank=True,
    )

    def __str__(self):
        return f"{self.user.username} profile"

    @property
    def badge_name(self):
        return self.current_badge["name"]

    @property
    def current_badge(self):
        return next(
            badge
            for badge in reversed(BADGE_LEVELS)
            if self.total_points >= badge["threshold"]
        )

    @property
    def next_badge(self):
        return next(
            (
                badge
                for badge in BADGE_LEVELS
                if badge["threshold"] > self.total_points
            ),
            None,
        )

    @property
    def completion_percentage(self):
        fields = [
            self.user.get_full_name(),
            self.user.email,
            self.mobile_number,
            self.door_number,
            self.area_locality,
            self.area_type,
            self.district,
            self.ward_number,
            self.pincode,
            self.preferred_waste_category,
        ]
        completed = sum(bool(value) for value in fields)
        return round((completed / len(fields)) * 100)


class Friend(models.Model):
    name = models.CharField(max_length=120)
    contact = models.CharField(max_length=120, blank=True)
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friends",
    )

    def __str__(self):
        return f"{self.name} ({self.linked_user.username})"


class Submission(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_DUPLICATE = "Duplicate Submission"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_DUPLICATE, "Duplicate Submission"),
    ]
    CATEGORY_WET = "Wet Waste"
    CATEGORY_DRY = "Dry Waste"
    CATEGORY_SANITARY = "Sanitary Waste"
    CATEGORY_SPECIAL = "Special Waste"
    CATEGORY_INVALID = "Invalid"

    CATEGORY_CHOICES = [
        (CATEGORY_WET, "Wet Waste"),
        (CATEGORY_DRY, "Dry Waste"),
        (CATEGORY_SANITARY, "Sanitary Waste"),
        (CATEGORY_SPECIAL, "Special Waste"),
        (CATEGORY_INVALID, "Invalid"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    friend = models.ForeignKey(
        Friend,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    image = models.ImageField(upload_to="submissions/")
    image_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    points = models.PositiveIntegerField(default=0)
    # ML prediction label kept compatible with the original rewards/dashboard views.
    waste_type = models.CharField(max_length=100, blank=True)
    waste_category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, blank=True)
    prediction_confidence = models.FloatField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if not self.image_hash and self.image:
            import hashlib
            sha256 = hashlib.sha256()
            try:
                if hasattr(self.image, "chunks"):
                    for chunk in self.image.chunks():
                        sha256.update(chunk)
                else:
                    with self.image.open("rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256.update(chunk)
            except Exception:
                try:
                    with open(self.image.path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256.update(chunk)
                except Exception:
                    pass
            self.image_hash = sha256.hexdigest()

        if self.status != self.STATUS_APPROVED:
            self.points = 0
        super().save(*args, **kwargs)

    def __str__(self):
        target = self.friend.name if self.friend else self.user.username
        return f"{target} - {self.status} - {self.points} pts"


class Guideline(models.Model):
    CATEGORY_WET = "Wet Waste"
    CATEGORY_DRY = "Dry Waste"
    CATEGORY_SANITARY = "Sanitary Waste"
    CATEGORY_SPECIAL = "Special Waste"
    CATEGORY_GENERAL = "General Eco Tips"

    CATEGORY_CHOICES = [
        (CATEGORY_WET, "Wet Waste"),
        (CATEGORY_DRY, "Dry Waste"),
        (CATEGORY_SANITARY, "Sanitary Waste"),
        (CATEGORY_SPECIAL, "Special Waste"),
        (CATEGORY_GENERAL, "General Eco Tips"),
    ]

    MEDIA_NONE = "None"
    MEDIA_IMAGE = "Image"
    MEDIA_VIDEO = "Video"
    MEDIA_YOUTUBE = "YouTube"

    MEDIA_TYPE_CHOICES = [
        (MEDIA_NONE, "None"),
        (MEDIA_IMAGE, "Uploaded image"),
        (MEDIA_VIDEO, "Uploaded video"),
        (MEDIA_YOUTUBE, "YouTube link"),
    ]

    CATEGORY_COLORS = {
        CATEGORY_WET: "#2f9e44",
        CATEGORY_DRY: "#1971c2",
        CATEGORY_SANITARY: "#e03131",
        CATEGORY_SPECIAL: "#7048e8",
        CATEGORY_GENERAL: "#0ca678",
    }

    category = models.CharField(
        max_length=40,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL,
    )
    title = models.CharField(max_length=180)
    short_description = models.CharField(max_length=240, blank=True)
    detailed_tips = models.TextField(blank=True)
    dos = models.TextField("Do's", blank=True)
    donts = models.TextField("Don'ts", blank=True)
    recycling_tips = models.TextField(blank=True)
    ai_eco_tip = models.TextField("AI Eco Tip", blank=True)
    badge_labels = models.CharField(
        max_length=180,
        blank=True,
        help_text="Comma-separated mini badges shown on the learning card.",
    )
    media_file = models.FileField(upload_to="guidelines/", blank=True)
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default=MEDIA_NONE,
    )
    youtube_url = models.URLField(blank=True)
    icon = models.CharField(max_length=12, default="\u267b")
    theme_color = models.CharField(max_length=20, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["display_order", "category", "title"]

    def __str__(self):
        return self.title

    @property
    def display_color(self):
        return self.theme_color or self.CATEGORY_COLORS.get(self.category, "#0ca678")

    @property
    def badge_list(self):
        if self.badge_labels:
            return [badge.strip() for badge in self.badge_labels.split(",") if badge.strip()]
        defaults = {
            self.CATEGORY_WET: ["Biodegradable", "Compostable"],
            self.CATEGORY_DRY: ["Recyclable", "Reusable"],
            self.CATEGORY_SANITARY: ["Non-Recyclable", "Handle Safely"],
            self.CATEGORY_SPECIAL: ["Hazardous", "Needs Special Care"],
            self.CATEGORY_GENERAL: ["Eco Habit", "Daily Action"],
        }
        return defaults.get(self.category, ["Learn", "Act"])

    @property
    def category_slug(self):
        return self.category.lower().replace(" ", "-")

    @property
    def youtube_video_id(self):
        if not self.youtube_url:
            return ""
        from urllib.parse import urlparse, parse_qs
        url = self.youtube_url.strip()
        parsed = urlparse(url)
        
        # youtu.be/xxx
        if parsed.netloc == "youtu.be" or parsed.netloc.endswith(".youtu.be"):
            path = parsed.path.lstrip('/')
            if path:
                return path.split('/')[0]
                
        # youtube.com/watch?v=xxx or youtube.com/v/xxx or youtube.com/embed/xxx or youtube.com/shorts/xxx
        if "youtube.com" in parsed.netloc or "youtube-nocookie.com" in parsed.netloc:
            if parsed.path == "/watch" or parsed.path.startswith("/watch/"):
                qs = parse_qs(parsed.query)
                if "v" in qs:
                    return qs["v"][0]
            if parsed.path.startswith("/embed/"):
                parts = parsed.path.split('/')
                if len(parts) > 2:
                    return parts[2]
            if parsed.path.startswith("/v/"):
                parts = parsed.path.split('/')
                if len(parts) > 2:
                    return parts[2]
            if parsed.path.startswith("/shorts/"):
                parts = parsed.path.split('/')
                if len(parts) > 2:
                    return parts[2]
                    
        # Fallbacks for incomplete or headless URLs
        if "youtube.com/watch" in url and "v=" in url:
            try:
                return url.split("v=", 1)[1].split("&", 1)[0]
            except Exception:
                pass
        if "youtu.be/" in url:
            try:
                return url.split("youtu.be/", 1)[1].split("?", 1)[0].split("/", 1)[0]
            except Exception:
                pass
                
        return ""

    @property
    def youtube_embed_url(self):
        video_id = self.youtube_video_id
        if video_id:
            return f"https://www.youtube-nocookie.com/embed/{video_id}"
        return ""

    @property
    def resolved_media_url_type(self):
        """
        Determines the type of the media provided in the youtube_url field.
        Returns: 'youtube', 'image', or 'invalid'
        """
        if not self.youtube_url:
            return "invalid"
            
        url = self.youtube_url.strip()
        
        # 1. Check if it is a YouTube URL
        if self.youtube_video_id:
            return "youtube"
            
        # 2. Check if it is an Image URL
        lower_url = url.lower()
        if any(lower_url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp", ".tiff"]) or "images" in lower_url:
            return "image"
            
        return "invalid"


def recalculate_total_points(user):
    approved_points = (
        Submission.objects.filter(user=user, status=Submission.STATUS_APPROVED)
        .aggregate(total=Sum("points"))
        .get("total")
        or 0
    )
    Profile.objects.update_or_create(user=user, defaults={"total_points": approved_points})


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Submission)
def sync_points_after_submission_save(sender, instance, **kwargs):
    recalculate_total_points(instance.user)


@receiver(post_delete, sender=Submission)
def sync_points_after_submission_delete(sender, instance, **kwargs):
    recalculate_total_points(instance.user)
