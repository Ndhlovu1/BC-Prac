import random
import string
from django.db import models
from django.core.validators import EmailValidator
from simple_history.models import HistoricalRecords



"""
#############################################################
        HELPER FUNCTIONS FOR CLIENT TRACKER APP
#############################################################

"""

# Needed for generating unique initials for clients


def _initials(name: str) -> str:
    """
    Returns 3 alphabetic characters derived from `name`.
    - Take first letters of each word (up to 3 words), pad with letters from name,
      then with random letters if needed.
    """
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch.isspace()).strip()
    words = cleaned.split()

    letters = ""
    for w in words:
        if w and w[0].isalpha():
            letters += w[0].upper()
        if len(letters) == 3:
            break

    if len(letters) < 3:
        for ch in cleaned.upper():
            if ch.isalpha() and ch not in letters:
                letters += ch
            if len(letters) == 3:
                break

    while len(letters) < 3:
        letters += random.choice(string.ascii_uppercase)

    return letters[:3].upper()


def generate_client_code(name: str) -> str:
    """
    ABC001, ABC002, ... — 3 alpha chars from name + 3-digit auto-increment
    scoped to the same prefix.
    """
    prefix = _initials(name)
    last = (
        Client.objects.filter(code__startswith=prefix)
        .order_by("-code")
        .first()
    )
    next_num = int(last.code[3:]) + 1 if last and last.code[3:].isdigit() else 1
    return f"{prefix}{next_num:03d}"


"""
#############################################################
        MODELS DEFINITION FOR CLIENT TRACKER APP
#############################################################

"""

# Model for a client, which can contain numerous associated contacts.

class Client(models.Model):
    # Basic identity and branding details for the client.
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=6, unique=True, blank=True, editable=False)
    logo = models.ImageField(upload_to="client_logos/", blank=True, null=True)

    # Audit and delinking fields track when the client was created or deactivated.
    created_at = models.DateTimeField(auto_now_add=True)
    is_delinked = models.BooleanField(default=False, db_index=True)
    delinked_at = models.DateTimeField(null=True, blank=True)

    # Keep a historical record of changes made to this model.
    history = HistoricalRecords()  

    class Meta:
        # Return clients alphabetically by name when no explicit ordering is given.
        ordering = ["name"]

    def __str__(self):
        # Display the client name together with its unique code in admin and shell views.
        return f"{self.name} ({self.code})"

    @property
    def initials_label(self) -> str:
        """'Protea Hotel (PH)' or 'Hilton (H)' — used when no logo is uploaded."""
        # Split the name into words and derive initials for a fallback logo label.
        words = [w for w in self.name.split() if w]
        if not words:
            return f"{self.name} ()"

        # Use the first letter for a single word, or the first letter of every word otherwise.
        short = words[0][0].upper() if len(words) == 1 else "".join(w[0].upper() for w in words)
        return f"{self.name} ({short})"

    @property
    def logo_display(self) -> str:
        # Prefer the uploaded logo URL; otherwise, use the generated initials label.
        return self.logo.url if self.logo else self.initials_label

    def save(self, *args, **kwargs):
        # Assign a unique business code only when the client is being created without one.
        if not self.code:
            self.code = generate_client_code(self.name)
        super().save(*args, **kwargs)


# Model for a contact associated with a client.
class Contact(models.Model):
    client = models.ForeignKey(Client,on_delete=models.SET_NULL, null=True,blank=True, related_name="contacts",)
    first_name = models.CharField(max_length=100)
    surname    = models.CharField(max_length=100)
    email      = models.EmailField(unique=True, validators=[EmailValidator()])
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()  

    class Meta:
        ordering = ["surname", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.surname}"

    @property
    def is_delinked(self) -> bool:
        return self.client_id is None
    




