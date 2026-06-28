from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html

from .models import Friend, Guideline, Profile, Submission


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    readonly_fields = ("total_points",)
    fieldsets = (
        ("Eco Profile", {"fields": ("total_points", "preferred_waste_category")}),
        (
            "Contact",
            {"fields": ("mobile_number",)},
        ),
        (
            "Address",
            {
                "fields": (
                    "door_number",
                    "area_locality",
                    "area_type",
                    "district",
                    "ward_number",
                    "pincode",
                )
            },
        ),
    )


class CustomUserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "total_points")
    search_fields = ("username", "email", "first_name", "last_name")
    inlines = (ProfileInline,)

    @admin.display(description="Total points")
    def total_points(self, obj):
        return getattr(obj.profile, "total_points", 0)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "friend",
        "preview",
        "status",
        "waste_category",
        "waste_type",
        "points",
        "submitted_at_ist",
    )
    list_display_links = ("id", "preview")
    list_filter = ("status", "waste_category", "timestamp")
    search_fields = ("user__username", "friend__name", "waste_type", "waste_category")
    readonly_fields = ("submitted_at_ist", "preview")
    fields = (
        "user",
        "friend",
        "image",
        "preview",
        "status",
        "waste_category",
        "waste_type",
        "rejection_reason",
        "points",
        "submitted_at_ist",
    )
    actions = ("mark_pending", "reject_selected")

    @admin.display(description="Image")
    def preview(self, obj):
        if not obj.image:
            return "-"
        return format_html('<img src="{}" style="height:70px;border-radius:6px;" />', obj.image.url)

    @admin.display(description="Submitted at (IST)", ordering="timestamp")
    def submitted_at_ist(self, obj):
        if not obj.timestamp:
            return "-"
        formatted = timezone.localtime(obj.timestamp).strftime("%d %b %Y, %I:%M %p")
        return formatted.replace(", 0", ", ", 1)

    @admin.action(description="Mark selected submissions as pending")
    def mark_pending(self, request, queryset):
        for submission in queryset:
            submission.status = Submission.STATUS_PENDING
            submission.save()

    @admin.action(description="Reject selected submissions")
    def reject_selected(self, request, queryset):
        for submission in queryset:
            submission.status = Submission.STATUS_REJECTED
            submission.save()


@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    list_display = ("name", "contact", "linked_user")
    search_fields = ("name", "contact", "linked_user__username")


@admin.register(Guideline)
class GuidelineAdmin(admin.ModelAdmin):
    list_display = (
        "display_order",
        "icon",
        "title",
        "category",
        "media_type",
        "is_active",
        "created_at_ist",
    )
    list_display_links = ("title",)
    list_editable = ("display_order", "is_active")
    list_filter = ("category", "media_type", "is_active")
    search_fields = ("title", "short_description", "detailed_tips", "recycling_tips")
    fieldsets = (
        (
            "Learning Card",
            {
                "fields": (
                    "is_active",
                    "display_order",
                    "category",
                    "icon",
                    "theme_color",
                    "title",
                    "short_description",
                    "badge_labels",
                )
            },
        ),
        (
            "Learning Content",
            {
                "fields": (
                    "detailed_tips",
                    "dos",
                    "donts",
                    "recycling_tips",
                    "ai_eco_tip",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "media_type",
                    "media_file",
                    "youtube_url",
                )
            },
        ),
        ("System", {"fields": ("created_at_ist",)}),
    )
    readonly_fields = ("created_at_ist",)

    @admin.display(description="Created at (IST)", ordering="created_at")
    def created_at_ist(self, obj):
        if not obj.created_at:
            return "-"
        formatted = timezone.localtime(obj.created_at).strftime("%d %b %Y, %I:%M %p")
        return formatted.replace(", 0", ", ", 1)


try:
    admin.site.unregister(User)
except NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)
admin.site.site_header = "Smart Waste Management Admin"
admin.site.site_title = "Waste Admin"
admin.site.index_title = "Admin Validation Dashboard"
