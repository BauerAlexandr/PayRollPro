from flask import Flask, session
from sqlalchemy import func, and_, ForeignKey
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import DecimalField, StringField, DateField, SubmitField, FloatField, HiddenField, PasswordField, SelectField, ValidationError, FormField, TextAreaField, validators
from wtforms.validators import Optional, DataRequired
from datetime import datetime, timedelta, date
from flask_wtf.file import FileField, FileAllowed
from flask_wtf import FlaskForm, CSRFProtect
from flask_sqlalchemy import SQLAlchemy



db = SQLAlchemy()

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
    name = db.Column(db.String(80), nullable=False)
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
    role = db.Column(db.String(20))
    user = db.relationship('User', back_populates='join_requests', foreign_keys=[user_id], overlaps='companies')
    company = db.relationship('Company', back_populates='join_requests')
    is_read = db.Column(db.Boolean, default=False)

    def __init__(self, user, company_id):
        self.user = user
        self.company_id = company_id
        self.status = 'pending'

class Position(db.Model):
    __tablename__ = 'positions' 
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    employees = db.relationship('User', back_populates='position')


class RegistrationForm(FlaskForm):
    role = SelectField('Роль', choices=[('employee', 'Employee'), ('manager', 'Manager')], validators=[DataRequired()])
    
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Регистрация')
    

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Вход')


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


class SalaryForm(FlaskForm):
    salary_id = HiddenField('Salary ID')
    base_salary = FloatField('Оклад', validators=[Optional()])
    bonuses = FloatField('Бонусы', validators=[Optional()])
    deductions = FloatField('Вычеты', validators=[Optional()])
    effective_date = DateField('Дата', format='%Y-%m-%d', validators=[DataRequired()])
    start_date = DateField('Начальная дата', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('Конечная дата', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Save')

 
class SalaryAssignmentForm(FlaskForm):
    user_id = SelectField('Имя пользователя', choices=[], coerce=int) 
    base_salary = FloatField('Оклад', validators=[Optional()])
    bonuses = FloatField('Бонусы', validators=[Optional()])
    deductions = FloatField('Вычеты', validators=[Optional()])
    effective_date = DateField('Дата', format='%Y-%m-%d', validators=[DataRequired()])
    start_date = DateField('Начальная дата', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('Конечная дата', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Назначать заработную плату')


class CompanyForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание')
    company_type = StringField('Тип компании', validators=[Optional()])
    contact_info = StringField('Контактная информация', validators=[Optional()])
    foundation_date = DateField('Дата основания', format='%Y-%m-%d', validators=[Optional()])
    
    submit = SubmitField('Сохранить')


class DepartmentForm(FlaskForm):
    department_name = StringField('Имя отдела', validators=[DataRequired()])
    department_description = TextAreaField('Описание')
    submit = SubmitField('Добавить отдел')


class JoinRequestForm(FlaskForm):
    company_id = SelectField('Компания', coerce=int)

    def __init__(self, *args, **kwargs):
        super(JoinRequestForm, self).__init__(*args, **kwargs)
        self.company_id.choices = [(company.id, company.name) for company in Company.query.all()]


class AddPositionForm(FlaskForm):
    position_name = StringField('Должность', validators=[DataRequired()])
    submit = SubmitField('Добавить должность')

    def validate_position_id(self, field):
        if field.data == 0: 
            raise ValidationError('Please select a position.')



    

class UserProfileForm(FlaskForm):
    csrf_token = HiddenField('CSRF Token')
    role = StringField('Роль', render_kw={'readonly': True}) 
    first_name = StringField('Фамилия', validators=[Optional()])
    last_name = StringField('Имя', validators=[Optional()])
    middle_name = StringField('Отчество', validators=[Optional()])
    birth_date = DateField('Дата рождения', format='%Y-%m-%d', validators=[Optional()])
    job_place = StringField('Место работы', validators=[Optional()])
    position = StringField('Должность', validators=[Optional()])
    photo = FileField('Фото профиля', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    base_salary = FloatField('Оклад', validators=[Optional()])
    bonuses = FloatField('Бонусы', validators=[Optional()])
    deductions = FloatField('Вычеты', validators=[Optional()])
    effective_date = DateField('Дата', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Сохранить')