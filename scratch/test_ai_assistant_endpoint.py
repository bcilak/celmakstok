import sys
import os
from dotenv import load_dotenv

sys.path.append('/Users/emin/ProgrammingProjects/celmak/celmakstok')
load_dotenv('/Users/emin/ProgrammingProjects/celmak/celmakstok/.env')

from app import create_app, db
from app.models import User, Product

app = create_app()

with app.app_context():
    # Let's find an admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Admin user not found!")
        sys.exit(1)

    print("Testing /reports/ai-assistant/ask with selected product #3752...")
    client = app.test_client()
    
    # Log in the user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True

    # Test query specifying product ID 3752
    response = client.post('/reports/ai-assistant/ask', json={
        'query': '10 adet #3752 üretmek istesem maliyeti ne olur?',
        'history': []
    })
    
    print("Status Code:", response.status_code)
    print("Response JSON:", response.get_json())
