from flask import Blueprint, render_template, redirect, request, flash, session, url_for
from app import app
from models import db, User
from werkzeug.security import check_password_hash, generate_password_hash
from decorators import login_required

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return render_template("auth/login.html")

@auth.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password :
        flash('Please fill out all the fields')
        return redirect(url_for('auth.login'))
        
    user = User.query.filter_by(email=email).first()
 
    if not user:
        flash('Username does not exist')
        return redirect(url_for('auth.login'))
    
    if not check_password_hash(user.password, password):
        flash('Incorrect password')
        return redirect(url_for('auth.login'))
    
    session['user_id'] = user.id
    session['email'] = user.email
    session['is_admin'] = user.is_admin
    flash('Login Successful')

    if user.is_admin:
        return redirect(url_for('admin.index'))
    return redirect(url_for('user.index'))



@auth.route('/register')
def register():
    return render_template("auth/register.html")


@auth.route('/register', methods=['POST'])
def register_post():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    
    if not full_name or not email or not password or not confirm_password:
        flash('Please fill out all required fields')
        return redirect(url_for('auth.register'))
    
    if password != confirm_password:
        flash('Password not matching')
        return redirect(url_for('auth.register'))
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('Email already registered')
        return redirect(url_for('auth.register'))

    generate_password = generate_password_hash(password)
    new_user = User(full_name=full_name, email=email, password=generate_password, phone=phone)
    db.session.add(new_user)
    db.session.commit()

    flash('Registration successful! Now you can book your slot')
    return redirect(url_for('user.index'))


# LOGOUT
@auth.route('/logout')
@login_required
def logout():
    session.clear() # also session.pop("user_id")
    flash('You have been logged out.')
    return redirect(url_for('user.index'))