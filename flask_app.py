"""Entry point for PythonAnywhere (the WSGI file imports `app` from here).

The application code lives in the mumbai_opticals/ package.
"""
from mumbai_opticals import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
