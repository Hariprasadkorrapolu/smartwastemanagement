from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("scan-for-friend/", views.friend_submission, name="friend_submission"),
    path("rewards/", views.rewards, name="rewards"),
    path("guidelines/", views.guidelines, name="guidelines"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("profile/", views.profile, name="profile"),
    path("profile/eco-id/", views.eco_id_qr_download, name="eco_id_qr_download"),
]
