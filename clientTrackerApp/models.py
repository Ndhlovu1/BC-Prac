import random
import string
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import EmailValidator
from django.utils.text import slugify



"""
#############################################################
        HELPER FUNCTIONS FOR CLIENT TRACKER APP
#############################################################

"""

# Needed for generating unique initials for clients
def _initials(name: str) -> str:
    """
    Returns 3 alphabetic characters derived from `name`.
    - Take first letters of each word (up to 3 words), padded with random letters
    - If fewer words, pad using letters from the name, then random letters
    """
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch.isspace()).strip()
    words = cleaned.split()

    letters = ""
    # First: initials of each word
    for w in words:
        if w[0].isalpha():
            letters += w[0].upper()
        if len(letters) == 3:
            break

    # Then: remaining letters from the name (uppercase, alphabetical only)
    if len(letters) < 3:
        for ch in cleaned.upper():
            if ch.isalpha() and ch not in letters:
                letters += ch
            if len(letters) == 3:
                break

    # Finally: pad with random letters
    while len(letters) < 3:
        letters += random.choice(string.ascii_uppercase)

    return letters[:3].upper()

def generate_client_code(name: str) -> str:
    """
    Generate code like ABC001, ABC002, ...
    3 alpha chars from name + 3-digit auto-increment based on same prefix.
    """
    prefix = _initials(name)

    # Find last code with same prefix
    last = (
        Client.objects.filter(code__startswith=prefix)
        .order_by("-code")
        .first()
    )

    if last and last.code[3:].isdigit():
        next_num = int(last.code[3:]) + 1
    else:
        next_num = 1

    return f"{prefix}{next_num:03d}"

"""
#############################################################
        MODELS DEFINITION FOR CLIENT TRACKER APP
#############################################################

"""

class Client(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=6, unique=True, blank=True, editable=False)
    logo = models.ImageField(upload_to="client_logos/", blank=True, null=True)

    # Reverse relation to contacts via M2M below (a client has many contacts)
    # We use a M2M through-style via Contact.client FK -> so one client → many contacts
    # but contacts can also belong to many clients (matching the "select2 to link
    # more than one client to a contact" workflow).

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    # Displaying the logo or initials is useful for the select2 dropdowns, so users can see the logo if uploaded, otherwise the initials. 
    @property
    def logo_display(self) -> str:
        """
        If a logo exists -> return its URL.
        If omitted -> fall back to initials: 'Protea Hotel (PH)' / 'Hilton (H)'
        """
        if self.logo:
            return self.logo.url
        return self.initials_label

    # Displaying with the initials in parentheses is useful for the select2 dropdowns, so users can see the initials even if no logo is uploaded.
    @property
    def initials_label(self) -> str:
        """e.g. 'Protea Hotel (PH)' or 'Hilton (H)'"""
        words = [w for w in self.name.split() if w]
        if not words:
            return f"{self.name} ()"
        if len(words) == 1:
            short = words[0][0].upper()
        else:
            short = "".join(w[0].upper() for w in words)
        return f"{self.name} ({short})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_client_code(self.name)
        super().save(*args, **kwargs)


class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    email = models.EmailField(unique=True, validators=[EmailValidator()])

    # A contact can be linked to one or more clients (select2 during form)
    clients = models.ManyToManyField(
        Client,
        related_name="contacts",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["surname", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.surname}"

    @property
    def linked_clients_count(self) -> int:
        return self.clients.count()

    



