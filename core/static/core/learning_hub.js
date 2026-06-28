document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".hub-category-card").forEach(function (card, index) {
        card.style.animationDelay = index * 60 + "ms";
        card.classList.add("learning-card--ready");
    });
});
