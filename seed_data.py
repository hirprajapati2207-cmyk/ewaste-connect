import os
from app import app, db, User, EWasteRequest
from werkzeug.security import generate_password_hash
from datetime import datetime

with app.app_context():
    # Ensure tables exist
    db.create_all()
    
    # 1. Create a Standard User Account
    user = User.query.filter_by(email='john@example.com').first()
    if not user:
        user = User(
            name='John Doe',
            email='john@example.com',
            password_hash=generate_password_hash('password123'),
            role='user',
            phone='555-0101',
            address='123 Green St, Eco City'
        )
        db.session.add(user)

    # 2. Create a Collection Partner Account
    partner = User.query.filter_by(email='partner@recycle.com').first()
    if not partner:
        partner = User(
            name='Green Recycle Ltd.',
            email='partner@recycle.com',
            password_hash=generate_password_hash('password123'),
            role='partner',
            phone='555-9999',
            address='456 Industrial Pkwy'
        )
        db.session.add(partner)

    db.session.commit()

    # 3. Submit E-Waste Requests & Update Statuses

    # Clear existing demo requests for this user to avoid duplicates if run multiple times
    EWasteRequest.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    
    # Request A: Newly submitted (Pending Partner Acceptance)
    req1 = EWasteRequest(
        user_id=user.id,
        category='Laptops & Computers',
        item_name='Old Dell Inspiron',
        quantity=1,
        condition='Not Working',
        estimated_weight=2.5,
        pickup_mode='pickup',
        scheduled_date='2026-10-10',
        time_slot='Morning (9 AM - 12 PM)',
        collection_address=user.address,
        status='Requested'
    )
    
    # Request B: Accepted & Scheduled by Partner
    req2 = EWasteRequest(
        user_id=user.id,
        partner_id=partner.id,
        category='Mobile Phones',
        item_name='Broken iPhone 11',
        quantity=2,
        condition='Broken',
        estimated_weight=0.4,
        pickup_mode='dropoff',
        scheduled_date='2026-10-05',
        time_slot='Afternoon (12 PM - 4 PM)',
        collection_address='Green Recycle Ltd. Drop-off Center',
        status='Scheduled'
    )
    
    # Request C: Fully Collected and Processed (User earned points!)
    req3 = EWasteRequest(
        user_id=user.id,
        partner_id=partner.id,
        category='Monitors & Displays',
        item_name='Samsung 24" Monitor',
        quantity=1,
        condition='Working',
        estimated_weight=4.0,
        pickup_mode='pickup',
        scheduled_date='2026-09-01',
        time_slot='Morning (9 AM - 12 PM)',
        collection_address=user.address,
        status='Processed'
    )
    # Award points (10 per kg) manually just like the backend route does
    user.eco_points += int(4.0 * 10)
    
    db.session.add_all([req1, req2, req3])
    db.session.commit()

    print("Successfully seeded standard user, collection partner, and full lifecycle requests!")
