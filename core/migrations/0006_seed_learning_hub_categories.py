from django.db import migrations


DEFAULT_GUIDELINES = [
    {
        "category": "Wet Waste",
        "title": "Wet Waste",
        "short_description": "Food scraps, fruit peels, vegetable waste, tea leaves, and garden leftovers.",
        "detailed_tips": "Wet waste contains organic material that can decompose naturally. Keep it separate from dry waste so it can be composted safely and does not contaminate recyclable items.",
        "dos": "Use a green bin for food scraps.\nDrain excess liquid before disposal.\nCompost fruit peels, vegetable waste, and tea leaves.",
        "donts": "Do not mix plastic wrappers with food scraps.\nDo not throw wet waste into recyclable dry waste bags.\nDo not leave organic waste uncovered for long periods.",
        "recycling_tips": "Turn kitchen waste into compost for plants or community gardens. Small daily segregation habits reduce landfill smell and methane emissions.",
        "ai_eco_tip": "Segregating organic waste at the source makes composting cleaner and faster.",
        "badge_labels": "Biodegradable, Compostable",
        "icon": "🥬",
        "theme_color": "#11920f",
        "display_order": 1,
    },
    {
        "category": "Dry Waste",
        "title": "Dry Waste",
        "short_description": "Paper, plastic, glass, metal, cardboard, bottles, cans, and clean packaging.",
        "detailed_tips": "Dry waste includes reusable and recyclable materials. Keep it clean and dry so it can move efficiently into recycling channels.",
        "dos": "Rinse bottles and containers.\nFlatten cardboard boxes.\nStore paper, plastic, glass, and metal separately when possible.",
        "donts": "Do not add food-stained paper or oily containers.\nDo not mix sharp glass loosely with other waste.\nDo not wet recyclable material.",
        "recycling_tips": "Clean and dry recyclables have higher recovery value. Reuse containers before recycling them.",
        "ai_eco_tip": "Dry waste has the best recycling value when it is clean, dry, and sorted.",
        "badge_labels": "Recyclable, Reusable",
        "icon": "🗂️",
        "theme_color": "#1468d8",
        "display_order": 2,
    },
    {
        "category": "Sanitary Waste",
        "title": "Sanitary Waste",
        "short_description": "Used tissues, diapers, sanitary pads, masks, gloves, and hygiene waste.",
        "detailed_tips": "Sanitary waste needs careful handling because it may contain germs or biological contamination. Wrap it securely before disposal.",
        "dos": "Wrap sanitary waste before discarding.\nUse clearly marked disposal bags.\nFollow local collection rules for hygiene waste.",
        "donts": "Do not mix sanitary waste with recyclables.\nDo not leave used hygiene items exposed.\nDo not flush pads, diapers, or wipes.",
        "recycling_tips": "Most sanitary waste is not recyclable. Safe wrapping and separate disposal protects workers and communities.",
        "ai_eco_tip": "Safe sanitary waste disposal protects both public health and sanitation workers.",
        "badge_labels": "Non-Recyclable, Handle Safely",
        "icon": "🧻",
        "theme_color": "#dc1f26",
        "display_order": 3,
    },
    {
        "category": "Special Waste",
        "title": "Special Waste",
        "short_description": "Batteries, electronics, bulbs, chemicals, e-waste, and hazardous household items.",
        "detailed_tips": "Special waste should never enter normal bins. It may contain toxic, sharp, flammable, or electronically sensitive components.",
        "dos": "Store batteries and e-waste separately.\nUse authorized drop-off points.\nKeep chemicals sealed and labeled.",
        "donts": "Do not burn e-waste or batteries.\nDo not mix hazardous items with regular household waste.\nDo not break bulbs or electronic parts.",
        "recycling_tips": "Use certified e-waste recyclers and collection drives. Responsible disposal recovers valuable materials and prevents pollution.",
        "ai_eco_tip": "Special waste needs special care because small items can create big environmental damage.",
        "badge_labels": "Hazardous, Needs Special Care",
        "icon": "🔋",
        "theme_color": "#6d28d9",
        "display_order": 4,
    },
    {
        "category": "General Eco Tips",
        "title": "Daily Eco Habits",
        "short_description": "Small daily actions make waste management smarter and cleaner.",
        "detailed_tips": "Smart waste habits start with source segregation, responsible reuse, and consistent recycling.",
        "dos": "Segregate waste at home.\nReuse before recycling.\nTeach others simple bin habits.",
        "donts": "Do not mix all waste into one bag.\nDo not ignore local collection instructions.\nDo not contaminate clean recyclables.",
        "recycling_tips": "Create a simple two-bin or three-bin setup at home to make segregation effortless.",
        "ai_eco_tip": "Segregating waste correctly reduces pollution and helps in building a sustainable future.",
        "badge_labels": "Eco Habit, Daily Action",
        "icon": "🌍",
        "theme_color": "#0c9f8c",
        "display_order": 5,
    },
]


def seed_learning_hub(apps, schema_editor):
    Guideline = apps.get_model("core", "Guideline")
    for defaults in DEFAULT_GUIDELINES:
        Guideline.objects.update_or_create(
            category=defaults["category"],
            title=defaults["title"],
            defaults={**defaults, "is_active": True, "media_type": "None"},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_guideline_badge_labels"),
    ]

    operations = [
        migrations.RunPython(seed_learning_hub, migrations.RunPython.noop),
    ]
