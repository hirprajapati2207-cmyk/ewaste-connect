import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-ewaste-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ewaste.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'user', 'partner', 'admin'
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    eco_points = db.Column(db.Integer, default=0)

    requests = db.relationship('EWasteRequest', backref='user', lazy=True, foreign_keys='EWasteRequest.user_id')
    partner_requests = db.relationship('EWasteRequest', backref='partner', lazy=True, foreign_keys='EWasteRequest.partner_id')

class EWasteRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    partner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Assigned partner
    category = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    condition = db.Column(db.String(50))
    estimated_weight = db.Column(db.Float, nullable=False)
    photo_path = db.Column(db.String(255))
    
    pickup_mode = db.Column(db.String(20), nullable=False) # 'pickup' or 'dropoff'
    scheduled_date = db.Column(db.String(20))
    time_slot = db.Column(db.String(50))
    collection_address = db.Column(db.String(255))
    
    status = db.Column(db.String(50), default='Requested') # Requested, Accepted, Scheduled, Collected, Processed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Context Processor for common metrics
@app.context_processor
def inject_metrics():
    if current_user.is_authenticated:
        total_weight = db.session.query(db.func.sum(EWasteRequest.estimated_weight)).filter(EWasteRequest.status.in_(['Collected', 'Processed'])).scalar() or 0
        total_items = db.session.query(db.func.sum(EWasteRequest.quantity)).filter(EWasteRequest.status.in_(['Collected', 'Processed'])).scalar() or 0
        return dict(global_weight=total_weight, global_items=total_items)
    return dict()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password_hash=hashed_password, role=role, phone=phone, address=address)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
            
        flash('Invalid email or password.', 'danger')
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
    if current_user.role == 'admin':
        users_count = User.query.count()
        partners_count = User.query.filter_by(role='partner').count()
        reqs = EWasteRequest.query.all()
        return render_template('admin_dashboard.html', users_count=users_count, partners_count=partners_count, reqs=reqs)
        
    elif current_user.role == 'partner':
        # Get requests assigned to this partner or unassigned
        pending_requests = EWasteRequest.query.filter_by(status='Requested').all()
        assigned_requests = EWasteRequest.query.filter_by(partner_id=current_user.id).all()
        return render_template('partner_dashboard.html', pending=pending_requests, assigned=assigned_requests)
        
    else:
        user_requests = EWasteRequest.query.filter_by(user_id=current_user.id).order_by(EWasteRequest.created_at.desc()).all()
        total_weight = sum(req.estimated_weight for req in user_requests if req.status in ['Collected', 'Processed'])
        return render_template('user_dashboard.html', requests=user_requests, my_weight=total_weight)

@app.route('/add-ewaste', methods=['GET', 'POST'])
@login_required
def add_ewaste():
    if current_user.role != 'user':
        flash('Only users can submit e-waste requests.', 'danger')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        category = request.form.get('category')
        item_name = request.form.get('item_name')
        quantity = int(request.form.get('quantity', 1))
        condition = request.form.get('condition')
        weight = float(request.form.get('weight', 0))
        pickup_mode = request.form.get('pickup_mode')
        scheduled_date = request.form.get('date')
        time_slot = request.form.get('time_slot')
        address = request.form.get('address')
        
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file.filename != '':
                filename = secure_filename(f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = filename
                
        new_request = EWasteRequest(
            user_id=current_user.id,
            category=category,
            item_name=item_name,
            quantity=quantity,
            condition=condition,
            estimated_weight=weight,
            photo_path=photo_path,
            pickup_mode=pickup_mode,
            scheduled_date=scheduled_date,
            time_slot=time_slot,
            collection_address=address
        )
        db.session.add(new_request)
        db.session.commit()
        
        flash('E-Waste request submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('add_ewaste.html')

@app.route('/update-request/<int:req_id>', methods=['POST'])
@login_required
def update_request(req_id):
    if current_user.role not in ['partner', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
        
    req = EWasteRequest.query.get_or_404(req_id)
    action = request.form.get('action')
    
    if action == 'accept':
        req.status = 'Accepted'
        req.partner_id = current_user.id
    elif action == 'schedule':
        req.status = 'Scheduled'
    elif action == 'collect':
        req.status = 'Collected'
        # Award eco points
        req.user.eco_points += int(req.estimated_weight * 10) # Simple formula: 10 pts per kg
    elif action == 'process':
        req.status = 'Processed'
        
    db.session.commit()
    flash(f'Request #{req.id} updated to {req.status}', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Add default admin if not exists
        if not User.query.filter_by(email='admin@ewaste.com').first():
            admin = User(name='System Admin', email='admin@ewaste.com', password_hash=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
            
    app.run(debug=True, port=5000)
