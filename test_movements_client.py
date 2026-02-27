import os
import sys
import traceback
from app import create_app, db
from app.models import User

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    with app.app_context():
        user = User.query.filter_by(role='Genel').first()
        if not user:
            user = User(username='testgenel2', name='Test Genel 2', role='Genel')
            user.set_password('1234')
            db.session.add(user)
            db.session.commit()
        user.set_password('1234')
        db.session.commit()

    resp = client.post('/auth/login', data={'username': user.username, 'password': '1234'}, follow_redirects=True)
    
    try:
        resp = client.get('/reports/movements', follow_redirects=True)
        with open('test_error_clean.txt', 'w', encoding='utf-8') as f:
            f.write(f"Status Code: {resp.status_code}\n")
            if resp.status_code == 500:
                f.write(resp.data.decode('utf-8'))
    except Exception as e:
        with open('test_error_clean.txt', 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
