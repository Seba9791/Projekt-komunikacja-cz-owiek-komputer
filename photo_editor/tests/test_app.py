import unittest
from app import app, db, User
from werkzeug.security import generate_password_hash
import os

class TestPhotoEditing(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()  # Clear the database
            db.create_all()

        # Create a test user
        hashed_password = generate_password_hash('password', method='pbkdf2:sha256')
        user = User(username='testuser', password=hashed_password)
        with app.app_context():
            db.session.add(user)
            db.session.commit()

        # Ensure the upload directory exists
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'tests'), exist_ok=True)

    def tearDown(self):
        with app.app_context():
            db.drop_all()

    def login(self):
        response = self.client.post('/login', data=dict(username='testuser', password='password'), follow_redirects=True)
        return response

    # You can add any other tests that were working correctly.

if __name__ == '__main__':
    unittest.main()

