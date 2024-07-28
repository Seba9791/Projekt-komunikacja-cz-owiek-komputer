from flask import Flask, request, redirect, url_for, render_template, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import os
import numpy as np
import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Flask-Migrate configuration
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

PREDEFINED_SIZES = {
    "9x13": (1051, 1535),
    "10x15": (1205, 1795),
    "13x18": (1500, 2102),
    "15x21": (1795, 2551),
    "20x30": (2480, 3508),
    "25x25": (3000, 4500),
    "25x38": (3012, 4512)
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Draft(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=False)  # Nowe pole
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegistrationForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired(), Length(min=2, max=150)])
    password = PasswordField('Hasło', validators=[DataRequired(), Length(min=6, max=150)])
    confirm_password = PasswordField('Potwierdź hasło', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Zarejestruj się')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Nazwa użytkownika jest już zajęta. Wybierz inną nazwę.')

class LoginForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[DataRequired()])
    password = PasswordField('Hasło', validators=[DataRequired()])
    submit = SubmitField('Zaloguj się')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_vignette(img, intensity):
    width, height = img.size
    gradient = Image.new('L', (width, height))
    for y in range(height):
        for x in range(width):
            distance_to_center = np.sqrt((x - width / 2) ** 2 + (y - height / 2) ** 2)
            distance_to_center = float(distance_to_center) / (np.sqrt(2) * max(width, height) / 2)
            gradient.putpixel((x, y), int(255 * (1 - intensity * distance_to_center)))
    vignette = ImageOps.colorize(gradient, black="black", white="white")
    return Image.composite(img, vignette, gradient)

def add_frame(img, frame_width, color):
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    border = Image.new('RGBA', (img.width + 2*frame_width, img.height + 2*frame_width), color)
    border.paste(img, (frame_width, frame_width))
    return border.convert('RGB')

@app.route('/')
def index():
    drafts = []
    if current_user.is_authenticated:
        drafts = Draft.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', drafts=drafts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Twoje konto zostało utworzone! Możesz się teraz zalogować.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Zalogowałeś się!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Logowanie nieudane. Sprawdź nazwę użytkownika i hasło.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'success')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Brak pliku.')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Nie wybrano pliku.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            try:
                # Try to open the file to ensure it's a valid image
                with Image.open(filepath) as img:
                    img.verify()
            except Exception as e:
                os.remove(filepath)
                flash('Nieprawidłowy plik obrazu.')
                return redirect(request.url)

            # Save a copy of the original image
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], f'original_{file.filename}')
            file.save(original_path)
            # Initialize a copy for undo functionality
            undo_path = os.path.join(app.config['UPLOAD_FOLDER'], f'undo_{file.filename}')
            file.save(undo_path)
            return redirect(url_for('edit_image', filename=file.filename))
        else:
            flash('Nieprawidłowy typ pliku.')
            return redirect(request.url)
    return render_template('upload.html')

@app.route('/edit/<filename>', methods=['GET', 'POST'])
@login_required
def edit_image(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], f'original_{filename}')
    undo_path = os.path.join(app.config['UPLOAD_FOLDER'], f'undo_{filename}')

    try:
        with Image.open(filepath) as img:
            img.load()
    except Exception as e:
        flash('Nieprawidłowy plik obrazu.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')
        print(f"Received action: {action}")
        if action == 'undo':
            # Restore the image from the undo copy
            if os.path.exists(undo_path):
                try:
                    with Image.open(undo_path) as undo_img:
                        undo_img.load()
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    os.rename(undo_path, filepath)
                    # Recreate the undo copy
                    with Image.open(filepath) as img:
                        img.save(undo_path)
                except Exception as e:
                    flash('Błąd podczas cofania.')
                    return redirect(url_for('edit_image', filename=filename))
        elif action == 'crop_interactive':
            try:
                with Image.open(filepath) as img:
                    # Save the current state for undo functionality
                    img.save(undo_path)

                    x = int(float(request.form.get('x')))
                    y = int(float(request.form.get('y')))
                    width = int(float(request.form.get('width')))
                    height = int(float(request.form.get('height')))

                    print(f"Cropping image at ({x}, {y}, {width}, {height})")

                    img = img.crop((x, y, x + width, y + height))
                    img.save(filepath)
            except Exception as e:
                print(f"Error during cropping: {e}")
                flash('Błąd podczas przetwarzania obrazu.')
                return redirect(url_for('edit_image', filename=filename))
        elif action == 'save_draft':
            draft_name = request.form.get('draft_name', 'Wersja robocza')
            draft_filename = f'draft_{filename}'
            draft_filepath = os.path.join(app.config['UPLOAD_FOLDER'], draft_filename)
            try:
                with Image.open(filepath) as img:
                    img.save(draft_filepath)
                draft = Draft(user_id=current_user.id, filename=draft_filename, name=draft_name)
                db.session.add(draft)
                db.session.commit()
                flash('Wersja robocza została zapisana.', 'success')
            except Exception as e:
                print(f"Error during saving draft: {e}")
                flash('Błąd podczas zapisywania wersji roboczej.', 'danger')
            return redirect(url_for('edit_image', filename=filename))
        else:
            try:
                with Image.open(filepath) as img:
                    # Save the current state for undo functionality
                    img.save(undo_path)

                    intensity = float(request.form.get('intensity', 1))

                    if action == 'grayscale':
                        img = img.convert('L')
                    elif action == 'blur':
                        img = img.filter(ImageFilter.GaussianBlur(intensity))
                    elif action == 'contour':
                        img = img.filter(ImageFilter.CONTOUR)
                    elif action == 'detail':
                        img = img.filter(ImageFilter.DETAIL)
                    elif action == 'edge_enhance':
                        img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
                    elif action == 'sharpen':
                        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150 * intensity, threshold=3))
                    elif action == 'emboss':
                        img = img.filter(ImageFilter.EMBOSS)
                    elif action == 'brightness':
                        enhancer = ImageEnhance.Brightness(img)
                        img = enhancer.enhance(intensity)
                    elif action == 'contrast':
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(intensity)
                    elif action == 'saturation':
                        enhancer = ImageEnhance.Color(img)
                        img = enhancer.enhance(intensity)
                    elif action == 'vignette':
                        img = add_vignette(img, intensity)
                    elif action == 'resize':
                        size = request.form.get('size')
                        if size in PREDEFINED_SIZES:
                            img = img.resize(PREDEFINED_SIZES[size])
                        else:
                            width = int(request.form.get('width'))
                            height = int(request.form.get('height'))
                            img = img.resize((width, height))
                    elif action == 'add_frame':
                        frame_width = int(request.form.get('frame_width', 10))
                        color = request.form.get('color', 'black')
                        img = add_frame(img, frame_width, color)
                    elif action == 'crop':
                        x = int(float(request.form.get('x')))
                        y = int(float(request.form.get('y')))
                        width = int(float(request.form.get('width')))
                        height = int(float(request.form.get('height')))
                        img = img.crop((x, y, x + width, y + height))
                    elif action == 'crop_vertical':
                        top = int(request.form.get('top'))
                        bottom = int(request.form.get('bottom'))
                        width, height = img.size
                        img = img.crop((0, top, width, height - bottom))
                    elif action == 'crop_horizontal':
                        left = int(request.form.get('left'))
                        right = int(request.form.get('right'))
                        width, height = img.size
                        img = img.crop((left, 0, width - right, height))
                    elif action == 'rotate':
                        angle = float(request.form.get('angle', 0))
                        img = img.rotate(angle, expand=True)
                    elif action == 'flip_vertical':
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)
                    elif action == 'flip_horizontal':
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    img.save(filepath)
            except Exception as e:
                print(f"Error during image processing: {e}")
                flash('Błąd podczas przetwarzania obrazu.')
                return redirect(url_for('edit_image', filename=filename))

        return redirect(url_for('edit_image', filename=filename))
    return render_template('edit.html', filename=filename)

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/load_draft/<draft_id>')
@login_required
def load_draft(draft_id):
    draft = Draft.query.get(draft_id)
    if draft and draft.user_id == current_user.id:
        return redirect(url_for('edit_image', filename=draft.filename))
    else:
        flash('Nie masz dostępu do tej wersji roboczej.', 'danger')
        return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
