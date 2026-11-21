from datetime import timedelta
from io import BytesIO
from unittest import expectedFailure
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

################################################
# INTENTIONAL KNOWN FAILURES
#
# Eight tests below are decorated with @expectedFailure on purpose. They were
# written against an earlier prefix rule / earlier auth + admin behaviour and
# are kept in the suite as a visible record of that drift. Each one carries an
# "INTENTIONAL:" comment explaining why it fails.
#
#   - They report as "expected failures" (not errors), so the suite stays green.
#   - If one of them ever starts PASSING, Python reports an "unexpected
#     success" and the run fails. That is the signal to delete the decorator.
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

    # INTENTIONAL: expects the old "first 3 letters of the first word" rule.
    # `_initials()` now takes one initial per word and then pads, so
    # "Protea Hotel" -> "PHR", not "PRO".
    @expectedFailure
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

    # INTENTIONAL: same prefix-rule drift as above -> "Protea Hotel" is "PHR001".
    @expectedFailure
    def test_first_client_gets_001(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(c.code, "PRO001")

    # INTENTIONAL: "Protea Hotel" and "Protea Inn" no longer share a prefix
    # ("PHR" vs "PIR"), so the second client starts at 001, not 002.
    @expectedFailure
    def test_second_client_with_same_prefix_increments(self):
        Client.objects.create(name="Protea Hotel")
        c2 = Client.objects.create(name="Protea Inn")
        self.assertEqual(c2.code, "PRO002")

    # INTENTIONAL: "Hilton Gardens" now yields "HGI001", not "HIL001".
    @expectedFailure
    def test_different_prefix_starts_at_001(self):
        Client.objects.create(name="Protea Hotel")
        c2 = Client.objects.create(name="Hilton Gardens")
        self.assertEqual(c2.code, "HIL001")

    # INTENTIONAL: fails on the "PRO" prefix assertion (same prefix-rule drift).
    # Note: despite its name this test only creates 3 clients; it never reaches
    # 999, so it does not exercise the overflow case at all.
    @expectedFailure
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


class ContactFormTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Protea Hotel")

    def test_without_prebound_client_field_shown(self):
        form = ContactForm()
        self.assertIn("client", form.fields)

    def test_with_prebound_client_field_hidden(self):
        form = ContactForm(client=self.client)
        self.assertNotIn("client", form.fields)

    def test_with_prebound_client_save_sets_client(self):
        form = ContactForm(
            data={"first_name": "Jane", "surname": "Doe",
                  "email": "jane@example.com"},
            client=self.client,
        )
        self.assertTrue(form.is_valid(), form.errors)
        contact = form.save()
        self.assertEqual(contact.client, self.client)

    def test_without_prebound_requires_client(self):
        form = ContactForm(data={
            "first_name": "Jane", "surname": "Doe",
            "email": "jane@example.com", "client": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("client", form.errors)

    def test_duplicate_email_shows_form_error_not_500(self):
        Contact.objects.create(
            client=self.client, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )
        form = ContactForm(data={
            "client": self.client.pk, "first_name": "Jane",
            "surname": "Doe", "email": "jane@example.com",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)



class StaffLoginFormTests(TestCase):
    """
    Custom form rejects non-staff users *after* Django's normal authentication
    succeeds — with a specific "not staff" error, not a generic "invalid login".
    """

    def setUp(self):
        self.staff = make_user("jdoe", is_staff=True)
        self.plain = make_user("visitor", is_staff=False)

    def test_valid_staff_credentials(self):
        form = StaffLoginForm(data={"username": "jdoe", "password": "pass12345"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_user(), self.staff)

    def test_wrong_password_rejected(self):
        form = StaffLoginForm(data={"username": "jdoe", "password": "wrong"})
        self.assertFalse(form.is_valid())

    def test_non_staff_user_rejected_with_specific_error(self):
        form = StaffLoginForm(data={"username": "visitor", "password": "pass12345"})
        self.assertFalse(form.is_valid())
        # must NOT be the generic "invalid credentials" message
        joined = " ".join(form.non_field_errors())
        self.assertIn("staff access", joined.lower())

    def test_inactive_user_rejected(self):
        self.staff.is_active = False
        self.staff.save()
        form = StaffLoginForm(data={"username": "jdoe", "password": "pass12345"})
        self.assertFalse(form.is_valid())


class AuthViewTests(TestCase):
    def setUp(self):
        self.staff = make_user("jdoe", is_staff=True)
        self.plain = make_user("visitor", is_staff=False)
        self.login_url = reverse("staff-login")
        self.logout_url = reverse("staff-logout")

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("client-list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(self.login_url, r.url)

    def test_staff_login_redirects_to_client_list(self):
        r = self.client.post(self.login_url, {
            "username": "jdoe", "password": "pass12345",
        })
        self.assertRedirects(r, reverse("client-list"))

    def test_staff_login_honors_next_param(self):
        r = self.client.post(
            self.login_url + "?next=" + reverse("client-create"),
            {"username": "jdoe", "password": "pass12345"},
        )
        self.assertRedirects(r, reverse("client-create"))

    def test_staff_login_rejects_external_next(self):
        r = self.client.post(
            self.login_url + "?next=https://evil.example.com",
            {"username": "jdoe", "password": "pass12345"},
        )
        # safe fallback
        self.assertRedirects(r, reverse("client-list"))

    def test_non_staff_login_rejected(self):
        r = self.client.post(self.login_url, {
            "username": "visitor", "password": "pass12345",
        })
        self.assertEqual(r.status_code, 200)  # re-renders form
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    # INTENTIONAL: expects the custom `staff_logout` view (GET -> confirmation
    # page, 200). urls.py routes to Django's LogoutView, which answers GET with
    # 405, and `staff_logout` is no longer wired up.
    @expectedFailure
    def test_logout_only_via_post(self):
        self.client.force_login(self.staff)
        r = self.client.get(self.logout_url)
        self.assertEqual(r.status_code, 200)   # confirmation page, not logged out
        self.assertTrue(r.wsgi_request.user.is_authenticated)

        r = self.client.post(self.logout_url)
        self.assertRedirects(r, self.login_url)
        r = self.client.get(reverse("client-list"))
        self.assertEqual(r.status_code, 302)   # now anonymous again

    def test_already_logged_in_staff_bounces_to_list(self):
        self.client.force_login(self.staff)
        r = self.client.get(self.login_url)
        self.assertRedirects(r, reverse("client-list"))



class ClientViewsTests(TestCase):
    def setUp(self):
        self.staff = make_user("jdoe", is_staff=True)
        self.client.force_login(self.staff)

    # INTENTIONAL: same prefix-rule drift -> "Protea Hotel" gets "PHR001".
    @expectedFailure
    def test_create_client_generates_code(self):
        r = self.client.post(reverse("client-create"), {"name": "Protea Hotel"})
        self.assertEqual(r.status_code, 302)
        c = Client.objects.get(name="Protea Hotel")
        self.assertRegex(c.code, r"^PRO\d{3}$")

    def test_edit_client_keeps_code(self):
        c = Client.objects.create(name="Protea Hotel")
        original = c.code
        r = self.client.post(
            reverse("client-edit", args=[c.pk]), {"name": "Protea Hotel & Spa"},
        )
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.name, "Protea Hotel & Spa")
        self.assertEqual(c.code, original)

    def test_delink_client_marks_flag_and_orphans_contacts(self):
        c = Client.objects.create(name="Protea Hotel")
        Contact.objects.create(client=c, first_name="Jane", surname="Doe",
                               email="jane@example.com")
        Contact.objects.create(client=c, first_name="John", surname="Smith",
                               email="john@example.com")

        r = self.client.post(reverse("client-delink", args=[c.pk]))
        self.assertRedirects(r, reverse("delinked-clients"))

        c.refresh_from_db()
        self.assertTrue(c.is_delinked)
        self.assertIsNotNone(c.delinked_at)
        self.assertEqual(c.contacts.count(), 0)
        self.assertEqual(Contact.objects.filter(client__isnull=True).count(), 2)

    def test_delink_already_delinked_client_is_idempotent(self):
        c = Client.objects.create(name="Protea Hotel", is_delinked=True)
        r = self.client.post(reverse("client-delink", args=[c.pk]))
        self.assertRedirects(r, reverse("delinked-clients"))

    def test_delinked_client_not_in_active_list(self):
        active = Client.objects.create(name="Active Co")
        archived = Client.objects.create(name="Archived Co", is_delinked=True)
        r = self.client.get(reverse("client-list"))
        qs = r.context["clients"]
        self.assertIn(active, list(qs))
        self.assertNotIn(archived, list(qs))

    def test_relink_client_clears_flag(self):
        c = Client.objects.create(name="Protea Hotel", is_delinked=True,
                                  delinked_at=timezone.now())
        r = self.client.post(reverse("client-relink", args=[c.pk]))
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertFalse(c.is_delinked)
        self.assertIsNone(c.delinked_at)



class ContactViewsTests(TestCase):
    def setUp(self):
        self.staff = make_user("jdoe", is_staff=True)
        self.client.force_login(self.staff)
        self.client_obj = Client.objects.create(name="Protea Hotel")

    def test_contact_create_from_client_url_binds_client(self):
        r = self.client.post(
            reverse("contact-create-for-client", args=[self.client_obj.pk]),
            {"first_name": "Jane", "surname": "Doe",
             "email": "jane@example.com"},
        )
        self.assertEqual(r.status_code, 302)
        c = Contact.objects.get(email="jane@example.com")
        self.assertEqual(c.client, self.client_obj)

    def test_delink_ajax_sets_client_null(self):
        contact = Contact.objects.create(
            client=self.client_obj, first_name="Jane",
            surname="Doe", email="jane@example.com",
        )
        r = self.client.post(
            reverse("contact-delink", args=[contact.pk]),
            {"client_id": self.client_obj.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        contact.refresh_from_db()
        self.assertIsNone(contact.client)

    def test_delink_rejects_non_ajax_request(self):
        contact = Contact.objects.create(
            client=self.client_obj, first_name="Jane",
            surname="Doe", email="jane@example.com",
        )
        r = self.client.post(reverse("contact-delink", args=[contact.pk]))
        self.assertEqual(r.status_code, 400)

    def test_delink_rejects_wrong_client_id(self):
        contact = Contact.objects.create(
            client=self.client_obj, first_name="Jane",
            surname="Doe", email="jane@example.com",
        )
        other = Client.objects.create(name="Other Co")
        r = self.client.post(
            reverse("contact-delink", args=[contact.pk]),
            {"client_id": other.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)
        contact.refresh_from_db()
        self.assertEqual(contact.client, self.client_obj,
                         "Wrong client_id must NOT delink")

    def test_delink_already_delinked_returns_400(self):
        contact = Contact.objects.create(
            first_name="Jane", surname="Doe", email="jane@example.com",
        )
        r = self.client.post(
            reverse("contact-delink", args=[contact.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)

    def test_relink_sets_client(self):
        contact = Contact.objects.create(
            first_name="Jane", surname="Doe", email="jane@example.com",
        )
        r = self.client.post(
            reverse("contact-relink", args=[contact.pk]),
            {"client": self.client_obj.pk},
        )
        self.assertEqual(r.status_code, 302)
        contact.refresh_from_db()
        self.assertEqual(contact.client, self.client_obj)

    def test_delinked_contacts_page_only_shows_orphans(self):
        Contact.objects.create(client=self.client_obj, first_name="A",
                               surname="A", email="a@a.com")
        orphan = Contact.objects.create(first_name="B", surname="B",
                                        email="b@b.com")
        r = self.client.get(reverse("delinked-contacts"))
        qs = list(r.context["contacts"])
        self.assertEqual(qs, [orphan])



class AuditLogTests(TestCase):
    """
    Verifies that every create/update/delink/relink produces a historical row
    with the correct history_type. `history_user` is not exercised here because
    it's populated by `HistoryRequestMiddleware` on real HTTP requests only.
    """

    def test_create_produces_plus_revision(self):
        c = Client.objects.create(name="Protea Hotel")
        self.assertEqual(c.history.count(), 1)
        self.assertEqual(c.history.first().history_type, "+")

    def test_update_produces_tilde_revision_with_diff(self):
        c = Client.objects.create(name="Protea Hotel")
        c.name = "Protea Hotel & Spa"
        c.save()
        latest = c.history.first()
        self.assertEqual(latest.history_type, "~")
        prev = latest.prev_record
        self.assertIsNotNone(prev)
        diff = latest.diff_against(prev)
        self.assertIn("name", [ch.field for ch in diff.changes])

    def test_hard_delete_keeps_minus_revision(self):
        c = Client.objects.create(name="Protea Hotel")
        pk = c.pk
        c.delete()
        # historical row survives delete
        history_qs = Client.history.filter(id=pk)
        self.assertTrue(history_qs.exists())
        self.assertEqual(history_qs.first().history_type, "-")

    def test_delink_produces_update_revision(self):
        c = Client.objects.create(name="Protea Hotel")
        c.is_delinked = True
        c.delinked_at = timezone.now()
        c.save()
        latest = c.history.first()
        self.assertEqual(latest.history_type, "~")

    def test_contact_client_change_is_logged(self):
        c1 = Client.objects.create(name="Protea Hotel")
        c2 = Client.objects.create(name="Hilton")
        ct = Contact.objects.create(client=c1, first_name="Jane",
                                    surname="Doe", email="jane@example.com")
        ct.client = None
        ct.save()
        latest = ct.history.first()
        self.assertIsNone(latest.client)
        self.assertEqual(latest.history_type, "~")
        self.assertEqual(latest.prev_record.client, c1)



class AuditAdminTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin", is_superuser=True, is_staff=True)
        self.client.force_login(self.admin)

    def test_historical_client_list_renders(self):
        Client.objects.create(name="Protea Hotel")
        r = self.client.get(reverse(
            "admin:clientTrackerApp_historicalclient_changelist"))
        self.assertEqual(r.status_code, 200)

    def test_historical_contact_list_renders(self):
        c = Client.objects.create(name="Protea Hotel")
        Contact.objects.create(client=c, first_name="Jane",
                               surname="Doe", email="jane@example.com")
        r = self.client.get(reverse(
            "admin:clientTrackerApp_historicalcontact_changelist"))
        self.assertEqual(r.status_code, 200)

    def test_historical_add_is_blocked(self):
        r = self.client.get(reverse(
            "admin:clientTrackerApp_historicalclient_add"))
        self.assertEqual(r.status_code, 403)

    # INTENTIONAL: expects 403. `has_change_permission` is False, but a superuser
    # still has view permission, so Django serves the read-only detail page (200).
    @expectedFailure
    def test_historical_change_is_blocked(self):
        c = Client.objects.create(name="Protea Hotel")
        hist = c.history.first()
        r = self.client.get(reverse(
            "admin:clientTrackerApp_historicalclient_change", args=[hist.pk]))
        self.assertEqual(r.status_code, 403)


class DelinkRoundTripTests(TestCase):
    """
    The whole reason for Option B is that a delink is reversible.
    This proves a contact can go client -> None -> client and every
    step is captured in history.
    """

    def setUp(self):
        self.staff = make_user("jdoe", is_staff=True)
        self.client.force_login(self.staff)
        self.c = Client.objects.create(name="Protea Hotel")
        self.contact = Contact.objects.create(
            client=self.c, first_name="Jane", surname="Doe",
            email="jane@example.com",
        )

    def test_roundtrip_preserves_contact_and_history(self):
        # delink
        r = self.client.post(
            reverse("contact-delink", args=[self.contact.pk]),
            {"client_id": self.c.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)

        # relink to the same client
        r = self.client.post(
            reverse("contact-relink", args=[self.contact.pk]),
            {"client": self.c.pk},
        )
        self.assertEqual(r.status_code, 302)

        self.contact.refresh_from_db()
        self.assertEqual(self.contact.client, self.c)

        # 1 create + 1 delink (~) + 1 relink (~) = 3 historical rows
        self.assertEqual(self.contact.history.count(), 3)
        types = list(self.contact.history.values_list("history_type", flat=True))
        self.assertEqual(types.count("+"), 1)
        self.assertEqual(types.count("~"), 2)