import os
import json
import openai
from flask import Flask, render_template, redirect, url_for, request, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret')  # 🔁 Secure key fallback

# --- Flask-Mail setup ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # 🔁 From env
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # 🔁 From env

mail = Mail(app)

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- User class and database ---
class User(UserMixin):
    def __init__(self, id):
        self.id = id

users = {
    'admin': {'password': '1234', 'role': 'admin'}
}

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# --- Load products ---
def load_products():
    with open('products.json') as f:
        return json.load(f)

# --- AI-like Recommendation System ---
def get_recommendations(cart):
    products = load_products()
    recommended = [p for p in products if str(p['id']) not in cart]
    return recommended[:3]

# --- Routes ---
@app.route('/')
def home():
    products = load_products()
    cart = session.get('cart', {})
    recommended = get_recommendations(cart)
    return render_template('home.html', products=products, recommended=recommended)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return "Username already exists."
        users[username] = {'password': password, 'role': 'user'}
        login_user(User(username))
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)
        if user and user['password'] == password:
            login_user(User(username))
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('home'))

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form['product_id']
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    cart[product_id] = cart.get(product_id, 0) + quantity
    session['cart'] = cart
    return redirect(url_for('home'))

@app.route('/checkout')
@login_required
def checkout():
    cart = session.get('cart', {})
    products = load_products()
    selected_items = []
    total = 0
    for product in products:
        pid = str(product['id'])
        if pid in cart:
            quantity = cart[pid]
            product_copy = product.copy()
            product_copy['quantity'] = quantity
            product_copy['total'] = round(product['price'] * quantity, 2)
            selected_items.append(product_copy)
            total += product_copy['total']
    return render_template('checkout.html', items=selected_items, total=round(total, 2))

@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    cart = session.get('cart', {})
    products = load_products()
    selected_items = []
    total = 0
    for product in products:
        pid = str(product['id'])
        if pid in cart:
            quantity = cart[pid]
            product_copy = product.copy()
            product_copy['quantity'] = quantity
            product_copy['total'] = round(product['price'] * quantity, 2)
            selected_items.append(product_copy)
            total += product_copy['total']

    session['cart'] = {}

    item_lines = [f"{item['name']} (x{item['quantity']}) - ${item['total']}" for item in selected_items]
    body = f"Hi {current_user.id},\n\nThanks for your order!\n\nYour items:\n" + "\n".join(item_lines) + f"\n\nTotal: ${round(total, 2)}\n\n— Malvern Store"

    msg = Message("Your Malvern Store Order Confirmation",
                  sender=app.config['MAIL_USERNAME'],  # 🔁 Use env sender
                  recipients=["recipient@example.com"],  # 💡 Later you can use a user-provided email
                  body=body)
    mail.send(msg)

    return render_template('receipt.html', items=selected_items, total=round(total, 2))

@app.route('/admin')
@login_required
def admin_panel():
    if users[current_user.id]['role'] != 'admin':
        return "Access denied."
    return "<h2>Welcome to the admin panel!</h2><a href='/'>Back to Store</a>"

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        msg_body = f"Message from {name} <{email}>:\n\n{message}"
        msg = Message("New Contact Message",
                      sender=app.config['MAIL_USERNAME'],  # 🔁 Use env sender
                      recipients=[app.config['MAIL_USERNAME']],  # 🔁 Self-send
                      body=msg_body)
        mail.send(msg)

        return "<h3>Thanks for reaching out! We'll get back to you soon.</h3><a href='/'>Back to store</a>"

    return render_template('contact.html')
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    reply = ""
    if request.method == 'POST':
        user_message = request.form['message']
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}]
        )
        reply = response.choices[0].message.content
    return render_template('chat.html', reply=reply)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=True, host='0.0.0.0', port=port)



