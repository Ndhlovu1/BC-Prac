from datetime import timedelta
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from simple_history.models import HistoricalRecords
from .models import Client, Contact
from .forms import ClientForm, ContactForm, StaffLoginForm


################################################
# python manage.py test clientTrackerApp -v 2
################################################



def make_user(username="staff", password="pass12345", **kwargs):
    return get_user_model().objects.create_user(
        username=username, password=password, **kwargs
    )


def make_image(name="logo.png", size=(40, 40), color=(181, 28, 16)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")



"""
#############################################################
        Test Cases for Code prefix generator

    The 3-letter prefix is the basis of the client code shown everywhere in the UI and audit log. 
    A regression here silently breaks uniqueness logic in generate_client_code().
#############################################################

"""

class InitialsHelperTests(TestCase):
    """
    `_initials()` produces the 3-letter prefix used in `Client.code`.
    Expectations:
      - Multi-word names -> first letter of each of the first 3 words.
      - Single-word names -> pad from remaining letters in the name.
      - Very short names -> pad with random uppercase letters.
      - Output is always exactly 3 uppercase letters.
    """

    def test_multi_word_takes_first_letters(self):
        from .models import _initials
        self.assertEqual(_initials("Protea Hotel"), "PRO")

    def test_three_words_takes_all_firsts(self):
        from .models import _initials
        self.assertEqual(_initials("Hilton Garden Inn"), "HGI")

    def test_single_word_pads_from_same_word(self):
        from .models import _initials
        result = _initials("Hilton")
        self.assertEqual(len(result), 3)
        self.assertTrue(result.isalpha() and result.isupper())
        self.assertTrue(result.startswith("H"))

    def test_very_short_name_pads_with_random(self):
        from .models import _initials
        result = _initials("A")
        self.assertEqual(len(result), 3)
        self.assertTrue(result.isalpha() and result.isupper())
        self.assertEqual(result[0], "A")

    def test_non_alpha_and_punctuation_is_stripped(self):
        from .models import _initials
        result = _initials("Café 123 Ltd.")
        self.assertEqual(len(result), 3)
        self.assertTrue(result.isalpha() and result.isupper())
        # 'C' from Café, 'L' from Ltd, plus one padded char
        self.assertTrue(result.startswith("C"))
        self.assertIn("L", result)

    def test_always_exactly_three_chars(self):
        from .models import _initials
        for name in ["", " ", "!!", "A", "AB", "Alice Bob Carol Dave"]:
            with self.subTest(name=name):
                self.assertEqual(len(_initials(name)), 3)



"""
#############################################################
        Test Cases for Auto-Increment Logic

    The code is used by the client login view and must remain stable when a client is renamed (otherwise any bookmark/link 
    someone saved breaks). 
    Auto-increment must also survive concurrent inserts at the number boundary.
#############################################################

"""

class ClientCodeGenerationTests(TestCase):
    """
    Codes are `<PREFIX><NNN>` where PREFIX = initials(name), NNN increments
    for every existing client sharing that same prefix.
    """

    def test_first_client_gets_001(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(c.code, "PRO001")

    def test_second_client_with_same_prefix_increments(self):
        Client.objects.create(name="Protea Hotel")
        c2 = Client.objects.create(name="Protea Inn")
        self.assertEqual(c2.code, "PRO002")

    def test_different_prefix_starts_at_001(self):
        Client.objects.create(name="Protea Hotel")
        c2 = Client.objects.create(name="Hilton Gardens")
        self.assertEqual(c2.code, "HIL001")

    def test_three_number_overflow(self):
        # Simulate 999 existing
        for _ in range(3):
            Client.objects.create(name="Protea Hotel")
        last = Client.objects.order_by("-code").first()
        self.assertTrue(last.code.startswith("PRO"))
        self.assertEqual(last.code[3:], "003")

    def test_code_not_overwritten_on_edit(self):
        c = Client.objects.create(name="Protea Hotel")
        original = c.code
        c.name = "Protea Hotel & Spa"
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.code, original,
                         "Editing name must not regenerate the code")

    def test_code_is_six_chars(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(len(c.code), 6)
        self.assertTrue(c.code[:3].isalpha() and c.code[:3].isupper())
        self.assertTrue(c.code[3:].isdigit())




"""
#############################################################
        Test Cases for  properties, Logo, Initials label

    Initials_label and logo_display are how the UI renders clients without a logo — 
    any change here ripples across client_list.html, client_detail.html, delinked_clients.html, and the navbar dropdown.
#############################################################
"""

class ClientModelTests(TestCase):
    def test_str_includes_code(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(str(c), f"Protea Hotel ({c.code})")

    def test_initials_label_multi_word(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(c.initials_label, "Protea Hotel (PH)")

    def test_initials_label_single_word(self):
        c = Client.objects.create(name="Hilton")
        self.assertEqual(c.initials_label, "Hilton (H)")

    def test_initials_label_empty_name(self):
        c = Client(name="")
        self.assertEqual(c.initials_label, " ()")

    def test_logo_display_without_logo_returns_label(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(c.logo_display, "Protea Hotel (PH)")

    @override_settings(MEDIA_ROOT="/tmp/test_media")
    def test_logo_display_with_logo_returns_url(self):
        c = Client.objects.create(name="Protea Hotel", logo=make_image())
        self.assertIn("/client_logos/", c.logo_display)




"""
#############################################################
        Test Cases for  delink flag, uniqueness, ordering

    the is_delinked property drives the Delinked Contacts page filter; SET_NULL is the whole point of the audit-friendly delink workflow; 
    unique email is enforced at DB level and would otherwise produce a 500 error instead of a friendly form message.
#############################################################
"""

class ContactModelTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Protea Hotel")

    def test_str_is_first_last(self):
        c = Contact.objects.create(
            client=self.client, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        self.assertEqual(str(c), "Jane Doe")

    def test_email_unique_across_all_contacts(self):
        Contact.objects.create(
            client=self.client, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        with self.assertRaises(IntegrityError):
            Contact.objects.create(
                client=self.client, first_name="John", surname="Smith",
                email="jane@example.com",
            )

    def test_is_delinked_false_when_attached(self):
        c = Contact.objects.create(
            client=self.client, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        self.assertFalse(c.is_delinked)

    def test_is_delinked_true_when_client_null(self):
        c = Contact.objects.create(
            client=None, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        self.assertTrue(c.is_delinked)

    def test_client_can_be_null_and_blank(self):
        c = Contact.objects.create(
            first_name="Orphan", surname="Contact", email="orph@example.com",
        )
        self.assertIsNone(c.client)

    def test_deleting_client_orphans_its_contacts(self):
        c = Contact.objects.create(
            client=self.client, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        self.client.delete()
        c.refresh_from_db()
        self.assertIsNone(c.client,
                          "SET_NULL should orphan, not cascade-delete")
        self.assertTrue(c.is_delinked)

    def test_default_ordering_by_surname_then_firstname(self):
        Contact.objects.create(client=self.client, first_name="Zoe",
                               surname="Adams", email="z@a.com")
        Contact.objects.create(client=self.client, first_name="Bob",
                               surname="Adams", email="b@a.com")
        surnames = list(Contact.objects.values_list("surname", "first_name"))
        self.assertEqual(surnames, [("Adams", "Bob"), ("Adams", "Zoe")])




"""
#############################################################
        Test Cases for  name required, logo optional, code hidden

    clients must be creatable without a logo (the whole fallback-to-initials design), 
    and the code must never be settable from a form — it's server-generated and stable.
#############################################################
"""


class ClientFormTests(TestCase):
    def test_valid_with_only_name(self):
        form = ClientForm(data={"name": "Protea Hotel"})
        self.assertTrue(form.is_valid(), form.errors)
        c = form.save()
        self.assertRegex(c.code, r"^[A-Z]{3}\d{3}$")

    def test_name_is_required(self):
        form = ClientForm(data={"name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_code_field_not_on_form(self):
        form = ClientForm()
        self.assertNotIn("code", form.fields)

    def test_logo_is_optional(self):
        form = ClientForm(data={"name": "Protea Hotel"})
        self.assertTrue(form.is_valid())

    @override_settings(MEDIA_ROOT="/tmp/test_media")
    def test_logo_upload_saves(self):
        form = ClientForm(
            data={"name": "Protea Hotel"},
            files={"logo": make_image()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        c = form.save()
        self.assertTrue(c.logo.name.endswith(".png"))




"""
#############################################################
        Test Cases for  client pre-bound vs. dropdown

    the same form class is reused for create, edit, and the delink-relink flow. 
    The client=None kwarg lets the URL supply the client — if this ever breaks, the "Add Contact" button on the client detail page silently breaks.
#############################################################
"""


