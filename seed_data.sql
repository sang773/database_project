-- ═══════════════════════════════════════════════════════════════
--  CampusSwap — Demo Seed Data
--  Run once on your MySQL database to populate sample data.
--  Command: mysql -u root -p college_marketplace < seed_data.sql
-- ═══════════════════════════════════════════════════════════════

-- ── Categories ──────────────────────────────────────────────────
INSERT IGNORE INTO Category (CategoryName) VALUES
    ('Textbooks'),
    ('Electronics'),
    ('Furniture'),
    ('Clothes'),
    ('Sports'),
    ('Appliances');

-- ── Students ────────────────────────────────────────────────────
INSERT IGNORE INTO Student (Name, Email, Password, University, Rating, JoinDate) VALUES
    ('Alex Johnson',    'alex@gsu.edu',    'pass123', 'Georgia State University', 0.0, '2025-08-20'),
    ('Maria Garcia',    'maria@gsu.edu',   'pass123', 'Georgia State University', 0.0, '2025-09-01'),
    ('Kevin Park',      'kevin@gsu.edu',   'pass123', 'Georgia State University', 0.0, '2025-09-05'),
    ('Priya Patel',     'priya@gsu.edu',   'pass123', 'Georgia State University', 0.0, '2025-09-10'),
    ('Marcus Williams', 'marcus@gsu.edu',  'pass123', 'Georgia State University', 0.0, '2025-09-15');

-- ── Variable helpers (MySQL user-defined variables) ──────────────
SET @alex   = (SELECT StudentID FROM Student WHERE Email = 'alex@gsu.edu'   LIMIT 1);
SET @maria  = (SELECT StudentID FROM Student WHERE Email = 'maria@gsu.edu'  LIMIT 1);
SET @kevin  = (SELECT StudentID FROM Student WHERE Email = 'kevin@gsu.edu'  LIMIT 1);
SET @priya  = (SELECT StudentID FROM Student WHERE Email = 'priya@gsu.edu'  LIMIT 1);
SET @marcus = (SELECT StudentID FROM Student WHERE Email = 'marcus@gsu.edu' LIMIT 1);

SET @books   = (SELECT CategoryID FROM Category WHERE CategoryName = 'Textbooks'   LIMIT 1);
SET @elec    = (SELECT CategoryID FROM Category WHERE CategoryName = 'Electronics' LIMIT 1);
SET @furn    = (SELECT CategoryID FROM Category WHERE CategoryName = 'Furniture'   LIMIT 1);
SET @clothes = (SELECT CategoryID FROM Category WHERE CategoryName = 'Clothes'     LIMIT 1);
SET @sports  = (SELECT CategoryID FROM Category WHERE CategoryName = 'Sports'      LIMIT 1);
SET @appli   = (SELECT CategoryID FROM Category WHERE CategoryName = 'Appliances'  LIMIT 1);

-- ── Listings ────────────────────────────────────────────────────
INSERT INTO Listing (Title, Description, Price, `Condition`, `Status`, DatePosted, StudentID, CategoryID) VALUES
    -- Textbooks (avg ≈ $50)
    ('Calculus Early Transcendentals 8th Ed',
     'Barely used, no highlights. Great for any Calc class.',
     42.00, 'Like New', 'active', '2026-03-01', @alex,   @books),

    ('Organic Chemistry 12th Edition',
     'Some notes in pencil. Very helpful annotations. Includes solutions manual.',
     58.00, 'Good', 'active', '2026-03-05', @maria,  @books),

    ('Intro to Algorithms (CLRS)',
     'A few dog-eared pages, otherwise in great shape.',
     50.00, 'Good', 'active', '2026-03-08', @kevin,  @books),

    -- Electronics (avg ≈ $500 — iPhone deliberately below avg to trigger Hot Deal)
    ('iPhone 14 Pro 256GB Space Black',
     'No scratches, Face ID works perfectly. OEM charger included.',
     380.00, 'Good', 'active', '2026-03-10', @alex,   @elec),

    ('MacBook Air M2 13" Starlight',
     '8GB RAM, 256GB SSD. Battery health at 98%. Includes charger.',
     850.00, 'Like New', 'active', '2026-03-12', @priya,  @elec),

    ('Sony WH-1000XM5 Headphones',
     'Perfect noise cancellation. Includes carrying case and cables.',
     150.00, 'Good', 'active', '2026-03-14', @marcus, @elec),

    ('iPad Air 5th Gen 64GB WiFi',
     'Space Gray. Comes with Apple Pencil 1st gen.',
     420.00, 'Good', 'active', '2026-03-20', @maria,  @elec),

    -- Furniture (avg ≈ $90)
    ('IKEA MICKE Desk White 73x50cm',
     'Minor scuffs on the legs. Very sturdy and functional.',
     55.00, 'Good', 'active', '2026-03-15', @maria,  @furn),

    ('Ergonomic Mesh Office Chair',
     'Lumbar support, great for long study sessions.',
     120.00, 'Good', 'active', '2026-03-16', @kevin,  @furn),

    ('Dorm Room Mini Fridge 3.2 cu ft',
     'Quiet and efficient. Perfect for a dorm room.',
     85.00, 'Good', 'active', '2026-03-18', @priya,  @furn),

    -- Clothes (avg ≈ $61)
    ('GSU Panthers Hoodie Size XL',
     'Only worn twice. Blue with gold lettering.',
     28.00, 'Like New', 'active', '2026-03-20', @marcus, @clothes),

    ('Patagonia Better Sweater Jacket Size M',
     'Excellent condition, barely worn. Dark Navy.',
     75.00, 'Like New', 'active', '2026-03-21', @alex,   @clothes),

    ('Nike Air Force 1 White Size 10',
     'Clean pair, no yellowing. Original box included.',
     80.00, 'Good', 'active', '2026-03-22', @maria,  @clothes),

    -- Sports (avg ≈ $32)
    ('Official NBA Spalding Basketball',
     'Slight grip wear. Great bounce. Perfect for outdoor courts.',
     22.00, 'Good', 'active', '2026-03-23', @kevin,  @sports),

    ('Lululemon The Mat 5mm Yoga Mat',
     'Non-slip, great cushion. Carrying strap included.',
     18.00, 'Like New', 'active', '2026-03-24', @priya,  @sports),

    ('Adjustable Dumbbell Set 5-25 lbs',
     'Both handles included. No rust. Works with standard plates.',
     55.00, 'Good', 'active', '2026-03-25', @marcus, @sports),

    -- Appliances (avg ≈ $36)
    ('Keurig K-Mini Coffee Maker',
     'Works perfectly. Includes 12 K-Cups to get you started.',
     32.00, 'Good', 'active', '2026-04-01', @alex,   @appli),

    ('Aroma 8-Cup Rice Cooker',
     'Never had issues. Makes perfect rice every time.',
     24.00, 'Like New', 'active', '2026-04-02', @maria,  @appli),

    ('Ninja Air Fryer 4 Qt AF101',
     'Used maybe 10 times. Very clean inside and out.',
     52.00, 'Like New', 'active', '2026-04-03', @kevin,  @appli);

-- ── Store listing IDs ──────────────────────────────────────────
SET @l_calc  = (SELECT ListingID FROM Listing WHERE Title = 'Calculus Early Transcendentals 8th Ed' LIMIT 1);
SET @l_chem  = (SELECT ListingID FROM Listing WHERE Title = 'Organic Chemistry 12th Edition'         LIMIT 1);
SET @l_bball = (SELECT ListingID FROM Listing WHERE Title = 'Official NBA Spalding Basketball'       LIMIT 1);
SET @l_yoga  = (SELECT ListingID FROM Listing WHERE Title = 'Lululemon The Mat 5mm Yoga Mat'         LIMIT 1);
SET @l_keurig= (SELECT ListingID FROM Listing WHERE Title = 'Keurig K-Mini Coffee Maker'             LIMIT 1);
SET @l_nikes = (SELECT ListingID FROM Listing WHERE Title = 'Nike Air Force 1 White Size 10'         LIMIT 1);
SET @l_iphone= (SELECT ListingID FROM Listing WHERE Title = 'iPhone 14 Pro 256GB Space Black'        LIMIT 1);

-- ── Messages ────────────────────────────────────────────────────
INSERT INTO Message (Content, Timestamp, IsRead, SenderID, ReceiverID, ListingID) VALUES
    ('Hi! Is the Calculus book still available? Can we meet at the library?',
     NOW(), 0, @kevin,  @alex,  @l_calc),
    ('Yes it is! I am free Tuesday and Thursday after 2pm.',
     NOW(), 0, @alex,   @kevin, @l_calc),
    ('Is the iPhone unlocked for all carriers?',
     NOW(), 0, @maria,  @alex,  @l_iphone),
    ('Yes, fully unlocked! Happy to meet at the Student Center.',
     NOW(), 0, @alex,   @maria, @l_iphone),
    ('Does the chemistry book include the solutions manual?',
     NOW(), 0, @priya,  @maria, @l_chem);

-- ── Transactions (5 completed sales) ────────────────────────────
INSERT INTO Transaction (Date, FinalPrice, PaymentMethod, ListingID, BuyerID, SellerID) VALUES
    ('2026-03-20', 55.00, 'Cash',  @l_chem,  @kevin,  @maria),
    ('2026-03-28', 20.00, 'Venmo', @l_bball, @alex,   @kevin),
    ('2026-04-05', 30.00, 'Zelle', @l_keurig,@priya,  @alex),
    ('2026-04-08', 78.00, 'Venmo', @l_nikes, @marcus, @maria),
    ('2026-04-10', 16.00, 'Cash',  @l_yoga,  @maria,  @priya);

-- Mark those listings as sold
UPDATE Listing SET `Status` = 'sold'
WHERE ListingID IN (@l_chem, @l_bball, @l_keurig, @l_nikes, @l_yoga);

-- ── Transaction ID helpers ───────────────────────────────────────
SET @t1 = (SELECT TransactionID FROM Transaction WHERE ListingID = @l_chem   LIMIT 1);
SET @t2 = (SELECT TransactionID FROM Transaction WHERE ListingID = @l_bball  LIMIT 1);
SET @t3 = (SELECT TransactionID FROM Transaction WHERE ListingID = @l_keurig LIMIT 1);
SET @t4 = (SELECT TransactionID FROM Transaction WHERE ListingID = @l_nikes  LIMIT 1);
SET @t5 = (SELECT TransactionID FROM Transaction WHERE ListingID = @l_yoga   LIMIT 1);

-- ── Reviews ─────────────────────────────────────────────────────
INSERT INTO Review (Rating, Comment, Date, ReviewerID, RevieweeID, TransactionID) VALUES
    (5, 'Great seller! Book was exactly as described. Easy library meetup.',       '2026-03-21', @kevin,  @maria, @t1),
    (5, 'Ball in great condition. Fast response and smooth campus exchange!',      '2026-03-29', @alex,   @kevin, @t2),
    (4, 'Coffee maker works perfectly. Alex was very responsive.',                 '2026-04-06', @priya,  @alex,  @t3),
    (5, 'Shoes were spotless, came in original box. Amazing deal!',                '2026-04-09', @marcus, @maria, @t4),
    (4, 'Yoga mat clean and in perfect condition. Very smooth transaction!',       '2026-04-11', @maria,  @priya, @t5);

-- ── Recalculate seller ratings ───────────────────────────────────
UPDATE Student
SET Rating = (
    SELECT ROUND(AVG(Rating), 2)
    FROM Review
    WHERE RevieweeID = Student.StudentID
)
WHERE StudentID IN (@alex, @maria, @kevin, @priya, @marcus);

-- ═══════════════════════════════════════════════════════════════
--  Done! Visit http://localhost:5000 to see the seeded data.
--  Login with any email above, password: pass123
-- ═══════════════════════════════════════════════════════════════
