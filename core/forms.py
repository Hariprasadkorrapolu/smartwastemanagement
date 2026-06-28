from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Friend, Profile, Submission


class SignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("image",)
        widgets = {
            "image": forms.ClearableFileInput(
                attrs={
                    "accept": "image/*",
                    "class": "form-control",
                }
            )
        }


class FriendSubmissionForm(forms.Form):
    friend_name = forms.CharField(max_length=120)
    contact = forms.CharField(max_length=120, required=False)
    image = forms.ImageField()

    def save(self, user):
        friend = Friend.objects.create(
            name=self.cleaned_data["friend_name"],
            contact=self.cleaned_data.get("contact", ""),
            linked_user=user,
        )
        return Submission.objects.create(
            user=user,
            friend=friend,
            image=self.cleaned_data["image"],
        )


class ProfileUpdateForm(forms.Form):
    full_name = forms.CharField(max_length=301, required=False, label="Full Name")
    mobile_number = forms.CharField(
        max_length=10,
        min_length=10,
        required=False,
        label="Mobile Number",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "pattern": r"\d{10}",
                "maxlength": "10",
                "oninput": "this.value=this.value.replace(/[^0-9]/g,'').slice(0,10)",
            }
        ),
    )
    door_number = forms.CharField(max_length=80, required=False, label="Door Number")
    area_locality = forms.CharField(max_length=180, required=False, label="Area / Locality")
    area_type = forms.ChoiceField(
        choices=[("", "Select area type"), *Profile.AREA_TYPE_CHOICES],
        required=False,
        label="Urban / Rural",
    )
    district = forms.CharField(max_length=120, required=False)
    ward_number = forms.CharField(max_length=40, required=False, label="Ward Number")
    pincode = forms.CharField(
        max_length=6,
        min_length=6,
        required=False,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "pattern": r"\d{6}",
                "maxlength": "6",
                "oninput": "this.value=this.value.replace(/[^0-9]/g,'').slice(0,6)",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        initial = kwargs.setdefault("initial", {})
        if user:
            profile = user.profile
            initial.update(
                {
                    "full_name": user.get_full_name(),
                    "mobile_number": profile.mobile_number,
                    "door_number": profile.door_number,
                    "area_locality": profile.area_locality,
                    "area_type": profile.area_type,
                    "district": profile.district,
                    "ward_number": profile.ward_number,
                    "pincode": profile.pincode,
                }
            )
        super().__init__(*args, **kwargs)
        if user:
            profile = user.profile
            for field in ["door_number", "area_locality", "area_type", "district", "ward_number", "pincode"]:
                if getattr(profile, field, ""):
                    self.fields[field].disabled = True

    def clean_mobile_number(self):
        value = self.cleaned_data["mobile_number"]
        if value and (not value.isdigit() or len(value) != 10):
            raise forms.ValidationError("Mobile number must contain exactly 10 digits.")
        return value

    def clean_pincode(self):
        value = self.cleaned_data["pincode"]
        if value and (not value.isdigit() or len(value) != 6):
            raise forms.ValidationError("Pincode must contain exactly 6 digits.")
        return value

    def save(self):
        user = self.user
        profile = user.profile
        name_parts = self.cleaned_data["full_name"].split(maxsplit=1)
        user.first_name = name_parts[0] if name_parts else ""
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        user.save(update_fields=["first_name", "last_name"])

        profile.mobile_number = self.cleaned_data["mobile_number"]
        profile.door_number = self.cleaned_data["door_number"]
        profile.area_locality = self.cleaned_data["area_locality"]
        profile.area_type = self.cleaned_data["area_type"]
        profile.district = self.cleaned_data["district"]
        profile.ward_number = self.cleaned_data["ward_number"]
        profile.pincode = self.cleaned_data["pincode"]
        profile.full_clean()
        profile.save()
        return user
