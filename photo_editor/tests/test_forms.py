import unittest
from flask import Flask
from flask_testing import TestCase
from app import app, db, RegistrationForm, LoginForm

class TestForms(TestCase):
    def create_app(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        return app

    def setUp(self):
        self.app_context = self.create_app().app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_registration_form_valid(self):
        with self.app_context:
            form = RegistrationForm(username='newuser', password='password123', confirm_password='password123')
            self.assertTrue(form.validate())

    def test_registration_form_invalid(self):
        with self.app_context:
            form = RegistrationForm(username='newuser', password='password123', confirm_password='wrongpassword')
            self.assertFalse(form.validate())

    def test_login_form_valid(self):
        with self.app_context:
            form = LoginForm(username='testuser', password='password123')
            self.assertTrue(form.validate())

if __name__ == '__main__':
    unittest.main()
