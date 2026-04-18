# CampusSwap — Final Project Report
**Course:** Database Systems  
**Application:** College Student Marketplace  
**Team Members:** Sangeet Gaire, [Teammate Name]  
**Platform:** Flask (Python) + MySQL  

---

## 1. Introduction

### What is CampusSwap?

CampusSwap is a web-based marketplace built specifically for college students. The idea is simple — students have a ton of stuff they no longer need (old textbooks, electronics, furniture, clothes) and other students need exactly those things, usually at a budget-friendly price. Instead of posting on general platforms like Craigslist or Facebook Marketplace where anyone can see your listing, CampusSwap is designed for students within the same university community.

The app lets students create an account, post items they want to sell with photos and a price, browse what other students are selling, save items to a watchlist, message sellers directly, and leave reviews after completing a purchase.

### Why This Application?

We chose a marketplace because it covers a really wide range of database operations naturally. Almost every interaction a user makes — posting, searching, buying, messaging — touches the database in a meaningful way. It gave us a chance to work with:

- Multiple related tables with real foreign key relationships
- Aggregate queries that actually mean something (average prices, ratings, sales counts)
- A search system that needed to be smarter than a simple keyword match
- Data integrity concerns (no duplicate watchlist entries, no reviewing the same transaction twice)

It is also genuinely useful. College students spend a lot of money on textbooks and supplies every semester. A platform that helps them buy and sell within their campus community makes real financial sense.

### Key Components

- A student account system with login, registration, and public profiles
- A listing system where you can post items with photos, edit them, and mark them as sold
- A full-text search engine with filters for price, condition, and category
- A watchlist (save items for later)
- A messaging system between buyers and sellers
- A review system tied to completed transactions
- A Smart Price Suggester that recommends a fair selling price based on past sales
- A Personalized Recommendation Engine that suggests items based on your interests
- A Market Intelligence Dashboard showing platform-wide analytics

---

## 2. Database Design

### E-R Model

The database has 8 tables. At the center of everything is the **Student** and the **Listing**. A student can post many listings, and each listing belongs to one category. When a sale happens, a Transaction is recorded. Either party can leave a Review tied to that transaction. Students can save listings to their Watchlist and send Messages about listings.

The relationships are:

- Student → Listing (one-to-many: one student posts many listings)
- Listing → Category (many-to-one: many listings belong to one category)
- Listing → ListingImage (one-to-many: a listing can have multiple photos)
- Transaction → Listing, Student (many-to-one each: one transaction involves one listing, one buyer, one seller)
- Review → Transaction, Student (tied to a transaction, written by one student about another)
- Message → Listing, Student (a message is about a listing, between two students)
- Watchlist → Student, Listing (many-to-many bridge table)

### Relational Schema

```
Student(StudentID PK, Name, Email UNIQUE, Password, University, Rating, JoinDate)

Category(CategoryID PK, CategoryName)

Listing(ListingID PK, Title, Description, Price, Condition, Status, DatePosted,
        StudentID FK→Student, CategoryID FK→Category)

ListingImage(ImageID PK, ListingID FK→Listing, ImagePath, SortOrder)

Transaction(TransactionID PK, Date, FinalPrice, PaymentMethod,
            ListingID FK→Listing, BuyerID FK→Student, SellerID FK→Student)

Review(ReviewID PK, Rating, Comment, Date,
       ReviewerID FK→Student, RevieweeID FK→Student, TransactionID FK→Transaction)

Message(MessageID PK, Content, Timestamp, IsRead,
        SenderID FK→Student, ReceiverID FK→Student, ListingID FK→Listing)

Watchlist(WatchlistID PK, StudentID FK→Student, ListingID FK→Listing, DateAdded,
          UNIQUE(StudentID, ListingID))
```

### Normalization

All eight tables are in **BCNF (Boyce-Codd Normal Form)**.

To explain briefly:

- **1NF**: Every column holds a single atomic value. For example, we do not store multiple images as a comma-separated string — we have a separate `ListingImage` table.
- **2NF**: Every non-key column depends on the whole primary key, not just part of it. Since most tables use a single-column surrogate primary key (auto_increment integer), partial dependency is not possible.
- **3NF / BCNF**: There are no transitive dependencies. For example, a student's university name does not determine their rating — both are direct facts about the student. Category names are stored in their own table, not repeated in every listing row.

The `Watchlist` table deserves special mention. It acts as a many-to-many bridge between Student and Listing, with a `UNIQUE KEY` constraint on the (StudentID, ListingID) pair. This prevents a student from saving the same item twice at the database level — not just in application code.

### Other Constraints

- `Email` in Student is declared `UNIQUE` — no two accounts with the same email
- `ON DELETE CASCADE` on all foreign keys pointing to Listing and Student, so deleting a listing also cleans up its images, messages, and watchlist entries
- `Rating` in Student is automatically recalculated using an UPDATE + subquery every time a new review is posted, keeping it always accurate
- A `FULLTEXT INDEX` is created on `Listing(Title, Description)` at startup to support relevance-ranked search

---

## 3. Functionality Details

### Basic Functions

**1. Insert Records**

The app has multiple insert operations:

- **Register** — inserts a new row into `Student` with the user's name, email, university, and a starting rating of 0
- **Post Listing** — inserts into `Listing` and then separately inserts one row per uploaded photo into `ListingImage`
- **Send Message** — inserts into `Message` with sender, receiver, listing reference, and timestamp
- **Save Item** — inserts into `Watchlist` using `INSERT IGNORE` so that even if a user clicks the save button twice, only one row is ever created (the unique constraint + IGNORE handles it cleanly)
- **Leave Review** — inserts into `Review`, then immediately runs an UPDATE to recalculate the seller's average rating

**2. Search and List Results**

The search page accepts a text query plus optional filters: category, minimum price, maximum price, and condition. Results can be sorted by newest, price low-to-high, or price high-to-low.

When a keyword is given, the app first tries a **FULLTEXT search** using MySQL's `MATCH() AGAINST()` syntax. If the full-text search returns no results (for example, a very short or common word), it automatically falls back to a `LIKE` search on Title and Description. The full-text path also adds a `Relevance` score to each result so we can sort by closest match.

```sql
SELECT ..., MATCH(l.Title, l.Description) AGAINST(? IN NATURAL LANGUAGE MODE) AS Relevance
FROM Listing l ...
WHERE MATCH(l.Title, l.Description) AGAINST(? IN NATURAL LANGUAGE MODE)
ORDER BY Relevance DESC
```

**3. Join and Aggregate Queries**

Several pages involve complex queries. The main listing select statement (used on the home page and search page) joins four tables:

```sql
SELECT l.*, s.Name AS SellerName, c.CategoryName,
       ROUND(ca.AvgPrice, 2) AS CatAvg,
       CASE
         WHEN l.Price < ca.AvgPrice * 0.80 THEN 'Hot'
         WHEN l.Price > ca.AvgPrice * 1.20 THEN 'High'
         ELSE 'Fair'
       END AS DealScore
FROM Listing l
JOIN Student s  ON l.StudentID  = s.StudentID
JOIN Category c ON l.CategoryID = c.CategoryID
LEFT JOIN (
    SELECT CategoryID, AVG(Price) AS AvgPrice
    FROM Listing WHERE Status = 'active'
    GROUP BY CategoryID
) ca ON ca.CategoryID = l.CategoryID
```

The `ca` subquery is an inline aggregate — it calculates the average price per category from all active listings, and that number is then used to compute a `DealScore` for each listing. A listing tagged "Hot" is priced at least 20% below the category average. This runs on every page load and gives buyers an instant signal on whether a price is good.

**4. Update Records**

- **Edit Listing** — lets the seller change the title, description, price, condition, and category of an existing listing. Also lets them remove old photos and upload new ones.
- **Mark as Sold** — the seller fills in the final price and payment method, which inserts a Transaction and sets the listing's Status to 'sold' via an UPDATE.
- **Rating Update** — after every new review is submitted, the seller's Rating is recalculated:
  ```sql
  UPDATE Student
  SET Rating = (SELECT ROUND(AVG(Rating), 2) FROM Review WHERE RevieweeID = ?)
  WHERE StudentID = ?
  ```

**5. Delete Records**

- **Delete Listing** — before deleting, the app queries the `ListingImage` table to get all photo file paths, removes the physical image files from disk, then deletes the listing row. `ON DELETE CASCADE` handles cleaning up related messages and watchlist entries automatically.
- **Unsave / Remove from Watchlist** — deletes from `Watchlist` where both StudentID and ListingID match.
- **Delete Image** — sellers can individually remove photos from a listing without deleting the whole listing.

---

### Advanced Functions

**Advanced Function 1: Smart Price Suggester**

When a seller is posting a new listing, they often have no idea what a fair price is. The Smart Price Suggester solves this automatically. As the seller types the item title, the app sends a request to a backend endpoint that runs a multi-step query pipeline to suggest a price range.

The logic works in three steps:

**Step 1 — Keyword match against completed transactions (most accurate)**

The title is cleaned by removing stop words ("the", "a", "for", "like", "pro", "air", etc.) using a Python function that strips common filler words and keeps only meaningful keywords, sorted longest-first. The app then queries `Transaction JOIN Listing` using `LIKE '%keyword%'` to find items with similar names that actually sold. If found, it returns those real sale prices.

```python
for kw in _extract_keywords(title)[:3]:
    SELECT AVG(FinalPrice), MIN(FinalPrice), MAX(FinalPrice), COUNT(*)
    FROM Transaction t JOIN Listing l ON t.ListingID = l.ListingID
    WHERE l.Title LIKE '%keyword%'
```

For example: typing "Calculus Textbook" extracts the keyword "calculus", finds a past sale at $28.50, and says "Similar items sold for $28.50."

**Step 2 — Keyword match against active listings**

If no transaction history exists, it looks for at least 2 active listings with the same keyword, and uses those prices as a reference. This represents the current market asking price.

**Step 3 — Category fallback**

If neither keyword search produces results, it falls back to the category-wide average. The UI shows a note telling the user how confident the suggestion is ("Based on 1 past sale" vs "Based on category average").

This is genuinely useful and technically non-trivial because it requires keyword extraction, a waterfall query strategy, and dynamic SQL construction at runtime.

---

**Advanced Function 2: Personalized Recommendation Engine**

On the home page, logged-in users see a "Recommended For You" section. This section surfaces listings that the user is likely to be interested in but has not seen yet.

The recommendation logic uses a single SQL query with two correlated subqueries:

```sql
SELECT l.*, s.Name, c.CategoryName, ...
FROM Listing l
JOIN Student s  ON l.StudentID  = s.StudentID
JOIN Category c ON l.CategoryID = c.CategoryID
LEFT JOIN (...avg price subquery...) ca ON ca.CategoryID = l.CategoryID
WHERE l.Status = 'active'
  AND l.StudentID != ?                          -- not the user's own listing
  AND l.ListingID NOT IN (                      -- not already saved
      SELECT ListingID FROM Watchlist WHERE StudentID = ?
  )
  AND l.CategoryID IN (                         -- in a category user has shown interest in
      SELECT DISTINCT l2.CategoryID
      FROM Watchlist w JOIN Listing l2 ON w.ListingID = l2.ListingID
      WHERE w.StudentID = ?
  )
ORDER BY DealScore ASC, l.DatePosted DESC
LIMIT 4
```

The query spans 5 tables (Listing, Student, Category, Watchlist, and the category average subquery). It uses:
- One `NOT IN` subquery to exclude already-saved items
- One `IN` subquery to identify categories the user has interacted with
- A computed `DealScore` ranking that prioritizes "Hot" deals (items priced ≥20% below average) first

The recommendations update immediately as the user saves or unsaves items. This is the kind of collaborative interest-based filtering that powers real recommendation systems like Amazon's "Customers also viewed."

---

**Advanced Function 3: Market Intelligence Dashboard**

The `/insights` page is a full analytics dashboard for the platform. It runs six separate complex queries and presents them visually:

1. **Platform summary** — four aggregate subqueries in one SELECT: total active listings, total students, completed sales count, and total platform transaction volume
2. **Category price analytics** — LEFT JOIN between Category and Listing, with GROUP BY and aggregate functions (AVG, MIN, MAX, COUNT). Includes a correlated subquery counting how many transactions happened per category.
3. **Hot deals** — finds listings that are currently priced more than 20% below their category average using a JOIN against an inline aggregate subquery, sorted by "percent below average"
4. **Recent transactions** — a 4-table JOIN (Transaction, Listing, Category, Student×2 for buyer and seller names)
5. **Top-rated sellers** — GROUP BY with HAVING to filter only students who have at least one review, then sort by rating and review count
6. **Most-saved listings** — JOIN between Listing and Watchlist, GROUP BY listing, ORDER BY save count — surfaces the most wanted items on the platform

This page alone demonstrates more query complexity than most basic database projects, and it updates in real time as the database changes.

---

## 4. Implementation Details

### Languages and Platforms

| Layer | Technology |
|---|---|
| Backend language | Python 3 |
| Web framework | Flask |
| Database | MySQL 9.6 |
| DB connector | mysql-connector-python |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| Templating | Jinja2 (Flask built-in) |
| File storage | Local filesystem (`static/uploads/listings/`) |

### How the Frontend Interacts with the Backend

Flask uses a request-response model. When a user visits a URL like `/search?q=calculus`, Flask runs the Python function associated with that route, builds a MySQL query, fetches the results as a list of Python dictionaries, and passes them to a Jinja2 HTML template. The template then loops over the data and renders the final HTML that the browser sees.

For form submissions (posting a listing, sending a message, etc.), the browser sends a POST request. Flask reads `request.form` for text fields and `request.files` for uploaded images. Images are saved to disk using an absolute path constructed from `app.root_path` (a critical fix we made — relative paths caused uploaded files to be saved in the wrong location and never appear on the site).

The Smart Price Suggester uses JavaScript's `fetch()` API to call `/price_suggestion?title=...&category_id=...` in the background as the user types. This is an AJAX call — the page does not reload, it just updates the price hint box.

The Watchlist save/unsave buttons are HTML forms with POST method, which avoids the security problems that come with using GET for state-changing operations.

### Session Management

Flask's server-side session stores the logged-in student's `StudentID` and `Name` after a successful login. All protected routes check `'student_id' in session` before doing anything. Logout clears the session entirely.

### Key Engineering Decisions

- **`INSERT IGNORE` on Watchlist** — instead of checking "does this entry exist?" first and then inserting, we let the database's UNIQUE constraint handle deduplication. One query instead of two, and no race condition.
- **`ON DELETE CASCADE`** — when a listing is deleted, all related images, messages, and watchlist entries are removed automatically by the database, not by application code.
- **FULLTEXT index** — created at app startup with a try/except so it silently skips if it already exists. Enables relevance-ranked search with a single SQL keyword instead of multiple LIKE statements.
- **Absolute upload path** — image files are saved using `os.path.join(app.root_path, 'static', 'uploads', 'listings')`. This ensures file saves work correctly regardless of what directory the app is started from.

### Code Repository

The full source code is available at: [GitHub link here — upload before submission]

---

## 5. Group Member Evaluation

| Member | Contributions | Score (out of 10) |
|---|---|---|
| Sangeet Gaire | Backend Flask routes (search, watchlist, recommendations, mark-as-sold, review system, price suggester), database schema design, full-text search implementation, image upload pipeline, Market Intelligence Dashboard, frontend design and CSS, debugging | 10/10 |
| [Teammate Name] | [Describe your teammate's contributions here — e.g., initial database schema, seed data, login/register system, specific templates, report writing, etc.] | 10/10 |

*Note: Both members contributed equally to the overall project. Work was divided by feature area and both members participated in design decisions throughout.*

---

## 6. Experiences

### What We Learned

The biggest lesson was that designing a database schema up front saves a huge amount of refactoring later. We had to add the `ListingImage` and `Watchlist` tables after the initial schema was built because we had not anticipated needing them. Adding those tables mid-project required updating multiple routes and templates at the same time.

We also learned that SQL can do more than we expected. Before this project, we thought of SQL as something you just use to "get data." After building this, we realized that CASE expressions, correlated subqueries, inline aggregate views, and FULLTEXT indexes are real tools that change what is possible. The DealScore computation — which classifies every listing as Hot, Fair, or High in a single query — would have required a Python loop with multiple queries before we figured out how to do it inline.

### Hard Problems We Solved

**Image uploads not appearing on the site** — After adding photo upload functionality, uploaded images were saving to disk but never showing up on listing pages. The root cause was that `UPLOAD_FOLDER` was set as a relative path (`'static/uploads/listings'`), which meant files were being saved relative to whatever directory the terminal was running from, not the project folder. Changing to `os.path.join(app.root_path, 'static', 'uploads', 'listings')` fixed it immediately.

**Full-text search on short words** — MySQL's FULLTEXT search ignores words shorter than 4 characters by default. A search for "lab" or "desk" would return no results. We solved this by building a LIKE fallback that automatically activates when full-text returns nothing, so users always get results.

**Preventing duplicate watchlist entries** — Early on, clicking the save button multiple times would create duplicate Watchlist rows. Rather than adding a Python check before every insert, we added a `UNIQUE KEY (StudentID, ListingID)` constraint directly to the table and used `INSERT IGNORE`. This is safer because the constraint enforcement happens at the database level, not just in code.

**Making recommendations work without purchase history** — Most recommendation engines are based on what you bought. Our users have no purchase history when they first join. We used the Watchlist as a proxy for interest — if you save a textbook, we assume you are interested in textbooks. This made the recommendation engine useful from day one, not just after many transactions.

### How to Extend the Project

Given more time, here is how we would take this further:

- **Real authentication** — right now passwords are stored as plain text. A production system would use bcrypt hashing.
- **University verification** — require a `.edu` email address to confirm the user is actually a college student.
- **In-app real-time messaging** — currently messages are stored in the database but require a page reload. WebSocket support (Flask-SocketIO) would make it feel like a real chat.
- **Image recognition for pricing** — instead of keyword matching, pass uploaded listing photos to a vision API to identify the item automatically and pull a suggested price.
- **Geo-filtering** — if students from multiple universities use the app, filter listings to show only items from your own campus first.
- **Transaction rating threshold** — automatically flag sellers whose average rating drops below 3.0 and show a warning to buyers.

---

## 7. References

- Flask documentation: https://flask.palletsprojects.com/
- MySQL FULLTEXT search documentation: https://dev.mysql.com/doc/refman/8.0/en/fulltext-search.html
- MySQL Connector/Python documentation: https://dev.mysql.com/doc/connector-python/en/
- Werkzeug secure_filename: https://werkzeug.palletsprojects.com/en/2.3.x/utils/#werkzeug.utils.secure_filename
- W3Schools SQL reference: https://www.w3schools.com/sql/
- Database normalization (BCNF/3NF): Course lecture notes
- CSS design inspiration: Linear.app, Vercel dashboard UI patterns
- Python uuid module: https://docs.python.org/3/library/uuid.html

---

*Report prepared for Database Systems course final project submission.*
