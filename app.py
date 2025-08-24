from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mysqldb import MySQL
from config import Config
from models import init_models
import random
import string

app = Flask(__name__)
app.config.from_object(Config)

# Initialize MySQL properly
mysql = MySQL(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

User, Account, Transaction, Transfer = init_models(app, mysql)

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id, mysql)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register.html')
        
        # Check if user exists
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash('Username or email already exists!', 'danger')
            return render_template('register.html')
        
        # Create user
        user_id = User.create(username, email, password, first_name, last_name, mysql)
        
        # Create account for user
        account_number = generate_account_number()
        Account.create(user_id, account_number, 'Savings', mysql)
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.authenticate(username, password, mysql)
        
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = Account.get_by_user_id(current_user.id, mysql)
    return render_template('dashboard.html', accounts=accounts)

@app.route('/accounts')
@login_required
def accounts():
    accounts = Account.get_by_user_id(current_user.id, mysql)
    return render_template('accounts.html', accounts=accounts)

@app.route('/transactions/<account_id>')
@login_required
def transactions(account_id):
    # Verify the account belongs to the current user
    accounts = Account.get_by_user_id(current_user.id, mysql)
    account_ids = [str(acc.id) for acc in accounts]
    
    if account_id not in account_ids:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    
    transactions = Transaction.get_by_account_id(account_id, mysql)
    transfers = Transfer.get_by_account_id(account_id, mysql)
    
    return render_template('transactions.html', 
                          transactions=transactions, 
                          transfers=transfers,
                          account_id=account_id)

@app.route('/deposit', methods=['POST'])
@login_required
def deposit():
    account_id = request.form['account_id']
    amount = float(request.form['amount'])
    description = request.form.get('description', 'Deposit')
    
    # Verify the account belongs to the current user
    accounts = Account.get_by_user_id(current_user.id, mysql)
    account_ids = [str(acc.id) for acc in accounts]
    
    if account_id not in account_ids:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Update account balance
    Account.update_balance(account_id, amount, mysql)
    
    # Record transaction
    Transaction.create(account_id, 'Deposit', amount, description, mysql)
    
    return jsonify({'success': True, 'message': 'Deposit successful!'})

@app.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    account_id = request.form['account_id']
    amount = float(request.form['amount'])
    description = request.form.get('description', 'Withdrawal')
    
    # Verify the account belongs to the current user
    accounts = Account.get_by_user_id(current_user.id, mysql)
    account_ids = [str(acc.id) for acc in accounts]
    
    if account_id not in account_ids:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Check if sufficient balance
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT balance FROM accounts WHERE id = %s', (account_id,))
    account = cursor.fetchone()
    
    if account['balance'] < amount:
        return jsonify({'success': False, 'message': 'Insufficient balance!'})
    
    # Update account balance
    Account.update_balance(account_id, -amount, mysql)
    
    # Record transaction
    Transaction.create(account_id, 'Withdrawal', -amount, description, mysql)
    
    return jsonify({'success': True, 'message': 'Withdrawal successful!'})

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'GET':
        accounts = Account.get_by_user_id(current_user.id, mysql)
        return render_template('transfer.html', accounts=accounts)
    
    # Handle POST request
    from_account_id = request.form['from_account']
    to_account_number = request.form['to_account']
    amount = float(request.form['amount'])
    description = request.form.get('description', 'Fund Transfer')
    
    # Verify the from account belongs to the current user
    accounts = Account.get_by_user_id(current_user.id, mysql)
    account_ids = [str(acc.id) for acc in accounts]
    
    if from_account_id not in account_ids:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Check if recipient account exists
    to_account = Account.get_by_number(to_account_number, mysql)
    if not to_account:
        return jsonify({'success': False, 'message': 'Recipient account not found!'})
    
    # Check if sufficient balance in from account
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT balance FROM accounts WHERE id = %s', (from_account_id,))
    from_account_balance = cursor.fetchone()['balance']
    
    if from_account_balance < amount:
        return jsonify({'success': False, 'message': 'Insufficient balance!'})
    
    # Perform transfer
    try:
        # Deduct from sender
        Account.update_balance(from_account_id, -amount, mysql)
        Transaction.create(from_account_id, 'Transfer', -amount, 
                          f"Transfer to {to_account_number}: {description}", mysql)
        
        # Add to recipient
        Account.update_balance(to_account.id, amount, mysql)
        Transaction.create(to_account.id, 'Transfer', amount, 
                          f"Transfer from {current_user.username}: {description}", mysql)
        
        # Record transfer
        Transfer.create(from_account_id, to_account.id, amount, description, mysql)
        
        return jsonify({'success': True, 'message': 'Transfer successful!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Transfer failed: {str(e)}'})

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

def generate_account_number():
    return ''.join(random.choices(string.digits, k=12))

if __name__ == '__main__':
    app.run(debug=True)