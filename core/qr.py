from io import BytesIO

import qrcode


def eco_id_payload(user):
    profile = user.profile
    return "\n".join(
        [
            f"username: {user.username}",
            f"user_id: {user.pk}",
            f"eco_badge: {profile.badge_name}",
            f"points: {profile.total_points}",
        ]
    )


def build_eco_id_qr(user):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(eco_id_payload(user))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#14532d", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
