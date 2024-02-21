import os
import uuid
from sqlalchemy import func, and_, ForeignKey
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import DecimalField, StringField, DateField, SubmitField, FloatField, HiddenField, PasswordField, SelectField, ValidationError, FormField, TextAreaField, validators
from wtforms.validators import Optional, DataRequired
from flask_wtf.file import FileField, FileAllowed
from datetime import datetime, timedelta, date
from sqlalchemy.sql import text
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, aliased


app = Flask(__name__)
csrf = CSRFProtect(app)
app.secret_key = 'secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

UPLOAD_FOLDER = 'static\\uploads'  # Папка для сохранения фотографий
ALLOWED_EXTENSIONS = {'jpg', 'png', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def generate_unique_filename(filename):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_part = uuid.uuid4().hex[:6]  # Генерация случайной части имени файла
    _, extension = os.path.splitext(filename)  # Получение расширения файла
    return f"{timestamp}_{random_part}{extension}"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False, default='employee')
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    middle_name = db.Column(db.String(50))
    birth_date = db.Column(db.Date)
    job_place = db.Column(db.String(100))
    position = db.Column(db.String(100))
    photo_path = db.Column(db.String(255))
    salaries = db.relationship('Salary', back_populates='user')
    company = db.relationship('Company', back_populates='manager', uselist=False,
                              primaryjoin="and_(User.company_id == Company.id, User.role == 'manager')", overlaps="manager")
    employee_company = db.relationship('Company', back_populates='employees', uselist=False,
                                       primaryjoin="and_(User.company_id == Company.id, User.role == 'employee')",
                                       overlaps="company")
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'))
    join_requests = db.relationship('JoinRequest', back_populates='user', overlaps='user_join_requests')
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    department = db.relationship('Department', back_populates='employees', foreign_keys=[department_id])
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'))
    position = db.relationship('Position', back_populates='employees', lazy='joined')
    

    
    
    
    def add_company(self, company):
        self.company = company
        db.session.commit()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    description = db.Column(db.String(255))
    company_type = db.Column(db.String(50))
    contact_info = db.Column(db.String(100))
    foundation_date = db.Column(db.Date)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    manager = db.relationship('User', back_populates='company', foreign_keys=[manager_id],
                              primaryjoin="Company.id == foreign(User.company_id) and User.role == 'manager'", overlaps="employee_company")
    employees = db.relationship('User', back_populates='employee_company', lazy='dynamic', passive_deletes=True,
                                primaryjoin="Company.id == foreign(User.company_id) and User.role == 'employee'", overlaps="company,manager")
    departments = db.relationship('Department', back_populates='company', lazy='dynamic')
    join_requests = db.relationship('JoinRequest', back_populates='company', overlaps='company_join_requests')
    

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    company = db.relationship('Company', back_populates='departments')
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager = db.relationship('User', backref='managers', uselist=False, foreign_keys=[manager_id])
    employees = db.relationship('User', back_populates='department', foreign_keys=[User.department_id])


class JoinRequest(db.Model):
    __tablename__ = 'join_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'))
    status = db.Column(db.String(20), default='pending')
    role = db.Column(db.String(20))  # Добавьте это поле
    user = db.relationship('User', back_populates='join_requests', foreign_keys=[user_id], overlaps='companies')
    company = db.relationship('Company', back_populates='join_requests')
    is_read = db.Column(db.Boolean, default=False)

    def __init__(self, user, company_id):
        self.user = user
        self.company_id = company_id
        self.status = 'pending'

class Position(db.Model):
    __tablename__ = 'positions'  # Изменим название таблицы, чтобы избежать конфликтов
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    employees = db.relationship('User', back_populates='position')


class RegistrationForm(FlaskForm):
    role = SelectField('Role', choices=[('employee', 'Employee'), ('manager', 'Manager')], validators=[DataRequired()])
    
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')
    

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class Salary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_amount = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', back_populates='salaries')
    base_salary = db.Column(db.Float)
    bonuses = db.Column(db.Float)
    deductions = db.Column(db.Float)
    effective_date = db.Column(db.Date)
    added_by_manager = db.Column(db.Boolean, default=True)

    @property
    def total_amount(self):
        base_salary = self.base_salary if self.base_salary is not None else 0
        bonuses = self.bonuses if self.bonuses is not None else 0
        deductions = self.deductions if self.deductions is not None else 0
        return base_salary + bonuses - deductions

    def __repr__(self):
        return f"Salary('{self.base_salary}', '{self.bonuses}', '{self.deductions}', '{self.effective_date}')"

def create_db():
    with app.app_context():
        db.create_all()

        # Проверим, есть ли уже записи о зарплате, и если нет, создадим их
        users = User.query.all()
        for user in users:
            if not user.salaries:
                salary = Salary(user_id=user.id)
                db.session.add(salary)

        db.session.commit()

create_db()


def get_unique_years_months():
    query = db.session.query(
        db.func.strftime("%Y", Salary.effective_date).label("year"),
        db.func.strftime("%m", Salary.effective_date).label("month")
    ).filter(
        Salary.user_id == User.id,
        User.username == session.get('username', '')
    ).group_by(
        "year",
        "month"
    ).order_by(
        db.text("year desc, month desc")
    ).all()

    return query

class SalaryForm(FlaskForm):
    salary_id = HiddenField('Salary ID')
    base_salary = FloatField('Base Salary', validators=[Optional()])
    bonuses = FloatField('Bonuses', validators=[Optional()])
    deductions = FloatField('Deductions', validators=[Optional()])
    effective_date = DateField('Effective Date', format='%Y-%m-%d', validators=[DataRequired()])
    start_date = DateField('Start Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('End Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Save')

 
class SalaryAssignmentForm(FlaskForm):
    user_id = SelectField('Employee ID', choices=[], coerce=int)  # Пустой список выборов, который будет заполнен динамически
    base_salary = FloatField('Base Salary', validators=[Optional()])
    bonuses = FloatField('Bonuses', validators=[Optional()])
    deductions = FloatField('Deductions', validators=[Optional()])
    effective_date = DateField('Effective Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[DataRequired()])
    start_date = DateField('Start Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('End Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Assign Salary')

def get_distinct_years(user_id):
    distinct_years = (
        db.session.query(func.extract('year', Salary.effective_date))
        .filter_by(user_id=user_id, added_by_manager=False)  # Учитываем только зарплаты, добавленные сотрудником
        .distinct()
        .all()
    )

    return sorted([year[0] for year in distinct_years if year[0] is not None], reverse=True)

def get_total_amount(user_id, selected_year=None, start_date=None, end_date=None):
    salaries_query = Salary.query.filter_by(user_id=user_id, added_by_manager=False)

    if selected_year is not None:
        salaries_query = salaries_query.filter(func.extract('year', Salary.effective_date) == selected_year)

    if start_date and end_date:
        salaries_query = salaries_query.filter(Salary.effective_date.between(start_date, end_date))

    salaries_query = salaries_query.order_by(Salary.effective_date.desc())
    salaries = salaries_query.all()
    
    return sum(s.total_amount for s in salaries)

def get_total_months(user_id, selected_year=None):
    salaries_query = Salary.query.filter_by(user_id=user_id, added_by_manager=False)

    if selected_year is not None:
        salaries_query = salaries_query.filter(func.extract('year', Salary.effective_date) == selected_year)

    salaries_query = salaries_query.order_by(Salary.effective_date.desc())
    salaries = salaries_query.all()
    
    distinct_years_months = set((salary.effective_date.year, salary.effective_date.month) for salary in salaries if salary.effective_date is not None)
    return len(distinct_years_months)

def get_total_months_period(user_id, start_date, end_date):
    user = User.query.get(user_id)

    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        return 0  # или другое значение по умолчанию

    # Рассчитываем общее количество месяцев для всех данных пользователя
    all_user_salaries = Salary.query.filter_by(user_id=user_id).all()

    # Фильтруем данные по указанному периоду
    filtered_salaries = [salary for salary in all_user_salaries if getattr(salary, 'effective_date') and start_date <= getattr(salary, 'effective_date') <= end_date]

    # Рассчитываем общее количество месяцев для выбранного периода
    total_months = len(set((salary.effective_date.year, salary.effective_date.month) for salary in filtered_salaries))

    return total_months

def calculate_average_monthly_salary(salary_info, start_date, end_date):
    total_salary = 0
    total_months = 0

   

    for salaries in salary_info.values():
        for s in salaries:
            # Проверяем, что дата зарплаты не None и попадает в заданный период
           
            if s.effective_date and start_date and end_date and start_date <= s.effective_date <= end_date:
                total_salary += (s.base_salary if s.base_salary is not None else 0) + (s.bonuses if s.bonuses is not None else 0) - (s.deductions if s.deductions is not None else 0)
                total_months += 1
  

    if total_months > 0:
        average_monthly_salary = total_salary / total_months
        return average_monthly_salary
    else:
        return 0

    return total_salary / total_months



class CompanyForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    company_type = StringField('Company Type', validators=[Optional()])
    contact_info = StringField('Contact Info', validators=[Optional()])
    foundation_date = DateField('Foundation Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    
    submit = SubmitField('Save Company Information')


class DepartmentForm(FlaskForm):
    department_name = StringField('Department Name', validators=[DataRequired()])
    department_description = TextAreaField('Department Description')
    submit = SubmitField('Create Department')


class JoinRequestForm(FlaskForm):
    company_id = SelectField('Company', coerce=int)

    def __init__(self, *args, **kwargs):
        super(JoinRequestForm, self).__init__(*args, **kwargs)
        self.company_id.choices = [(company.id, company.name) for company in Company.query.all()]


class AddPositionForm(FlaskForm):
    position_name = StringField('Position Name', validators=[DataRequired()])
    submit = SubmitField('Add Position')

    def validate_position_id(self, field):
        if field.data == 0:  # или любое другое значение, которое вы используете для "Select Position"
            raise ValidationError('Please select a position.')



    

class UserProfileForm(FlaskForm):
    csrf_token = HiddenField('CSRF Token')
    role = StringField('Role', render_kw={'readonly': True})  # Добавляем поле для отображения роли
    first_name = StringField('First Name', validators=[Optional()])
    last_name = StringField('Last Name', validators=[Optional()])
    middle_name = StringField('Middle Name', validators=[Optional()])
    birth_date = DateField('Birth Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    job_place = StringField('Job Place', validators=[Optional()])
    position = StringField('Position', validators=[Optional()])
    photo = FileField('Profile Photo', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    base_salary = FloatField('Base Salary', validators=[Optional()])
    bonuses = FloatField('Bonuses', validators=[Optional()])
    deductions = FloatField('Deductions', validators=[Optional()])
    effective_date = DateField('Effective Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Save')

@app.route('/')
def index():
    username = session.get('username', '')
    user_role = 'employee'  # Default role if not logged in
    company = None
    user = None
    form = CompanyForm()  # Инициализируем form по умолчанию

    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            user_role = user.role
            company = user.company

            if request.method == 'POST':
                # Обработка формы для ввода информации о компании
                if not company:
                    if form.validate_on_submit():
                        # Создаем компанию и связываем с пользователем
                        company = Company(name=form.name.data)
                        db.session.add(company)
                        user.company = company
                        db.session.commit()
                       

                        # Перенаправляем на ту же страницу для ввода дополнительной информации
                        return redirect(url_for('index'))
    if 'loaded' in session:
        # Если страница уже загружена, устанавливаем loaded в False
        session['loaded'] = False
    else:
        # Если страница не была загружена, устанавливаем loaded в True
        session['loaded'] = True

    return render_template('index.html', username=username, user_role=user_role, company=company, form=form, user=user)

@app.route('/register_login', methods=['GET', 'POST'])
def register_login():
    login_form = LoginForm()
    registration_form = RegistrationForm()
    
    show_login_button = True
    show_register_button = True

    if registration_form.validate_on_submit():
        username = registration_form.username.data
        password = registration_form.password.data
        role = registration_form.role.data
       
        existing_user = User.query.filter_by(username=username).first()

        show_login_button = False

        if existing_user:
            flash('Ошибка регистрации. Пользователь уже существует.', 'warning')
        else:
            new_user = User(username=username, role=role)
            
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()
            session['company_id'] = new_user.company_id
            session['username'] = username
            return redirect(url_for('index'))

    elif login_form.validate_on_submit():
        username = login_form.username.data
        password = login_form.password.data

        user = User.query.filter_by(username=username).first()



        if user and user.check_password(password):
            flash('Вход в систему успешен!', 'success')
            session['company_id'] = user.company_id
            session['username'] = username
            show_register_button = False
            return redirect(url_for('index'))
        else:
            flash('Ошибка входа. Проверьте свое имя пользователя и пароль.', 'warning')

    return render_template('register_login.html', login_form=login_form, registration_form=registration_form,
                           show_login_button=show_login_button, show_register_button=show_register_button)



@app.route('/profile', methods=['GET', 'POST'])
def profile():
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            form = UserProfileForm(obj=user)

            if form.validate_on_submit():
                user.first_name = form.first_name.data
                user.last_name = form.last_name.data
                user.middle_name = form.middle_name.data
                user.birth_date = form.birth_date.data if form.birth_date.data else None
                user.job_place = form.job_place.data
                user.position = form.position.data
                user.photo = form.photo.data

                if form.photo.data:
                    photo_file = form.photo.data
                    if '.' in photo_file.filename and photo_file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                        filename = generate_unique_filename(photo_file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        photo_file.save(filepath)
                        user.photo_path = f'uploads/{filename}'
                    else:
                      
                        return redirect(url_for('profile'))

                db.session.commit()
               
                return redirect(url_for('profile'))

            return render_template('profile.html', user=user, form=form, role=user.role)

   
    return redirect(url_for('register_login'))


@app.route('/salary', methods=['GET', 'POST'])
def salary():
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            form = SalaryForm()
            years = get_distinct_years(user.id)
            selected_year = request.args.get('year', type=int)
            start_date = request.args.get('start_date', type=str)
            end_date = request.args.get('end_date', type=str)

            total_months_period = get_total_months_period(user.id, start_date, end_date)
            
            total_months = get_total_months(user.id, selected_year)
            years_months = get_unique_years_months()

            if start_date and end_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()


            if form.validate_on_submit():
                salary = Salary(
                    user_id=user.id,
                    base_salary=form.base_salary.data,
                    bonuses=form.bonuses.data,
                    deductions=form.deductions.data,
                    effective_date=form.effective_date.data,
                    added_by_manager=False  # Установите значение добавления зарплаты сотрудником
                )
                db.session.add(salary)
                db.session.commit()
              
                return redirect(url_for('salary', year=selected_year))

            if selected_year:
                
                salaries = Salary.query.filter_by(user_id=user.id, added_by_manager=False).filter(Salary.effective_date.isnot(None)).filter(func.extract('year', Salary.effective_date) == selected_year).order_by(Salary.effective_date.desc()).all()
                total_amount = get_total_amount(user.id, selected_year, start_date, end_date)
                total_months = get_total_months(user.id, selected_year)
                
            elif start_date and end_date:
                salaries = Salary.query.filter_by(user_id=user.id, added_by_manager=False).filter(Salary.effective_date.between(start_date, end_date)).order_by(Salary.effective_date.desc()).all()
                total_amount = get_total_amount(user.id, selected_year, start_date, end_date)
                total_months = get_total_months(user.id, selected_year)
                
            else:
               
                salaries = Salary.query.filter_by(user_id=user.id, added_by_manager=False).order_by(Salary.effective_date.desc()).all()
                total_amount = get_total_amount(user.id, selected_year, start_date, end_date)
                total_months = get_total_months(user.id, selected_year)
           

            user_salaries = {}
            for salary in salaries:
                if salary.effective_date:
                    year_month = (salary.effective_date.year, salary.effective_date.month)
                    if year_month not in user_salaries:
                        user_salaries[year_month] = []
                    user_salaries[year_month].append(salary)

            return render_template('salary.html', user=user, form=form, user_salaries=user_salaries, years_months=years_months, total_amount=total_amount, selected_year=selected_year, years=years, start_date=start_date, end_date=end_date, total_months=total_months, total_months_period=total_months_period)

  
    return redirect(url_for('register_login'))

# Новый маршрут для редактирования зарплаты
@app.route('/edit_salary/<int:salary_id>', methods=['GET', 'POST'])
def edit_salary(salary_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            salary = Salary.query.get(salary_id)
            if salary and salary.user_id == user.id:  # Проверьте, является ли вошедший в систему пользователь владельцем
                form = SalaryForm(obj=salary)

                if form.validate_on_submit():
                    form.populate_obj(salary)
                    db.session.commit()
                  
                    return redirect(url_for('salary'))

                return render_template('edit_salary.html', user=user, form=form, salary=salary)
            else:
              
                return redirect(url_for('salary'))

  
    return redirect(url_for('register_login'))


@app.route('/delete_salary/<int:salary_id>', methods=['POST'])
def delete_salary(salary_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            salary = Salary.query.get(salary_id)
            if salary and salary.user_id == user.id:  # Проверьте, является ли вошедший в систему пользователь владельцем
                db.session.delete(salary)
                db.session.commit()
               
            else:
               pass

    return redirect(url_for('salary'))



@app.route('/company', methods=['GET', 'POST'])
def company():
   
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            company = user.company
            company_form = CompanyForm()
            department_form = DepartmentForm()
            form = AddPositionForm()

            # Добавленный код для просмотра и управления запросами
            join_requests = []
            companies = []
            employees = []

            if user.role == 'manager':
              
                join_requests = JoinRequest.query\
                    .join(User, JoinRequest.user_id == User.id)\
                    .join(Company, JoinRequest.company_id == Company.id)\
                    .filter(Company.id == company.id if company else False)\
                    .all()

                companies = Company.query.all()
                existing_positions = Position.query.all()

                # Обновите choices для position_id
                form.position_name.choices = [(position.id, position.name) for position in existing_positions]

                if form.validate_on_submit():
                    # Получите данные из формы
                    employee_id = request.form.get('employee_id')
                    position_name_ = form.position_name.data

                    # Найдите пользователя и должность в базе данных
                    employee = User.query.get(employee_id)
                    position = Position.query.get(position_name_)

                    # Проверка, чтобы убедиться, что пользователь и должность существуют
                  

                    if employee and position:
                        # Присвойте сотруднику выбранную должность
                        employee.position = position
                        db.session.commit()
                       
                      
                        return redirect(url_for('company'))
                    
                

                # Вставим отладочный вывод здесь
               
               

                if request.method == 'POST':
                    request_id = int(request.form.get('request_id', 0))
                    action = request.form.get('action')

                    process_join_request(request_id, action)


            if request.method == 'POST':
                if ('next_step' in request.form or company_form.validate_on_submit()) and not 'add_department' in request.form:
                    if not company_form.name.data.strip():  # Проверяем, что название не пустое
                        pass
                    else:
                        existing_company = Company.query.filter_by(name=company_form.name.data).first()
                        if existing_company:
                            existing_company.description = company_form.description.data
                            existing_company.company_type = company_form.company_type.data
                            existing_company.contact_info = company_form.contact_info.data
                            existing_company.foundation_date = company_form.foundation_date.data
                            db.session.commit()
                           
                            department_form = DepartmentForm()
                        else:
                            if user.company is None:
                                company = Company(name='')
                                user.add_company(company)
                                db.session.add(company)
                            else:
                                company = user.company
                            company.name = company_form.name.data
                            company.description = company_form.description.data
                            company.company_type = company_form.company_type.data
                            company.contact_info = company_form.contact_info.data
                            company.foundation_date = company_form.foundation_date.data
                            db.session.commit()
                           
                            department_form = DepartmentForm()
                            
                        

                    db.session.commit()
                   
                    department_form = DepartmentForm()


                elif 'add_department' in request.form and department_form.validate_on_submit():
                    department_name = department_form.department_name.data
                    existing_department = Department.query.filter_by(name=department_name).first()
                    if existing_department:
                        pass
                       
                    else:
                        if user.company:
                            department = Department(
                                name=department_name,
                                description=department_form.department_description.data,
                                company=user.company
                            )
                            db.session.add(department)
                            db.session.commit()
                           
                            
                    return redirect(url_for('company'))

            if company is None:
                company_form = CompanyForm()
            else:
                company_form = CompanyForm(obj=company)

            if company is not None:
                employees = User.query.join(Position).filter(
                    User.company_id == company.id,
                    User.role != 'manager'
                ).all()
            else:
                employees = []

            departments = user.company.departments.all() if user.company else []
            JoinRequest.query.filter_by(is_read=False).update({'is_read': True})
            db.session.commit()

            # Подсчет непрочитанных запросов
            unread_requests_count = JoinRequest.query.filter_by(is_read=False).count()
            

            return render_template('company.html', user=user, form=form, company_form=company_form, department_form=department_form, company=company, departments=departments, join_requests=join_requests, companies=companies, employees=employees, unread_requests_count=unread_requests_count)

   
    return redirect(url_for('register_login'))




@app.route('/edit_department/<int:department_id>', methods=['GET', 'POST'])
def edit_department(department_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            department = db.session.get(Department, department_id)
            if department and department.company_id == user.company.id:  
                form = DepartmentForm()

                if request.method == 'POST' and form.validate_on_submit():
                    # Обновление информации о отделе
                    department.name = request.form['department_name']
                    department.description = request.form['department_description']
                    
                    db.session.commit()
                    
                    return redirect(url_for('company'))

                # Заполняем форму значениями из объекта department
                form.department_name.data = department.name
                form.department_description.data = department.description

                return render_template('edit_department.html', user=user, form=form, department=department)
            else:
                
                return redirect(url_for('company'))

    
    return redirect(url_for('register_login'))

@app.route('/delete_department/<int:department_id>', methods=['POST'])
def delete_department(department_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            department = Department.query.get(department_id)
            if department and department.company_id == user.company.id:  
                db.session.delete(department)
                db.session.commit()
                
            else:
                pass
                

    return redirect(url_for('company'))

@app.route('/my_company', methods=['GET', 'POST'])
def my_company():
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            if user.role == 'employee':
                available_companies = Company.query.all()
                join_request_form = JoinRequestForm()

                if request.method == 'POST' and join_request_form.validate_on_submit():
                    selected_company_id = join_request_form.company_id.data
                    selected_company = Company.query.get(selected_company_id)

                    if selected_company:
                        join_request = JoinRequest(user=user, company_id=selected_company_id)
                        
                        db.session.add(join_request)
                        db.session.commit()
                       
                        
                        
                        return redirect(url_for('index'))

                return render_template('my_company.html', user=user, available_companies=available_companies, join_request_form=join_request_form)
    
    return redirect(url_for('index'))



@app.route('/process_join_request/<int:request_id>/<action>', methods=['POST'])
def process_join_request(request_id, action):
    join_request = JoinRequest.query.get(request_id)

    if join_request:
        

        company = join_request.company
        user = join_request.user

        if action == 'accept':
            existing_company = user.company

            if existing_company:
                
                existing_company.name = company.name
                existing_company.description = company.description
                existing_company.company_type = company.company_type
                existing_company.contact_info = company.contact_info
                existing_company.foundation_date = company.foundation_date
            else:
                
                user.add_company(company)

            try:
               
                db.session.delete(join_request)
                db.session.commit()
               
               

                try:
                   
                    company.employees.append(user)
                    db.session.commit()  # Добавлен этот вызов
                   
                
                    position_id = int(request.form.get('position_id', 0))
                    if position_id:
                        position = Position.query.get(position_id)
                        if position:
                            user.position = position
                            db.session.commit()

                except IntegrityError as e:
                    db.session.rollback()
                   
                   

            except Exception as e:
                db.session.rollback()
               
               

        elif action == 'reject':
            try:
               
                db.session.delete(join_request)
                db.session.commit()
              
              
            except Exception as e:
                db.session.rollback()
              
               

    return redirect(url_for('company'))

def get_salary_info():
    salary_info = {}
    employees = User.query.filter_by(role='employee').all()
    for employee in employees:
        # Получить последнюю запись о зарплате для каждого сотрудника
        salary = Salary.query.filter_by(user_id=employee.id).order_by(Salary.effective_date.desc()).first()
        salary_info[employee.id] = salary
    return salary_info

    
@app.route('/assign_salary', methods=['GET', 'POST'])
def assign_salary():
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user and user.role == 'manager':
            form = SalaryAssignmentForm()

            # Получите список сотрудников, которым нужно назначить зарплату
            employees = User.query.filter_by(company_id=user.company_id, role='employee').all()

            # Получите зарплатные данные для каждого сотрудника, добавленные менеджером
            salary_info = {}
            for employee in employees:
                salaries = Salary.query.filter_by(user_id=employee.id, added_by_manager=True).order_by(Salary.effective_date.desc()).all()
                salary_info[employee.id] = salaries

            # Обновите поле выбора user_id в форме
            form.user_id.choices = [(employee.id, employee.username) for employee in employees]

            if form.validate_on_submit():
                user_id = form.user_id.data
                base_salary = form.base_salary.data
                bonuses = form.bonuses.data
                deductions = form.deductions.data
                effective_date = form.effective_date.data

                salary = Salary(user_id=user_id, base_salary=base_salary, bonuses=bonuses, deductions=deductions, effective_date=effective_date, added_by_manager=True)  # Установите флаг added_by_manager в True
                db.session.add(salary)
                db.session.commit()

               
                return redirect(url_for('assign_salary'))

            return render_template('assign_salary.html', user=user, form=form, employees=employees, salary_info=salary_info)

   
    return redirect(url_for('index'))

    
# Новый маршрут для редактирования зарплаты
@app.route('/assign_edit_salary/<int:salary_id>', methods=['GET', 'POST'])
def assign_edit_salary(salary_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            salary = Salary.query.get(salary_id)
            if salary and (salary.user_id == user.id or user.role=='manager'):  # Проверьте, является ли вошедший в систему пользователь владельцем
                form = SalaryForm(obj=salary)

                if form.validate_on_submit():
                    form.populate_obj(salary)
                    db.session.commit()
                  
                    return redirect(url_for('assign_salary'))

                return render_template('edit_salary.html', user=user, form=form, salary=salary)
            else:
              
                return redirect(url_for('assign_salary'))

   
    return redirect(url_for('register_login'))


@app.route('/assign_delete_salary/<int:salary_id>', methods=['POST'])
def assign_delete_salary(salary_id):
    username = session.get('username', '')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            salary = Salary.query.get(salary_id)
            if salary and (salary.user_id == user.id or user.role=='manager'):  # Проверьте, является ли вошедший в систему пользователь владельцем
                db.session.delete(salary)
                db.session.commit()
               
            else:
                pass
              

    return redirect(url_for('assign_salary'))


    
@app.route('/department/<int:department_id>', methods=['GET', 'POST'])
def department_info(department_id):
    department = Department.query.get(department_id)

    if department:
        form = SalaryAssignmentForm()
        employees = department.employees if department.employees else []
        salary_info = {}  # Словарь для хранения информации о зарплате каждого сотрудника
        total_department_salary = 0  # Переменная для хранения общей зарплаты отдела
        total_employee_salary = {}  # Словарь для хранения общей зарплаты каждого сотрудника

        if form.validate_on_submit():
            start_date = form.start_date.data
            end_date = form.end_date.data

            for employee in department.employees:
                salaries = Salary.query.filter_by(user_id=employee.id).filter(Salary.effective_date.between(start_date, end_date)).filter(Salary.added_by_manager == True).all()
                if salaries:
                    salary_info[employee.id] = salaries
                    total_salary = sum((s.base_salary if s.base_salary is not None else 0) + (s.bonuses if s.bonuses is not None else 0) - (s.deductions if s.deductions is not None else 0) for s in salaries)
                    total_department_salary += total_salary
                    total_employee_salary[employee.id] = total_salary

        else:
            

            for employee in department.employees:
                latest_salaries = Salary.query.filter_by(user_id=employee.id).order_by(Salary.effective_date.desc()).filter(Salary.added_by_manager == True).all()
                if latest_salaries:
                    filtered_salaries = []
                    for s in latest_salaries:
                        if s.effective_date is not None:
                           
                            if form.start_date.data is None or form.end_date.data is None:
                                filtered_salaries.append(s)
                            elif s.effective_date >= form.start_date.data and s.effective_date <= form.end_date.data:
                                filtered_salaries.append(s)
                        else:
                            filtered_salaries.append(s)

                    if filtered_salaries:
                        salary_info[employee.id] = filtered_salaries
                        total_salary = sum((s.base_salary if s.base_salary is not None else 0) + (s.bonuses if s.bonuses is not None else 0) - (s.deductions if s.deductions is not None else 0) for s in filtered_salaries)
                        total_department_salary += total_salary
                        total_employee_salary[employee.id] = total_salary

        user_id = session.get('user_id')
        average_monthly_salary = calculate_average_monthly_salary(salary_info, form.start_date.data, form.end_date.data)
        total_salary_all_employees = sum((s.base_salary if s.base_salary is not None else 0) + (s.bonuses if s.bonuses is not None else 0) - (s.deductions if s.deductions is not None else 0) for salaries in salary_info.values() for s in salaries)
        
        return render_template('department_info.html', department=department, form=form, user_id=user_id, salary_info=salary_info, total_department_salary=total_department_salary, total_salary_all_employees=total_salary_all_employees, total_employee_salary=total_employee_salary, average_monthly_salary=average_monthly_salary)

   
    return redirect(url_for('index'))
@app.route('/distribute_employee/<int:user_id>', methods=['POST'])
def distribute_employee(user_id):
    user = User.query.get(user_id)

    if user:
        department_id = int(request.form.get('department_id', 0))
        if department_id:
            department = Department.query.get(department_id)
            if department:
               
                department.employees.append(user)
              
                db.session.commit()
               
                return redirect(url_for('company'))

  
    return redirect(url_for('company'))

@app.route('/add_position', methods=['GET', 'POST'])
def add_position():
    form = AddPositionForm()

    # Получите список уже существующих должностей
    existing_positions = Position.query.all()

    # Обновите choices для position_id
    form.position_name.choices = [(position.id, position.name) for position in existing_positions]

    if form.validate_on_submit():
     
        # Проверка на уникальность должности по названию
        existing_position_names = set(position.name.lower() for position in existing_positions)
        new_position_name = form.position_name.data.lower()

        if new_position_name not in existing_position_names:
            # Создайте новую должность и добавьте ее в базу данных
            new_position = Position(name=form.position_name.data)
            db.session.add(new_position)

            try:
                db.session.commit()
              
            except IntegrityError:
                # Если IntegrityError произошел, это значит, что попытка добавить
                # должность с уже существующим именем. Откатите транзакцию.
                db.session.rollback()
               

            return redirect(url_for('add_position'))

        else:
            pass

          
    else:
        pass
       

    return render_template('add_position.html', form=form)




@app.route('/logout')
def logout():
    session.pop('username', None)
  
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
