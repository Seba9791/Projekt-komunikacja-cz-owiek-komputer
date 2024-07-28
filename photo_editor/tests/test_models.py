import unittest
from app import app, db, User, Draft, generate_password_hash

class TestModels(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_user_creation(self):
        user = User(username='testuser', password=generate_password_hash('testpassword', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        self.assertEqual(User.query.count(), 1)

    def test_draft_creation(self):
        user = User(username='testuser', password=generate_password_hash('testpassword', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        draft = Draft(user_id=user.id, filename='test.jpg', name='Test Draft')
        db.session.add(draft)
        db.session.commit()
        self.assertEqual(Draft.query.count(), 1)

if __name__ == '__main__':
    unittest.main()
