from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
import os
import re
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'campusswap_secret_2024'

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'listings')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─────────────────────────────────────────
#  DB CONNECTION
# ─────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password= #MY PASSWORD (I AM NOT PUTTING HERE)
        database='college_marketplace'
    )

# ─────────────────────────────────────────
#  REUSABLE LISTING SELECT (includes DealScore + PrimaryImage)
# ─────────────────────────────────────────
_LISTING_SELECT = """
    SELECT l.*, s.Name AS SellerName, s.Rating AS SellerRating,
           c.CategoryName,
           ROUND(ca.AvgPrice, 2) AS CatAvg,
           CASE
             WHEN ca.AvgPrice IS NULL OR ca.AvgPrice = 0 THEN 'Fair'
             WHEN l.Price < ca.AvgPrice * 0.80              THEN 'Hot'
             WHEN l.Price > ca.AvgPrice * 1.20              THEN 'High'
             ELSE 'Fair'
           END AS DealScore,
           (SELECT ii.ImagePath FROM ListingImage ii
            WHERE ii.ListingID = l.ListingID
            ORDER BY ii.SortOrder LIMIT 1) AS PrimaryImage
    FROM Listing l
    JOIN Student s ON l.StudentID = s.StudentID
    JOIN Category c ON l.CategoryID = c.CategoryID
    LEFT JOIN (
        SELECT CategoryID, AVG(Price) AS AvgPrice
        FROM Listing WHERE `Status` = 'active'
        GROUP BY CategoryID
    ) ca ON ca.CategoryID = l.CategoryID
"""

# ─────────────────────────────────────────
#  CREATE TABLES (run once at startup)
# ─────────────────────────────────────────
def _create_tables():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ListingImage (
            ImageID   INT AUTO_INCREMENT PRIMARY KEY,
            ListingID INT NOT NULL,
            ImagePath VARCHAR(255) NOT NULL,
            SortOrder INT DEFAULT 0,
            FOREIGN KEY (ListingID) REFERENCES Listing(ListingID) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Watchlist (
            WatchlistID INT AUTO_INCREMENT PRIMARY KEY,
            StudentID   INT NOT NULL,
            ListingID   INT NOT NULL,
            DateAdded   DATE NOT NULL,
            UNIQUE KEY uq_watch (StudentID, ListingID),
            FOREIGN KEY (StudentID) REFERENCES Student(StudentID)  ON DELETE CASCADE,
            FOREIGN KEY (ListingID) REFERENCES Listing(ListingID)  ON DELETE CASCADE
        )
    """)
    # Full-text index for smart search (silently skip if already exists)
    try:
        cur.execute("CREATE FULLTEXT INDEX ft_listing ON Listing(Title, Description)")
    except Exception:
        pass
    db.commit()
    db.close()

try:
    _create_tables()
except Exception:
    pass  

# ─────────────────────────────────────────
#  WATCHED SET HELPER
# ─────────────────────────────────────────
def _get_watched_set(cur):
    """Return set of ListingIDs the logged-in student has saved, or empty set."""
    if 'student_id' not in session:
        return set()
    cur.execute("SELECT ListingID FROM Watchlist WHERE StudentID=%s",
                (session['student_id'],))
    return {r['ListingID'] for r in cur.fetchall()}

# ─────────────────────────────────────────
#  KEYWORD EXTRACTOR  (for Smart Price Suggester)
# ─────────────────────────────────────────
def _extract_keywords(title):
    stop = {
        'the','a','an','and','or','for','with','in','on','at','to','is','it',
        'its','of','this','that','from','by','as','up','new','used','good',
        'fair','like','size','edition','gen','gb','tb','mb','inch','pro',
        'max','air','plus','mini','set','case','lot','pack','box','kit',
    }
    words = re.findall(r'[a-zA-Z]{3,}', title.lower())
    keywords = [w for w in words if w not in stop]
    keywords.sort(key=len, reverse=True)
    return keywords

# ─────────────────────────────────────────
#  IMAGE SAVE HELPER
# ─────────────────────────────────────────
def _save_images(cur, listing_id, files):
    order = 0
    for f in files:
        if not f or not f.filename:
            continue
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            continue
        fname = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, fname))
        cur.execute("""
            INSERT INTO ListingImage (ListingID, ImagePath, SortOrder)
            VALUES (%s, %s, %s)
        """, (listing_id, f'uploads/listings/{fname}', order))
        order += 1

# ─────────────────────────────────────────
#  HOME
# ─────────────────────────────────────────
@app.route('/')
def home():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(_LISTING_SELECT +
                " WHERE l.`Status`='active' ORDER BY l.DatePosted DESC")
    listings = cur.fetchall()
    cur.execute("SELECT * FROM Category")
    categories = cur.fetchall()
    trending = [l for l in listings if l['DealScore'] == 'Hot'][:3]
    watched_set = _get_watched_set(cur)

    # ── Personalized recommendations (only for logged-in users with watchlist activity) ──
    recommendations = []
    if 'student_id' in session:
        sid = session['student_id']
        cur.execute("""
            SELECT l.ListingID, l.Title, l.Price, l.`Condition`, l.DatePosted,
                   s.Name AS SellerName, s.Rating AS SellerRating,
                   c.CategoryName,
                   ROUND(ca.AvgPrice, 2) AS CatAvg,
                   CASE
                     WHEN ca.AvgPrice IS NULL OR ca.AvgPrice = 0 THEN 'Fair'
                     WHEN l.Price < ca.AvgPrice * 0.80            THEN 'Hot'
                     WHEN l.Price > ca.AvgPrice * 1.20            THEN 'High'
                     ELSE 'Fair'
                   END AS DealScore,
                   (SELECT ii.ImagePath FROM ListingImage ii
                    WHERE ii.ListingID = l.ListingID
                    ORDER BY ii.SortOrder LIMIT 1) AS PrimaryImage
            FROM Listing l
            JOIN Student s  ON l.StudentID  = s.StudentID
            JOIN Category c ON l.CategoryID = c.CategoryID
            LEFT JOIN (
                SELECT CategoryID, AVG(Price) AS AvgPrice
                FROM Listing WHERE `Status` = 'active'
                GROUP BY CategoryID
            ) ca ON ca.CategoryID = l.CategoryID
            WHERE l.`Status` = 'active'
              AND l.StudentID != %s
              AND l.ListingID NOT IN (
                  SELECT ListingID FROM Watchlist WHERE StudentID = %s
              )
              AND l.CategoryID IN (
                  SELECT DISTINCT l2.CategoryID
                  FROM Watchlist w
                  JOIN Listing l2 ON w.ListingID = l2.ListingID
                  WHERE w.StudentID = %s
              )
            ORDER BY
              CASE
                WHEN ca.AvgPrice IS NULL OR ca.AvgPrice = 0 THEN 1
                WHEN l.Price < ca.AvgPrice * 0.80            THEN 0
                WHEN l.Price > ca.AvgPrice * 1.20            THEN 2
                ELSE 1
              END ASC,
              l.DatePosted DESC
            LIMIT 4
        """, (sid, sid, sid))
        recommendations = cur.fetchall()

    return render_template('home.html',
        listings=listings, categories=categories,
        trending=trending, watched_set=watched_set,
        recommendations=recommendations)

# ─────────────────────────────────────────
#  SEARCH  (full-text + filters + sort)
# ─────────────────────────────────────────
@app.route('/search')
def search():
    q       = request.args.get('q', '').strip()
    cat     = request.args.get('category', '')
    min_p   = request.args.get('min_price', '')
    max_p   = request.args.get('max_price', '')
    cond    = request.args.get('condition', '')
    sort    = request.args.get('sort', 'newest')

    db  = get_db()
    cur = db.cursor(dictionary=True)

    # Build WHERE clauses (non-search filters)
    filters, fparams = [], []
    filters.append("l.`Status`='active'")
    if cat:
        filters.append("l.CategoryID=%s");  fparams.append(cat)
    if min_p:
        filters.append("l.Price>=%s");      fparams.append(min_p)
    if max_p:
        filters.append("l.Price<=%s");      fparams.append(max_p)
    if cond:
        filters.append("l.`Condition`=%s"); fparams.append(cond)

    where = " WHERE " + " AND ".join(filters)

    # Sort clause
    sort_map = {
        'price_asc':  "l.Price ASC",
        'price_desc': "l.Price DESC",
        'newest':     "l.DatePosted DESC",
        'relevance':  "l.DatePosted DESC",   # overridden below for FT
    }
    order = " ORDER BY " + sort_map.get(sort, "l.DatePosted DESC")

    listings = []
    used_fulltext = False

    if q:

        try:
            ft_select = _LISTING_SELECT.replace(
                "FROM Listing l",
                ", MATCH(l.Title, l.Description)"
                " AGAINST(%s IN NATURAL LANGUAGE MODE) AS Relevance\n    FROM Listing l"
            )
            ft_where  = where + " AND MATCH(l.Title, l.Description) AGAINST(%s IN NATURAL LANGUAGE MODE)"
            ft_order  = (" ORDER BY Relevance DESC" if sort == 'relevance'
                         else order)
            cur.execute(ft_select + ft_where + ft_order, [q] + fparams + [q])
            listings = cur.fetchall()
            used_fulltext = True
        except Exception:
            listings = []

        # ── LIKE fallback when full-text returns nothing ──
        if not listings:
            like = f'%{q}%'
            like_where = where + " AND (l.Title LIKE %s OR l.Description LIKE %s)"
            cur.execute(_LISTING_SELECT + like_where + order,
                        fparams + [like, like])
            listings = cur.fetchall()
            used_fulltext = False
    else:
        cur.execute(_LISTING_SELECT + where + order, fparams)
        listings = cur.fetchall()

    cur.execute("SELECT * FROM Category")
    categories = cur.fetchall()
    watched_set = _get_watched_set(cur)

    return render_template('home.html',
        listings=listings, categories=categories,
        query=q, active_cat=cat, sort=sort,
        min_price=min_p, max_price=max_p, condition=cond,
        watched_set=watched_set, used_fulltext=used_fulltext)

# ─────────────────────────────────────────
#  REGISTER
# ─────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        password = request.form['password']
        uni      = request.form['university']
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("""
                INSERT INTO Student (Name, Email, Password, University, Rating, JoinDate)
                VALUES (%s, %s, %s, %s, 0.0, CURDATE())
            """, (name, email, password, uni))
            db.commit()
            return redirect('/login')
        except mysql.connector.IntegrityError:
            error = 'That email is already registered.'
    return render_template('register.html', error=error)

# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM Student WHERE Email=%s AND Password=%s",
                    (email, password))
        student = cur.fetchone()
        if student:
            session['student_id'] = student['StudentID']
            session['name']       = student['Name']
            return redirect('/')
        error = 'Wrong email or password.'
    return render_template('login.html', error=error)

# ─────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ─────────────────────────────────────────
#  POST LISTING
# ─────────────────────────────────────────
@app.route('/post', methods=['GET', 'POST'])
def post_listing():
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM Category")
    categories = cur.fetchall()
    if request.method == 'POST':
        cur.execute("""
            INSERT INTO Listing
                (Title, Description, Price, `Condition`, `Status`, DatePosted, StudentID, CategoryID)
            VALUES (%s, %s, %s, %s, 'active', CURDATE(), %s, %s)
        """, (
            request.form['title'], request.form['description'],
            request.form['price'], request.form['condition'],
            session['student_id'], request.form['category_id']
        ))
        new_id = cur.lastrowid
        _save_images(cur, new_id, request.files.getlist('images'))
        db.commit()
        return redirect('/')
    return render_template('post_listing.html', categories=categories)

# ─────────────────────────────────────────
#  SMART PRICE SUGGESTER
# ─────────────────────────────────────────
@app.route('/price_suggestion')
def price_suggestion():
    cat_id    = request.args.get('category_id')
    raw_title = request.args.get('title', '').strip()
    db  = get_db()
    cur = db.cursor(dictionary=True)


    if len(raw_title) >= 3:
        for kw in _extract_keywords(raw_title)[:3]:
            like = f'%{kw}%'
            # Try completed-transaction prices for this keyword first
            cur.execute("""
                SELECT ROUND(AVG(t.FinalPrice), 2) AS avg,
                       ROUND(MIN(t.FinalPrice), 2) AS min_p,
                       ROUND(MAX(t.FinalPrice), 2) AS max_p,
                       COUNT(*)                    AS total
                FROM Transaction t
                JOIN Listing l ON t.ListingID = l.ListingID
                WHERE l.Title LIKE %s
            """, (like,))
            result = cur.fetchone()
            if result and result['avg']:
                result['source']    = 'item_sold'
                result['match_key'] = kw
                return jsonify(result)
            # Try active listings with ≥ 2 matches (1 would be the item itself)
            cur.execute("""
                SELECT ROUND(AVG(Price), 2) AS avg,
                       ROUND(MIN(Price), 2) AS min_p,
                       ROUND(MAX(Price), 2) AS max_p,
                       COUNT(*)             AS total
                FROM Listing
                WHERE Title LIKE %s AND `Status` = 'active'
            """, (like,))
            result = cur.fetchone()
            if result and result['avg'] and result['total'] >= 2:
                result['source']    = 'item_active'
                result['match_key'] = kw
                return jsonify(result)

    # ── Step 2: Category fallback ──
    cur.execute("""
        SELECT ROUND(AVG(t.FinalPrice), 2) AS avg,
               ROUND(MIN(t.FinalPrice), 2) AS min_p,
               ROUND(MAX(t.FinalPrice), 2) AS max_p,
               COUNT(*)                    AS total
        FROM Transaction t
        JOIN Listing l ON t.ListingID = l.ListingID
        WHERE l.CategoryID = %s
    """, (cat_id,))
    result = cur.fetchone()
    if result and result['avg']:
        result['source'] = 'sold'
        return jsonify(result)
    cur.execute("""
        SELECT ROUND(AVG(Price), 2) AS avg,
               ROUND(MIN(Price), 2) AS min_p,
               ROUND(MAX(Price), 2) AS max_p,
               COUNT(*)             AS total
        FROM Listing
        WHERE CategoryID = %s AND `Status` = 'active'
    """, (cat_id,))
    result = cur.fetchone()
    if result is None:
        result = {'avg': None, 'min_p': None, 'max_p': None, 'total': 0}
    result['source'] = 'active'
    return jsonify(result)

# ─────────────────────────────────────────
#  LISTING DETAIL
# ─────────────────────────────────────────
@app.route('/listing/<int:lid>')
def listing_detail(lid):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT l.*, s.Name AS SellerName, s.Email AS SellerEmail,
               s.Rating AS SellerRating, s.StudentID AS SellerID,
               s.University, c.CategoryName,
               ROUND(ca.AvgPrice, 2) AS CatAvg,
               ROUND(ca.MinPrice, 2) AS CatMin,
               ROUND(ca.MaxPrice, 2) AS CatMax,
               CASE
                 WHEN ca.AvgPrice IS NULL OR ca.AvgPrice = 0 THEN 'Fair'
                 WHEN l.Price < ca.AvgPrice * 0.80              THEN 'Hot'
                 WHEN l.Price > ca.AvgPrice * 1.20              THEN 'High'
                 ELSE 'Fair'
               END AS DealScore
        FROM Listing l
        JOIN Student s ON l.StudentID = s.StudentID
        JOIN Category c ON l.CategoryID = c.CategoryID
        LEFT JOIN (
            SELECT CategoryID,
                   AVG(Price) AS AvgPrice,
                   MIN(Price) AS MinPrice,
                   MAX(Price) AS MaxPrice
            FROM Listing WHERE `Status` = 'active'
            GROUP BY CategoryID
        ) ca ON ca.CategoryID = l.CategoryID
        WHERE l.ListingID = %s
    """, (lid,))
    listing = cur.fetchone()
    if not listing:
        return redirect('/')

    # Similar listings — same category, closest price, excluding this listing
    cur.execute("""
        SELECT l.ListingID, l.Title, l.Price, l.`Condition`,
               s.Name AS SellerName, c.CategoryName
        FROM Listing l
        JOIN Student s ON l.StudentID = s.StudentID
        JOIN Category c ON l.CategoryID = c.CategoryID
        WHERE l.CategoryID = %s
          AND l.ListingID  != %s
          AND l.`Status`   = 'active'
        ORDER BY ABS(l.Price - %s) ASC
        LIMIT 3
    """, (listing['CategoryID'], lid, listing['Price']))
    similar = cur.fetchall()

    # Messages for this listing (seller view only)
    messages = []
    if 'student_id' in session and session['student_id'] == listing['SellerID']:
        cur.execute("""
            SELECT m.*, s.Name AS SenderName
            FROM Message m
            JOIN Student s ON m.SenderID = s.StudentID
            WHERE m.ListingID = %s
            ORDER BY m.Timestamp DESC
        """, (lid,))
        messages = cur.fetchall()

    # Seller reviews preview
    cur.execute("""
        SELECT r.*, s.Name AS ReviewerName
        FROM Review r
        JOIN Student s ON r.ReviewerID = s.StudentID
        WHERE r.RevieweeID = %s
        ORDER BY r.Date DESC
        LIMIT 3
    """, (listing['SellerID'],))
    seller_reviews = cur.fetchall()

    # All images for this listing
    cur.execute("""
        SELECT * FROM ListingImage WHERE ListingID=%s ORDER BY SortOrder
    """, (lid,))
    listing_images = cur.fetchall()

    # Watchlist info
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM Watchlist WHERE ListingID=%s
    """, (lid,))
    watchlist_count = cur.fetchone()['cnt']
    is_watched = False
    if 'student_id' in session:
        cur.execute("SELECT 1 FROM Watchlist WHERE StudentID=%s AND ListingID=%s",
                    (session['student_id'], lid))
        is_watched = bool(cur.fetchone())

    return render_template('listing_detail.html',
        listing=listing, messages=messages,
        seller_reviews=seller_reviews, similar=similar,
        listing_images=listing_images,
        watchlist_count=watchlist_count, is_watched=is_watched)

# ─────────────────────────────────────────
#  WATCHLIST  (save / unsave a listing)
# ─────────────────────────────────────────
@app.route('/watch/<int:lid>', methods=['POST'])
def watch(lid):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT IGNORE INTO Watchlist (StudentID, ListingID, DateAdded)
        VALUES (%s, %s, CURDATE())
    """, (session['student_id'], lid))
    db.commit()
    return redirect(request.referrer or f'/listing/{lid}')

@app.route('/unwatch/<int:lid>', methods=['POST'])
def unwatch(lid):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM Watchlist WHERE StudentID=%s AND ListingID=%s",
                (session['student_id'], lid))
    db.commit()
    return redirect(request.referrer or f'/listing/{lid}')

# ─────────────────────────────────────────
#  SEND MESSAGE
# ─────────────────────────────────────────
@app.route('/send_message', methods=['POST'])
def send_message():
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO Message (Content, Timestamp, IsRead, SenderID, ReceiverID, ListingID)
        VALUES (%s, NOW(), 0, %s, %s, %s)
    """, (
        request.form['content'],
        session['student_id'],
        request.form['receiver_id'],
        request.form['listing_id']
    ))
    db.commit()
    ref = request.referrer or f"/listing/{request.form['listing_id']}"
    return redirect(ref)

# ─────────────────────────────────────────
#  EDIT LISTING
# ─────────────────────────────────────────
@app.route('/edit/<int:lid>', methods=['GET', 'POST'])
def edit_listing(lid):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM Listing WHERE ListingID=%s AND StudentID=%s",
                (lid, session['student_id']))
    listing = cur.fetchone()
    if not listing:
        return redirect('/')
    cur.execute("SELECT * FROM Category")
    categories = cur.fetchall()
    # Fetch existing images for display
    cur.execute("SELECT * FROM ListingImage WHERE ListingID=%s ORDER BY SortOrder", (lid,))
    existing_images = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            UPDATE Listing
            SET Title=%s, Description=%s, Price=%s,
                `Condition`=%s, CategoryID=%s
            WHERE ListingID=%s
        """, (
            request.form['title'], request.form['description'],
            request.form['price'], request.form['condition'],
            request.form['category_id'], lid
        ))
        # Remove images the user deleted
        remove_ids = request.form.getlist('remove_images')
        for img_id in remove_ids:
            cur.execute("SELECT ImagePath FROM ListingImage WHERE ImageID=%s AND ListingID=%s",
                        (img_id, lid))
            row = cur.fetchone()
            if row:
                try:
                    os.remove(os.path.join(app.root_path, 'static', row['ImagePath']))
                except OSError:
                    pass
                cur.execute("DELETE FROM ListingImage WHERE ImageID=%s", (img_id,))
        # Save new uploads
        _save_images(cur, lid, request.files.getlist('images'))
        db.commit()
        return redirect(f'/listing/{lid}')
    return render_template('edit_listing.html', listing=listing,
                           categories=categories, existing_images=existing_images)

# ─────────────────────────────────────────
#  DELETE LISTING
# ─────────────────────────────────────────
@app.route('/delete/<int:lid>', methods=['POST'])
def delete_listing(lid):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor(dictionary=True)
    # Verify ownership first
    cur.execute("SELECT ListingID FROM Listing WHERE ListingID=%s AND StudentID=%s",
                (lid, session['student_id']))
    if not cur.fetchone():
        return redirect('/profile')
    # Remove image files from disk
    cur.execute("SELECT ImagePath FROM ListingImage WHERE ListingID=%s", (lid,))
    for img in cur.fetchall():
        try:
            os.remove(os.path.join(app.root_path, 'static', img['ImagePath']))
        except OSError:
            pass
    cur = db.cursor()
    cur.execute("DELETE FROM Message   WHERE ListingID=%s", (lid,))
    cur.execute("DELETE FROM Listing   WHERE ListingID=%s AND StudentID=%s",
                (lid, session['student_id']))
    db.commit()
    return redirect('/profile')

# ─────────────────────────────────────────
#  DELETE IMAGE
# ─────────────────────────────────────────
@app.route('/delete_image/<int:img_id>', methods=['POST'])
def delete_image(img_id):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT li.ImagePath, li.ListingID
        FROM ListingImage li
        JOIN Listing l ON li.ListingID = l.ListingID
        WHERE li.ImageID=%s AND l.StudentID=%s
    """, (img_id, session['student_id']))
    row = cur.fetchone()
    if row:
        try:
            os.remove(os.path.join(app.root_path, 'static', row['ImagePath']))
        except OSError:
            pass
        cur = db.cursor()
        cur.execute("DELETE FROM ListingImage WHERE ImageID=%s", (img_id,))
        db.commit()
        return redirect(f'/edit/{row["ListingID"]}')
    return redirect('/')

# ─────────────────────────────────────────
#  MARK AS SOLD  (Transaction)
# ─────────────────────────────────────────
@app.route('/mark_sold/<int:lid>', methods=['POST'])
def mark_sold(lid):
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO Transaction
            (Date, FinalPrice, PaymentMethod, ListingID, BuyerID, SellerID)
        VALUES (CURDATE(), %s, %s, %s, %s, %s)
    """, (
        request.form['final_price'],
        request.form['payment_method'],
        lid,
        request.form['buyer_id'],
        session['student_id']
    ))
    cur.execute("UPDATE Listing SET `Status`='sold' WHERE ListingID=%s", (lid,))
    db.commit()
    return redirect(f'/listing/{lid}')

# ─────────────────────────────────────────
#  LEAVE REVIEW
# ─────────────────────────────────────────
@app.route('/review', methods=['POST'])
def leave_review():
    if 'student_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor(dictionary=True)
    # Prevent duplicate reviews for the same transaction
    cur.execute("""
        SELECT ReviewID FROM Review
        WHERE TransactionID = %s AND ReviewerID = %s
    """, (request.form['transaction_id'], session['student_id']))
    if cur.fetchone():
        return redirect('/profile?msg=already_reviewed')
    cur = db.cursor()
    cur.execute("""
        INSERT INTO Review (Rating, Comment, Date, ReviewerID, RevieweeID, TransactionID)
        VALUES (%s, %s, CURDATE(), %s, %s, %s)
    """, (
        request.form['rating'], request.form['comment'],
        session['student_id'],
        request.form['reviewee_id'],
        request.form['transaction_id']
    ))
    # Recalculate seller's average rating
    cur.execute("""
        UPDATE Student
        SET Rating = (
            SELECT ROUND(AVG(Rating), 2) FROM Review WHERE RevieweeID = %s
        )
        WHERE StudentID = %s
    """, (request.form['reviewee_id'], request.form['reviewee_id']))
    db.commit()
    return redirect('/profile?msg=reviewed')

# ─────────────────────────────────────────
#  PROFILE
# ─────────────────────────────────────────
@app.route('/profile')
def profile():
    if 'student_id' not in session:
        return redirect('/login')
    sid = session['student_id']
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM Student WHERE StudentID=%s", (sid,))
    student = cur.fetchone()

    cur.execute("""
        SELECT l.*, c.CategoryName,
               (SELECT ii.ImagePath FROM ListingImage ii
                WHERE ii.ListingID = l.ListingID
                ORDER BY ii.SortOrder LIMIT 1) AS PrimaryImage
        FROM Listing l
        JOIN Category c ON l.CategoryID = c.CategoryID
        WHERE l.StudentID = %s
        ORDER BY l.DatePosted DESC
    """, (sid,))
    my_listings = cur.fetchall()

    cur.execute("""
        SELECT r.*, s.Name AS ReviewerName
        FROM Review r
        JOIN Student s ON r.ReviewerID = s.StudentID
        WHERE r.RevieweeID = %s
        ORDER BY r.Date DESC
    """, (sid,))
    reviews = cur.fetchall()

    cur.execute("""
        SELECT t.*, l.Title AS ListingTitle, s.Name AS SellerName
        FROM Transaction t
        JOIN Listing l  ON t.ListingID  = l.ListingID
        JOIN Student s  ON t.SellerID   = s.StudentID
        WHERE t.BuyerID = %s
        ORDER BY t.Date DESC
    """, (sid,))
    purchases = cur.fetchall()

    # Check which transactions this student has already reviewed
    reviewed_tx_ids = set()
    if purchases:
        cur.execute("""
            SELECT TransactionID FROM Review WHERE ReviewerID = %s
        """, (sid,))
        reviewed_tx_ids = {r['TransactionID'] for r in cur.fetchall()}

    cur.execute("""
        SELECT m.*, s.Name AS SenderName, l.Title AS ListingTitle
        FROM Message m
        JOIN Student s ON m.SenderID  = s.StudentID
        JOIN Listing l ON m.ListingID = l.ListingID
        WHERE m.ReceiverID = %s
        ORDER BY m.Timestamp DESC
    """, (sid,))
    inbox = cur.fetchall()

    # Saved / watchlist items
    cur.execute("""
        SELECT l.ListingID, l.Title, l.Price, l.`Condition`, l.`Status`,
               c.CategoryName, s2.Name AS SellerName,
               w.DateAdded,
               (SELECT ii.ImagePath FROM ListingImage ii
                WHERE ii.ListingID = l.ListingID
                ORDER BY ii.SortOrder LIMIT 1) AS PrimaryImage
        FROM Watchlist w
        JOIN Listing  l  ON w.ListingID  = l.ListingID
        JOIN Category c  ON l.CategoryID = c.CategoryID
        JOIN Student  s2 ON l.StudentID  = s2.StudentID
        WHERE w.StudentID = %s
        ORDER BY w.DateAdded DESC
    """, (sid,))
    watchlist = cur.fetchall()

    unreviewed_purchases = [p for p in purchases
                            if p['TransactionID'] not in reviewed_tx_ids]

    msg = request.args.get('msg')
    return render_template('profile.html',
        student=student, my_listings=my_listings,
        reviews=reviews, purchases=purchases,
        unreviewed_purchases=unreviewed_purchases,
        inbox=inbox, watchlist=watchlist, msg=msg)

# ─────────────────────────────────────────
#  MARKET INTELLIGENCE DASHBOARD  ★ Advanced Feature
# ─────────────────────────────────────────
@app.route('/insights')
def insights():
    db = get_db()
    cur = db.cursor(dictionary=True)

    # ── Platform summary (aggregate subqueries) ──
    cur.execute("""
        SELECT
            (SELECT COUNT(*)                         FROM Listing     WHERE `Status`='active') AS active_listings,
            (SELECT COUNT(*)                         FROM Student)                              AS total_students,
            (SELECT COUNT(*)                         FROM Transaction)                          AS completed_sales,
            (SELECT COALESCE(ROUND(SUM(FinalPrice),2),0) FROM Transaction)                     AS total_value
    """)
    summary = cur.fetchone()

    # ── Category price stats (LEFT JOIN + GROUP BY + aggregates) ──
    cur.execute("""
        SELECT c.CategoryName,
               COUNT(l.ListingID)      AS active_count,
               ROUND(AVG(l.Price), 2)  AS avg_price,
               ROUND(MIN(l.Price), 2)  AS min_price,
               ROUND(MAX(l.Price), 2)  AS max_price,
               (SELECT COUNT(*) FROM Transaction t2
                JOIN Listing l2 ON t2.ListingID=l2.ListingID
                WHERE l2.CategoryID=c.CategoryID)   AS sales_count
        FROM Category c
        LEFT JOIN Listing l
               ON c.CategoryID = l.CategoryID AND l.`Status` = 'active'
        GROUP BY c.CategoryID, c.CategoryName
        ORDER BY avg_price DESC
    """)
    category_stats = cur.fetchall()
    max_avg = max((c['avg_price'] or 0) for c in category_stats) or 1
    for c in category_stats:
        c['bar_pct'] = round((c['avg_price'] or 0) / max_avg * 100)

    # ── Top deals — listings ≥ 20% below category average (subquery JOIN) ──
    cur.execute("""
        SELECT l.ListingID, l.Title, l.Price, l.`Condition`,
               s.Name AS SellerName, c.CategoryName,
               ROUND(ca.AvgPrice, 2)                        AS CatAvg,
               ROUND((1 - l.Price / ca.AvgPrice) * 100, 0)  AS PctBelow
        FROM Listing l
        JOIN Student  s  ON l.StudentID  = s.StudentID
        JOIN Category c  ON l.CategoryID = c.CategoryID
        JOIN (
            SELECT CategoryID, AVG(Price) AS AvgPrice
            FROM Listing
            WHERE `Status` = 'active'
            GROUP BY CategoryID
            HAVING AVG(Price) > 0
        ) ca ON ca.CategoryID = l.CategoryID
        WHERE l.`Status` = 'active'
          AND l.Price < ca.AvgPrice * 0.80
        ORDER BY PctBelow DESC
        LIMIT 6
    """)
    top_deals = cur.fetchall()

    # ── Recent completed sales (multi-table JOIN) ──
    cur.execute("""
        SELECT t.Date, t.FinalPrice, t.PaymentMethod,
               l.Title      AS ItemTitle,
               c.CategoryName,
               buyer.Name   AS BuyerName,
               seller.Name  AS SellerName
        FROM Transaction t
        JOIN Listing  l      ON t.ListingID  = l.ListingID
        JOIN Category c      ON l.CategoryID = c.CategoryID
        JOIN Student  buyer  ON t.BuyerID    = buyer.StudentID
        JOIN Student  seller ON t.SellerID   = seller.StudentID
        ORDER BY t.Date DESC
        LIMIT 8
    """)
    recent_transactions = cur.fetchall()

    # ── Top-rated sellers (GROUP BY + HAVING) ──
    cur.execute("""
        SELECT s.StudentID,
               s.Name,
               s.University,
               ROUND(s.Rating, 1)             AS Rating,
               COUNT(DISTINCT l.ListingID)    AS total_listings,
               COUNT(DISTINCT r.ReviewID)     AS review_count,
               COUNT(DISTINCT t.TransactionID) AS sales_count
        FROM Student s
        LEFT JOIN Listing     l ON s.StudentID = l.StudentID
        LEFT JOIN Review      r ON s.StudentID = r.RevieweeID
        LEFT JOIN Transaction t ON s.StudentID = t.SellerID
        GROUP BY s.StudentID, s.Name, s.University, s.Rating
        HAVING review_count > 0
        ORDER BY s.Rating DESC, review_count DESC
        LIMIT 5
    """)
    top_sellers = cur.fetchall()

    # ── Most-saved listings (Watchlist × Listing JOIN + GROUP BY) ──
    cur.execute("""
        SELECT l.ListingID, l.Title, l.Price, l.`Condition`,
               c.CategoryName, s.Name AS SellerName,
               COUNT(w.WatchlistID) AS save_count
        FROM Listing l
        JOIN Category c  ON l.CategoryID = c.CategoryID
        JOIN Student  s  ON l.StudentID  = s.StudentID
        JOIN Watchlist w ON l.ListingID  = w.ListingID
        WHERE l.`Status` = 'active'
        GROUP BY l.ListingID, l.Title, l.Price, l.`Condition`,
                 c.CategoryName, s.Name
        ORDER BY save_count DESC
        LIMIT 5
    """)
    most_saved = cur.fetchall()

    return render_template('insights.html',
        summary=summary,
        category_stats=category_stats,
        top_deals=top_deals,
        recent_transactions=recent_transactions,
        top_sellers=top_sellers,
        most_saved=most_saved)

# ─────────────────────────────────────────
#  PUBLIC SELLER PROFILE
# ─────────────────────────────────────────
@app.route('/student/<int:sid>')
def student_profile(sid):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM Student WHERE StudentID=%s", (sid,))
    seller = cur.fetchone()
    if not seller:
        return redirect('/')

    # Their active listings
    cur.execute(_LISTING_SELECT +
                " WHERE l.`Status`='active' AND l.StudentID=%s"
                " ORDER BY l.DatePosted DESC", (sid,))
    listings = cur.fetchall()

    # All reviews about them
    cur.execute("""
        SELECT r.*, s.Name AS ReviewerName
        FROM Review r
        JOIN Student s ON r.ReviewerID = s.StudentID
        WHERE r.RevieweeID = %s
        ORDER BY r.Date DESC
    """, (sid,))
    reviews = cur.fetchall()

    # Sales summary — aggregate over Transaction
    cur.execute("""
        SELECT COUNT(*)                         AS total_sales,
               COALESCE(SUM(t.FinalPrice), 0)  AS total_earned,
               COUNT(DISTINCT l.CategoryID)    AS categories_sold
        FROM Transaction t
        JOIN Listing l ON t.ListingID = l.ListingID
        WHERE t.SellerID = %s
    """, (sid,))
    stats = cur.fetchone()

    return render_template('student_profile.html',
        seller=seller, listings=listings, reviews=reviews, stats=stats)

# ─────────────────────────────────────────
#  SEED DEMO DATA  (debug only)
# ─────────────────────────────────────────
@app.route('/seed_db')
def seed_db():
    if not app.debug:
        return redirect('/')
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM Student")
    if cur.fetchone()[0] >= 4:
        return "Already seeded — skipping.", 200
    _seed(db)
    return redirect('/')

@app.route('/seed_demo')
def seed_demo():
    """Seed transactions, reviews, messages, watchlist using whatever students/listings exist."""
    if not app.debug:
        return redirect('/')
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Get existing students + listings
    cur.execute("SELECT StudentID FROM Student ORDER BY StudentID")
    sids = [r['StudentID'] for r in cur.fetchall()]
    cur.execute("SELECT ListingID, StudentID, Price FROM Listing WHERE `Status`='active' ORDER BY ListingID")
    listings = cur.fetchall()

    if len(sids) < 3 or len(listings) < 3:
        return "Not enough data to seed.", 400

    cur.execute("SELECT COUNT(*) AS cnt FROM Transaction")
    if cur.fetchone()['cnt'] > 0:
        return "Demo data already seeded.", 200

    cur = db.cursor()
    tids = []
    sold_lids = []

    # Create up to 5 transactions using listings whose owner is not the buyer
    pairs = []
    for l in listings:
        buyer = next((s for s in sids if s != l['StudentID']), None)
        if buyer:
            pairs.append((l, buyer))
        if len(pairs) == 5:
            break

    for l, buyer in pairs:
        final = round(float(l['Price']) * 0.95, 2)
        cur.execute("""
            INSERT INTO Transaction (Date, FinalPrice, PaymentMethod, ListingID, BuyerID, SellerID)
            VALUES ('2026-04-10', %s, 'Venmo', %s, %s, %s)
        """, (final, l['ListingID'], buyer, l['StudentID']))
        tids.append(cur.lastrowid)
        sold_lids.append(l['ListingID'])
        cur.execute("UPDATE Listing SET `Status`='sold' WHERE ListingID=%s", (l['ListingID'],))

    db.commit()

    # Reviews for each transaction
    review_texts = [
        (5, 'Smooth transaction! Item was exactly as described. Highly recommend.'),
        (5, 'Great seller — very responsive and easy to meet on campus.'),
        (4, 'Good condition, fair price. Would buy from again.'),
        (5, 'Quick reply and honest description. Perfect deal!'),
        (4, 'Item in great shape. Friendly seller. Good experience overall.'),
    ]
    cur = db.cursor(dictionary=True)
    for i, (pair, tid) in enumerate(zip(pairs, tids)):
        l, buyer = pair
        rating, comment = review_texts[i % len(review_texts)]
        cur.execute("""
            INSERT INTO Review (Rating, Comment, Date, ReviewerID, RevieweeID, TransactionID)
            VALUES (%s, %s, '2026-04-11', %s, %s, %s)
        """, (rating, comment, buyer, l['StudentID'], tid))
    db.commit()

    # Recalculate all seller ratings
    cur.execute("SELECT DISTINCT StudentID FROM Student")
    for row in cur.fetchall():
        sid = row['StudentID']
        cur.execute("""
            UPDATE Student
            SET Rating = (SELECT ROUND(AVG(Rating),2) FROM Review WHERE RevieweeID=%s)
            WHERE StudentID=%s
        """, (sid, sid))
    db.commit()

    # Watchlist entries on remaining active listings
    cur.execute("SELECT ListingID, StudentID FROM Listing WHERE `Status`='active' ORDER BY ListingID")
    active = cur.fetchall()
    cur = db.cursor()
    for i, listing in enumerate(active[:8]):
        watcher = sids[(i + 2) % len(sids)]  # different from owner
        if watcher != listing['StudentID']:
            cur.execute("""
                INSERT IGNORE INTO Watchlist (StudentID, ListingID, DateAdded)
                VALUES (%s, %s, '2026-04-12')
            """, (watcher, listing['ListingID']))
    db.commit()

    # A few messages
    if len(active) >= 2:
        cur.execute("""
            INSERT IGNORE INTO Message (Content, Timestamp, IsRead, SenderID, ReceiverID, ListingID)
            VALUES
              ('Hi! Is this still available? Can we meet at the library?',   NOW(), 0, %s, %s, %s),
              ('Yes, still available! I am free Tuesday and Thursday.',       NOW(), 0, %s, %s, %s)
        """, (
            sids[1], active[0]['StudentID'], active[0]['ListingID'],
            active[0]['StudentID'], sids[1],  active[0]['ListingID'],
        ))
        db.commit()

    return redirect('/insights')

def _seed(db):
    cur = db.cursor()
    for cat in ['Textbooks','Electronics','Furniture','Clothes','Sports','Appliances']:
        cur.execute("INSERT IGNORE INTO Category (CategoryName) VALUES (%s)", (cat,))
    db.commit()

    students = [
        ('Alex Johnson',    'alex@gsu.edu',    'pass123', 'Georgia State University', 4.8),
        ('Maria Garcia',    'maria@gsu.edu',   'pass123', 'Georgia State University', 4.5),
        ('Kevin Park',      'kevin@gsu.edu',   'pass123', 'Georgia State University', 4.2),
        ('Priya Patel',     'priya@gsu.edu',   'pass123', 'Georgia State University', 4.9),
        ('Marcus Williams', 'marcus@gsu.edu',  'pass123', 'Georgia State University', 3.8),
    ]
    for s in students:
        try:
            cur.execute("""
                INSERT INTO Student (Name,Email,Password,University,Rating,JoinDate)
                VALUES (%s,%s,%s,%s,%s,CURDATE())
            """, s)
        except Exception:
            pass
    db.commit()

    def sid(email):
        cur.execute("SELECT StudentID FROM Student WHERE Email=%s", (email,))
        r = cur.fetchone(); return r[0] if r else None

    def cid(name):
        cur.execute("SELECT CategoryID FROM Category WHERE CategoryName=%s", (name,))
        r = cur.fetchone(); return r[0] if r else None

    S = {e: sid(e) for e in ['alex@gsu.edu','maria@gsu.edu','kevin@gsu.edu',
                              'priya@gsu.edu','marcus@gsu.edu']}
    C = {n: cid(n) for n in ['Textbooks','Electronics','Furniture','Clothes','Sports','Appliances']}

    listings = [
        ('Calculus Early Transcendentals 8th Ed',  'Barely used, no highlights. Great for any Calc class.',      42.00, 'Like New', S['alex@gsu.edu'],   C['Textbooks']),
        ('Organic Chemistry 12th Edition',          'Some notes in pencil. Helpful annotations throughout.',      58.00, 'Good',     S['maria@gsu.edu'],  C['Textbooks']),
        ('Intro to Algorithms (CLRS)',              'A few dog-eared pages, otherwise excellent.',                50.00, 'Good',     S['kevin@gsu.edu'],  C['Textbooks']),
        ('iPhone 14 Pro 256GB Space Black',         'No scratches, Face ID works perfectly, OEM charger included.', 580.00, 'Like New', S['alex@gsu.edu'],   C['Electronics']),
        ('MacBook Air M2 13" Starlight',            '8GB RAM, 256GB SSD. Battery health 98%. Includes charger.',  850.00, 'Like New', S['priya@gsu.edu'],  C['Electronics']),
        ('Sony WH-1000XM5 Headphones',              'Perfect noise cancellation. Includes case and cables.',      150.00, 'Good',     S['marcus@gsu.edu'], C['Electronics']),
        ('iPad Air 5th Gen 64GB WiFi',              'Space Gray. Comes with Apple Pencil 1st gen.',               420.00, 'Good',     S['maria@gsu.edu'],  C['Electronics']),
        ('IKEA MICKE Desk White 73x50cm',           'Minor scuffs on legs. Very sturdy.',                         65.00, 'Good',     S['maria@gsu.edu'],  C['Furniture']),
        ('Ergonomic Mesh Office Chair',             'Lumbar support, great for long study sessions.',            120.00, 'Good',     S['kevin@gsu.edu'],  C['Furniture']),
        ('Dorm Room Mini Fridge 3.2 cu ft',         'Quiet and efficient. Perfect for a dorm.',                   85.00, 'Good',     S['priya@gsu.edu'],  C['Furniture']),
        ('GSU Panthers Hoodie Size XL',             'Only worn twice. Blue with gold lettering.',                  28.00, 'Like New', S['marcus@gsu.edu'], C['Clothes']),
        ('Patagonia Better Sweater Jacket Size M',  'Excellent condition. Dark Navy.',                             75.00, 'Like New', S['alex@gsu.edu'],   C['Clothes']),
        ('Nike Air Force 1 White Size 10',          'Clean pair, no yellowing. Original box included.',            80.00, 'Good',     S['maria@gsu.edu'],  C['Clothes']),
        ('Official NBA Spalding Basketball',        'Good bounce. Slight grip wear. Great for outdoor courts.',   22.00, 'Good',     S['kevin@gsu.edu'],  C['Sports']),
        ('Lululemon The Mat 5mm Yoga Mat',          'Non-slip, great cushion. Carrying strap included.',           18.00, 'Like New', S['priya@gsu.edu'],  C['Sports']),
        ('Adjustable Dumbbell Set 5–25 lbs',        'Both handles. No rust. Works with standard plates.',          55.00, 'Good',     S['marcus@gsu.edu'], C['Sports']),
        ('Keurig K-Mini Coffee Maker',              'Works perfectly. Includes 12 K-Cups.',                        32.00, 'Good',     S['alex@gsu.edu'],   C['Appliances']),
        ('Aroma 8-Cup Rice Cooker',                 'Never had an issue. Makes perfect rice.',                     24.00, 'Like New', S['maria@gsu.edu'],  C['Appliances']),
        ('Ninja Air Fryer 4 Qt AF101',              'Used ~10 times. Very clean inside and out.',                  52.00, 'Like New', S['kevin@gsu.edu'],  C['Appliances']),
    ]
    lids = []
    for li in listings:
        cur.execute("""
            INSERT INTO Listing
                (Title,Description,Price,`Condition`,`Status`,DatePosted,StudentID,CategoryID)
            VALUES (%s,%s,%s,%s,'active','2026-03-15',%s,%s)
        """, li)
        lids.append(cur.lastrowid)
    db.commit()

    # Transactions (sell 5 items)
    txns = [
        (55.00, 'Cash',  lids[1],  S['kevin@gsu.edu'],  S['maria@gsu.edu']),
        (20.00, 'Venmo', lids[13], S['alex@gsu.edu'],   S['kevin@gsu.edu']),
        (30.00, 'Zelle', lids[16], S['priya@gsu.edu'],  S['alex@gsu.edu']),
        (78.00, 'Venmo', lids[12], S['marcus@gsu.edu'], S['maria@gsu.edu']),
        (16.00, 'Cash',  lids[14], S['maria@gsu.edu'],  S['priya@gsu.edu']),
    ]
    tids = []
    for t in txns:
        cur.execute("""
            INSERT INTO Transaction (Date,FinalPrice,PaymentMethod,ListingID,BuyerID,SellerID)
            VALUES ('2026-04-10',%s,%s,%s,%s,%s)
        """, t)
        tids.append(cur.lastrowid)
        cur.execute("UPDATE Listing SET `Status`='sold' WHERE ListingID=%s", (t[2],))
    db.commit()

    reviews = [
        (5, 'Great seller! Book was exactly as described. Easy library meetup.',      S['kevin@gsu.edu'],  S['maria@gsu.edu'],  tids[0]),
        (5, 'Ball in great condition. Fast response and easy campus exchange!',       S['alex@gsu.edu'],   S['kevin@gsu.edu'],  tids[1]),
        (4, 'Coffee maker works perfectly. Very responsive and accommodating.',       S['priya@gsu.edu'],  S['alex@gsu.edu'],   tids[2]),
        (5, 'Shoes were spotless. Came in original box. Amazing deal!',               S['marcus@gsu.edu'], S['maria@gsu.edu'],  tids[3]),
        (4, 'Yoga mat clean and perfect condition. Smooth transaction!',              S['maria@gsu.edu'],  S['priya@gsu.edu'],  tids[4]),
    ]
    for r in reviews:
        cur.execute("""
            INSERT INTO Review (Rating,Comment,Date,ReviewerID,RevieweeID,TransactionID)
            VALUES (%s,%s,'2026-04-12',%s,%s,%s)
        """, r)

    for email in S:
        s = S[email]
        cur.execute("""
            UPDATE Student SET Rating=(
                SELECT ROUND(AVG(Rating),2) FROM Review WHERE RevieweeID=%s
            ) WHERE StudentID=%s
        """, (s, s))

    # Sample messages
    cur.execute("""
        INSERT INTO Message (Content,Timestamp,IsRead,SenderID,ReceiverID,ListingID)
        VALUES
          ('Hi! Is the Calculus book still available?', NOW(), 0, %s, %s, %s),
          ('Yes it is! Free Tuesday after 2pm.', NOW(), 0, %s, %s, %s),
          ('Is the iPhone unlocked for all carriers?', NOW(), 0, %s, %s, %s)
    """, (
        S['kevin@gsu.edu'], S['alex@gsu.edu'],  lids[0],
        S['alex@gsu.edu'],  S['kevin@gsu.edu'], lids[0],
        S['maria@gsu.edu'], S['alex@gsu.edu'],  lids[3],
    ))
    db.commit()

if __name__ == '__main__':
    app.run(debug=True)
