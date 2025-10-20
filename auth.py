import json
import os
from flask import Blueprint, render_template, redirect, url_for, request, session, current_app, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from forms import LoginForm
from uploader import IGPoster

auth_bp = Blueprint('auth', __name__)

# This would be replaced by a database in a real application
users = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        ig_poster = IGPoster(username, password)
        if ig_poster.login():
            session['username'] = username
            with open("credentials.json", "w") as f:
                json.dump({"username": username, "password": password}, f)

            return redirect(url_for('index'))
        else:
            flash('Invalid Instagram credentials.', 'danger')

    return render_template('login.html', form=form)

@auth_bp.route('/logout')
def logout():
    if os.path.exists("credentials.json"):
        os.remove("credentials.json")

    current_app.clear_all_data()
    session.clear()
    flash("You have been logged out and all data has been cleared.", "success")
    return redirect(url_for('auth.login'))
