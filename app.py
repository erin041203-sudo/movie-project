from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import sqlite3
import os
import random
import bcrypt
import json
from datetime import datetime, timedelta
import threading

EXTERNAL_REVIEW_TTL_DAYS = 7
EXTERNAL_REVIEW_LIMIT = 30
analysis_jobs = {}
analysis_job_lock = threading.Lock()
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RENDER_JAVA_HOME = os.path.join(PROJECT_ROOT, ".jdk")

if os.path.exists(RENDER_JAVA_HOME):
    os.environ["JAVA_HOME"] = RENDER_JAVA_HOME
    os.environ["PATH"] = os.path.join(RENDER_JAVA_HOME, "bin") + os.pathsep + os.environ.get("PATH", "")

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS external_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            movie_title TEXT NOT NULL,
            source TEXT NOT NULL,
            review_text TEXT NOT NULL,
            rating REAL,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS external_analysis_cache (
            movie_id INTEGER PRIMARY KEY,
            movie_title TEXT NOT NULL,
            source TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            review_count INTEGER DEFAULT 0,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    sentiment_dict = {}

    for item in data:
        word = item.get("word")
        polarity = item.get("polarity")

        if word and polarity:
            sentiment_dict[word] = int(polarity)

    return sentiment_dict

SENTIMENT_DICTIONARY = load_sentiment_dictionary()

def match_sentiment_words(content):
    matched_words = []

    tokens = okt.morphs(content)
    candidates = set(tokens + content.split())

    for word in candidates:
        if word in SENTIMENT_DICTIONARY:
            matched_words.append({
                "word": word,
                "polarity": SENTIMENT_DICTIONARY[word],
                "count": tokens.count(word) + content.split().count(word)
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

    senti_result = analyze_review_with_sentiment_dict(content)

    positive_count += senti_result["positive_count"]
    negative_count += senti_result["negative_count"]

    for item in senti_result["matched_words"]:
        matched_words.append({
            "word": item["word"],
            "category": "감성",
            "sentiment": "긍정" if item["polarity"] > 0 else "부정",
            "count": item["count"]
        })

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

def build_visual_analysis(analysis_result):
    categories = ["스토리", "연기", "연출", "몰입도", "음악"]
    category_scores = {category: 0 for category in categories}
    keyword_cards = {category: {"positive": [], "negative": []} for category in categories}

    if analysis_result and analysis_result.get("matched_words"):
        for item in analysis_result["matched_words"]:
            category = item.get("category")
            sentiment = item.get("sentiment")
            word = item.get("word")
            count = item.get("count", 1)

            if category in category_scores:
                category_scores[category] += count

            if category in keyword_cards and word:
                if sentiment == "긍정":
                    keyword_cards[category]["positive"].append(word)
                else:
                    keyword_cards[category]["negative"].append(word)

    max_count = max(category_scores.values()) if category_scores else 0

    radar_values = []
    for category in categories:
        if max_count == 0:
            score = 30
        else:
            score = max(30, round((category_scores[category] / max_count) * 100))
        radar_values.append(score)

    radar_points = []
    center_x = 110
    center_y = 90
    radius = 62

    for i, value in enumerate(radar_values):
        angle = -90 + (360 / len(categories)) * i
        rad = angle * 3.141592 / 180
        point_radius = radius * value / 100
        x = center_x + point_radius * __import__("math").cos(rad)
        y = center_y + point_radius * __import__("math").sin(rad)
        radar_points.append(f"{round(x, 1)},{round(y, 1)}")

    top_card_categories = [
        category for category in sorted(
            categories,
            key=lambda category: category_scores[category],
            reverse=True
        )
        if category_scores[category] > 0
    ][:3]

    visible_keyword_cards = []

    for category in top_card_categories:
        positives = keyword_cards[category]["positive"][:3]
        negatives = keyword_cards[category]["negative"][:2]

        visible_keyword_cards.append({
            "category": category,
            "positive": positives,
            "negative": negatives
        })

    return {
        "categories": categories,
        "radar_points": " ".join(radar_points),
        "keyword_cards": visible_keyword_cards
    }

def build_summary_text(analysis_result):
    if not analysis_result or not analysis_result.get("matched_words"):
        return "아직 분석된 키워드가 부족하여 종합 요약을 생성할 수 없습니다."

    category_words = {}

    for item in analysis_result["matched_words"]:
        category = item.get("category")
        word = item.get("word")
        count = item.get("count", 1)

        if not category or not word:
            continue

        if category not in category_words:
            category_words[category] = []

        category_words[category].append({
            "word": word,
            "count": count
        })

    sorted_categories = sorted(
        category_words.items(),
        key=lambda x: sum(item["count"] for item in x[1]),
        reverse=True
    )[:3]

    parts = []

    for category, words in sorted_categories:
        sorted_words = sorted(words, key=lambda x: x["count"], reverse=True)
        top_words = [item["word"] for item in sorted_words[:3]]
        word_text = ", ".join(top_words)

        parts.append(f"{category} 부문에서 [{word_text}]에 대한 언급이 많았습니다")

    return "이 영화는 " + ", ".join(parts) + "."

def calculate_score(analysis_result):
    if not analysis_result:
        return 0

    positive = analysis_result.get("positive_count", 0)
    negative = analysis_result.get("negative_count", 0)
    total = positive + negative

    if total == 0:
        return 3.0

    score = 3.0 + ((positive - negative) / total) * 2
    score = max(1.0, min(5.0, score))

    return round(score, 1)

def calculate_freshness(analysis_result):
    if not analysis_result:
        return 70

    positive = analysis_result.get("positive_count", 0)
    negative = analysis_result.get("negative_count", 0)
    total = positive + negative

    if total == 0:
        return 70

    freshness = round((positive / total) * 100)
    freshness = max(30, min(98, freshness))

    return freshness

def get_sample_external_reviews(movie_title):
    return [
        f"{movie_title}는 스토리 몰입감이 좋고 연출이 인상적이었다.",
        f"{movie_title}는 배우들의 연기가 자연스럽고 음악도 잘 어울렸다.",
        f"{movie_title}는 중반부가 조금 지루했지만 전체적으로 볼만했다.",
        f"{movie_title}는 스토리 전개가 탄탄하고 몰입감이 뛰어났다.",
        f"{movie_title}는 연출은 좋았지만 결말이 아쉬웠다.",
        f"{movie_title}는 음악과 분위기가 좋아서 기억에 남는다.",
        f"{movie_title}는 배우 연기가 좋아 감정선이 잘 전달됐다.",
        f"{movie_title}는 약간 지루한 부분도 있었지만 완성도는 좋았다."
    ]

def collect_kinolights_reviews(movie_title):
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,1000")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(8)
        wait = WebDriverWait(driver, 5)

        driver.get("https://m.kinolights.com/search")
        print("키노라이츠 검색 페이지 접속 완료")
        time.sleep(1)

        search_box = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )

        print("검색창 찾기 성공")
        search_box.clear()
        search_box.send_keys(movie_title)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)

        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/title/']")
        title_url = ""

        for link in links:
            href = link.get_attribute("href")
            text = link.text.strip()

            if href and "/title/" in href:
                if movie_title.replace(" ", "") in text.replace(" ", ""):
                    title_url = href
                    break

        if not title_url and links:
            title_url = links[0].get_attribute("href")

        if not title_url:
            driver.quit()
            return []

        title_id = title_url.split("/title/")[1].split("/")[0].split("?")[0]
        review_url = f"https://m.kinolights.com/title/{title_id}/reviews"

        driver.get(review_url)
        print("리뷰 페이지 접속:", review_url)
        time.sleep(2)

        print("현재 페이지 제목:", driver.title)
        print("현재 주소:", driver.current_url)

        body_text = driver.find_element(By.TAG_NAME, "body").text
        print("본문 일부:", body_text[:1000])

        for _ in range(8):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        reviews = []

        body_text = driver.find_element(By.TAG_NAME, "body").text
        lines = [line.strip() for line in body_text.split("\n") if line.strip()]

        reviews = []
        skip_words = [
            "공유하기", "더보기", "좋아요", "싫어요",
            "보고싶어요", "보는중", "봤어요",
            "작품정보", "영상/이미지", "전체",
            "인증회원", "팔로잉", "사이트 정보", "저작권",
            "주메뉴", "홈", "랭킹", "탐색", "혜택",
            "고객센터", "이용약관", "개인정보", "회사 안내"
            ]

        for line in lines:
            clean = " ".join(line.split())

            korean_count = sum(1 for ch in clean if "가" <= ch <= "힣")
            english_count = sum(1 for ch in clean if ("a" <= ch.lower() <= "z"))

            if korean_count == 0:
                continue

            if english_count > korean_count:
                continue

            if len(clean) < 8:
                continue

            if len(clean) > 120:
                continue

            if clean == movie_title:
                continue

            if movie_title in clean and len(clean) < len(movie_title) + 20:
                continue

            if clean.endswith("%"):
                continue

            if clean.replace(".", "", 1).isdigit():
                continue

            if clean.endswith("전"):
                continue

            if "·" in clean and len(clean) < 30:
                continue

            if clean.count(" ") == 0 and len(clean) <= 8:
                continue

            if any(char.isdigit() for char in clean) and len(clean) < 20:
                continue

            if clean.replace(".", "", 1).isdigit():
                continue

            if "@" in clean:
                continue

            if any(word in clean for word in skip_words):
                continue

            if clean.endswith("전"):
                continue

            if clean.startswith("[리뷰]"):
                clean = clean.replace("[리뷰]", "").strip()

            if clean in reviews:
                continue

            if "_" in clean:
                continue

            if clean.isdigit():
                continue

            if clean.count(" ") == 0 and len(clean) <= 8:
                continue

            try:
                score = float(clean)
                if 0 <= score <= 5:
                    continue
            except:
                pass

            reviews.append(clean)

            if len(reviews) >= EXTERNAL_REVIEW_LIMIT:
                break


        if len(reviews) > EXTERNAL_REVIEW_LIMIT:
            step = max(1, len(reviews) // EXTERNAL_REVIEW_LIMIT)
            reviews = reviews[::step][:EXTERNAL_REVIEW_LIMIT]

        driver.quit()
        return reviews

    except Exception as e:
        print("키노라이츠 리뷰 수집 실패:", type(e).__name__, repr(e))
        return []

def get_external_analysis(movie_id, movie_title):
    now = datetime.now()

    conn = get_db()

    reviews = collect_kinolights_reviews(movie_title)

    if len(reviews) == 0:
        conn.execute("DELETE FROM external_analysis_cache WHERE movie_id = ?", (movie_id,))
        conn.commit()
        conn.close()

        return {
            "analysis_result": None,
            "visual_analysis": None,
            "summary_text": "키노라이츠 리뷰 페이지에는 접근했지만, 실제 리뷰 텍스트를 수집하지 못했습니다.",
            "average_score": 0,
            "freshness_score": 0,
            "from_cache": False,
            "collected_at": now.isoformat(timespec="seconds"),
            "review_count": 0
        }

    conn.execute("DELETE FROM external_reviews WHERE movie_id = ?", (movie_id,))

    for review in reviews:
        conn.execute(
            "INSERT INTO external_reviews (movie_id, movie_title, source, review_text, rating, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
            (movie_id, movie_title, "KINOLIGHTS", review, None, now.isoformat(timespec="seconds"))
        )

    all_text = " ".join(reviews)

    analysis_result = analyze_review(all_text)
    visual_analysis = build_visual_analysis(analysis_result)
    summary_text = build_summary_text(analysis_result)
    average_score = calculate_score(analysis_result)
    freshness_score = calculate_freshness(analysis_result)

    data = {
        "analysis_result": analysis_result,
        "visual_analysis": visual_analysis,
        "summary_text": summary_text,
        "average_score": average_score,
        "freshness_score": freshness_score,
        "from_cache": False,
        "collected_at": now.isoformat(timespec="seconds"),
        "review_count": len(reviews)
    }

    conn.execute(
        """
        INSERT OR REPLACE INTO external_analysis_cache
        (movie_id, movie_title, source, analysis_json, review_count, collected_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            movie_id,
            movie_title,
            "KINOLIGHTS",
            json.dumps(data, ensure_ascii=False),
            len(reviews),
            now.isoformat(timespec="seconds")
        )
    )

    conn.commit()
    conn.close()

    return data

def is_external_cache_valid(cached):
    if not cached:
        return False

    try:
        collected_at = datetime.fromisoformat(cached["collected_at"])
        expire_time = datetime.now() - timedelta(days=EXTERNAL_REVIEW_TTL_DAYS)
        return collected_at >= expire_time
    except:
        return False

def run_external_analysis_job(movie_id, movie_title):
    try:
        get_external_analysis(movie_id, movie_title)

        with analysis_job_lock:
            analysis_jobs[movie_id] = "done"

    except Exception as e:
        print("백그라운드 외부 리뷰 분석 실패:", e)

        with analysis_job_lock:
            analysis_jobs[movie_id] = "failed"

def start_external_analysis_job(movie_id, movie_title):
    with analysis_job_lock:
        if analysis_jobs.get(movie_id) == "running":
            return

        analysis_jobs[movie_id] = "running"

    thread = threading.Thread(
        target=run_external_analysis_job,
        args=(movie_id, movie_title),
        daemon=True
    )
    thread.start()

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

    if not movie:
        movie = {
            "id": movie_id,
            "title": "영화 제목",
            "poster_path": None,
            "genres": [],
            "release_date": "",
            "vote_average": 0,
            "overview": "영화 정보를 불러오지 못했습니다."
        }

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

    cached = conn.execute(
        "SELECT * FROM external_analysis_cache WHERE movie_id = ?",
        (movie_id,)
    ).fetchone()

    conn.close()

    user_reviews_text = " ".join([row["content"] for row in other_reviews])

    analysis_result = None
    visual_analysis = None
    summary_text = ""
    average_score = 0
    freshness_score = 70
    analysis_source = "none"
    external_info = None

    if user_reviews_text:
        analysis_result = analyze_review(user_reviews_text)
        visual_analysis = build_visual_analysis(analysis_result)
        summary_text = build_summary_text(analysis_result)
        average_score = calculate_score(analysis_result)
        freshness_score = calculate_freshness(analysis_result)
        analysis_source = "user"

    elif is_external_cache_valid(cached):
        external_info = json.loads(cached["analysis_json"])
        external_info["from_cache"] = True
        external_info["collected_at"] = cached["collected_at"]
        external_info["review_count"] = cached["review_count"]

        analysis_result = external_info["analysis_result"]
        visual_analysis = external_info["visual_analysis"]
        summary_text = external_info["summary_text"]
        average_score = external_info["average_score"]
        freshness_score = external_info["freshness_score"]
        analysis_source = "external"

    else:
        start_external_analysis_job(movie_id, movie["title"])
        analysis_source = "external_loading"
        summary_text = "외부 리뷰를 수집하여 분석 중입니다."

    conn = get_db()
    external_reviews = conn.execute(
        """
        SELECT *
        FROM external_reviews
        WHERE movie_id = ?
        ORDER BY id DESC
        """,
        (movie_id,)
    ).fetchall()
    conn.close()

    personal_analysis_result = None

    if user_review:
        personal_analysis_result = analyze_review(user_review["content"])

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
        personal_analysis_result=personal_analysis_result,
        visual_analysis=visual_analysis,
        summary_text=summary_text,
        average_score=average_score,
        freshness_score=freshness_score,
        analysis_source=analysis_source,
        external_info=external_info,
        external_reviews=external_reviews
    )

@app.route("/movie/<int:movie_id>/external-status")
def external_status(movie_id):
    if not login_required():
        return jsonify({"status": "unauthorized"})

    status = analysis_jobs.get(movie_id, "none")

    conn = get_db()
    cached = conn.execute(
        "SELECT * FROM external_analysis_cache WHERE movie_id = ?",
        (movie_id,)
    ).fetchone()
    conn.close()

    if is_external_cache_valid(cached):
        status = "done"

    return jsonify({"status": status})

@app.route("/movie/<int:movie_id>/review", methods=["POST"])
def submit_review(movie_id):
    if not login_required():
        return redirect(url_for("login"))

    content = request.form.get("content", "").strip()
    movie_title = request.form.get("movie_title", "영화 제목").strip()

    if content:
        
        conn = get_db()
        conn.execute(
            "INSERT INTO reviews (user_id, movie_id, movie_title, content) VALUES (?, ?, ?, ?)",
            (session["user_id"], movie_id, movie_title, content)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("movie_detail", movie_id=movie_id, analysis="result", open_personal=1))

@app.route("/movie/<int:movie_id>/my-analysis")
def my_analysis(movie_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    user_review = conn.execute(
        "SELECT * FROM reviews WHERE user_id = ? AND movie_id = ? ORDER BY id DESC LIMIT 1",
        (session["user_id"], movie_id)
    ).fetchone()
    conn.close()

    analysis_result = None
    visual_analysis = None

    if user_review:
        analysis_result = analyze_review(user_review["content"])
        visual_analysis = build_visual_analysis(analysis_result)

    return render_template(
        "my_analysis.html",
        analysis_result=analysis_result,
        visual_analysis=visual_analysis,
        movie_id=movie_id,
        user_review=user_review
)

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