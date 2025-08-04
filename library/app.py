from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',      
        password='Prasad@123',  
        database='library'
    )

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS count FROM books")
    total_books = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM members")
    total_members = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM bookloans WHERE status = 'On Loan'")
    total_loans = cursor.fetchone()['count']

    cursor.execute("""
        SELECT b.title, CONCAT(m.first_name, ' ', m.last_name) AS member, bl.due_date
        FROM bookloans bl
        JOIN books b ON bl.book_id = b.book_id
        JOIN members m ON bl.member_id = m.member_id
        WHERE bl.status = 'Overdue'
        ORDER BY bl.due_date
        LIMIT 5
    """)
    overdues = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
                           total_books=total_books,
                           total_members=total_members,
                           total_loans=total_loans,
                           overdues=overdues)

@app.route('/books')
def view_books():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get('search', '')
    if search:
        query = """
        SELECT 
            b.book_id, b.title, b.isbn, b.publication_year, b.available_copies, b.total_copies,
            GROUP_CONCAT(CONCAT(a.first_name, ' ', a.last_name)) AS authors,
            p.name AS publisher
        FROM books b
        LEFT JOIN bookauthors ba ON b.book_id = ba.book_id
        LEFT JOIN authors a ON ba.author_id = a.author_id
        JOIN publishers p ON b.publisher_id = p.publisher_id
        WHERE b.title LIKE %s OR b.isbn LIKE %s OR a.first_name LIKE %s OR a.last_name LIKE %s
        GROUP BY b.book_id
        """
        search_term = f"%{search}%"
        cursor.execute(query, (search_term, search_term, search_term, search_term))
    else:
        query = """
        SELECT 
            b.book_id, b.title, b.isbn, b.publication_year, b.available_copies, b.total_copies,
            GROUP_CONCAT(CONCAT(a.first_name, ' ', a.last_name)) AS authors,
            p.name AS publisher
        FROM books b
        LEFT JOIN bookauthors ba ON b.book_id = ba.book_id
        LEFT JOIN authors a ON ba.author_id = a.author_id
        JOIN publishers p ON b.publisher_id = p.publisher_id
        GROUP BY b.book_id
        ORDER BY b.title
        """
        cursor.execute(query)

    books = cursor.fetchall()  
    cursor.close()
    conn.close()

    return render_template('books.html', books=books, search=search)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        isbn = request.form['isbn']
        pub_year = request.form['publication_year']
        edition = request.form['edition'] or None
        pub_id = request.form['publisher_id']
        category = request.form['category'] or None
        location = request.form['shelf_location'] or None
        copies = request.form['total_copies']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO books (title, isbn, publication_year, edition, publisher_id, 
                                   category, shelf_location, available_copies, total_copies)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (title, isbn, pub_year, edition, pub_id, category, location, copies, copies))
            conn.commit()
            book_id = cursor.lastrowid
            flash(f"Book '{title}' added successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            conn.rollback()
            return redirect(url_for('add_book'))

        author_ids = request.form.getlist('author_ids')
        for aid in author_ids:
            try:
                cursor.execute("INSERT INTO bookauthors (book_id, author_id) VALUES (%s, %s)", (book_id, aid))
            except:
                pass  
        conn.commit()
        conn.close()

        return redirect(url_for('view_books'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT author_id, CONCAT(first_name, ' ', last_name) AS name FROM authors ORDER BY name")
    authors = cursor.fetchall()
    cursor.execute("SELECT publisher_id, name FROM publishers ORDER BY name")
    publishers = cursor.fetchall()
    conn.close()

    return render_template('add_book.html', authors=authors, publishers=publishers)

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form['title']
        isbn = request.form['isbn']
        pub_year = request.form['publication_year']
        edition = request.form['edition'] or None
        pub_id = request.form['publisher_id']
        category = request.form['category'] or None
        location = request.form['shelf_location'] or None
        total_copies = int(request.form['total_copies'])
        available_copies = int(request.form['available_copies'])

        try:
            cursor.execute("""
                UPDATE books SET title=%s, isbn=%s, publication_year=%s, edition=%s,
                publisher_id=%s, category=%s, shelf_location=%s, total_copies=%s, available_copies=%s
                WHERE book_id=%s
            """, (title, isbn, pub_year, edition, pub_id, category, location, total_copies, available_copies, book_id))
            conn.commit()
            flash("Book updated successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            conn.rollback()

        cursor.execute("DELETE FROM bookauthors WHERE book_id = %s", (book_id,))
        author_ids = request.form.getlist('author_ids')
        for aid in author_ids:
            cursor.execute("INSERT INTO bookauthors (book_id, author_id) VALUES (%s, %s)", (book_id, aid))
        conn.commit()

        conn.close()
        return redirect(url_for('view_books'))

    cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
    book = cursor.fetchone()

    cursor.execute("SELECT author_id, CONCAT(first_name, ' ', last_name) AS name FROM authors ORDER BY name")
    authors = cursor.fetchall()

    cursor.execute("SELECT publisher_id, name FROM publishers ORDER BY name")
    publishers = cursor.fetchall()

    cursor.execute("SELECT author_id FROM bookauthors WHERE book_id = %s", (book_id,))
    book_authors = [row['author_id'] for row in cursor.fetchall()]

    conn.close()
    return render_template('edit_book.html', book=book, authors=authors, publishers=publishers, book_authors=book_authors)

@app.route('/delete_book/<int:book_id>')
def delete_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
        conn.commit()
        flash("Book deleted successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Cannot delete: {err}", "danger")
    conn.close()
    return redirect(url_for('view_books'))

@app.route('/authors')
def view_authors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT *, CONCAT(first_name, ' ', last_name) AS full_name FROM authors ORDER BY last_name")
    authors = cursor.fetchall()
    conn.close()
    return render_template('authors.html', authors=authors)

@app.route('/add_author', methods=['GET', 'POST'])
def add_author():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        birth_date = request.form['birth_date'] or None
        nationality = request.form['nationality']
        biography = request.form['biography']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO authors (first_name, last_name, birth_date, nationality, biography)
                VALUES (%s, %s, %s, %s, %s)
            """, (first_name, last_name, birth_date, nationality, biography))
            conn.commit()
            flash(f"Author {first_name} {last_name} added!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            conn.rollback()
        conn.close()
        return redirect(url_for('view_authors'))
    return render_template('add_author.html')

@app.route('/edit_author/<int:author_id>', methods=['GET', 'POST'])
def edit_author(author_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        birth_date = request.form['birth_date'] or None
        nationality = request.form['nationality']
        biography = request.form['biography']

        cursor.execute("""
            UPDATE authors SET first_name=%s, last_name=%s, birth_date=%s,
            nationality=%s, biography=%s WHERE author_id=%s
        """, (first_name, last_name, birth_date, nationality, biography, author_id))
        conn.commit()
        flash("Author updated!", "success")
        conn.close()
        return redirect(url_for('view_authors'))

    cursor.execute("SELECT * FROM authors WHERE author_id = %s", (author_id,))
    author = cursor.fetchone()
    conn.close()
    return render_template('edit_author.html', author=author)

@app.route('/delete_author/<int:author_id>')
def delete_author(author_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM authors WHERE author_id = %s", (author_id,))
        conn.commit()
        flash("Author deleted.", "success")
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
    conn.close()
    return redirect(url_for('view_authors'))

@app.route('/members')
def view_members():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT *, CONCAT(first_name, ' ', last_name) AS full_name, 
               DATEDIFF(membership_expiry, CURDATE()) AS days_left
        FROM members ORDER BY last_name
    """)
    members = cursor.fetchall()
    conn.close()
    return render_template('members.html', members=members)

@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        membership_date = request.form['membership_date']
        membership_expiry = request.form['membership_expiry']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO members (first_name, last_name, email, phone, address,
                membership_date, membership_expiry)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, phone, address, membership_date, membership_expiry))
            conn.commit()
            flash(f"Member {first_name} added!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            conn.rollback()
        conn.close()
        return redirect(url_for('view_members'))
    return render_template('add_member.html')

@app.route('/loans')
def view_loans():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT bl.loan_id, b.title, CONCAT(m.first_name, ' ', m.last_name) AS member,
               bl.loan_date, bl.due_date, bl.return_date, bl.status
        FROM bookloans bl
        JOIN books b ON bl.book_id = b.book_id
        JOIN members m ON bl.member_id = m.member_id
        ORDER BY bl.loan_date DESC
    """)
    loans = cursor.fetchall()
    conn.close()
    return render_template('loans.html', loans=loans)

@app.route('/issue_book', methods=['GET', 'POST'])
def issue_book():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        book_id = request.form['book_id']
        member_id = request.form['member_id']
        loan_date = request.form['loan_date']
        due_date = request.form['due_date']

        cursor.execute("SELECT available_copies FROM books WHERE book_id = %s", (book_id,))
        row = cursor.fetchone()
        if row['available_copies'] <= 0:
            flash("This book is not available!", "warning")
            return redirect(url_for('issue_book'))

        try:
            cursor.execute("""
                INSERT INTO bookloans (book_id, member_id, loan_date, due_date, status)
                VALUES (%s, %s, %s, %s, 'On Loan')
            """, (book_id, member_id, loan_date, due_date))

            cursor.execute("""
                UPDATE books SET available_copies = available_copies - 1 WHERE book_id = %s
            """, (book_id,))
            conn.commit()
            flash("Book issued successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            conn.rollback()
        conn.close()
        return redirect(url_for('view_loans'))

    cursor.execute("SELECT book_id, title FROM books WHERE available_copies > 0")
    books = cursor.fetchall()
    cursor.execute("SELECT member_id, CONCAT(first_name, ' ', last_name) AS name FROM members WHERE status = 'Active'")
    members = cursor.fetchall()
    conn.close()
    return render_template('issue_book.html', books=books, members=members)

@app.route('/return_book/<int:loan_id>')
def return_book(loan_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT book_id FROM bookloans WHERE loan_id = %s", (loan_id,))
        book_id = cursor.fetchone()[0]

        cursor.execute("UPDATE bookloans SET return_date = CURDATE(), status = 'Returned' WHERE loan_id = %s", (loan_id,))
        cursor.execute("UPDATE books SET available_copies = available_copies + 1 WHERE book_id = %s", (book_id,))
        conn.commit()
        flash("Book returned successfully!", "success")
    except Exception as e:
        flash(f"Error returning book: {e}", "danger")
        conn.rollback()
    conn.close()
    return redirect(url_for('view_loans'))

@app.route('/publishers')
def view_publishers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM publishers ORDER BY name")
    pubs = cursor.fetchall()
    conn.close()
    return render_template('publishers.html', publishers=pubs)

if __name__ == '__main__':
    app.run(debug=True)