from flask import Flask, render_template, request, redirect, url_for, session
import boto3
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = 'YOUR_SECRET_KEY'  # Replace with a strong secret key for session management

# Load AWS credentials from environment variables for security

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")  # Replace with your AWS Access Key
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY") # Replace with your AWS Secret Key
AWS_REGION = os.getenv("AWS_REGION")

dynamodb = boto3.resource(
    'dynamodb',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# DynamoDB setup
users_table = dynamodb.Table('User')  # Replace with your Users table
finance_table = dynamodb.Table('FinanceTracker')  # Replace with your FinanceTracker table

# Helper function to get current date
def get_current_date():
    return datetime.now().strftime('%Y-%m-%d')

# ** New Index Route **
@app.route('/')
def index():
    return render_template('index.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        response = users_table.get_item(Key={'email': email})
        if 'Item' in response:
            return "User already exists. Please choose a different email."

        # Add user to DynamoDB
        users_table.put_item(Item={'email': email, 'password': password})

        # Redirect to login page
        return redirect(url_for('login'))
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Verify user credentials
        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')

        if user and user['password'] == password:
            session['email'] = email
            return redirect(url_for('home'))
        else:
            return "Invalid email or password. Please try again."
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    return render_template('home.html')

# Add record route
@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    if 'email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        record_type = request.form['type']
        category = request.form['category']
        amount = Decimal(request.form['amount'])
        description = request.form.get('description', '')
        date = get_current_date()

        # Add record to DynamoDB
        record_id = str(uuid4())
        finance_table.put_item(
            Item={
                'record_id': record_id,
                'date': date,
                'type': record_type,
                'category': category,
                'amount': amount,
                'description': description,
                'email': session['email']  # Link record to logged-in user
            }
        )
        return redirect(url_for('record_added'))
    return render_template('add_record.html')

@app.route('/record_added', methods=['GET'])
def record_added():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('record_added.html')

# View records route
@app.route('/view_records', methods=['GET', 'POST'])
def view_records():
    # Check if the user is logged in
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']

    # Handle data from the form (POST request)
    if request.method == 'POST':
        month = request.form['month']  # Get month from POST data
    else:  # For GET requests
        month = request.args.get('month', get_current_date()[:7])

    # month_str = request.form['month']  # For example, '2024-09'
    # Convert the month string to a datetime object
    month_obj = datetime.strptime(month, '%Y-%m')
    # Format it to "Month Year" (e.g., "September 2024")
    formatted_month = month_obj.strftime('%B %Y')

    # Query DynamoDB
    response = finance_table.scan()
    items = response['Items']

    # Filter records for the logged-in user and selected month
    transactions = [
        item for item in items
        if 'email' in item and item['email'] == email and item['date'].startswith(month)
    ]

    total_income = sum(float(item['amount']) for item in transactions if item['type'] == 'income')
    total_expense = sum(float(item['amount']) for item in transactions if item['type'] == 'expense')
    budget = sum(float(item['amount']) for item in transactions if item['type'] == 'budget')
    savings = total_income - total_expense

    # Render the 'view_monthly_records.html' page with the filtered data
    return render_template(
        'view_monthly_records.html',
        transactions=transactions,
        total_income=total_income,
        total_expense=total_expense,
        budget=budget,
        savings=savings,
        month=formatted_month
    )

if __name__ == '__main__':
    app.run(debug=True)
