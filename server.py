from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from io import BytesIO
import os

app = Flask(__name__)

# Configuration for production/development
if os.environ.get('DATABASE_URL'):
    # Production (Render/Railway)
    database_url = os.environ.get('DATABASE_URL')
    # Fix for Render PostgreSQL URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Development (Local)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'hotel-management-secret-key-2024')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration (Optional)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'student@gmail.com'  # Change this
app.config['MAIL_PASSWORD'] = '123455'      # Change this
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'  # Change this

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='staff')
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'), nullable=True)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='available')
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500), default='https://images.unsplash.com/photo-1611892440504-42a792e24d32?w=500')
    amenities = db.Column(db.String(500))  # Comma-separated: "WiFi,AC,TV"
    capacity = db.Column(db.Integer, default=2)
    bookings = db.relationship('Booking', backref='room', lazy=True)
    reviews = db.relationship('Review', backref='room', lazy=True)

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20), nullable=False)
    id_proof = db.Column(db.String(50))
    address = db.Column(db.Text)
    loyalty_points = db.Column(db.Integer, default=0)
    loyalty_tier = db.Column(db.String(20), default='Bronze')  # Bronze, Silver, Gold, Platinum
    bookings = db.relationship('Booking', backref='guest', lazy=True)
    user = db.relationship('User', backref='guest_account', uselist=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime)
    expected_checkout = db.Column(db.DateTime)
    total_amount = db.Column(db.Float, default=0)
    advance_payment = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    guest = db.relationship('Guest', backref='reviews')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, danger
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notifications')

class RoomImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdditionalService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))  # food, laundry, transport, etc.
    is_active = db.Column(db.Boolean, default=True)

class BookingService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('additional_service.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    service = db.relationship('AdditionalService')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))  # cash, card, online, razorpay
    transaction_id = db.Column(db.String(200))
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    booking = db.relationship('Booking', backref='payments')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'guest':
            return redirect(url_for('guest_dashboard'))
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'guest':
                return redirect(url_for('guest_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('guest_dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        username = request.form.get('username')
        password = request.form.get('password')
        id_proof = request.form.get('id_proof')
        address = request.form.get('address')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        # Create guest record
        new_guest = Guest(name=name, email=email, phone=phone, 
                         id_proof=id_proof, address=address)
        db.session.add(new_guest)
        db.session.flush()
        
        # Create user account linked to guest
        new_user = User(username=username, 
                       password=generate_password_hash(password),
                       role='guest',
                       guest_id=new_guest.id)
        db.session.add(new_user)
        db.session.commit()
        
        # Send welcome email
        send_welcome_email(new_guest, username)
        
        flash('Registration successful! Please login. Check your email for welcome message.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ADMIN/STAFF ROUTES
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    
    total_rooms = Room.query.count()
    available_rooms = Room.query.filter_by(status='available').count()
    occupied_rooms = Room.query.filter_by(status='occupied').count()
    active_bookings = Booking.query.filter_by(status='active').count()
    total_guests = Guest.query.count()
    
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         total_rooms=total_rooms,
                         available_rooms=available_rooms,
                         occupied_rooms=occupied_rooms,
                         active_bookings=active_bookings,
                         total_guests=total_guests,
                         recent_bookings=recent_bookings)

@app.route('/rooms')
@login_required
def rooms():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    all_rooms = Room.query.all()
    return render_template('rooms.html', rooms=all_rooms)

@app.route('/rooms/add', methods=['POST'])
@login_required
def add_room():
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    room_number = request.form.get('room_number')
    room_type = request.form.get('room_type')
    price = float(request.form.get('price'))
    description = request.form.get('description')
    image_url = request.form.get('image_url') or 'https://images.unsplash.com/photo-1611892440504-42a792e24d32?w=500'
    amenities = request.form.get('amenities')
    capacity = int(request.form.get('capacity', 2))
    
    if Room.query.filter_by(room_number=room_number).first():
        flash('Room number already exists', 'danger')
        return redirect(url_for('rooms'))
    
    new_room = Room(room_number=room_number, room_type=room_type, 
                   price=price, description=description, image_url=image_url,
                   amenities=amenities, capacity=capacity)
    db.session.add(new_room)
    db.session.commit()
    flash('Room added successfully', 'success')
    return redirect(url_for('rooms'))

@app.route('/rooms/delete/<int:room_id>')
@login_required
def delete_room(room_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    room = Room.query.get_or_404(room_id)
    if room.status == 'occupied':
        flash('Cannot delete occupied room', 'danger')
        return redirect(url_for('rooms'))
    
    db.session.delete(room)
    db.session.commit()
    flash('Room deleted successfully', 'success')
    return redirect(url_for('rooms'))

@app.route('/guests')
@login_required
def guests():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    all_guests = Guest.query.all()
    return render_template('guests.html', guests=all_guests)

@app.route('/guests/add', methods=['POST'])
@login_required
def add_guest():
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    id_proof = request.form.get('id_proof')
    address = request.form.get('address')
    
    new_guest = Guest(name=name, email=email, phone=phone, 
                     id_proof=id_proof, address=address)
    db.session.add(new_guest)
    db.session.commit()
    flash('Guest added successfully', 'success')
    return redirect(url_for('guests'))

@app.route('/bookings')
@login_required
def bookings():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    
    all_bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    available_rooms = Room.query.filter_by(status='available').all()
    all_guests = Guest.query.all()
    return render_template('bookings.html', bookings=all_bookings, 
                         rooms=available_rooms, guests=all_guests)

@app.route('/bookings/add', methods=['POST'])
@login_required
def add_booking():
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    guest_id = int(request.form.get('guest_id'))
    room_id = int(request.form.get('room_id'))
    check_in = datetime.now()
    expected_checkout = datetime.strptime(request.form.get('expected_checkout'), '%Y-%m-%d')
    advance_payment = float(request.form.get('advance_payment', 0))
    
    room = Room.query.get(room_id)
    if room.status != 'available':
        flash('Room is not available', 'danger')
        return redirect(url_for('bookings'))
    
    new_booking = Booking(guest_id=guest_id, room_id=room_id, 
                         check_in=check_in, expected_checkout=expected_checkout,
                         advance_payment=advance_payment)
    
    room.status = 'occupied'
    db.session.add(new_booking)
    db.session.commit()
    flash('Booking created successfully', 'success')
    return redirect(url_for('bookings'))

@app.route('/bookings/checkout/<int:booking_id>', methods=['POST'])
@login_required
def checkout_booking(booking_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.status == 'completed':
        flash('Booking already checked out', 'warning')
        return redirect(url_for('bookings'))
    
    booking.check_out = datetime.now()
    booking.status = 'completed'
    
    days = (booking.check_out - booking.check_in).days or 1
    booking.total_amount = days * booking.room.price
    
    # Award loyalty points
    points_earned = calculate_loyalty_points(booking.total_amount)
    booking.guest.loyalty_points += points_earned
    update_guest_loyalty(booking.guest)
    
    booking.room.status = 'available'
    
    db.session.commit()
    
    # Send checkout receipt
    send_checkout_receipt(booking)
    
    # Notify guest about points
    if booking.guest.user:
        create_notification(
            booking.guest.user[0].id,
            'Loyalty Points Earned!',
            f'You earned {points_earned} points! Total: {booking.guest.loyalty_points} points. Tier: {booking.guest.loyalty_tier}',
            'success'
        )
    
    flash(f'Checkout successful. Total: ₹{booking.total_amount:.2f}, Balance: ₹{booking.total_amount - booking.advance_payment:.2f}. Guest earned {points_earned} loyalty points!', 'success')
    return redirect(url_for('bookings'))

@app.route('/calendar')
@login_required
def calendar():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    all_rooms = Room.query.all()
    return render_template('calendar.html', rooms=all_rooms)

@app.route('/api/bookings')
@login_required
def api_bookings():
    bookings = Booking.query.all()
    events = []
    
    for booking in bookings:
        end_date = booking.check_out if booking.check_out else booking.expected_checkout
        if not end_date:
            end_date = booking.check_in + timedelta(days=1)
        
        display_end = end_date + timedelta(days=1)
        
        events.append({
            'id': booking.id,
            'title': f"Room {booking.room.room_number} - {booking.guest.name}",
            'start': booking.check_in.strftime('%Y-%m-%d'),
            'end': display_end.strftime('%Y-%m-%d'),
            'color': '#28a745' if booking.status == 'active' else '#6c757d',
            'extendedProps': {
                'guest': booking.guest.name,
                'room': booking.room.room_number,
                'status': booking.status,
                'phone': booking.guest.phone
            }
        })
    
    return jsonify(events)

@app.route('/reports')
@login_required
def reports():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    
    # Get date range from query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = Booking.query.filter_by(status='completed')
    
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Booking.check_out >= start, Booking.check_out <= end)
        except ValueError:
            flash('Invalid date format', 'danger')
    
    # Calculate statistics
    completed_bookings_list = query.all()
    total_revenue = sum([b.total_amount for b in completed_bookings_list if b.total_amount])
    total_bookings = Booking.query.count()
    completed_bookings = len(completed_bookings_list)
    
    return render_template('reports.html', 
                         total_revenue=total_revenue,
                         total_bookings=total_bookings,
                         completed_bookings=completed_bookings,
                         start_date=start_date,
                         end_date=end_date,
                         bookings_list=completed_bookings_list)

@app.route('/analytics')
@login_required
def analytics():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    
    # Monthly revenue
    from datetime import date
    current_month = date.today().month
    current_year = date.today().year
    
    monthly_revenue = db.session.query(db.func.sum(Booking.total_amount)).filter(
        db.extract('month', Booking.check_out) == current_month,
        db.extract('year', Booking.check_out) == current_year,
        Booking.status == 'completed'
    ).scalar() or 0
    
    # Top guests (by number of bookings)
    top_guests = db.session.query(
        Guest.name,
        Guest.phone,
        db.func.count(Booking.id).label('booking_count'),
        db.func.sum(Booking.total_amount).label('total_spent')
    ).join(Booking).filter(
        Booking.status == 'completed'
    ).group_by(Guest.id).order_by(db.desc('booking_count')).limit(5).all()
    
    # Room performance
    room_performance = db.session.query(
        Room.room_number,
        Room.room_type,
        db.func.count(Booking.id).label('bookings'),
        db.func.sum(Booking.total_amount).label('revenue')
    ).join(Booking).filter(
        Booking.status == 'completed'
    ).group_by(Room.id).order_by(db.desc('revenue')).limit(10).all()
    
    # Average stay duration - simplified calculation
    completed_bookings = Booking.query.filter_by(status='completed').all()
    if completed_bookings:
        total_days = sum([(b.check_out - b.check_in).days or 1 for b in completed_bookings])
        avg_stay = total_days / len(completed_bookings)
    else:
        avg_stay = 0
    
    return render_template('analytics.html',
                         monthly_revenue=monthly_revenue,
                         top_guests=top_guests,
                         room_performance=room_performance,
                         avg_stay=round(avg_stay, 1))

@app.route('/api/revenue-chart')
@login_required
def revenue_chart():
    # Get revenue data for last 7 days
    from datetime import date, timedelta
    today = date.today()
    labels = []
    data = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%d %b'))
        
        # Calculate revenue for that day
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        revenue = db.session.query(db.func.sum(Booking.total_amount)).filter(
            Booking.check_out >= day_start,
            Booking.check_out <= day_end,
            Booking.status == 'completed'
        ).scalar() or 0
        
        data.append(float(revenue))
    
    return jsonify({'labels': labels, 'data': data})

@app.route('/api/room-type-chart')
@login_required
def room_type_chart():
    # Get room type distribution
    room_types = db.session.query(
        Room.room_type,
        db.func.count(Room.id)
    ).group_by(Room.room_type).all()
    
    labels = [rt[0] for rt in room_types]
    data = [rt[1] for rt in room_types]
    
    return jsonify({'labels': labels, 'data': data})

@app.route('/api/occupancy-chart')
@login_required
def occupancy_chart():
    # Get occupancy data for last 7 days
    from datetime import date, timedelta
    today = date.today()
    labels = []
    occupied = []
    available = []
    
    total_rooms = Room.query.count()
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%d %b'))
        
        # This is simplified - in production you'd check actual booking dates
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        occupied_count = Booking.query.filter(
            Booking.check_in <= day_end,
            db.or_(
                Booking.check_out >= day_start,
                Booking.check_out == None
            ),
            Booking.status == 'active'
        ).count()
        
        occupied.append(occupied_count)
        available.append(total_rooms - occupied_count)
    
    return jsonify({
        'labels': labels,
        'occupied': occupied,
        'available': available
    })

# GUEST ROUTES
@app.route('/guest/dashboard')
@login_required
def guest_dashboard():
    if current_user.role != 'guest':
        return redirect(url_for('dashboard'))
    
    guest = Guest.query.get(current_user.guest_id)
    my_bookings = Booking.query.filter_by(guest_id=guest.id).order_by(Booking.created_at.desc()).all()
    active_bookings = Booking.query.filter_by(guest_id=guest.id, status='active').count()
    completed_bookings = Booking.query.filter_by(guest_id=guest.id, status='completed').count()
    
    return render_template('guest_dashboard.html', 
                         guest=guest,
                         bookings=my_bookings,
                         active_bookings=active_bookings,
                         completed_bookings=completed_bookings)

@app.route('/guest/book-room', methods=['GET', 'POST'])
@login_required
def guest_book_room():
    if current_user.role != 'guest':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        room_id = int(request.form.get('room_id'))
        expected_checkout = datetime.strptime(request.form.get('expected_checkout'), '%Y-%m-%d')
        advance_payment = float(request.form.get('advance_payment', 0))
        
        room = Room.query.get(room_id)
        if room.status != 'available':
            flash('Room is not available', 'danger')
            return redirect(url_for('guest_book_room'))
        
        new_booking = Booking(guest_id=current_user.guest_id, room_id=room_id, 
                             check_in=datetime.now(), expected_checkout=expected_checkout,
                             advance_payment=advance_payment)
        
        room.status = 'occupied'
        db.session.add(new_booking)
        db.session.commit()
        
        # Send confirmation email
        send_booking_confirmation(new_booking)
        
        flash('Booking created successfully! Check your email for confirmation.', 'success')
        return redirect(url_for('guest_dashboard'))
    
    # Get filter parameters
    room_type = request.args.get('room_type', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    capacity = request.args.get('capacity', type=int)
    search_query = request.args.get('search', '')
    
    # Start with available rooms
    query = Room.query.filter_by(status='available')
    
    # Apply filters
    if room_type:
        query = query.filter(Room.room_type == room_type)
    if min_price:
        query = query.filter(Room.price >= min_price)
    if max_price:
        query = query.filter(Room.price <= max_price)
    if capacity:
        query = query.filter(Room.capacity >= capacity)
    if search_query:
        query = query.filter(
            db.or_(
                Room.room_number.contains(search_query),
                Room.description.contains(search_query),
                Room.amenities.contains(search_query)
            )
        )
    
    available_rooms = query.all()
    
    # Get unique room types for filter dropdown
    room_types = db.session.query(Room.room_type).distinct().all()
    room_types = [rt[0] for rt in room_types]
    
    return render_template('guest_book_room.html', 
                         rooms=available_rooms,
                         room_types=room_types,
                         filters={
                             'room_type': room_type,
                             'min_price': min_price,
                             'max_price': max_price,
                             'capacity': capacity,
                             'search': search_query
                         })

@app.route('/guest/my-invoice/<int:booking_id>')
@login_required
def guest_invoice(booking_id):
    if current_user.role != 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.guest_id != current_user.guest_id:
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    if booking.status != 'completed':
        flash('Invoice can only be generated for completed bookings', 'warning')
        return redirect(url_for('guest_dashboard'))
    
    return generate_invoice_pdf(booking)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role == 'guest':
        guest = Guest.query.get(current_user.guest_id)
        
        if request.method == 'POST':
            guest.name = request.form.get('name')
            guest.email = request.form.get('email')
            guest.phone = request.form.get('phone')
            guest.address = request.form.get('address')
            guest.id_proof = request.form.get('id_proof')
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        
        return render_template('profile.html', guest=guest)
    else:
        return render_template('profile.html', guest=None)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'danger')
            return redirect(url_for('change_password'))
        
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template('notifications.html', notifications=user_notifications, unread_count=unread_count)

@app.route('/notifications/read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/notifications/read-all')
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read', 'success')
    return redirect(url_for('notifications'))

@app.route('/api/notifications/unread')
@login_required
def unread_notifications_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@app.route('/services')
@login_required
def services():
    if current_user.role == 'guest':
        return redirect(url_for('guest_dashboard'))
    all_services = AdditionalService.query.all()
    return render_template('services.html', services=all_services)

@app.route('/services/add', methods=['POST'])
@login_required
def add_service():
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    category = request.form.get('category')
    
    new_service = AdditionalService(name=name, description=description, price=price, category=category)
    db.session.add(new_service)
    db.session.commit()
    flash('Service added successfully', 'success')
    return redirect(url_for('services'))

@app.route('/services/toggle/<int:service_id>')
@login_required
def toggle_service(service_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    service = AdditionalService.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Service {"activated" if service.is_active else "deactivated"}', 'success')
    return redirect(url_for('services'))

@app.route('/booking/<int:booking_id>/add-service', methods=['POST'])
@login_required
def add_booking_service(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    service_id = int(request.form.get('service_id'))
    quantity = int(request.form.get('quantity', 1))
    
    service = AdditionalService.query.get_or_404(service_id)
    total_price = service.price * quantity
    
    booking_service = BookingService(
        booking_id=booking_id,
        service_id=service_id,
        quantity=quantity,
        total_price=total_price
    )
    db.session.add(booking_service)
    db.session.commit()
    
    flash(f'{service.name} added to booking', 'success')
    return redirect(url_for('bookings'))

@app.route('/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Check permission
    if current_user.role == 'guest':
        if booking.guest_id != current_user.guest_id:
            flash('Access denied', 'danger')
            return redirect(url_for('guest_dashboard'))
    
    if booking.status == 'completed':
        flash('Cannot cancel completed booking', 'danger')
        return redirect(url_for('bookings') if current_user.role != 'guest' else url_for('guest_dashboard'))
    
    booking.status = 'cancelled'
    booking.room.status = 'available'
    db.session.commit()
    
    # Create notification
    if current_user.role != 'guest':
        user = booking.guest.user[0] if booking.guest.user else None
        if user:
            create_notification(
                user.id,
                'Booking Cancelled',
                f'Your booking for Room {booking.room.room_number} has been cancelled.',
                'warning'
            )
    
    flash('Booking cancelled successfully', 'success')
    return redirect(url_for('bookings') if current_user.role != 'guest' else url_for('guest_dashboard'))

@app.route('/room/<int:room_id>/add-image', methods=['POST'])
@login_required
def add_room_image(room_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    room = Room.query.get_or_404(room_id)
    image_url = request.form.get('image_url')
    is_primary = request.form.get('is_primary') == 'on'
    
    if not image_url:
        flash('Please provide an image URL', 'danger')
        return redirect(url_for('room_details', room_id=room_id))
    
    # If this is primary, unset other primary images
    if is_primary:
        RoomImage.query.filter_by(room_id=room_id, is_primary=True).update({'is_primary': False})
    
    new_image = RoomImage(room_id=room_id, image_url=image_url, is_primary=is_primary)
    db.session.add(new_image)
    db.session.commit()
    
    flash('Image added successfully', 'success')
    return redirect(url_for('room_details', room_id=room_id))

@app.route('/room-image/<int:image_id>/delete')
@login_required
def delete_room_image(image_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    image = RoomImage.query.get_or_404(image_id)
    room_id = image.room_id
    db.session.delete(image)
    db.session.commit()
    
    flash('Image deleted successfully', 'success')
    return redirect(url_for('room_details', room_id=room_id))

@app.route('/room-image/<int:image_id>/set-primary')
@login_required
def set_primary_image(image_id):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    image = RoomImage.query.get_or_404(image_id)
    
    # Unset other primary images for this room
    RoomImage.query.filter_by(room_id=image.room_id, is_primary=True).update({'is_primary': False})
    
    # Set this as primary
    image.is_primary = True
    db.session.commit()
    
    flash('Primary image updated', 'success')
    return redirect(url_for('room_details', room_id=image.room_id))

@app.route('/booking/<int:booking_id>/extend', methods=['POST'])
@login_required
def extend_checkout(booking_id):
    if current_user.role != 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.guest_id != current_user.guest_id:
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    if booking.status != 'active':
        flash('Can only extend active bookings', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    new_checkout = datetime.strptime(request.form.get('new_checkout'), '%Y-%m-%d')
    
    if new_checkout <= booking.expected_checkout:
        flash('New checkout date must be after current date', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    booking.expected_checkout = new_checkout
    db.session.commit()
    
    # Notify admin
    admin_users = User.query.filter(User.role.in_(['admin', 'staff'])).all()
    for admin in admin_users:
        create_notification(
            admin.id,
            'Checkout Extension Request',
            f'{booking.guest.name} extended checkout for Room {booking.room.room_number} to {new_checkout.strftime("%d %b %Y")}',
            'info'
        )
    
    create_notification(
        current_user.id,
        'Checkout Extended',
        f'Your checkout for Room {booking.room.room_number} has been extended to {new_checkout.strftime("%d %b %Y")}',
        'success'
    )
    
    flash('Checkout date extended successfully!', 'success')
    return redirect(url_for('guest_dashboard'))

@app.route('/staff')
@login_required
def staff():
    if current_user.role != 'admin':
        flash('Access denied - Admin only', 'danger')
        return redirect(url_for('dashboard'))
    
    all_staff = User.query.filter(User.role.in_(['admin', 'staff'])).all()
    return render_template('staff.html', staff=all_staff)

@app.route('/staff/add', methods=['POST'])
@login_required
def add_staff():
    if current_user.role != 'admin':
        flash('Access denied - Admin only', 'danger')
        return redirect(url_for('dashboard'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'staff')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('staff'))
    
    new_user = User(
        username=username,
        password=generate_password_hash(password),
        role=role
    )
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'Staff account created: {username}', 'success')
    return redirect(url_for('staff'))

@app.route('/staff/<int:user_id>/delete')
@login_required
def delete_staff(user_id):
    if current_user.role != 'admin':
        flash('Access denied - Admin only', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Cannot delete your own account', 'danger')
        return redirect(url_for('staff'))
    
    if user.role == 'guest':
        flash('Cannot delete guest accounts from here', 'danger')
        return redirect(url_for('staff'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Staff account deleted: {username}', 'success')
    return redirect(url_for('staff'))

@app.route('/staff/<int:user_id>/reset-password', methods=['POST'])
@login_required
def reset_staff_password(user_id):
    if current_user.role != 'admin':
        flash('Access denied - Admin only', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password')
    
    user.password = generate_password_hash(new_password)
    db.session.commit()
    
    flash(f'Password reset for {user.username}', 'success')
    return redirect(url_for('staff'))

@app.route('/booking/<int:booking_id>/timeline')
@login_required
def booking_timeline(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Check access
    if current_user.role == 'guest':
        if booking.guest_id != current_user.guest_id:
            flash('Access denied', 'danger')
            return redirect(url_for('guest_dashboard'))
    
    return render_template('booking_timeline.html', booking=booking)

@app.route('/room/<int:room_id>/cleaning/<status>')
@login_required
def update_cleaning_status(room_id, status):
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    room = Room.query.get_or_404(room_id)
    
    if status not in ['clean', 'cleaning', 'dirty']:
        flash('Invalid cleaning status', 'danger')
        return redirect(url_for('rooms'))
    
    room.cleaning_status = status
    if status == 'clean':
        room.last_cleaned = datetime.now()
    
    db.session.commit()
    flash(f'Room {room.room_number} marked as {status}', 'success')
    return redirect(url_for('rooms'))

@app.route('/cleaning-dashboard')
@login_required
def cleaning_dashboard():
    if current_user.role == 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('guest_dashboard'))
    
    clean_rooms = Room.query.filter_by(cleaning_status='clean').count()
    cleaning_rooms = Room.query.filter_by(cleaning_status='cleaning').count()
    dirty_rooms = Room.query.filter_by(cleaning_status='dirty').count()
    
    rooms_to_clean = Room.query.filter_by(cleaning_status='dirty').all()
    
    return render_template('cleaning_dashboard.html',
                         clean_rooms=clean_rooms,
                         cleaning_rooms=cleaning_rooms,
                         dirty_rooms=dirty_rooms,
                         rooms_to_clean=rooms_to_clean)

@app.route('/guest/add-review/<int:room_id>', methods=['POST'])
@login_required
def add_review(room_id):
    if current_user.role != 'guest':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    rating = int(request.form.get('rating'))
    comment = request.form.get('comment')
    
    # Check if guest has completed booking for this room
    completed_booking = Booking.query.filter_by(
        guest_id=current_user.guest_id, 
        room_id=room_id, 
        status='completed'
    ).first()
    
    if not completed_booking:
        flash('You can only review rooms you have stayed in', 'warning')
        return redirect(url_for('guest_dashboard'))
    
    # Check if already reviewed
    existing_review = Review.query.filter_by(
        guest_id=current_user.guest_id, 
        room_id=room_id
    ).first()
    
    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        flash('Review updated successfully', 'success')
    else:
        new_review = Review(room_id=room_id, guest_id=current_user.guest_id,
                           rating=rating, comment=comment)
        db.session.add(new_review)
        flash('Review added successfully', 'success')
    
    db.session.commit()
    return redirect(url_for('guest_dashboard'))

@app.route('/room/<int:room_id>')
@login_required
def room_details(room_id):
    room = Room.query.get_or_404(room_id)
    reviews = Review.query.filter_by(room_id=room_id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    if reviews:
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
    else:
        avg_rating = 0
    
    # Check if current user can review (for guests only)
    can_review = False
    if current_user.role == 'guest':
        completed_booking = Booking.query.filter_by(
            guest_id=current_user.guest_id,
            room_id=room_id,
            status='completed'
        ).first()
        can_review = completed_booking is not None
    
    return render_template('room_details.html', room=room, reviews=reviews, 
                         avg_rating=avg_rating, can_review=can_review)

@app.route('/invoice/<int:booking_id>')
@login_required
def generate_invoice(booking_id):
    if current_user.role == 'guest':
        return redirect(url_for('guest_invoice', booking_id=booking_id))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.status != 'completed':
        flash('Invoice can only be generated for completed bookings', 'warning')
        return redirect(url_for('bookings'))
    
    return generate_invoice_pdf(booking)

def generate_invoice_pdf(booking):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("HOTEL INVOICE", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    hotel_info = [
        ['Hotel Management System', ''],
        ['123 Hotel Street, City', f'Invoice #: INV-{booking.id:05d}'],
        ['Phone: +91-1234567890', f'Date: {datetime.now().strftime("%Y-%m-%d")}'],
    ]
    hotel_table = Table(hotel_info, colWidths=[3*inch, 3*inch])
    hotel_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
    ]))
    elements.append(hotel_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("<b>BILL TO:</b>", styles['Heading3']))
    guest_info = [
        ['Name:', booking.guest.name],
        ['Phone:', booking.guest.phone],
        ['Email:', booking.guest.email or 'N/A'],
        ['Address:', booking.guest.address or 'N/A'],
    ]
    guest_table = Table(guest_info, colWidths=[1.5*inch, 4.5*inch])
    guest_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(guest_table)
    elements.append(Spacer(1, 0.3*inch))
    
    check_in = booking.check_in.strftime('%Y-%m-%d %H:%M')
    check_out = booking.check_out.strftime('%Y-%m-%d %H:%M') if booking.check_out else 'N/A'
    days = (booking.check_out - booking.check_in).days if booking.check_out else 0
    if days == 0:
        days = 1
    
    data = [
        ['Description', 'Quantity', 'Rate', 'Amount'],
        [f'Room {booking.room.room_number} - {booking.room.room_type}', 
         f'{days} night(s)', 
         f'₹{booking.room.price:.2f}', 
         f'₹{booking.room.price * days:.2f}'],
        ['', '', '', ''],
        ['', '', 'Subtotal:', f'₹{booking.total_amount:.2f}'],
        ['', '', 'Advance Paid:', f'₹{booking.advance_payment:.2f}'],
        ['', '', 'Balance:', f'₹{booking.total_amount - booking.advance_payment:.2f}'],
    ]
    
    table = Table(data, colWidths=[3*inch, 1*inch, 1*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
        ('GRID', (0, 0), (-1, -4), 1, colors.black),
        ('FONTNAME', (2, -3), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -3), (-1, -1), 11),
        ('LINEABOVE', (2, -3), (-1, -3), 1, colors.black),
        ('LINEABOVE', (2, -1), (-1, -1), 2, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))
    
    info = [
        ['Check-in:', check_in],
        ['Check-out:', check_out],
        ['Duration:', f'{days} night(s)'],
    ]
    info_table = Table(info, colWidths=[1.5*inch, 4.5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5*inch))
    
    elements.append(Paragraph("<b>Thank you for choosing our hotel!</b>", styles['Normal']))
    elements.append(Paragraph("For any queries, please contact us at info@hotel.com", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=invoice_{booking.id}.pdf'
    
    return response

# Email Helper Functions
def send_booking_confirmation(booking):
    """Send booking confirmation email to guest"""
    # Email functionality disabled - using notifications instead
    create_notification(
        booking.guest.user[0].id if booking.guest.user else None,
        'Booking Confirmed',
        f'Your booking for Room {booking.room.room_number} has been confirmed!',
        'success'
    )

def send_checkout_receipt(booking):
    """Send checkout receipt email to guest"""
    # Email functionality disabled - using notifications instead
    create_notification(
        booking.guest.user[0].id if booking.guest.user else None,
        'Checkout Complete',
        f'Thank you for staying! Total: ₹{booking.total_amount:.2f}',
        'info'
    )

def send_welcome_email(guest, username):
    """Send welcome email to newly registered guest"""
    # Email functionality disabled - using notifications instead
    user = User.query.filter_by(username=username).first()
    if user:
        create_notification(
            user.id,
            'Welcome to Our Hotel!',
            f'Welcome {guest.name}! Your account has been created successfully.',
            'success'
        )

def create_notification(user_id, title, message, notification_type='info'):
    """Create a new notification for user"""
    if not user_id:
        return
    
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type
    )
    db.session.add(notification)
    db.session.commit()
    print(f"✓ Notification created for user {user_id}: {title}")

def calculate_loyalty_points(amount):
    """Calculate loyalty points: 1 point per ₹100 spent"""
    return int(amount / 100)

def update_guest_loyalty(guest):
    """Update guest loyalty tier based on points"""
    points = guest.loyalty_points
    
    if points >= 1000:
        guest.loyalty_tier = 'Platinum'
    elif points >= 500:
        guest.loyalty_tier = 'Gold'
    elif points >= 200:
        guest.loyalty_tier = 'Silver'
    else:
        guest.loyalty_tier = 'Bronze'
    
    db.session.commit()

def get_loyalty_discount(tier):
    """Get discount percentage based on tier"""
    discounts = {
        'Bronze': 0,
        'Silver': 5,
        'Gold': 10,
        'Platinum': 15
    }
    return discounts.get(tier, 0)

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', 
                        password=generate_password_hash('admin123'),
                        role='admin')
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created: username='admin', password='admin123'")

# Health check endpoint for Render
@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    init_db()
    # Use environment variable for port (required for Render/Railway)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
