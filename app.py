from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import sqlite3
import os
import random
import bcrypt
import json
from konlpy.tag import Okt
okt = Okt()

print("파일 로딩됨")

app = Flask(__name__)
app.secret_key = "movie-review-secret"

API_KEY = os.getenv("bf8d8752e8552276db00970a4f4f2f74", "bf8d8752e8552276db00970a4f4f2f74")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
DB_NAME = "reviews.db"
ADMIN_USER_IDS = ["chaeeuno4"]

def is_admin_account(user_id):
    return user_id in ADMIN_USER_IDS

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nickname TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            movie_title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            movie_title TEXT NOT NULL,
            poster_path TEXT,
            freshness TEXT DEFAULT '90%',
            UNIQUE(user_id, movie_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dictionary_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            category TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            count INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dictionary_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            count INTEGER DEFAULT 1
        )
    """)

    cur.execute("SELECT id FROM users WHERE user_id = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (user_id, password, nickname, is_admin) VALUES (?, ?, ?, ?)",
            ("admin", "admin1234", "관리자", 1)
        )

    cur.execute("SELECT COUNT(*) AS cnt FROM dictionary_words")
    if cur.fetchone()["cnt"] == 0:
        words = [
            ("레전드", "스토리", "긍정", 2341),
            ("몰입감", "몰입도", "긍정", 1892),
            ("노잼", "스토리", "부정", 1204),
            ("소름", "연기", "긍정", 987),
            ("지루", "몰입도", "부정", 843),
            ("띵작", "스토리", "긍정", 721)
        ]
        cur.executemany(
            "INSERT INTO dictionary_words (word, category, sentiment, count) VALUES (?, ?, ?, ?)",
            words
        )

    cur.execute("SELECT COUNT(*) AS cnt FROM dictionary_requests")
    if cur.fetchone()["cnt"] == 0:
        requests_data = [
            ("밤티", 3),
            ("갓벽", 7),
            ("띵작", 12)
        ]
        cur.executemany(
            "INSERT INTO dictionary_requests (word, count) VALUES (?, ?)",
            requests_data
        )

    conn.commit()
    conn.close()

def login_required():
    return "user_id" in session

def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user

def get_nickname():
    user = get_current_user()
    if user:
        return user["nickname"] + " 님"
    return "게스트 님"

def make_random_nickname():
    adjectives = ["영화보는", "조용한", "날카로운", "감성적인", "집중하는", "솔직한", "방구석"]
    nouns = ["평론가", "관객", "리뷰어", "시네필", "감상러", "영화팬"]
    number = random.randint(100, 999)
    return f"{random.choice(adjectives)}{random.choice(nouns)}{number}"

def is_valid_user_id(user_id):
    if len(user_id) < 4 or len(user_id) > 20:
        return False
    return user_id.isalnum()

def tmdb_get(path, params=None):
    if params is None:
        params = {}
    params["api_key"] = API_KEY
    try:
        response = requests.get(BASE_URL + path, params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        return None
    return None

def get_popular_movies():
    data = tmdb_get("/movie/popular", {"language": "ko-KR", "page": 1})
    if data:
        movies = []
        for item in data.get("results", [])[:5]:
            movies.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "freshness": str(int(item.get("vote_average", 0) * 10)) + "%",
                "genre": "인기 영화",
                "poster_path": item.get("poster_path")
            })
        return movies

    return [
        {"id": 447365, "title": "범죄도시4", "freshness": "92%", "genre": "액션 / 범죄", "poster_path": None},
        {"id": 99999, "title": "파묘", "freshness": "87%", "genre": "공포 / 미스터리", "poster_path": None},
        {"id": 12345, "title": "서울의 봄", "freshness": "95%", "genre": "드라마 / 역사", "poster_path": None},
        {"id": 1022789, "title": "인사이드 아웃2", "freshness": "88%", "genre": "애니메이션", "poster_path": None},
        {"id": 762509, "title": "듄: 파트2", "freshness": "82%", "genre": "SF / 어드벤처", "poster_path": None}
    ]

def get_favorite_movies(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT movie_id AS id, movie_title AS title, poster_path, freshness FROM favorites WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    if rows:
        return [dict(row) for row in rows]

    return [
        {"id": 1165067, "title": "올드보이", "freshness": "90%", "poster_path": None},
        {"id": 496243, "title": "기생충", "freshness": "97%", "poster_path": None},
        {"id": 786892, "title": "부산행", "freshness": "93%", "poster_path": None},
        {"id": 99998, "title": "곡성", "freshness": "85%", "poster_path": None}
    ]

def get_category_class(category):
    if category == "스토리":
        return "story"
    if category == "연출":
        return "directing"
    if category == "연기":
        return "acting"
    if category == "몰입도":
        return "immersion"
    if category == "음악":
        return "music"
    return "default"

def get_sentiment_class(sentiment):
    if sentiment == "긍정":
        return "positive"
    return "negative"

def load_sentiment_dictionary():
    with open("SentiWord_info.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    sentiment_dict = []

    for item in data:
        word = item.get("word")
        polarity = int(item.get("polarity"))

        sentiment_dict.append({
            "word": word,
            "polarity": polarity
        })

    return sentiment_dict

SENTIMENT_DICTIONARY = load_sentiment_dictionary()

def match_sentiment_words(content):
    matched_words = []

    tokens = okt.morphs(content)
    search_text = content + " " + " ".join(tokens)

    for item in SENTIMENT_DICTIONARY:
        word = item["word"]

        if word in search_text:
            matched_words.append({
                "word": word,
                "polarity": item["polarity"],
                "count": search_text.count(word)
            })

    return matched_words

def simple_analyze_review(content):
    matched_words = match_sentiment_words(content)

    positive = 0
    negative = 0

    for item in matched_words:
        if item["polarity"] > 0:
            positive += item["count"]
        elif item["polarity"] < 0:
            negative += item["count"]

    if positive > negative:
        result = "긍정"
    elif negative > positive:
        result = "부정"
    else:
        result = "중립"

    return {
        "sentiment_result": result,
        "positive_count": positive,
        "negative_count": negative,
        "matched_words": matched_words
    }

def analyze_review_with_sentiment_dict(content):
    matched_words = match_sentiment_words(content)

    positive_score = 0
    negative_score = 0

    for item in matched_words:
        score = item["polarity"] * item["count"]

        if score > 0:
            positive_score += score
        elif score < 0:
            negative_score += abs(score)

    total = positive_score + negative_score

    if total == 0:
        sentiment_result = "중립"
        positive_percent = 0
        negative_percent = 0
    else:
        positive_percent = round((positive_score / total) * 100, 1)
        negative_percent = round((negative_score / total) * 100, 1)

        if positive_score > negative_score:
            sentiment_result = "긍정"
        elif negative_score > positive_score:
            sentiment_result = "부정"
        else:
            sentiment_result = "중립"

    return {
        "sentiment_result": sentiment_result,
        "positive_count": positive_score,
        "negative_count": negative_score,
        "positive_percent": positive_percent,
        "negative_percent": negative_percent,
        "top_categories": [],
        "matched_words": matched_words
    }

print("함수 정의됨")

def analyze_review(content):
    conn = get_db()
    words = conn.execute("SELECT * FROM dictionary_words").fetchall()
    conn.close()

    category_counts = {}
    positive_count = 0
    negative_count = 0
    matched_words = []

    for row in words:
        word = row["word"]
        category = row["category"]
        sentiment = row["sentiment"]

        if word in content:
            count = content.count(word)

            category_counts[category] = category_counts.get(category, 0) + count

            if sentiment == "긍정":
                positive_count += count
            else:
                negative_count += count

            matched_words.append({
                "word": word,
                "category": category,
                "sentiment": sentiment,
                "count": count
            })

    top_categories = sorted(
        category_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3]

    if positive_count > negative_count:
        sentiment_result = "긍정"
    elif negative_count > positive_count:
        sentiment_result = "부정"
    else:
        sentiment_result = "중립"

    return {
        "sentiment_result": sentiment_result,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "top_categories": top_categories,
        "matched_words": matched_words
    }

def enrich_dictionary_items(rows):
    items = []
    for row in rows:
        item = dict(row)
        item["category_class"] = get_category_class(item["category"])
        item["sentiment_class"] = get_sentiment_class(item["sentiment"])
        items.append(item)
    return items

@app.route("/")
def root():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    message = request.args.get("message", "")
    error = ""

    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        user_by_id = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if not user_by_id:
            conn.close()
            return render_template(
                "login.html",
                error="가입되지 않은 아이디입니다. 회원가입을 진행해주세요.",
                message=message
            )

        user = user_by_id
        conn.close()

        stored_pw = user["password"]

        if isinstance(stored_pw, str):
            stored_pw = stored_pw.encode("utf-8")

        if bcrypt.checkpw(password.encode("utf-8"), stored_pw):
            if is_admin_account(user["user_id"]) and user["is_admin"] != 1:
                conn = get_db()
                conn.execute(
                    "UPDATE users SET is_admin = 1 WHERE id = ?",
                    (user["id"],)
                )
                conn.commit()
                conn.close()

                user = get_current_user()

            session["user_id"] = user["id"]
            session["nickname"] = user["nickname"]
            session["is_admin"] = user["is_admin"]
            return redirect(url_for("main"))

        return render_template(
            "login.html",
            error="비밀번호가 일치하지 않습니다.",
            message=message
        )

    return render_template("login.html", message=message, error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    random_nickname = make_random_nickname()

    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "").strip()
        password_confirm = request.form.get("password_confirm", "").strip()
        nickname = request.form.get("nickname", "").strip()

        if not user_id or not password or not password_confirm:
            error = "필수 항목을 입력해주세요."
        elif not is_valid_user_id(user_id):
            error = "아이디는 4~20자의 영문/숫자만 사용할 수 있습니다."
        elif len(password) < 8:
            error = "비밀번호는 8자 이상이어야 합니다."
        elif password != password_confirm:
            error = "비밀번호가 일치하지 않습니다."
        else:
            if not nickname:
                nickname = random_nickname

            conn = get_db()
            existing = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if existing:
                conn.close()
                error = "이미 사용 중인 아이디입니다."
            else:
                hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

                is_admin = 1 if is_admin_account(user_id) else 0
                
                conn.execute(
                    "INSERT INTO users (user_id, password, nickname, is_admin) VALUES (?, ?, ?, ?)",
                    (user_id, hashed_pw, nickname, is_admin)
                )
                conn.commit()
                conn.close()
                return redirect(url_for("login", message="회원가입이 성공적으로 완료되었습니다. 로그인해주세요."))

    return render_template(
        "register.html",
        error=error,
        random_nickname=random_nickname
    )

@app.route("/check-user-id")
def check_user_id():
    user_id = request.args.get("user_id", "").strip()

    if not is_valid_user_id(user_id):
        return jsonify({"available": False, "message": "아이디 형식이 올바르지 않습니다."})

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if existing:
        return jsonify({"available": False, "message": "이미 사용 중인 아이디입니다."})

    return jsonify({"available": True, "message": "사용 가능한 아이디입니다."})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login", message="로그아웃되었습니다."))

@app.route("/delete-account", methods=["GET", "POST"])
@app.route("/delete-account", methods=["GET", "POST"])
def delete_account():
    if not login_required():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()

    review_count = conn.execute(
        "SELECT COUNT(*) AS count FROM reviews WHERE user_id = ?",
        (user_id,)
    ).fetchone()["count"]

    favorite_count = conn.execute(
        "SELECT COUNT(*) AS count FROM favorites WHERE user_id = ?",
        (user_id,)
    ).fetchone()["count"]

    if request.method == "POST":
        conn.execute("DELETE FROM reviews WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        session.clear()
        return redirect(url_for("login", message="회원 탈퇴가 완료되었습니다."))

    conn.close()

    return render_template(
        "delete_account.html",
        nickname=get_nickname(),
        review_count=review_count,
        favorite_count=favorite_count
    )

@app.route("/main")
def main():
    if not login_required():
        return redirect(url_for("login"))

    popular_movies = get_popular_movies()
    favorite_movies = get_favorite_movies(session["user_id"])

    return render_template(
        "index.html",
        nickname=get_nickname(),
        popular_movies=popular_movies,
        favorite_movies=favorite_movies,
        image_base_url=IMAGE_BASE_URL,
        is_admin=session.get("is_admin") == 1
    )

@app.route("/movie-search")
def movie_search():
    return redirect(url_for("main"))

@app.route("/search")
def search():
    if not login_required():
        return redirect(url_for("login"))

    keyword = request.args.get("q", "").strip()
    results = []

    if keyword:
        data = tmdb_get("/search/movie", {"query": keyword, "language": "ko-KR"})
        if data:
            results = data.get("results", [])

    return render_template(
        "search_result.html",
        nickname=get_nickname(),
        query=keyword,
        results=results,
        result_count=len(results),
        image_base_url=IMAGE_BASE_URL
    )

@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    if not login_required():
        return redirect(url_for("login"))

    movie = tmdb_get(f"/movie/{movie_id}", {"language": "ko-KR"})

    conn = get_db()

    user_review = conn.execute(
        "SELECT * FROM reviews WHERE user_id = ? AND movie_id = ? ORDER BY id DESC LIMIT 1",
        (session["user_id"], movie_id)
    ).fetchone()

    other_reviews = conn.execute(
        "SELECT r.*, u.nickname FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.movie_id = ? ORDER BY r.id DESC",
        (movie_id,)
    ).fetchall()

    favorite = conn.execute(
        "SELECT * FROM favorites WHERE user_id = ? AND movie_id = ?",
        (session["user_id"], movie_id)
    ).fetchone()

    conn.close()

    personal_analysis_result = None
    if user_review:
        personal_analysis_result = simple_analyze_review(user_review["content"])

    all_review_content = " ".join([row["content"] for row in other_reviews])

    analysis_result = None
    if all_review_content:
        analysis_result = simple_analyze_review(all_review_content)

    return render_template(
        "movie_detail.html",
        analysis_result=analysis_result,
        nickname=get_nickname(),
        movie=movie,
        image_base_url=IMAGE_BASE_URL,
        analysis_mode=request.args.get("analysis", "result"),
        user_review=user_review,
        other_reviews=other_reviews,
        favorite=favorite,
        personal_analysis_result=personal_analysis_result
    )

@app.route("/movie/<int:movie_id>/review", methods=["POST"])
def submit_review(movie_id):
    if not login_required():
        return redirect(url_for("login"))

    content = request.form.get("content", "").strip()
    movie_title = request.form.get("movie_title", "영화 제목").strip()

    if content:
        matched_words = match_sentiment_words(content)
        print("외부 감성사전 매칭 결과:", matched_words)
        
        conn = get_db()
        conn.execute(
            "INSERT INTO reviews (user_id, movie_id, movie_title, content) VALUES (?, ?, ?, ?)",
            (session["user_id"], movie_id, movie_title, content)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("movie_detail", movie_id=movie_id, analysis="result", personal=1))

@app.route("/favorite/<int:movie_id>", methods=["POST"])
def toggle_favorite(movie_id):
    if not login_required():
        return redirect(url_for("login"))

    movie_title = request.form.get("movie_title", "영화 제목").strip()
    poster_path = request.form.get("poster_path", "").strip()

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM favorites WHERE user_id = ? AND movie_id = ?",
        (session["user_id"], movie_id)
    ).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND movie_id = ?",
            (session["user_id"], movie_id)
        )
    else:
        conn.execute(
            "INSERT INTO favorites (user_id, movie_id, movie_title, poster_path, freshness) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], movie_id, movie_title, poster_path, "90%")
        )

    conn.commit()
    conn.close()

    return redirect(url_for("movie_detail", movie_id=movie_id))

@app.route("/my-reviews")
def my_reviews():
    if not login_required():
        return redirect(url_for("login"))

    mode = request.args.get("mode", "")
    edit_id = request.args.get("edit_id", "")
    delete_id = request.args.get("delete_id", "")

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM reviews WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    reviews = []
    for row in rows:
        item = dict(row)
        item["title"] = item["movie_title"]
        item["date"] = item["created_at"][:10]
        item["editing"] = str(item["id"]) == edit_id and mode == "edit"
        reviews.append(item)

    delete_review = None
    if mode == "delete" and delete_id:
        for review in reviews:
            if str(review["id"]) == delete_id:
                delete_review = review
                break

    return render_template(
        "my_reviews.html",
        nickname=get_nickname(),
        reviews=reviews,
        delete_review=delete_review
    )

@app.route("/my-reviews/update/<int:review_id>", methods=["POST"])
def update_review(review_id):
    if not login_required():
        return redirect(url_for("login"))

    content = request.form.get("content", "").strip()

    if content:
        conn = get_db()
        conn.execute(
            "UPDATE reviews SET content = ? WHERE id = ? AND user_id = ?",
            (content, review_id, session["user_id"])
        )
        conn.commit()
        conn.close()

    return redirect(url_for("my_reviews"))

@app.route("/my-reviews/delete/<int:review_id>", methods=["POST"])
def delete_review(review_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "DELETE FROM reviews WHERE id = ? AND user_id = ?",
        (review_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("my_reviews"))

@app.route("/dictionary")
def dictionary():
    if not login_required():
        return redirect(url_for("login"))

    keyword = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "전체")

    query = "SELECT * FROM dictionary_words WHERE 1=1"
    params = []

    if selected_category != "전체":
        query += " AND category = ?"
        params.append(selected_category)

    if keyword:
        query += " AND word LIKE ?"
        params.append(f"%{keyword}%")

    query += " ORDER BY count DESC"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    dictionary_words = enrich_dictionary_items(rows)

    for idx, item in enumerate(dictionary_words, start=1):
        item["rank"] = idx

    return render_template(
        "dictionary.html",
        nickname=get_nickname(),
        dictionary_words=dictionary_words,
        categories=["전체", "스토리", "연출", "연기", "몰입도", "음악"],
        selected_category=selected_category,
        keyword=keyword
    )

@app.route("/dictionary/request", methods=["GET", "POST"])
def dictionary_request():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        word = request.form.get("word", "").strip()

        if word:
            conn = get_db()
            existing = conn.execute(
                "SELECT * FROM dictionary_requests WHERE word = ?",
                (word,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE dictionary_requests SET count = count + 1 WHERE word = ?",
                    (word,)
                )
            else:
                conn.execute(
                    "INSERT INTO dictionary_requests (word, count) VALUES (?, ?)",
                    (word, 1)
                )

            conn.commit()
            conn.close()

        return redirect(url_for("dictionary_request", submitted="1"))

    return render_template(
        "dictionary_request.html",
        nickname=get_nickname(),
        submitted=request.args.get("submitted", "")
    )

@app.route("/admin/dictionary")
def dictionary_admin():
    user = get_current_user()

    if not user or user["is_admin"] != 1:
        return redirect(url_for("main"))

    conn = get_db()
    pending_rows = conn.execute(
        "SELECT * FROM dictionary_requests ORDER BY id DESC"
    ).fetchall()

    recent_rows = conn.execute(
        "SELECT * FROM dictionary_words ORDER BY id DESC LIMIT 4"
    ).fetchall()
    conn.close()

    recent_words = enrich_dictionary_items(recent_rows)

    return render_template(
        "dictionary_admin.html",
        pending_requests=[dict(row) for row in pending_rows],
        recent_words=recent_words,
        pending_count=len(pending_rows),
        categories=["스토리", "연출", "연기", "몰입도", "음악"]
    )

@app.route("/admin/dictionary/action", methods=["POST"])
def dictionary_admin_action():
    user = get_current_user()

    if not user or user["is_admin"] != 1:
        return redirect(url_for("main"))

    action = request.form.get("action", "")
    request_id = request.form.get("request_id", "")
    category = request.form.get("category", "")
    sentiment = request.form.get("sentiment", "")

    conn = get_db()
    target = conn.execute(
        "SELECT * FROM dictionary_requests WHERE id = ?",
        (request_id,)
    ).fetchone()

    if not target:
        conn.close()
        return redirect(url_for("dictionary_admin"))

    if action == "approve":
        existing = conn.execute(
            "SELECT * FROM dictionary_words WHERE word = ? AND category = ? AND sentiment = ?",
            (target["word"], category, sentiment)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE dictionary_words SET count = count + ? WHERE id = ?",
                (target["count"], existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO dictionary_words (word, category, sentiment, count) VALUES (?, ?, ?, ?)",
                (target["word"], category, sentiment, target["count"])
            )

        conn.execute(
            "DELETE FROM dictionary_requests WHERE id = ?",
            (request_id,)
        )

    elif action == "reject":
        conn.execute(
            "DELETE FROM dictionary_requests WHERE id = ?",
            (request_id,)
        )

    conn.commit()
    conn.close()

    return redirect(url_for("dictionary_admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)