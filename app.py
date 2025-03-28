import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from forms import BudgetForm
from openai import OpenAI
import openai
import git
import string
import secrets
from functools import wraps
from dotenv import load_dotenv
load_dotenv()

#TODO Try to code for focused tabs (Create a function using python -> when you navigate to a tab, keep track of the page name and compare to button name to be able to change the button's css -> pageUrl = buttonUrl)
#TODO When new signup -> check if logged in database (new column "filled out form") -> if false summary button locked -> form submitted then unlock the summary button 


# Fetch the API key from the environment variable
api_key = os.getenv('OPENAI_API_KEY')

# Ensure the api_key is provided
if not api_key:
    raise ValueError("No API key found. Please set the OPENAI_API_KEY environment variable.")

#connects to the chatgpt api
client = OpenAI(api_key=api_key)

app = Flask(__name__)

#configures the secret key to be random and connecting database.db to SQLalchamey
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"

#creates a database for the app, checks if passwords match
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

#makes pages login restricted
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    financial_discipline = db.Column(db.String(100), nullable=False)
    spending_habits = db.Column(db.String(100), nullable=False)
    saving_importance = db.Column(db.String(100), nullable=False)
    short_term_savings = db.Column(db.Float, nullable=False)
    long_term_savings = db.Column(db.Float, nullable=False)
    investments = db.Column(db.Float, nullable=False)
    income = db.Column(db.Float, nullable=False)
    housing_utilities = db.Column(db.Float, nullable=False)
    communication = db.Column(db.Float, nullable=False)
    transportation = db.Column(db.Float, nullable=False)
    education = db.Column(db.Float, nullable=False)
    savings = db.Column(db.Float, nullable=False)
    food = db.Column(db.Float, nullable=False)
    entertainment = db.Column(db.Float, nullable=False)
    health_personal_care = db.Column(db.Float, nullable=False)
    clothing_laundry = db.Column(db.Float, nullable=False)
    debt_payments = db.Column(db.Float, nullable=False)
    form_submissions = db.Column(db.Integer, nullable=False, default=1)

def validate_username(username):
    existing_user_username = User.query.filter_by(username=username).first()
    if not existing_user_username:
        return True


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        form_type = request.form.get('form_type')

        if form_type == 'sign-up':  # Check if sign-up form is submitted
            #if username already exists
            if not validate_username(username):
                flash('Username is already in use.', 'error')
                return redirect(url_for('login'))
            
            # hashes password and uses that + username to store user in db
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            flash('Account created successfully. Please log in.', 'info')
            return redirect(url_for('login'))

        elif form_type == 'log-in':
            # Retrieve the user from the database
            user = User.query.filter_by(username=username).first()

            #if the username is valid and the password entered matches the username's hashed password
            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                session['user_id'] = user.id
                print(f"Logged in user ID: {current_user.id}")
                return redirect(url_for('form'))
            else:
                flash('Invalid credentials. Please try again.', 'error')

    return render_template('login.html')


@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():

    try:
        user_id = current_user.id
        budget = Budget.query.filter_by(user_id=user_id).order_by(Budget.form_submissions.desc()).first()

        form = BudgetForm(obj=budget)

        if form.validate_on_submit():
            new_budget = Budget(user_id=user_id)
            form.populate_obj(new_budget)  # Populate the new budget with form data

            # Determine the form submission number
            if budget:
                new_budget.form_submissions = budget.form_submissions + 1

            db.session.add(new_budget)
            db.session.commit()

            return redirect(url_for('summary'))
    except:
        return redirect(url_for('login'))
    
    return render_template('form.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/chatbot')
@login_required
def chatbot_site():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
@login_required
def chatbot():
    user_input = request.json.get('message')

    if user_input.lower() == 'exit':
        response = {"message": "Goodbye!"}
    else:
        last_budget = Budget.query.filter_by(user_id=current_user.id).order_by(Budget.id.desc()).first()
        if last_budget:
            personality = [
                last_budget.age,
                last_budget.financial_discipline,
                last_budget.spending_habits,
                last_budget.saving_importance
            ]
            financial_history = [
                last_budget.short_term_savings,
                last_budget.long_term_savings,
                last_budget.investments
            ]
            income = last_budget.income
            expenses = [
                last_budget.housing_utilities,
                last_budget.communication,
                last_budget.transportation,
                last_budget.education,
                last_budget.savings,
                last_budget.food,
                last_budget.entertainment,
                last_budget.health_personal_care,
                last_budget.clothing_laundry,
                last_budget.debt_payments
            ]
            initial_message = f"User's age: {personality[0]}\n" \
                              f"How often does the user follow a budget?: {personality[1]}\n" \
                              f"How would the user describe their spending habits?: {personality[2]}\n" \
                              f"How important is it for the user to save a portion of their income regularly: {personality[3]}\n" \
                              f"The user's short-term savings: ${financial_history[0]:.2f}\n" \
                              f"The user's long-term savings: ${financial_history[1]:.2f}\n" \
                              f"The money the user currently has invested: ${financial_history[2]:.2f}\n" \
                              f"User's monthly income: ${income:.2f}\n" \
                              f"Housing and Utilities expenses: ${expenses[0]:.2f}\n" \
                              f"Communication expenses: ${expenses[1]:.2f}\n" \
                              f"Transportation expenses: ${expenses[2]:.2f}\n" \
                              f"Education expenses: ${expenses[3]:.2f}\n" \
                              f"Savings expenses: ${expenses[4]:.2f}\n" \
                              f"Food expenses: ${expenses[5]:.2f}\n" \
                              f"Entertainment expenses: ${expenses[6]:.2f}\n" \
                              f"Health and Personal Care expenses: ${expenses[7]:.2f}\n" \
                              f"Clothing expenses: ${expenses[8]:.2f}\n" \
                              f"Debt Payments expenses: ${expenses[9]:.2f}\n"
            
        else:
            initial_message = "The user hasn't filled out the form yet."


        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Your name is Bud. You are a financial planner tasked with helping the user make smarter financial decisions."},
                    {"role": "system", "content": "Introduce yourself only on the first message."},
                    {"role": "system", "content": "Limit your responses to 500 characters"}, 
                    {"role": "system", "content": "Be friendly and make sure your responses are clear and simple. Someone with no financial knowledge should understand."},
                    {"role": "system", "content": "Offer practical tips and examples whenever possible."},
                    {"role": "system", "content": initial_message},
                    {"role": "system", "content": "Your audience is college students. Tailor your responses to the finances and situations of the typical American college student."},
                    {"role": "system", "content": "If you don't have the user's budget information, direct them to fill out the form in the form page first."},
                    {"role": "system", "content": "Remember that housing and utilities, communication, transportation, education, food, and health and personal care expenses are the user's needs. Entertainment and clothing expenses are the user's wants. Debt payment and saving expenses are the user's savings/debt repayments."},
                    {"role": "system", "content": "If the user asks about budgeting, tell them about the 50/30/20 budget rule."},
                    {"role": "system", "content": "Ideally, the user should allocate 50%% of their income to their needs, 30%% to their wants, and 20%% to their savings and debt repayments."},
                    {"role": "system", "content": "When responding to the user, consider the user's age, short and long term savings, investments, income, and expense information."},
                    {"role": "system", "content": "If the user asks advice about something they want to buy, pay attention to the user's short and long term savings in addition to their expenses and income."},
                    {"role": "user", "content": user_input}
                ]
            )
       
            message = response.choices[0].message.content.strip()
            response = {"message": message}
        except Exception as e:
            print(f"Error: {str(e)}")
            response = {"message": "Something went wrong"}

    return jsonify(response)

@app.route('/summary')
@login_required
def summary():

    try:
        budgets = Budget.query.filter_by(user_id=current_user.id).order_by(Budget.form_submissions.desc()).all()

        if not budgets:
            flash('Please fill out the form before accessing the summary page.', 'error')
            return redirect(url_for('form'))

        last_budget = budgets[0]

        if len(budgets) > 1:
            previous_budget = budgets[1]
            percentage_changes = [
                ((last_budget.housing_utilities - previous_budget.housing_utilities) / previous_budget.housing_utilities * 100) if previous_budget.housing_utilities != 0 else (last_budget.housing_utilities * 100 if last_budget.housing_utilities != 0 else 0),
                ((last_budget.communication - previous_budget.communication) / previous_budget.communication * 100) if previous_budget.communication != 0 else (last_budget.communication * 100 if last_budget.communication != 0 else 0),
                ((last_budget.transportation - previous_budget.transportation) / previous_budget.transportation * 100) if previous_budget.transportation != 0 else (last_budget.transportation * 100 if last_budget.transportation != 0 else 0),
                ((last_budget.education - previous_budget.education) / previous_budget.education * 100) if previous_budget.education != 0 else (last_budget.education * 100 if last_budget.education != 0 else 0),
                ((last_budget.savings - previous_budget.savings) / previous_budget.savings * 100) if previous_budget.savings != 0 else (last_budget.savings * 100 if last_budget.savings != 0 else 0),
                ((last_budget.food - previous_budget.food) / previous_budget.food * 100) if previous_budget.food != 0 else (last_budget.food * 100 if last_budget.food != 0 else 0),
                ((last_budget.entertainment - previous_budget.entertainment) / previous_budget.entertainment * 100) if previous_budget.entertainment != 0 else (last_budget.entertainment * 100 if last_budget.entertainment != 0 else 0),
                ((last_budget.health_personal_care - previous_budget.health_personal_care) / previous_budget.health_personal_care * 100) if previous_budget.health_personal_care != 0 else (last_budget.health_personal_care * 100 if last_budget.health_personal_care != 0 else 0),
                ((last_budget.clothing_laundry - previous_budget.clothing_laundry) / previous_budget.clothing_laundry * 100) if previous_budget.clothing_laundry != 0 else (last_budget.clothing_laundry * 100 if last_budget.clothing_laundry != 0 else 0),
                ((last_budget.debt_payments - previous_budget.debt_payments) / previous_budget.debt_payments * 100) if previous_budget.debt_payments != 0 else (last_budget.debt_payments * 100 if last_budget.debt_payments != 0 else 0),
            ]
        else:
            percentage_changes = [0] * 10

        all_changes_zero = all(change == 0 for change in percentage_changes)

        income = last_budget.income
        expenses = [
            last_budget.housing_utilities,
            last_budget.communication,
            last_budget.transportation,
            last_budget.education,
            last_budget.savings,
            last_budget.food,
            last_budget.entertainment,
            last_budget.health_personal_care,
            last_budget.clothing_laundry,
            last_budget.debt_payments
        ]
        financial_history = [
            last_budget.short_term_savings,
            last_budget.long_term_savings,
            last_budget.investments
        ]

        needs = sum([expenses[0], expenses[5], expenses[2], expenses[1], expenses[3], expenses[7]])
        wants = sum([expenses[6], expenses[8]])
        savings_or_debt = sum([expenses[4], expenses[9]])

        actual_amounts = {
            'Needs': needs,
            'Wants': wants,
            'Savings or Debt Repayment': savings_or_debt
        }

        actual_percentages = {
            'Needs': round((needs / income) * 100, 2) if income > 0 else 0,
            'Wants': round((wants / income) * 100, 2) if income > 0 else 0,
            'Savings or Debt Repayment': round((savings_or_debt / income) * 100, 2) if income > 0 else 0
        }

        ideal_amounts = {
            'Needs': income * 0.50,
            'Wants': income * 0.30,
            'Savings or Debt Repayment': income * 0.20
        }

        ideal_percentages = {
            'Needs': 50,
            'Wants': 30,
            'Savings or Debt Repayment': 20
        }

        return render_template('summary.html', 
                            income=income, 
                            expenses=expenses, 
                            financial_history=financial_history, 
                            actual_amounts=actual_amounts, 
                            actual_percentages=actual_percentages, 
                            ideal_amounts=ideal_amounts, 
                            ideal_percentages=ideal_percentages,
                            percentage_changes=percentage_changes,
                            all_changes_zero=all_changes_zero)

    except:
        return redirect(url_for('login'))


@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html')


@app.route("/update_server", methods=['POST'])
def webhook():
    if request.method == 'POST':
        repo = git.Repo('/home/BudgetBuddy12345/BudgetBuddy')
        origin = repo.remotes.origin
        origin.pull()
        return 'Updated PythonAnywhere successfully', 200
    else:
        return 'Wrong event type', 400


if __name__ == '__main__':
    app.run(debug=True)
