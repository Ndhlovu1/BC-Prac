# BC - Prac


## Setup 

*IDEALY HAVE PYTHON3.10+ WITH PIP INSTALLED*

1. Install Pipenv `pip install pipenv` : You can do this anywhere( Only if you dont already have this installed)

2. Activate the virtual environment `pipenv shell` : Do this in the project directory,, where you have the files Pipfile  and Pipfile.lock

3. Install the dependencies `pipenv install` : This will install dependencies in the Pipfile

4. If you run into issues at  the above stage delete the Pipfile.lock and re-run the command `pipenv install`

5. Assuming all has gone well, run the command `python manage.py runserver` : This should show you the localhost://8000 url which will take you to the web interface

## Project Structure

- `manage.py` — Django command-line entry point for running the development server, creating migrations, applying migrations, and performing other Django management tasks.
- `Pipfile` — Defines the project's Python dependencies and the Python version used by Pipenv.
- `Pipfile.lock` — Records exact dependency versions for reproducible Pipenv installations.
- `README.md` — Contains setup instructions and information about the project.
- Django project directory — Contains the project's main settings and configuration, including URL routing and global application settings.
- Django app directories — Contain application-specific code, models, views, templates, static files, and migrations.
- `models.py` — Defines the database models and the structure of application data.
- `views.py` — Contains request-handling logic and connects models, forms, and templates to web responses.
- `urls.py` — Maps URL paths to their corresponding views.
- `templates/` — Stores HTML templates rendered and returned by views.
- `static/` — Stores static assets such as CSS, JavaScript, and images.
- `migrations/` — Stores Django database migration files used to create and update database tables.
- `admin.py` — Registers application models with the Django administration interface.
- `apps.py` — Provides configuration for a Django application.
- `tests.py` — Contains automated tests for application behavior and functionality.




