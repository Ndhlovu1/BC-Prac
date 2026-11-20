import random
import string
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import EmailValidator
from django.utils.text import slugify


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





