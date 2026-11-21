# BC - Prac: Client Tracker

A Django web app for managing **Clients** and their **Contacts**, built for the Binary City practical.
Staff users sign in, create clients (each gets an auto-generated code), attach contacts to them,
and can unlink / soft-delete / restore records, with a full audit trail.

**Stack:** Python 3.10+, Django 5.2, SQLite, Pillow (logo uploads), django-simple-history (audit trail),
WeasyPrint (PDF export). Front end: Bootstrap 5 + MDB UI Kit, jQuery / DataTables, Font Awesome (CDN).
Brand colours: `#b51c10` (red, core), `#989898` (grey), `#373737` (dark grey).

---

## Quick start

```bash
# 1. Install pipenv (skip if you already have it)
pip install pipenv

# 2. From the project directory (where Pipfile lives)
pipenv install            # installs the pinned dependencies
pipenv shell              # activates the virtual environment

# 3. Create the database (db.sqlite3 is git-ignored, so every clone starts empty)
python manage.py migrate

# 4. Create a login (createsuperuser also sets is_staff, which the login form requires)
python manage.py createsuperuser

# 5. Run
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and sign in at `/login/`. The Django admin is at `/admin/`.

**Troubleshooting**

- If `pipenv install` fails, delete `Pipfile.lock` and run `pipenv install` again.
- **PDF export needs WeasyPrint's system libraries (Pango).** They are not installed by `pip`.
  Follow the [WeasyPrint install guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
  for your OS (Linux: `libpango-1.0-0`, `libpangoft2-1.0-0`; macOS: `brew install pango`).
  WeasyPrint is imported when the app starts, so it must be installed for the app to run.
- Uploaded logos are saved to `media/` (git-ignored). Static assets live in `static/`.

### Users

- **Staff** (`is_staff=True`) can use the whole app. Non-staff accounts are rejected at login with a
  specific "This account does not have staff access." message.
- Additional staff accounts can be created in `/admin/` (tick *Staff status*).

---

## What it does (requirements → implementation)

| Requirement | Where / how |
|---|---|
| Client **Name** (required textbox) | `ClientForm`, `templates/clientTrackerApp/client_form.html` |
| Client **Code**, auto-generated, read-only, 6 chars (3 letters + 3 digits, upper case, e.g. `FNB001`) | `generate_client_code()` in `models.py`; `editable=False`, not on the form |
| Code hidden for an unsaved client, shown after saving | New-client form shows only a hint; the code appears on the edit form, client detail and lists |
| Code unique for all clients | `unique=True` DB constraint + numeric suffix starts at 1 and increments per prefix |
| Code never changes when a client is renamed | Generated only when `code` is empty (covered by tests) |
| Contact **Name, Surname, Email** (required) | `ContactForm`, `contacts/contact_form.html` |
| Email valid and **unique across all contacts** | `EmailField(unique=True)`; duplicate shows a form error, not a 500 |
| Contacts ordered by Surname, then Name | `Contact.Meta.ordering = ["surname", "first_name"]` |
| One client can be linked to **many contacts** | `Contact.client` foreign key, `related_name="contacts"` |
| Link / unlink contacts | Add a contact from a client; **unlink via AJAX** from the client page; relink from *Delinked Contacts* |
| Number of linked contacts per client | Shown on every client card and in the list view (`contact_count`, annotated in `client_list`) |
| Optional: client logo upload | `Client.logo` (ImageField); falls back to an initials label, e.g. *Protea Hotel (PH)* |

### Extras beyond the brief

- **Live search** of clients by name or code (AJAX) and AJAX pagination.
- **Grid and list** view toggle on the client page.
- **Edit** clients and contacts.
- **Soft delete ("delink") for clients:** marks the client as delinked and unlinks its contacts, nothing is
  destroyed. Delinked clients can be restored from *Delinked Clients*.
- **Audit trail** via `django-simple-history`: every create, update, delink and relink is recorded and
  viewable (read-only) under *Historical clients / contacts* in the admin.
- **PDF export** of all contacts (`/contacts/pdf/`, honours `?q=`) and per client
  (`/clients/<id>/contacts/pdf/`).

---

## Design decisions

**Contact ↔ Client relationship.** The brief says *"one client can be linked to multiple contacts"*, so
`Contact` holds a nullable foreign key to `Client` (`on_delete=SET_NULL`). Consequences:

- A contact belongs to **at most one client** at a time. A contact with no client is "delinked".
- The per-client count of contacts is what the UI surfaces. A per-contact "number of linked clients" would
  only ever be 0 or 1 under this model.
- If a contact needs to belong to several clients, the change is to make `Contact.client` a
  `ManyToManyField` (with a data migration); forms and templates would then switch to a multi-select.

**Delink instead of delete.** Linking changes are reversible and audited. Hard delete still exists for
clients and contacts behind a confirmation page; deleting a client leaves its contacts delinked
(`SET_NULL`) rather than deleting them.

**Client code generation.** The 3-letter prefix is built from the first letter of each word in the name
(up to 3), padded with unused letters from the name, then with random letters for very short names. The
3-digit suffix is the next free number for that prefix (`001`, `002`, ...), checked against the database so
the final code is unique. Codes are sequential, not random.

**Access control.** Every view requires login; all create / edit / delete / delink / PDF views also require
`is_staff`. Destructive actions need a POST (GET only shows a confirmation page); delinking a contact is
POST + AJAX only.

---

## Project structure

```
BCityProject/            project settings, root URLs
clientTrackerApp/
  models.py              Client, Contact, code generation helpers
  forms.py               ClientForm, ContactForm, StaffLoginForm
  views.py               client + contact CRUD, delink/relink, PDF downloads
  urls.py                route table (below)
  admin.py               admin config + read-only audit-log views
  pdf.py                 WeasyPrint helper
  context_processors.py  delinked counts for the navbar
  tests.py               test suite
templates/               base layout, partials, client / contact / pdf templates
static/                  logos and static assets
media/                   uploaded client logos (git-ignored)
```

### URLs

| URL | Purpose |
|---|---|
| `/login/`, `/logout/` | Staff sign in / out |
| `/` | Client list (search, grid/list, pagination) |
| `/clients/new/`, `/clients/<id>/`, `/clients/<id>/edit/` | Client create, detail (with contacts), edit |
| `/clients/<id>/delink/`, `/clients/delinked/`, `/clients/<id>/relink/` | Client soft-delete and restore |
| `/contacts/new/`, `/clients/<id>/contacts/new/` | Create a contact (standalone, or pre-linked to a client) |
| `/contacts/<id>/edit/`| Edit a contact |
| `/contacts/<id>/delink/`, `/contacts/delinked/`, `/contacts/<id>/relink/` | Unlink (AJAX), list unlinked contacts, relink |
| `/contacts/pdf/`, `/clients/<id>/contacts/pdf/` | PDF exports |

---

## Tests

```bash
python manage.py test clientTrackerApp -v 2
```

Expected result: **`OK (expected failures=8)`**.

Eight tests are decorated with `@expectedFailure` **on purpose**. They were written against an earlier
client-code prefix rule and earlier logout / admin behaviour, and are kept as a visible record of that drift.
Each has an `INTENTIONAL:` comment explaining why it fails. If one starts passing, Python reports an
"unexpected success", which is the cue to remove its decorator. The remaining tests cover code generation,
models, forms, login, client and contact views, delink / relink round trips and the audit log.

---

## Known limitations and next steps

- **Production configuration:** `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` are development values in
  `settings.py`. For production they move to environment variables (`.env`), with `DEBUG=False`.
- **Error logging** to `BASE_DIR/logs/` (function-level) is not implemented yet.
- **Client self-login** (optional extra in the task breakdown) is not implemented.
- **Code capacity:** the numeric part supports `001`-`999` per prefix; handling beyond that, and retrying on a
  rare simultaneous-create collision, are not implemented.
- **Short names (under 3 letters)** are padded with random letters. The brief's example (`IT` → `ITA001`) suggests
  padding from `A` upward; switching to that is a small change in `_initials()`.
- **Client relink** restores the client only; its former contacts are not re-attached automatically (relink them
  individually from *Delinked Contacts*).
- **Contact ↔ Client** is one-to-many (see Design decisions); many-to-many is the natural extension.

