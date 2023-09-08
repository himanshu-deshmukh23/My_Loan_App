from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loan.db'
app.secret_key = 'abc123'
db = SQLAlchemy(app)

admin_id = 'admin1'
admin_key = 'myapp'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    loans = db.relationship('UserLoan', backref='user', lazy=True)


class UserLoan(db.Model):
    __tablename__ = 'user_loan'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    term = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    loans = db.relationship('Repayments', backref='user_loan')


class Repayments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('user_loan.id'), nullable=False)
    installment = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='PENDING')


@app.route('/')
def index():
    return render_template('base.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin1' and password == 'myapp':
            return redirect(url_for('admin_profile'))

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            return redirect(url_for('user_profile'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        new_username = request.form['new_username']
        new_password = request.form['new_password']

        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('login'))
        else:
            new_user = User(username=new_username, password=new_password)
            db.session.add(new_user)
            db.session.commit()

            flash('Registration successful. You can now log in.', 'success')
            return redirect(url_for('login'))


@app.route('/loan_application', methods=['GET', 'POST'])
def apply_loan():
    if 'user_id' in session:
        user_id = session['user_id']
        amount = request.form.get('amount')
        term = request.form.get('term')

        loan = UserLoan(user_id=user_id, amount=amount, term=term, status='Pending')

        db.session.add(loan)
        db.session.commit()

        flash('Loan application submitted. Waiting for admin approval.', 'success')
        return redirect(url_for('user_profile'))

    return redirect(url_for('login'))


@app.route('/user_profile')
def user_profile():
    user_id = session['user_id']
    user = User.query.get(user_id)
    loans = UserLoan.query.filter_by(user_id=session['user_id']).all()
    repayments = []
    print('a')

    approved_loan = UserLoan.query.filter_by(user_id=user_id, status='Approved').first()

    if approved_loan:
        repayments = Repayments.query.filter_by(loan_id=approved_loan.id).all()

    return render_template('user_profile.html', user=user, loans=loans, repayments=repayments)


@app.route('/admin_profile', methods=['GET', 'POST'])
def admin_profile():
    if request.method == 'POST':
        loan_id = request.form.get('loan_id')
        new_status = request.form.get('new_status')

        loan = UserLoan.query.get(loan_id)
        if loan:
            loan.status = new_status
            db.session.commit()

    loans = UserLoan.query.all()

    return render_template('admin_profile.html', loans=loans)


@app.route('/update_loan_status/<int:loan_id>', methods=['POST'])
def update_loan_status(loan_id):
    if request.method == 'POST':
        new_status = request.form.get('new_status')

        loan = UserLoan.query.get(loan_id)

        if loan:
            loan.status = new_status
            db.session.commit()

        current_date = datetime.utcnow()
        installment = round((loan.amount / loan.term), 2)
        total_dues = 0

        for _ in range(loan.term - 1):
            repayment = Repayments(loan_id=loan_id, installment=installment, date=current_date)
            db.session.add(repayment)
            current_date += timedelta(weeks=1)
            total_dues += installment

        final_due = round((loan.amount - total_dues), 2)
        repayment = Repayments(loan_id=loan_id, installment=final_due, date=current_date)
        db.session.add(repayment)
        db.session.commit()

    flash('Loan approved successfully!')
    return redirect(url_for('admin_profile'))


@app.route('/pay_repayment/<int:repayment_id>', methods=['POST'])
def pay_repayment(repayment_id):
    repayment = Repayments.query.get(repayment_id)

    if repayment is None:
        flash('Repayment not found', 'danger')
        return redirect(url_for('user_profile'))

    if repayment.status == 'PENDING':
        repayment.status = 'PAID'
        db.session.commit()
        flash('Repayment marked as PAID', 'success')

        loan_id = repayment.loan_id
        repayments = Repayments.query.filter_by(loan_id=loan_id).all()
        loan = UserLoan.query.get(loan_id)
        if all(repayment.status == 'PAID' for repayment in repayments):
            loan.status = 'All Dues Paid!'
            db.session.commit()
            flash('Loan status updated to All Dues Paid!', 'success')
    else:
        flash('Repayment has already been paid', 'warning')

    return redirect(url_for('user_profile'))


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
