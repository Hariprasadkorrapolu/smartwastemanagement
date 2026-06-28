import base64
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import FriendSubmissionForm, ProfileUpdateForm, SignupForm, SubmissionForm
from .models import BADGE_LEVELS, Guideline, Submission
from .qr import build_eco_id_qr
from .services import classify_submission


def available_home_carousel_images():
    images = []
    for index in range(1, 4):
        candidates = [
            f"images/corousel/slide{index}.jpg",
            f"images/corousel/silde{index}.jpg",
        ]
        image_path = next((path for path in candidates if finders.find(path)), None)
        if image_path:
            images.append(image_path)
    return images


@never_cache
@ensure_csrf_cookie
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("home")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def home(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.user = request.user
            submission.save()
            classify_submission(submission)
            if submission.status == Submission.STATUS_DUPLICATE:
                messages.warning(
                    request,
                    "Image analyzed successfully. This image was already submitted within the last 24 hours. No additional points were awarded."
                )
            request.session["ai_result"] = {
                "status": submission.status,
                "category": submission.waste_category or "Unclassified",
                "category_class": (submission.waste_category or "invalid")
                .lower()
                .replace(" ", "-"),
                "points": submission.points,
            }
            return redirect("home")
    else:
        form = SubmissionForm()

    ai_result = request.session.pop("ai_result", None)
    submissions = request.user.submissions.select_related("friend")
    return render(
        request,
        "core/home.html",
        {
            "form": form,
            "submissions": submissions,
            "total_points": request.user.profile.total_points,
            "ai_result": ai_result,
            "carousel_images": available_home_carousel_images(),
        },
    )


@login_required
def friend_submission(request):
    if request.method == "POST":
        form = FriendSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(request.user)
            classify_submission(submission)
            if submission.status == Submission.STATUS_DUPLICATE:
                messages.warning(
                    request,
                    "Image analyzed successfully. This image was already submitted within the last 24 hours. No additional points were awarded."
                )
            elif submission.status == Submission.STATUS_APPROVED:
                messages.success(
                    request,
                    f"Friend waste classified successfully as {submission.waste_category}.",
                )
            else:
                messages.warning(request, "Friend submission analyzed successfully, but it was rejected.")
            return redirect("home")
    else:
        form = FriendSubmissionForm()
    return render(request, "core/friend_submission.html", {"form": form})


@login_required
def rewards(request):
    profile = request.user.profile
    approved_submissions = request.user.submissions.filter(
        status=Submission.STATUS_APPROVED
    )
    total_points = profile.total_points
    current_badge = profile.current_badge
    next_badge = profile.next_badge
    if next_badge:
        points_into_badge = total_points - current_badge["threshold"]
        points_needed = next_badge["threshold"] - current_badge["threshold"]
        progress_percent = min(round((points_into_badge / points_needed) * 100), 100)
    else:
        progress_percent = 100

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    recent_totals = approved_submissions.aggregate(
        weekly_points=Sum("points", filter=Q(timestamp__date__gte=week_start)),
        monthly_points=Sum("points", filter=Q(timestamp__date__gte=month_start)),
        weekly_uploads=Count("pk", filter=Q(timestamp__date__gte=week_start)),
        monthly_uploads=Count("pk", filter=Q(timestamp__date__gte=month_start)),
    )

    category_counts = approved_submissions.values("waste_category").annotate(
        total=Count("pk")
    )
    category_count_map = {
        row["waste_category"]: row["total"] for row in category_counts
    }
    approved_count = approved_submissions.count()
    dry_count = category_count_map.get(Submission.CATEGORY_DRY, 0)
    special_count = category_count_map.get(Submission.CATEGORY_SPECIAL, 0)
    sanitary_count = category_count_map.get(Submission.CATEGORY_SANITARY, 0)

    activity_dates = {
        timezone.localtime(submission.timestamp).date()
        for submission in approved_submissions.only("timestamp")
    }
    streak = 0
    streak_day = today
    while streak_day in activity_dates:
        streak += 1
        streak_day -= timedelta(days=1)

    achievements = [
        {"name": "First Upload", "icon": "upload", "unlocked": approved_count >= 1},
        {"name": "100 Points Earned", "icon": "star", "unlocked": total_points >= 100},
        {"name": "Special Waste Expert", "icon": "hazard", "unlocked": special_count >= 3},
        {"name": "Dry Waste Recycler", "icon": "recycle", "unlocked": dry_count >= 3},
        {"name": "7 Day Activity Streak", "icon": "streak", "unlocked": streak >= 7},
        {"name": "Eco Contributor", "icon": "leaf", "unlocked": approved_count >= 10},
    ]

    category_meta = {
        Submission.CATEGORY_WET: {"class": "wet", "label": "Wet Waste", "icon": "leaf"},
        Submission.CATEGORY_DRY: {"class": "dry", "label": "Dry Waste", "icon": "recycle"},
        Submission.CATEGORY_SANITARY: {"class": "sanitary", "label": "Sanitary Waste", "icon": "hygiene"},
        Submission.CATEGORY_SPECIAL: {"class": "special", "label": "Special Waste", "icon": "hazard"},
    }
    activity = [
        {
            "submission": submission,
            "meta": category_meta.get(
                submission.waste_category,
                {
                    "class": "neutral",
                    "label": submission.waste_category or "Unclassified",
                    "icon": "leaf",
                },
            ),
        }
        for submission in approved_submissions[:20]
    ]

    users = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("-profile__total_points", "username")
    )
    eco_rank = next(
        (index for index, user in enumerate(users, start=1) if user.pk == request.user.pk),
        None,
    )

    return render(
        request,
        "core/rewards.html",
        {
            "approved_submissions": approved_submissions,
            "total_points": total_points,
            "badge": profile.badge_name,
            "current_badge": current_badge,
            "next_badge": next_badge,
            "progress_percent": progress_percent,
            "badge_levels": BADGE_LEVELS,
            "eco_rank": eco_rank,
            "user_rank": eco_rank,
            "achievements": achievements,
            "activity": activity,
            "weekly_points": recent_totals["weekly_points"] or 0,
            "monthly_points": recent_totals["monthly_points"] or 0,
            "weekly_uploads": recent_totals["weekly_uploads"] or 0,
            "monthly_uploads": recent_totals["monthly_uploads"] or 0,
            "total_uploads": approved_submissions.count(),
            "special_waste_count": approved_submissions.filter(
                waste_category=Submission.CATEGORY_SPECIAL
            ).count(),
            "impact": {
                "recyclable_items": dry_count,
                "hazardous_items": special_count,
                "sanitary_items": sanitary_count,
                "landfill_reduction": approved_count,
                "contributions": approved_count,
            },
        },
    )


@login_required
def guidelines(request):
    guidelines = Guideline.objects.filter(is_active=True)
    category_order = [
        Guideline.CATEGORY_WET,
        Guideline.CATEGORY_DRY,
        Guideline.CATEGORY_SANITARY,
        Guideline.CATEGORY_SPECIAL,
    ]
    category_guidelines = []
    for category in category_order:
        guideline = guidelines.filter(category=category).order_by("display_order", "title").first()
        if guideline:
            category_guidelines.append(guideline)
    ai_tip = guidelines.filter(category=Guideline.CATEGORY_GENERAL).first() or guidelines.first()
    return render(
        request,
        "core/guidelines.html",
        {
            "ai_tip": ai_tip,
            "category_guidelines": category_guidelines,
            "guidelines": guidelines,
        },
    )


@login_required
def leaderboard(request):
    from django.db.models import Avg, Q
    from .models import Submission
    
    # Fetch only top 10 active users to optimize query overhead
    top_users = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("-profile__total_points", "username")[:10]
    )
    
    rows = []
    for index, user in enumerate(top_users, start=1):
        points = getattr(user.profile, "total_points", 0)
        badge_level = getattr(user.profile, "current_badge", {}).get("name", "Beginner")
        waste_pref = getattr(user.profile, "preferred_waste_category", "") or "General"
        rows.append({
            "rank": index, 
            "user": user, 
            "points": points,
            "badge": badge_level,
            "waste_pref": waste_pref,
        })

    # Efficiently calculate current user's rank in DB
    current_user_points = request.user.profile.total_points
    better_users_count = User.objects.filter(
        Q(profile__total_points__gt=current_user_points) |
        Q(profile__total_points=current_user_points, username__lt=request.user.username),
        is_active=True
    ).count()
    current_rank = better_users_count + 1

    top_3 = rows[:3]

    total_waste_uploads = Submission.objects.filter(status=Submission.STATUS_APPROVED).count()
    highest_points = rows[0]["points"] if rows else 0
    
    # Calculate average citizen score directly in DB
    avg_score = User.objects.filter(is_active=True).aggregate(avg_score=Avg("profile__total_points"))["avg_score"]
    average_citizen_score = int(avg_score) if avg_score is not None else 0

    profile = request.user.profile
    current_badge = profile.current_badge
    next_badge = profile.next_badge
    if next_badge:
        points_into_badge = profile.total_points - current_badge["threshold"]
        points_needed = next_badge["threshold"] - current_badge["threshold"]
        progress_percent = min(round((points_into_badge / points_needed) * 100), 100)
    else:
        progress_percent = 100

    return render(
        request,
        "core/leaderboard.html",
        {
            "rows": rows, 
            "top_3": top_3,
            "current_rank": current_rank,
            "total_waste_uploads": total_waste_uploads,
            "highest_points": highest_points,
            "average_citizen_score": average_citizen_score,
            "current_user_points": profile.total_points,
            "current_badge": current_badge,
            "next_badge": next_badge,
            "progress_percent": progress_percent,
        },
    )


@login_required
def profile(request):
    profile_form = ProfileUpdateForm(user=request.user)
    password_form = PasswordChangeForm(request.user)
    edit_mode = request.GET.get("edit") == "1"

    if request.method == "POST":
        if "update_profile" in request.POST:
            edit_mode = True
            profile_form = ProfileUpdateForm(request.POST, user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect("profile")
        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")
                return redirect("profile")

    qr_png = build_eco_id_qr(request.user)
    recent_activity = request.user.submissions.filter(
        status=Submission.STATUS_APPROVED
    )[:5]
    return render(
        request,
        "core/profile.html",
        {
            "profile_form": profile_form,
            "password_form": password_form,
            "submissions": request.user.submissions.select_related("friend"),
            "total_points": request.user.profile.total_points,
            "profile_data": request.user.profile,
            "full_name": request.user.get_full_name() or request.user.username,
            "member_since": request.user.date_joined,
            "qr_data_uri": f"data:image/png;base64,{base64.b64encode(qr_png).decode('ascii')}",
            "recent_activity": recent_activity,
            "edit_mode": edit_mode,
        },
    )


@login_required
def eco_id_qr_download(request):
    response = HttpResponse(build_eco_id_qr(request.user), content_type="image/png")
    response["Content-Disposition"] = (
        f'attachment; filename="{request.user.username}-eco-id.png"'
    )
    return response
