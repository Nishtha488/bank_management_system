from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

def init_models(app, mysql):
    class User(UserMixin):
        def __init__(self, id, username, email, first_name, last_name):
            self.id = id
            self.username = username
            self.email = email
            self.first_name = first_name
            self.last_name = last_name

        @staticmethod
        def get_by_id(user_id, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            if user:
                return User(user['id'], user['username'], user['email'], user['first_name'], user['last_name'])
            return None

        @staticmethod
        def create(username, email, password, first_name, last_name, mysql):
            hashed_password = generate_password_hash(password)
            cursor = mysql.connection.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
            ''', (username, email, hashed_password, first_name, last_name))
            mysql.connection.commit()
            return cursor.lastrowid

        @staticmethod
        def authenticate(username, password, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                return User(user['id'], user['username'], user['email'], user['first_name'], user['last_name'])
            return None

    class Account:
        def __init__(self, id, user_id, account_number, balance, account_type):
            self.id = id
            self.user_id = user_id
            self.account_number = account_number
            self.balance = balance
            self.account_type = account_type

        @staticmethod
        def create(user_id, account_number, account_type, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('''
                INSERT INTO accounts (user_id, account_number, account_type)
                VALUES (%s, %s, %s)
            ''', (user_id, account_number, account_type))
            mysql.connection.commit()
            return cursor.lastrowid

        @staticmethod
        def get_by_user_id(user_id, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM accounts WHERE user_id = %s', (user_id,))
            accounts = cursor.fetchall()
            return [Account(acc['id'], acc['user_id'], acc['account_number'], 
                           acc['balance'], acc['account_type']) for acc in accounts]

        @staticmethod
        def get_by_number(account_number, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM accounts WHERE account_number = %s', (account_number,))
            account = cursor.fetchone()
            if account:
                return Account(account['id'], account['user_id'], account['account_number'], 
                              account['balance'], account['account_type'])
            return None

        @staticmethod
        def update_balance(account_id, amount, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('UPDATE accounts SET balance = balance + %s WHERE id = %s', (amount, account_id))
            mysql.connection.commit()

    class Transaction:
        @staticmethod
        def create(account_id, transaction_type, amount, description, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('''
                INSERT INTO transactions (account_id, transaction_type, amount, description)
                VALUES (%s, %s, %s, %s)
            ''', (account_id, transaction_type, amount, description))
            mysql.connection.commit()

        @staticmethod
        def get_by_account_id(account_id, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE account_id = %s 
                ORDER BY transaction_date DESC
            ''', (account_id,))
            return cursor.fetchall()

    class Transfer:
        @staticmethod
        def create(sender_account_id, receiver_account_id, amount, description, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('''
                INSERT INTO transfers (sender_account_id, receiver_account_id, amount, description)
                VALUES (%s, %s, %s, %s)
            ''', (sender_account_id, receiver_account_id, amount, description))
            mysql.connection.commit()
            return cursor.lastrowid

        @staticmethod
        def get_by_account_id(account_id, mysql):
            cursor = mysql.connection.cursor()
            cursor.execute('''
                SELECT t.*, 
                       s.account_number as sender_account,
                       r.account_number as receiver_account
                FROM transfers t
                JOIN accounts s ON t.sender_account_id = s.id
                JOIN accounts r ON t.receiver_account_id = r.id
                WHERE s.id = %s OR r.id = %s
                ORDER BY transfer_date DESC
            ''', (account_id, account_id))
            return cursor.fetchall()

    return User, Account, Transaction, Transfer