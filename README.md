# BC - Prac


## Setup 

*IDEALY HAVE PYTHON3.10+ WITH PIP INSTALLED*

1. Install Pipenv `pip install pipenv` : You can do this anywhere( Only if you dont already have this installed)

2. Activate the virtual environment `pipenv shell` : Do this in the project directory,, where you have the files Pipfile  and Pipfile.lock

3. Install the dependencies `pipenv install` : This will install dependencies in the Pipfile

4. If you run into issues at  the above stage delete the Pipfile.lock and re-run the command `pipenv install`

5. Assuming all has gone well, run the command `python manage.py runserver` : This should show you the localhost://8000 url which will take you to the web interface



