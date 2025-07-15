from flask import Blueprint, render_template, request, url_for, redirect, flash, session, abort
from app import app
from models import db, User, Vehicle, Address, ParkingLot, ParkingSpot, Reservation
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decorators import admin_required
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from sqlalchemy.sql.expression import case
import csv
from uuid import uuid4

admin = Blueprint('admin', __name__)



#---------------------------------------------------------LOTS------------------------------------------------------

# ADMIN: VIEW ALL LOTS
@admin.route('/admin/lots')
@admin_required
def view_lots():
    lots = ParkingLot.query.all()
    return render_template('admin/view_lots.html', lots=lots)



# ADMIN: ADD LOT
@admin.route('/lots/add', methods=['GET', 'POST'])
@admin_required
def add_lot():
    if request.method == 'POST':
        name = request.form.get('name')
        price_per_hour = float(request.form.get('price_per_hour'))
        max_spots = int(request.form.get('max_spots'))

        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        pincode = request.form.get('pincode')
        landmark = request.form.get('landmark')
        
        new_address = Address(address=address, city=city, state=state, pincode=pincode, landmark=landmark)
        db.session.add(new_address)
        db.session.commit()

        new_lot = ParkingLot(name=name, price_per_hour=price_per_hour, max_spots=max_spots, address_id=new_address.id)
        db.session.add(new_lot)
        db.session.commit()


        for i in range(1, max_spots + 1):
            spot = ParkingSpot(
                spot_number=str(i),
                lot_id=new_lot.id,
                status='A',
                is_active=True
            )
            db.session.add(spot)
        db.session.commit()


        flash('Parking lot added successfully.')
        return redirect(url_for('admin.view_lots'))

    addresses = Address.query.all()
    return render_template('admin/add_lot.html', addresses=addresses)



# ADMIN: EDIT LOT
@admin.route('/admin/lots/edit/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def edit_lot(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Lot not found")
        return redirect(url_for('view_lots'))

    if request.method == 'POST':
        lot.name = request.form.get('name')
        lot.price_per_hour = float(request.form.get('price_per_hour'))
        new_max_spots = int(request.form.get('max_spots'))

        lot.address.address = request.form.get('address')
        lot.address.city = request.form.get('city')
        lot.address.state = request.form.get('state')
        lot.address.pincode = request.form.get('pincode')
        lot.address.landmark = request.form.get('landmark')

        old_max_spots = lot.max_spots
        lot.max_spots = new_max_spots

        db.session.commit()

        current_spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.id).all()
        current_count = len(current_spots)

        if new_max_spots > current_count:
            for i in range(current_count + 1, new_max_spots + 1):
                spot = ParkingSpot(
                    spot_number=str(i),
                    lot_id=lot.id,
                    status='A',
                    is_active=True
                )
                db.session.add(spot)
            db.session.commit()
        elif new_max_spots < current_count:
            available_spots = [s for s in current_spots if s.status == 'A']
            to_remove = current_count - new_max_spots
            for spot in available_spots[:to_remove]:
                db.session.delete(spot)
            db.session.commit()

        flash('Parking lot updated.')
        return redirect(url_for('admin.view_lots'))

    addresses = Address.query.all()
    return render_template('admin/edit_lot.html', lot=lot, addresses=addresses)



# ADMIN: DELETE LOT
@admin.route('/admin/lots/delete/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def delete_lot(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Lot not found")
        return redirect(url_for('admin.view_lots'))
    if request.method == 'POST':
        db.session.delete(lot)
        db.session.commit()
        flash('Parking lot deleted.')
        return redirect(url_for('admin.view_lots'))
    return render_template('admin/delete_lot.html', lot=lot)


#-----------------------------------------------------SPOTS--------------------------------------------------------
# ADMIN: VIEW SPOTS
@admin.route('/admin/spots')
@admin_required
def view_spots():
    lots_with_stats = []
    lots = ParkingLot.query.all()
    
    for lot in lots:
        total_spots = ParkingSpot.query.filter_by(lot_id=lot.id).count()
        available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        maintenance = ParkingSpot.query.filter_by(lot_id=lot.id, status='M').count()
        
        lots_with_stats.append({
            'lot': lot,
            'total': total_spots,
            'available': available,
            'occupied': occupied,
            'maintenance': maintenance
        })
    
    return render_template('admin/view_spots.html', lots_stats=lots_with_stats)


@admin.route('/admin/spots/lot/<int:lot_id>')
@admin_required
def view_lot_spots(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    filter_by = request.args.get('filter', '').lower()

    if filter_by == 'occupied':
        spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').all()
    elif filter_by == 'available':
        spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()
    elif filter_by == 'maintenance':
        spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='M').all()
    else:
        spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()

    return render_template('admin/lot_spots.html', lot=lot, spots=spots, current_filter=filter_by)





# ADMIN: ADD SPOT
@admin.route('/admin/spots/add', methods=['GET', 'POST'])
@admin_required
def add_spot():
    if request.method == 'POST':
        spot_number = request.form.get('spot_number')
        lot_id = int(request.form.get('lot_id'))
        status = request.form.get('status') or 'A'
        is_active = True if request.form.get('is_active') == 'on' else False

        lot = ParkingLot.query.get(lot_id)
        if not lot:
            flash("Invalid parking lot selected.")
            return redirect(url_for('admin.add_spot'))

        existing = ParkingSpot.query.filter_by(spot_number=spot_number, lot_id=lot_id).first()
        if existing:
            flash("Spot number already exists in this lot.")
            return redirect(url_for('admin.add_spot'))

        new_spot = ParkingSpot(spot_number=spot_number, lot_id=lot_id, status=status, is_active=is_active)
        db.session.add(new_spot)
        db.session.commit()

        # Increment max_spots
        lot.max_spots += 1
        db.session.commit()

        flash('Parking spot added successfully.')
        return redirect(url_for('admin.view_spots'))

    lots = ParkingLot.query.all()
    return render_template('admin/add_spot.html', lots=lots)





# ADMIN: EDIT SPOT
@admin.route('/admin/<int:lot_id>/spots/edit/<int:spot_id>', methods=['GET', 'POST'])
@admin_required
def edit_spot(lot_id, spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)

    if request.method == 'POST':
        spot_number = request.form.get('spot_number')
        status = request.form.get('status') or 'A'
        is_active = request.form.get('is_active') == 'on'

        lot = ParkingLot.query.get(lot_id)
        if not lot:
            flash("Invalid parking lot selected.")
            return redirect(url_for('admin.edit_spot', spot_id=spot_id))

        # Check if another spot in the same lot already has the same spot number
        existing = ParkingSpot.query.filter_by(spot_number=spot_number, lot_id=lot_id).first()
        if existing and existing.id != spot.id:
            flash("Spot number already exists in this lot.")
            return redirect(url_for('admin.edit_spot', spot_id=spot_id))

        spot.spot_number = spot_number
        spot.lot_id = lot_id
        spot.status = status
        spot.is_active = is_active

        db.session.commit()
        flash('Spot updated successfully.')
        return redirect(url_for('admin.view_spots'))

    lots = ParkingLot.query.all()
    return render_template('admin/edit_spot.html', spot=spot, lots=lots)



# ADMIN: DELETE SPOT
@admin.route('/admin/<int:lot_id>/spots/delete/<int:spot_id>', methods=['POST'])
@admin_required
def admin_delete_spot(lot_id, spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot = ParkingLot.query.get_or_404(lot_id)
    if spot.reservations:
        flash("Cannot delete a spot with existing reservations.")
        return redirect(url_for('admin.view_spots'))

    db.session.delete(spot)
    db.session.commit()

    # Decrement max_spots
    if lot.max_spots > 1:
        lot.max_spots -= 1
        db.session.commit()

    flash('Spot deleted successfully.')
    return redirect(url_for('admin.view_spots'))



#------------------------------------------- RESERVATION -----------------------------------------------------------
# ADMIN: VIEW ALL RESERVATIONS WITH FILTERS
@admin.route('/admin/reservations')
@admin_required
def view_reservations():

    status_filter = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_query = request.args.get('search', '')
    

    query = Reservation.query
    
    # Apply status filter
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    
    # Apply date range filters
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Reservation.start_time >= start_datetime)
        except ValueError:
            pass  # Invalid date format, ignore
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # Add 23:59:59 to include the entire end date
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Reservation.start_time <= end_datetime)
        except ValueError:
            pass  # Invalid date format, ignore
    
    # Apply search filter (search in vehicle plate and user email)
    if search_query:
        query = query.join(User).filter(
            db.or_(
                Reservation.vehicle_plate.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%'),
                User.full_name.ilike(f'%{search_query}%')
            )
        )
    
    # Execute query with ordering
    reservations = query.order_by(Reservation.start_time.desc()).all()
    
    # Pass filter values back to template to maintain form state
    return render_template('admin/view_reservations.html', 
                         reservations=reservations,
                         current_status=status_filter,
                         current_start_date=start_date,
                         current_end_date=end_date,
                         current_search=search_query)


# Reservation History per User
@admin.route('/admin/user/<int:user_id>/reservations')
@admin_required
def user_reservations(user_id):
    user = User.query.get_or_404(user_id)
    reservations = Reservation.query.filter_by(user_id=user_id).all()
    return render_template('admin/user_reservations.html', user=user, reservations=reservations)

#--------------------------------------------------------------------------------------------------------------------
# Admin Dashboard Stats
@admin.route('/admin')
@admin_required
def index():
    # Stats calculation
    stats = {
        'total_users': User.query.count(),
        'total_lots': ParkingLot.query.count(),
        'total_spots': ParkingSpot.query.count(),
        'active_reservations': Reservation.query.filter_by(status='Active').count()
    }
    
    # Calculate spot status
    spot_status = {
        'available': ParkingSpot.query.filter_by(status='A').count(),
        'occupied': ParkingSpot.query.filter_by(status='O').count(),
        'maintenance': ParkingSpot.query.filter_by(status='M').count()
    }
    
    # Bookings by parking lot
    lot_bookings = []
    lot_names = []
    for lot in ParkingLot.query.all():
        bookings = Reservation.query.join(ParkingSpot).filter(
            ParkingSpot.lot_id == lot.id
        ).count()
        lot_bookings.append(bookings)
        lot_names.append(lot.name)
    
    # Revenue trends (last 7 days)
    revenue_data = []
    revenue_labels = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0)
        day_end = date.replace(hour=23, minute=59, second=59)
        
        daily_revenue = db.session.query(
            func.sum(Reservation.final_cost)
        ).filter(
            Reservation.end_time.between(day_start, day_end)
        ).scalar() or 0
        
        revenue_data.append(float(daily_revenue))
        revenue_labels.append(date.strftime('%a'))
    
    # Recent activities (example implementation)
    recent_activities = [
        {
            'icon_class': 'success',
            'icon': 'fas fa-plus',
            'title': 'New parking lot added: Downtown Mall',
            'time': '2 hours ago'
        },
        # Add more activities from your database
    ]
    
    return render_template(
        'admin/index.html',
        stats=stats,
        spot_status=spot_status,
        lot_bookings=lot_bookings,
        lot_names=lot_names,
        revenue_data=revenue_data,
        revenue_labels=revenue_labels,
        recent_activities=recent_activities,
        datetime=datetime
    )




# Admin: Manage Users with Search, Filters, and Actions
@admin.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    # Handle user actions
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        user = User.query.get_or_404(user_id)
        
        if action == 'toggle_role':
            user.is_admin = not user.is_admin
            db.session.commit()
            flash(f"User role {'promoted to admin' if user.is_admin else 'demoted to user'}", 'success')
            
        elif action == 'delete':
            if not user.is_admin:
                # Delete associated data
                Reservation.query.filter_by(user_id=user_id).delete()
                Vehicle.query.filter_by(user_id=user_id).delete()
                db.session.delete(user)
                db.session.commit()
                flash("User deleted successfully", 'success')
            else:
                flash("Cannot delete admin users", 'warning')
                
        return redirect(url_for('admin.manage_users'))
    
    # Handle search and filters
    q = request.args.get('q', '')
    role_filter = request.args.get('role', 'all')
    
    query = User.query
    
    # Apply search filter
    if q:
        query = query.filter(
            (User.full_name.ilike(f'%{q}%')) |
            (User.email.ilike(f'%{q}%')) |
            (User.phone.ilike(f'%{q}%'))
        )
    
    # Apply role filter
    if role_filter != 'all':
        is_admin = role_filter == 'admin'
        query = query.filter(User.is_admin == is_admin)
    
    users = query.order_by(User.registered_on.desc()).all()
    
    # Calculate statistics (without active_users)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    stats = {
        'total_users': User.query.count(),
        'new_users_week': User.query.filter(User.registered_on >= week_ago).count(),
        'new_users_month': User.query.filter(User.registered_on >= month_ago).count()
    }

    # Calculate registration graph data
    start_date = now - timedelta(days=29)
    registration_counts = []

    for i in range(30):
        day = start_date + timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = User.query.filter(
            User.registered_on >= day,
            User.registered_on < next_day
        ).count()
        registration_counts.append(count)

    reg_graph = {
        'labels': [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)],
        'data': registration_counts
    }

    return render_template(
        'admin/manage_users.html',
        users=users,
        search_query=q,
        role_filter=role_filter,
        stats=stats,
        reg_graph=reg_graph  # Add this to pass to template
    )



    
#-----------------------------------------------------------PROFILE-----------------------------------------------

# Admin: Edit User Profile
@admin.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    vehicle = Vehicle.query.filter_by(user_id=user.id).first()
    address = Address.query.get(user.address_id) if user.address_id else None

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')

  
        addr = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        pincode = request.form.get('pincode')
        landmark = request.form.get('landmark')

        if addr or city or state or pincode or landmark:
            if not address:
                address = Address(
                    address=addr,
                    city=city,
                    state=state,
                    pincode=pincode,
                    landmark=landmark
                )
                db.session.add(address)
                db.session.commit()
                user.address_id = address.id
            else:
                address.address = addr or address.address
                address.city = city or address.city
                address.state = state or address.state
                address.pincode = pincode or address.pincode
                address.landmark = landmark or address.landmark

 
        plate_number = request.form.get('plate_number')
        vehicle_type = request.form.get('vehicle_type')
        color = request.form.get('color')

        if plate_number or vehicle_type or color:
            if not vehicle:
                vehicle = Vehicle(
                    user_id=user.id,
                    plate_number=plate_number,
                    vehicle_type=vehicle_type,
                    color=color
                )
                db.session.add(vehicle)
            else:
                vehicle.plate_number = plate_number or vehicle.plate_number
                vehicle.vehicle_type = vehicle_type or vehicle.vehicle_type
                vehicle.color = color or vehicle.color


        db.session.commit()
        flash('User profile updated successfully.', 'success')
        return redirect(url_for('admin.manage_users'))

    return render_template(
        'admin/edit_user.html',
        user=user,
        vehicle=vehicle,
        address=address
    )




@admin.route('/admin/user/<int:user_id>/profile')
@admin_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/user_profile.html', user=user)

#-----------------------------------------------------------SEARCH-------------------------------------------------

# Admin: Search Users
@admin.route('/admin/search')
@admin_required
def search():
    users = User.query.all()
    return render_template('admin/search.html')

#-----------------------------------------------------------SUMMARY-------------------------------------------------
# Admin: Summmary
@admin.route('/admin/summary')
@admin_required
def summary():
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)

    total_users = User.query.count()
    total_admins = User.query.filter_by(is_admin=True).count()
    new_users_week = User.query.filter(User.registered_on >= one_week_ago).count()
    recent_users = User.query.order_by(User.registered_on.desc()).limit(5).all()
    
    # Parking Lot & Spot Stats
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    available_spots = ParkingSpot.query.filter_by(status='A').count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    inactive_spots = ParkingSpot.query.filter_by(is_active=False).count()
    
    # Full lots (no available spots)
    full_lots = db.session.query(
        ParkingLot.id
    ).join(ParkingSpot).filter(
        ParkingSpot.is_active == True
    ).group_by(ParkingLot.id).having(
        func.sum(case((ParkingSpot.status == 'A', 1), else_=0)) == 0
    ).count()
    
    # Reservation Summary
    total_reservations = Reservation.query.count()
    
    active_reservations = Reservation.query.filter(
        Reservation.start_time <= now,
        Reservation.end_time >= now,
        Reservation.status == 'active'
    ).count()
    
    released_reservations = Reservation.query.filter_by(status='released').count()
    expired_reservations = Reservation.query.filter(
        Reservation.end_time < now,
        Reservation.status == 'expired'
    ).count()
    
    # Average calculations
    avg_duration = db.session.query(
        func.avg(Reservation.end_time - Reservation.start_time)
    ).scalar()
    
    avg_cost = db.session.query(
        func.avg(Reservation.final_cost)
    ).scalar()
    
    # Chart 1: Bookings by Parking Lot
    lot_bookings = db.session.query(
        ParkingLot.name,
        func.count(Reservation.id)
    ).join(ParkingSpot, ParkingSpot.lot_id == ParkingLot.id)\
     .join(Reservation, Reservation.spot_id == ParkingSpot.id)\
     .group_by(ParkingLot.name)\
     .all()
    
    lot_names = [result[0] for result in lot_bookings]
    lot_booking_counts = [result[1] for result in lot_bookings]
    
    # Chart 2: Spot Status Overview
    spot_status = {
        'available': available_spots,
        'occupied': occupied_spots,
        'maintenance': inactive_spots
    }
    
    # Chart 3: Revenue Trends (Last 7 Days)
    revenue_by_day = db.session.query(
        func.date(Reservation.end_time),
        func.sum(Reservation.final_cost)
    ).filter(Reservation.end_time >= one_week_ago)\
     .group_by(func.date(Reservation.end_time))\
     .order_by(func.date(Reservation.end_time))\
     .all()
    
    # Generate all dates in the last 7 days
    date_labels = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    revenue_data = [0.0] * 7
    
    # Fill in revenue data where available
    for result in revenue_by_day:
        date_str = result[0]  # Already a string in 'YYYY-MM-DD' format
        if date_str in date_labels:
            idx = date_labels.index(date_str)
            revenue_data[idx] = float(result[1]) if result[1] else 0.0
    
    # Recent activities (dummy data)
    recent_activities = [
        {'title': 'New user registered', 'time': '2 minutes ago', 'icon': 'fas fa-user-plus', 'icon_class': 'info'},
        {'title': 'Parking spot reserved', 'time': '15 minutes ago', 'icon': 'fas fa-car', 'icon_class': 'success'},
        {'title': 'Payment processed', 'time': '1 hour ago', 'icon': 'fas fa-credit-card', 'icon_class': 'warning'}
    ]
    
    return render_template('admin/summary.html',
        # User stats
        total_users=total_users,
        total_admins=total_admins,
        new_users_week=new_users_week,
        recent_users=recent_users,
        
        # Parking stats
        total_lots=total_lots,
        total_spots=total_spots,
        available_spots=available_spots,
        occupied_spots=occupied_spots,
        inactive_spots=inactive_spots,
        full_lots=full_lots,
        
        # Reservation stats
        total_reservations=total_reservations,
        active_reservations=active_reservations,
        released_reservations=released_reservations,
        expired_reservations=expired_reservations,
        avg_duration=avg_duration,
        avg_cost=avg_cost,
        
        # Chart data
        lot_names=lot_names,
        lot_bookings=lot_booking_counts,
        spot_status=spot_status,
        revenue_labels=date_labels,
        revenue_data=revenue_data,
        recent_activities=recent_activities
    )





# ADMIN: SPOT DETAILS
@admin.route('/admin/spot-details/<int:spot_id>')
@admin_required
def spot_details(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    reservation = None
    if spot.status == 'O':
        reservation = Reservation.query.filter_by(spot_id=spot_id, status='Active').first()
    return render_template('admin/spot_details.html', spot=spot, reservation=reservation)

# ADMIN: RELEASE SPOT (optional feature)
@admin.route('/admin/release-spot/<int:spot_id>', methods=['POST'])
@admin_required
def release_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    if spot.status == 'O':
        # Find active reservation and mark as completed
        reservation = Reservation.query.filter_by(spot_id=spot_id, status='Active').first()
        if reservation:
            reservation.status = 'Completed'
            reservation.end_time = datetime.now()
        spot.status = 'A'  # Set to Available
        db.session.commit()
        flash('Spot released successfully.')
    return redirect(url_for('admin.view_spots'))



@admin.route('/admin/reservations/delete/<int:res_id>', methods=['POST'])
@admin_required
def delete_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    db.session.delete(reservation)
    db.session.commit()
    flash('Reservation deleted successfully', 'success')
    return redirect(url_for('admin.view_reservations'))
