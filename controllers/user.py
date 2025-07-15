from flask import Blueprint, render_template, request, url_for, redirect, flash, session
from app import app
from models import db, User, Vehicle, Address, ParkingLot, ParkingSpot, Reservation
from werkzeug.security import generate_password_hash
from functools import wraps
from sqlalchemy import func
from decorators import login_required
from datetime import datetime, timedelta
import math

user = Blueprint('user', __name__)


# USER HOME
@user.route('/', methods=['GET', 'POST'])
def index():
    current_date = datetime.now()
    
    # Calculate stats
    active_users = User.query.filter_by(is_admin=False).count()
    parking_locations = ParkingLot.query.count()
    total_bookings = Reservation.query.count()

    # Calculate uptime (example: always 99.9% for now)
    uptime_percent = 99.9

    user_stats = {
        'active_users': active_users,
        'parking_locations': parking_locations,
        'total_bookings': total_bookings,
        'uptime_percent': uptime_percent
    }
    
    return render_template('user/index.html', current_date=current_date, user_stats=user_stats)


# USER PROFILE
@user.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_obj = User.query.get(session['user_id'])
    
    vehicle = user_obj.vehicles[0] if user_obj.vehicles else None

    address = user_obj.address

    if request.method == 'POST':
        user_obj.full_name = request.form.get('full_name')
        user_obj.email = request.form.get('email')
        user_obj.phone = request.form.get('phone')
        new_password = request.form.get('new_password')
        if new_password:
            user_obj.password = generate_password_hash(new_password)
        user_obj.updated_on = datetime.utcnow()

        if vehicle:
            vehicle.plate_number = request.form.get('plate_number')
            vehicle.vehicle_type = request.form.get('vehicle_type')
            vehicle.color = request.form.get('color')
        else:
            vehicle = Vehicle(
                plate_number=request.form.get('plate_number'),
                vehicle_type=request.form.get('vehicle_type'),
                color=request.form.get('color'),
                user_id=user_obj.id
            )
            db.session.add(vehicle)

        if user_obj.address:
            address = user_obj.address
            address.address = request.form.get('address')
            address.city = request.form.get('city')
            address.state = request.form.get('state')
            address.pincode = request.form.get('pincode')
            address.landmark = request.form.get('landmark')
        else:
            address = Address(
                address=request.form.get('address'),
                city=request.form.get('city'),
                state=request.form.get('state'),
                pincode=request.form.get('pincode'),
                landmark=request.form.get('landmark')
            )
            db.session.add(address)
            db.session.flush()  
            user_obj.address = address  

        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('user.profile'))

    return render_template('user/profile.html', user=user_obj, vehicle=vehicle, address=address)


# USER VIEW SPOTS
@user.route('/lots/<int:lot_id>/spots')
@login_required
def view_spots(lot_id):
    spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()
    return {
        "spots": [
            {"id": spot.id, "spot_number": spot.spot_number}
            for spot in spots
        ]
    }


# ADD VEHICLE
@user.route('/add_vehicle', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        plate = request.form.get('plate_number')
        vtype = request.form.get('vehicle_type')
        color = request.form.get('color')

        new_vehicle = Vehicle(
            plate_number=plate,
            vehicle_type=vtype,
            color=color,
            user_id=session['user_id']
        )
        db.session.add(new_vehicle)
        db.session.commit()
        flash('Vehicle added')
        return redirect(url_for('user.index'))

    return render_template('user/add_vehicle.html')


# USER: BOOK SPOT PAGE
@user.route('/book/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def book_spot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    available_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()
    user_id = session['user_id']

    user = User.query.get(user_id)
    vehicle = user.vehicles[0] if user.vehicles else None
    address = user.address if user.address else None

    if request.method == 'POST':
        spot_id = request.form.get('spot_id')
        plate_number = request.form.get('plate_number')
        vehicle_type = request.form.get('vehicle_type')
        color = request.form.get('color')
        address_line = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        pincode = request.form.get('pincode')
        landmark = request.form.get('landmark')

        spot = ParkingSpot.query.filter_by(id=spot_id, status='A').first()
        if not spot:
            flash("Invalid spot selection", "danger")
            return redirect(url_for('user.book_spot', lot_id=lot_id))
        
        new_reservation = Reservation(
            user_id=user_id, 
            spot_id=spot.id,
            vehicle_plate=plate_number,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
            status='Active'
        )
        
        spot.status = 'O'  
        
        db.session.add(new_reservation)
        db.session.commit()
        
        flash('Booking successful!', 'success')
        return redirect(url_for('user.user_info'))
    
    return render_template('user/book_spot.html', lot=lot, spots=available_spots,timedelta=timedelta, current_time=datetime.utcnow(),vehicle=vehicle,  address=address)  


# RELEASE RESERVATION
@user.route('/release/<int:res_id>', methods=['GET', 'POST'])
@login_required
def release_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    
    if reservation.user_id != session['user_id']:
        flash('Unauthorized access')
        return redirect(url_for('user.index'))
    
    if request.method == 'POST':
        end_time = datetime.utcnow()
        duration = math.ceil((end_time - reservation.start_time).total_seconds() / 3600)
        rate = reservation.spot.lot.price_per_hour
        amount = round(duration * rate, 2)

        reservation.status = 'Released'
        reservation.end_time = end_time
        reservation.spot.status = 'A'
        reservation.final_cost = amount
        db.session.commit()
        flash('Reservation released successfully')
        return redirect(url_for('user.user_info'))
    

    current_time = datetime.utcnow()
    duration = math.ceil((current_time - reservation.start_time).total_seconds() / 3600)
    rate = reservation.spot.lot.price_per_hour
    estimated_cost = round(duration * rate, 2)
    
    return render_template('user/release.html', reservation=reservation, current_time=current_time,estimated_cost=estimated_cost)


# USER SUMMARY PAGE
from collections import Counter

@user.route('/summary')
@login_required
def summary():
    user_id = session['user_id']
    current_user = User.query.get(user_id)
    total_bookings = Reservation.query.filter_by(user_id=user_id).count()
    total_spent = db.session.query(
        func.coalesce(func.sum(Reservation.final_cost), 0.0)
    ).filter_by(user_id=user_id).scalar()
    active_session = Reservation.query.filter_by(
        user_id=user_id, status='Active'
    ).first()
    current_duration = 0.0
    current_cost = 0.0
    if active_session:
        current_duration = round((datetime.utcnow() - active_session.start_time).total_seconds() / 3600, 1)
        if active_session.spot and active_session.spot.lot:
            current_cost = round(current_duration * active_session.spot.lot.price_per_hour, 2)

    completed = Reservation.query.filter_by(
        user_id=user_id, status='Released'
    ).all()
    total_hours = 0.0
    for res in completed:
        if res.end_time:
            hours = (res.end_time - res.start_time).total_seconds() / 3600
            total_hours += hours
    avg_duration = round(total_hours / len(completed), 1) if completed else 0.0

    # Active/completed bookings
    active_sessions_count = Reservation.query.filter_by(
        user_id=user_id, status='Active'
    ).count()
    completed_bookings = Reservation.query.filter_by(
        user_id=user_id, status='Released'
    ).count()

    # Monthly statistics (for last 6 months)
    now = datetime.utcnow()
    monthly_costs = {}
    for i in range(5, -1, -1):
        month = (now.replace(day=1) - timedelta(days=30*i)).replace(day=1)
        next_month = (month + timedelta(days=32)).replace(day=1)
        label = month.strftime('%b %Y')
        cost = db.session.query(
            func.coalesce(func.sum(Reservation.final_cost), 0.0)
        ).filter(
            Reservation.user_id == user_id,
            Reservation.start_time >= month,
            Reservation.start_time < next_month
        ).scalar()
        monthly_costs[label] = float(cost or 0)

    # Vehicle type counts
    vehicle_types = [v.vehicle_type for v in current_user.vehicles]
    vehicle_type_counts = dict(Counter(vehicle_types))

    # Monthly bookings for doughnut chart
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month - timedelta(seconds=1)
    first_of_last_month = last_month_end.replace(day=1)
    previous_month_end = first_of_last_month - timedelta(seconds=1)
    first_of_previous_month = previous_month_end.replace(day=1)

    current_month_bookings = Reservation.query.filter(
        Reservation.user_id == user_id,
        Reservation.start_time >= first_of_this_month
    ).count()
    last_month_bookings = Reservation.query.filter(
        Reservation.user_id == user_id,
        Reservation.start_time >= first_of_last_month,
        Reservation.start_time < first_of_this_month
    ).count()
    previous_bookings = Reservation.query.filter(
        Reservation.user_id == user_id,
        Reservation.start_time >= first_of_previous_month,
        Reservation.start_time < first_of_last_month
    ).count()

    return render_template('user/summary.html',
        user=current_user,
        total_bookings=total_bookings,
        total_spent=total_spent,
        current_duration=current_duration,
        current_cost=current_cost,
        total_hours=round(total_hours, 1),
        avg_duration=avg_duration,
        active_sessions_count=active_sessions_count,
        completed_bookings=completed_bookings,
        current_month_bookings=current_month_bookings,
        last_month_bookings=last_month_bookings,
        previous_bookings=previous_bookings,
        active_session=active_session,
        vehicle_type_counts=vehicle_type_counts,
        monthly_costs=monthly_costs
    )



# User Info PAGE
@user.route('/user_info')
@login_required
def user_info():
    user = User.query.get(session['user_id'])
    lots = ParkingLot.query.all()
    current_date = datetime.utcnow()

    active_sessions = Reservation.query.filter_by(
        user_id=session['user_id'],
        status='Active'
    ).order_by(Reservation.start_time.desc()).all()

    recent_history = Reservation.query.filter_by(
        user_id=session['user_id']
    ).order_by(Reservation.start_time.desc()).limit(5).all()

    # --- Add these stats calculations ---
    total_bookings = Reservation.query.filter_by(user_id=user.id).count()
    completed = Reservation.query.filter_by(user_id=user.id, status='Released').count()
    active_now = Reservation.query.filter_by(user_id=user.id, status='Active').count()
    # Calculate total hours parked
    total_hours = 0
    completed_reservations = Reservation.query.filter_by(user_id=user.id, status='Released').all()
    for res in completed_reservations:
        if res.end_time:
            total_hours += (res.end_time - res.start_time).total_seconds() / 3600

    stats = {
        'total_bookings': total_bookings,
        'completed': completed,
        'active_now': active_now,
        'total_hours': round(total_hours, 1)
    }
    # --------------------------------------

    return render_template(
        'user/user_info.html',
        user=user,
        lots=lots,
        current_date=current_date,
        active_sessions=active_sessions,
        recent_history=recent_history,
        stats=stats  # <-- Pass the stats dictionary
    )



# NEW BOOKING PAGE
@user.route('/new_booking', methods=['GET', 'POST'])
@login_required
def new_booking():
    user = User.query.get(session['user_id'])
    current_date = datetime.utcnow()
    lots = []

    search_query = request.args.get('q')
    if search_query:
        lots = ParkingLot.query.join(Address).filter(
            (Address.address.ilike(f'%{search_query}%')) |
            (Address.pincode.ilike(f'%{search_query}%'))
        ).all()
    else:
        lots = ParkingLot.query.all()
    return render_template('user/new_booking.html', user=user, lots=lots, current_date=current_date, search_query=search_query)


# BOOKING HISTORY PAGE
@user.route('/history')
@login_required
def history():
    user_id = session['user_id']
    history = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.start_time.desc()).all()
    return render_template('user/history.html', history=history)





